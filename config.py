import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///monitor.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # APScheduler
    SCHEDULER_API_ENABLED = True
    JOBS_DB_URL = SQLALCHEMY_DATABASE_URI
