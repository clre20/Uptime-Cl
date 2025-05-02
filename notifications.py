import smtplib
import requests
from email.mime.text import MIMEText
from config import Config

SMTP_SERVER = 'smtp.example.com'
SMTP_PORT = 587
SMTP_USER = 'your-email@example.com'
SMTP_PASS = 'password'
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/...'  

def notify_all(monitor, result):
    subject = f"[Alert] {monitor.name} is down"
    body = f"Time: {result.timestamp}\nTarget: {monitor.target}\nType: {monitor.type}\n"
    send_email(monitor.user.email, subject, body)
    send_discord(subject + '\n' + body)


def send_email(to_addr, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_addr

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USER, SMTP_PASS)
    server.sendmail(SMTP_USER, [to_addr], msg.as_string())
    server.quit()


def send_discord(content):
    data = {"content": content}
    requests.post(DISCORD_WEBHOOK_URL, json=data)