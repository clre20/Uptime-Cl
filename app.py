from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt  # 使用 Flask-Bcrypt 來處理密碼加密
from flask_migrate import Migrate
from config import Config
from models import db, User, Monitor, MonitorResult
from scheduler import init_scheduler, scheduler
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.base import JobLookupError
import requests

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = "rjngrotgbt8486t4b6df847hbr68srdtfsbh"  # 用來加密 session

db.init_app(app)
migrate = Migrate(app, db)

bcrypt = Bcrypt(app)  # 初始化 Bcrypt

# 初始化背景調度器
scheduler = BackgroundScheduler()

# LoginManager 設定
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# 修改這裡，使用 db.session.get()
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# 初始化排程
with app.app_context():
    db.create_all()

# 路由: 登入 / 登出
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):  # 使用 check_password 來檢查密碼
            login_user(user)  # 登入用戶
            next_page = request.args.get('next')  # 如果有 next 參數，跳轉到該頁
            return redirect(next_page or url_for('monitors'))
        else:
            flash("帳號或密碼錯誤", "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# 路由: 監控列表
@app.route('/')
@login_required
def monitors():
    items = Monitor.query.filter_by(user_id=current_user.id).all()
    return render_template('monitors.html', monitors=items)

# 新增 / 編輯
@app.route('/monitor/<int:id>', methods=['GET', 'POST'])
@app.route('/monitor/new', methods=['GET', 'POST'])
@login_required
def monitor_edit_form(id=None):  # 修改函數名稱，避免與 monitor_form 路由衝突
    monitor = Monitor.query.get(id) if id else None
    if request.method == 'POST':
        data = request.form
        if monitor:
            # 更新
            monitor.name = data['name']
            monitor.type = data['type']
            monitor.target = data['target']
            monitor.port = data.get('port')
            monitor.keyword = data.get('keyword')
            monitor.frequency = int(data['frequency'])
        else:
            # 新增
            monitor = Monitor(user_id=current_user.id,
                              name=data['name'], type=data['type'],
                              target=data['target'], port=data.get('port'),
                              keyword=data.get('keyword'),
                              frequency=int(data['frequency']), enabled=True)
            db.session.add(monitor)
            db.session.flush()  # 取得 ID
            scheduler.add_job(run_monitor, 'interval', seconds=monitor.frequency, args=[monitor.id], id=str(monitor.id))
        db.session.commit()
        return redirect(url_for('monitors'))
    return render_template('monitor_form.html', monitor=monitor)

# 刪除
@app.route('/monitor/delete/<int:monitor_id>', methods=['POST'])
@login_required
def monitor_delete(monitor_id):
    monitor = Monitor.query.get_or_404(monitor_id)
    if monitor.user_id != current_user.id:
        abort(403)

    try:
        scheduler.remove_job(str(monitor.id))  # 假設你用 monitor.id 作為 job_id
    except JobLookupError:
        # 忽略找不到的 job，或可以加上 log/flash 提示
        print(f"Job with ID {monitor.id} not found in scheduler.")
        flash("未在排程器中找到對應的工作，但監控器資料已刪除。", "warning")

    db.session.delete(monitor)
    db.session.commit()
    flash("監控器已成功刪除！", "success")
    return redirect(url_for('monitors'))

# 圖表
@app.route('/monitor/chart/<int:id>')
@login_required
def monitor_chart(id):
    monitor = Monitor.query.get_or_404(id)
    results = MonitorResult.query.filter_by(monitor_id=id).order_by(MonitorResult.timestamp.asc()).all()
    times = [r.timestamp.strftime('%Y-%m-%d %H:%M:%S') for r in results]
    statuses = [1 if r.status.lower() in ['up', 'active'] else 0 for r in results]
    return render_template('chart.html', monitor=monitor, labels=times, data=statuses)

# 註冊路由
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]
        
        if User.query.filter_by(username=username).first():
            flash("該用戶名已經註冊", "danger")
            return redirect(url_for("register"))
        
        # 創建新用戶並設置密碼
        new_user = User(username=username, email=email)
        new_user.set_password(password)  # 使用 set_password 來加密密碼
        db.session.add(new_user)
        db.session.commit()
        
        flash("註冊成功！", "success")
        return redirect(url_for("login"))
    
    return render_template("register.html")

