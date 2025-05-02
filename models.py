from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()  # 初始化 Bcrypt

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    # 密碼設置方法：設置密碼時將密碼哈希處理後存儲
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    # 密碼檢查方法：檢查輸入的密碼是否與存儲的哈希匹配
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class Monitor(db.Model):
    __tablename__ = 'monitors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    target = db.Column(db.String(200), nullable=False)
    port = db.Column(db.Integer)
    keyword = db.Column(db.String(200))
    frequency = db.Column(db.Integer, nullable=False)
    last_status = db.Column(db.Boolean, default=True)
    enabled = db.Column(db.Boolean, default=True)
    user = db.relationship('User', backref='monitors')

class MonitorResult(db.Model):
    __tablename__ = 'monitor_results'
    id = db.Column(db.Integer, primary_key=True)
    monitor_id = db.Column(db.Integer, db.ForeignKey('monitors.id'))
    timestamp = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(10), nullable=False)
    response_time = db.Column(db.Float)
    details = db.Column(db.Text)
    monitor = db.relationship('Monitor', backref='results')
