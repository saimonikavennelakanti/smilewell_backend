import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')

print(f"Testing with: {EMAIL_USER}")

try:
    msg = MIMEText("Test email from Smilewell Backend")
    msg['Subject'] = 'Test Email'
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_USER # Send to self
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    server.send_message(msg)
    server.quit()
    print("Email sent successfully!")
except Exception as e:
    print(f"Error sending email: {e}")