import requests
import socket
import subprocess
from datetime import datetime

def run_monitor(monitor_id):
    monitor = Monitor.query.get(monitor_id)
    
    if monitor:
        if monitor.type == "ping":
            # 處理 ping 類型監控
            result = ping(monitor.target)  # 這是你的 ping 邏輯
            status = "up" if result else "down"
            details = f"Time: {result}ms" if result else "Ping failed"

        elif monitor.type == "dns":
            # 處理 DNS 類型監控
            result = dns_lookup(monitor.target)
            status = "up" if result else "down"
            details = f"DNS lookup result: {result}" if result else "DNS lookup failed"

        elif monitor.type == "http":
            # 處理 HTTP 類型監控
            url = monitor.target
            if not url.startswith("http://") and not url.startswith("https://"):
                url = f"http://{url}"
            if monitor.port:
                url = f"{url}:{monitor.port}"

            start_time = datetime.utcnow()
            try:
                response = requests.get(url, timeout=5)
                response_time = (datetime.utcnow() - start_time).total_seconds()

                if monitor.keyword:
                    is_up = monitor.keyword in response.text
                else:
                    is_up = response.status_code == 200

                status = "up" if is_up else "down"
                details = f"HTTP {response.status_code}" if not monitor.keyword else f"Keyword {'found' if is_up else 'not found'}"
            except requests.exceptions.RequestException as e:
                status = "down"
                details = f"Request failed: {str(e)}"

        elif monitor.type == "tcp":
            # 處理 TCP 類型監控
            result = tcp_check(monitor.target, monitor.port)
            status = "up" if result else "down"
            details = f"TCP check result: {result}" if result else "TCP check failed"
        
        else:
            # 處理未知的類型
            status = "down"
            details = "Unknown type"

        # 儲存監控結果
        monitor_result = MonitorResult(
            monitor_id=monitor.id,
            timestamp=datetime.utcnow(),
            status=status,
            response_time=response_time if 'response_time' in locals() else None,
            details=details
        )
        db.session.add(monitor_result)
        db.session.commit()
        print(f"Monitor {monitor.name} is {status}.")

# ping 檢查邏輯
def ping(target):
    try:
        # 使用系統的 ping 命令進行檢查
        output = subprocess.check_output(["ping", "-c", "1", target], stderr=subprocess.STDOUT, universal_newlines=True)
        # 可以解析命令輸出來獲取 ping 時間
        return True
    except subprocess.CalledProcessError:
        return False

# DNS 檢查邏輯
def dns_lookup(target):
    try:
        # 嘗試解析 DNS
        socket.gethostbyname(target)
        return True
    except socket.gaierror:
        return False

# TCP 檢查邏輯
def tcp_check(target, port):
    try:
        # 嘗試連接到指定的端口
        with socket.create_connection((target, port), timeout=5):
            return True
    except (socket.timeout, socket.error):
        return False


# 路由: 新增 / 編輯表單
@app.route('/monitor_form', methods=['GET', 'POST'])
def monitor_form():
    if request.method == 'POST':
        monitor_id = request.form.get('monitor_id')
        if monitor_id:
            # 更新已存在的監控器
            monitor = Monitor.query.get(monitor_id)
            if monitor:
                monitor.name = request.form['name']
                monitor.type = request.form['type']
                monitor.target = request.form['target']
                monitor.frequency = request.form['frequency']
                db.session.commit()
                flash("監控器已更新！", "success")
            else:
                flash("監控器未找到！", "danger")
        else:
            # 創建新的監控器
            new_monitor = Monitor(
                name=request.form['name'],
                type=request.form['type'],
                target=request.form['target'],
                frequency=request.form['frequency'],
                user_id=current_user.id
            )
            db.session.add(new_monitor)
            db.session.commit()
            flash("監控器已創建！", "success")
            
        return redirect(url_for('monitors'))
    return render_template('monitor_form.html')



@app.route('/run_test_monitor/<int:id>')
def run_test_monitor(id):
    run_monitor(id)
    return "Monitor triggered"


if __name__ == '__main__':
    scheduler.start() # ← 啟動排程器
    app.run(debug=True)
