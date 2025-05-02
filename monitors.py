import socket, subprocess, time
import requests
from icmplib import ping
from datetime import datetime
from models import db, Monitor, MonitorResult
from notifications import notify_all


def check_ping(monitor: Monitor):
    result = ping(monitor.target, count=1, timeout=2)
    status = 'up' if result.is_alive else 'down'
    return status, result.avg_rtt


def check_http(monitor: Monitor):
    start = time.time()
    try:
        resp = requests.get(monitor.target, timeout=5)
        elapsed = (time.time() - start) * 1000
        if resp.status_code == 200 and (not monitor.keyword or monitor.keyword in resp.text):
            return 'up', elapsed
        else:
            return 'down', elapsed
    except Exception as e:
        return 'down', None


def check_dns(monitor: Monitor):
    try:
        ip = socket.gethostbyname(monitor.target)
        return 'up', None
    except Exception:
        return 'down', None


def check_tcp(monitor: Monitor):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        res = sock.connect_ex((monitor.target, monitor.port))
        status = 'up' if res == 0 else 'down'
    finally:
        sock.close()
    return status, None


def run_monitor(monitor_id):
    monitor = Monitor.query.get(monitor_id)
    if not monitor or not monitor.enabled:
        return
    checks = {'ping': check_ping, 'http': check_http, 'dns': check_dns, 'tcp': check_tcp}
    func = checks.get(monitor.type)
    status, rtime = func(monitor)
    now = datetime.utcnow()
    # 儲存結果
    result = MonitorResult(monitor_id=monitor.id, timestamp=now,
                           status=status, response_time=rtime)
    db.session.add(result)
    # 首次異常通知
    if status == 'down' and monitor.last_status:
        notify_all(monitor, result)
    monitor.last_status = (status == 'up')
    db.session.commit()
