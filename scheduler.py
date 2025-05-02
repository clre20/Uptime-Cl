from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from models import Monitor, db
from monitors import run_monitor

scheduler = BackgroundScheduler()


def init_scheduler(app):
    scheduler.configure(jobstores={'default':
                                   {'type': 'sqlalchemy', 'url': app.config['SQLALCHEMY_DATABASE_URI']}})
    scheduler.start()
    # 載入所有啟用任務
    with app.app_context():
        for m in Monitor.query.filter_by(enabled=True).all():
            scheduler.add_job(func=run_monitor,
                              trigger='interval', seconds=m.frequency,
                              args=[m.id], id=str(m.id))
