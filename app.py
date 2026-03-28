from ultralytics import YOLO
import cv2
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import os
import traceback
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta, time
from werkzeug.utils import secure_filename
import google.generativeai as genai
from PIL import Image
import io

from apscheduler.schedulers.background import BackgroundScheduler
import firebase_admin
from firebase_admin import credentials, messaging

load_dotenv()

# Gemini Config
GEMINI_API_KEYS = os.getenv("GEMINI_API_KEYS", "").split(",")
if not GEMINI_API_KEYS or not GEMINI_API_KEYS[0]:
    single_key = os.getenv("GEMINI_API_KEY")
    if single_key:
        GEMINI_API_KEYS = [single_key]

def get_gemini_model():
    if not GEMINI_API_KEYS:
        return None
    api_key = random.choice(GEMINI_API_KEYS)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-flash')

app = Flask(__name__)
CORS(app)
MODEL_PATH = r"C:\Smilewell_project_new\AndroidStudioProjects\smilewell\smilewell_backend\best.pt"

yolo_model = YOLO(MODEL_PATH)
print("YOLO MODEL LOADED")
print(yolo_model.names)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'smile_well'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER') or 'your-email@gmail.com'
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS') or 'your-app-password'

UPLOAD_FOLDER = 'uploads/profiles'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

SCAN_UPLOAD_FOLDER = 'uploads/scans'
app.config['SCAN_UPLOAD_FOLDER'] = SCAN_UPLOAD_FOLDER
os.makedirs(SCAN_UPLOAD_FOLDER, exist_ok=True)

mysql = MySQL(app)

try:
    cred = credentials.Certificate("service-account-key.json")
    firebase_admin.initialize_app(cred)
    print("Firebase Admin Initialized successfully.")
except Exception as e:
    print(f"Firebase initialization skipped or failed: {e}")

def send_firebase_push(user_id, title, body):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT fcm_token FROM users WHERE id = %s", (user_id,))
        res = cur.fetchone()
        cur.close()
        if res and res[0]:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=res[0],
            )
            response = messaging.send(message)
            print('Successfully sent FCM message:', response)
    except Exception as e:
        print(f"Error sending Firebase push: {e}")
otp_storage = {}

def send_otp_email(email, otp):
    try:
        msg = MIMEText(f"Your Smile Well OTP is: {otp}")
        msg['Subject'] = 'Smile Well - Verification OTP'
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = email
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        print(f"DEBUG: OTP for {email} is {otp}") # Fallback for development
        return True # Return True to allow registration to proceed even if email fails in dev

def send_medication_reminder_email(email, user_name, med_details):
    try:
        body = f"Hello {user_name},\n\nThis is a reminder to take your medication in 10 minutes:\n\n"
        body += f"Medication: {med_details['name']}\n"
        body += f"Dosage: {med_details['dosage']}\n"
        body += f"Time: {med_details['time']}\n\n"
        body += "Please do not skip your dose.\n\nStay healthy,\nSmile Well Team"
        
        msg = MIMEText(body)
        msg['Subject'] = f"Medication Reminder: {med_details['name']} due in 10 mins"
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = email
        
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending med reminder: {e}")
        return False

def send_visit_reminder_email(email, user_name, visit_details):
    try:
        body = f"Hello {user_name},\n\nThis is a notification for your clinic visit scheduled for NOW:\n\n"
        body += f"Doctor: {visit_details['doctor_name']}\n"
        body += f"Clinic/Hospital: {visit_details['clinic_hospital']}\n"
        body += f"Time: {visit_details['time']}\n"
        body += f"Date: {visit_details['date']}\n\n"
        body += "Please ensure you are at the clinic or on your way.\n\nStay healthy,\nSmile Well Team"
        
        msg = MIMEText(body)
        msg['Subject'] = f"Appointment Alert: {visit_details['doctor_name']} - Scheduled Now"
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = email
        
        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
            server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending visit email: {e}")
        return False

def init_db():
    try:
        with app.app_context():
            cur = mysql.connection.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            user_required_columns = {"phone_number": "VARCHAR(20)", "profile_image": "VARCHAR(255)"}
            for col_name, col_type in user_required_columns.items():
                cur.execute(f"SHOW COLUMNS FROM users LIKE '{col_name}'")
                if not cur.fetchone():
                    cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS medications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    medication_name VARCHAR(255) NOT NULL,
                    dosage VARCHAR(100),
                    frequency VARCHAR(100),
                    time VARCHAR(100),
                    start_date VARCHAR(100),
                    end_date VARCHAR(100),
                    instructions TEXT,
                    last_notified_day VARCHAR(100) DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cur.execute("SHOW COLUMNS FROM medications LIKE 'last_notified_day'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE medications ADD COLUMN last_notified_day VARCHAR(100) DEFAULT ''")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS clinic_visits (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    doctor_name VARCHAR(255) NOT NULL,
                    clinic_hospital VARCHAR(255),
                    date VARCHAR(100),
                    time VARCHAR(100),
                    notes TEXT,
                    status VARCHAR(20) DEFAULT 'pending',
                    notified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cur.execute("SHOW COLUMNS FROM clinic_visits LIKE 'notified'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE clinic_visits ADD COLUMN notified BOOLEAN DEFAULT FALSE")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_notifications (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    type VARCHAR(50) DEFAULT 'general',
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    oral_score INT DEFAULT 0,
                    mental_score INT DEFAULT 0,
                    date VARCHAR(100),
                    time VARCHAR(100),
                    submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            cur.execute("DROP TABLE IF EXISTS oral_scans")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scan_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    score INT,
                    status VARCHAR(50),
                    problem_detected TEXT,
                    severity VARCHAR(50),
                    confidence_percentage VARCHAR(20),
                    risk_level VARCHAR(50),
                    understanding_results TEXT,
                    recommendation TEXT,
                    visit_dentist VARCHAR(50),
                    image_url VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS task_completions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    task_label VARCHAR(255) NOT NULL,
                    task_date VARCHAR(100) NOT NULL,
                    is_completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_task (user_id, task_label, task_date)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS emergency_contacts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    full_name VARCHAR(255) NOT NULL,
                    phone_number VARCHAR(20) NOT NULL,
                    relationship VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            cur.execute("DROP TABLE IF EXISTS assessment_answers")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS assessment_answers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    q1_ans VARCHAR(50),
                    q2_ans VARCHAR(50),
                    q3_ans VARCHAR(50),
                    q4_ans VARCHAR(50),
                    q5_ans VARCHAR(50),
                    q6_ans VARCHAR(50),
                    q7_ans VARCHAR(50),
                    q8_ans VARCHAR(50),
                    q9_ans VARCHAR(50),
                    q10_ans VARCHAR(50),
                    oral_score INT,
                    mental_score INT,
                    recommendations TEXT,
                    date VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            mysql.connection.commit()
            cur.close()
    except Exception as e:
        traceback.print_exc()

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        email = data.get('email')
        full_name = data.get('full_name')
        password = data.get('password')
        
        if not email: return jsonify({"error": "Email required"}), 400
        if not full_name: return jsonify({"error": "Full name required"}), 400
        if not password: return jsonify({"error": "Password required"}), 400
        
        # Check if user already exists
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
        existing_user = cur.fetchone()
        cur.close()
        
        if existing_user:
            return jsonify({"error": "User already exists. Please login."}), 400

        otp = str(random.randint(100000, 999999))
        email_sent = send_otp_email(email, otp)
        if not email_sent:
            # Use a fallback OTP and print to console for dev visibility
            otp = str(random.randint(100000, 999999))
            print(f"[WARN] Email failed for {email}. OTP (check console): {otp}")
            msg = "OTP sent to email"
        else:
            msg = "OTP sent to email"

        # Always store OTP regardless of email result
        otp_storage[email] = {
            "otp": otp, 
            "full_name": full_name, 
            "password": password, 
            "type": "registration",
            "expires": datetime.now() + timedelta(minutes=10)
        }
        return jsonify({"message": msg}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    try:
        data = request.get_json()
        email = data.get('email')
        if not email: return jsonify({"error": "Email required"}), 400
        
        otp = str(random.randint(100000, 999999))
        msg = "OTP resent successfully"
        if not send_otp_email(email, otp):
            otp = "123456"
            msg = "Email failed. Use 123456 for testing."
            print(f"DEBUG: Falling back to OTP 123456 for resend to {email}")

        if email in otp_storage:
            otp_storage[email]["otp"] = otp
            otp_storage[email]["expires"] = datetime.now() + timedelta(minutes=10)
        else:
            otp_storage[email] = {"otp": otp, "type": "resend", "expires": datetime.now() + timedelta(minutes=10)}
        return jsonify({"message": msg}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.get_json()
        email, otp = data.get('email'), data.get('otp')
        if not email or not otp:
            return jsonify({"error": "Email and OTP are required"}), 400
        
        stored = otp_storage.get(email)
        if not stored:
            return jsonify({"error": "No OTP found for this email. Please register again."}), 400
        
        # Check expiry
        if datetime.now() > stored.get('expires', datetime.min):
            del otp_storage[email]
            return jsonify({"error": "OTP has expired. Please register again to get a new OTP."}), 400
        
        if stored['otp'] != otp:
            return jsonify({"error": "Invalid OTP. Please check and try again."}), 400
        
        if stored.get("type") != "registration":
            return jsonify({"error": "Invalid OTP type. Please use the correct verification page."}), 400
        
        # OTP valid and type correct — create the user
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (full_name, email, password, is_verified) VALUES (%s, %s, %s, TRUE)",
                    (stored['full_name'], email, stored['password']))
        mysql.connection.commit()
        user_id = cur.lastrowid
        full_name = stored['full_name']
        cur.close()
        del otp_storage[email]
        return jsonify({"message": "Account verified successfully!", "user_id": user_id, "full_name": full_name}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password, full_name, is_verified FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
        user = cur.fetchone()
        cur.close()
        
        if user and password == user[1]:
            if not user[3]:
                return jsonify({"error": "Account not verified. Please verify your OTP."}), 403
            return jsonify({"user_id": user[0], "full_name": user[2]}), 200
        return jsonify({"error": "Invalid email or password"}), 401
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data = request.get_json()
        email = data.get('email')
        if not email: return jsonify({"error": "Email required"}), 400
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
        user = cur.fetchone()
        cur.close()
        
        if not user:
            return jsonify({"error": "No account found with this email address."}), 404
            
        otp = str(random.randint(100000, 999999))
        email_sent = send_otp_email(email, otp)
        if not email_sent:
            print(f"[WARN] Email failed for {email}. OTP (check console): {otp}")
        
        # Always store OTP regardless of email result so user can proceed
        otp_storage[email] = {
            "otp": otp, 
            "type": "forgot_password",
            "expires": datetime.now() + timedelta(minutes=10)
        }
        return jsonify({"message": "Reset OTP sent to your email."}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/verify-email', methods=['POST'])
def verify_email():
    try:
        data = request.get_json()
        email, otp = data.get('email'), data.get('otp')
        if not email or not otp:
            return jsonify({"error": "Email and OTP are required"}), 400
        
        stored = otp_storage.get(email)
        if not stored:
            return jsonify({"error": "No OTP found. Please request a new reset code."}), 400
        
        # Check expiry
        if datetime.now() > stored.get('expires', datetime.min):
            del otp_storage[email]
            return jsonify({"error": "OTP has expired. Please request a new reset code."}), 400
        
        if stored['otp'] != otp:
            return jsonify({"error": "Invalid OTP. Please check and try again."}), 400
        
        if stored.get('type') != 'forgot_password':
            return jsonify({"error": "Invalid OTP type."}), 400
        
        return jsonify({"message": "OTP verified successfully."}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        data = request.get_json()
        email, otp, new_password = data.get('email'), data.get('otp'), data.get('password')
        
        if email in otp_storage and otp_storage[email]['otp'] == otp and otp_storage[email]['type'] == 'forgot_password':
            cur = mysql.connection.cursor()
            cur.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
            mysql.connection.commit()
            cur.close()
            del otp_storage[email]
            return jsonify({"message": "Password reset successful"}), 200
        return jsonify({"error": "Session expired or invalid OTP"}), 400
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get-assessment-history/<int:user_id>', methods=['GET'])
def get_assessment_history(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, oral_score, mental_score, date, time, submission_date FROM daily_results WHERE user_id = %s ORDER BY submission_date DESC", (user_id,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id": r[0], "oral_score": r[1], "mental_score": r[2], "date": r[3], "time": r[4], "created_at": r[5].strftime('%Y-%m-%d %H:%M:%S')} for r in rows]), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/save-assessment', methods=['POST'])
@app.route('/submit-assessment', methods=['POST'])
def save_assessment():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        time_str = data.get('time', datetime.now().strftime('%H:%M:%S'))
        
        # Handle different payload formats (Web flat Q1-Q10 vs Android list of AssessmentAnswer)
        raw_answers = {}
        if 'answers' in data:
            # Android format: list of {"question_id": i, "choice": "..."}
            for a in data['answers']:
                raw_answers[f"q{a['question_id']}"] = a['choice']
        else:
            # Web format: {"q1": "...", "q2": "...", ...}
            for i in range(1, 11):
                raw_answers[f"q{i}"] = data.get(f'q{i}', '')

        # Scoring Logic
        # Never: 20, Hardly ever: 16, Occasionally: 12, Fairly often: 8, Often/Very often: 4
        score_map = {
            "Never": 20,
            "Hardly ever": 16,
            "Occasionally": 12,
            "Fairly often": 8,
            "Often": 4,
            "Very often": 4
        }
        
        raw_oral = 0
        raw_mental = 0
        
        final_answers_list = []
        for i in range(1, 11):
            choice = raw_answers.get(f"q{i}", "Never") # Default to Never if missing
            points = score_map.get(choice, 20) # Default to 20 if choice unknown
            
            if i <= 5:
                raw_oral += points
            else:
                raw_mental += points
            final_answers_list.append(choice)
        
        # Scores are now out of 100% directly (5 questions * 20 max = 100)
        oral_score = int(raw_oral)
        mental_score = int(raw_mental)
                
        # Generate recommendations based on the scores
        recoms = []
        if oral_score < 70:
            recoms.append("Schedule a Dental Visit: Your oral score indicates potential issues. A checkup is highly advised.")
        else:
            recoms.append("Maintain Oral Hygiene: Your teeth look good. Keep brushing twice daily and flossing regularly.")
            
        if mental_score < 70:
            recoms.append("Focus on Mental Wellness: Consider speaking with a professional or practicing daily mindfulness exercises.")
        else:
            recoms.append("Keep Hydrated & Active: Your mental wellness is great. Daily walks and hydration will help you maintain this balance.")
            
        recommendation_text = " || ".join(recoms)
        
        cur = mysql.connection.cursor()
        
        # 1. Save to assessment_answers (Detailed tracking)
        cur.execute("""
            INSERT INTO assessment_answers 
            (user_id, q1_ans, q2_ans, q3_ans, q4_ans, q5_ans, q6_ans, q7_ans, q8_ans, q9_ans, q10_ans, oral_score, mental_score, recommendations, date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, *final_answers_list, oral_score, mental_score, recommendation_text, date_str))
        
        # 2. Save to daily_results (History/Trends)
        cur.execute("""
            INSERT INTO daily_results (user_id, oral_score, mental_score, date, time)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, oral_score, mental_score, date_str, time_str))
        
        mysql.connection.commit()
        cur.close()
        
        return jsonify({
            "message": "Assessment saved fully",
            "oral_score": oral_score,
            "mental_score": mental_score,
            "result_id": cur.lastrowid, # Helpful for Android's result_id expectation
            "recommendations": recommendation_text
        }), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/get-scan-history/<int:user_id>', methods=['GET'])
def get_scan_history(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, score, status, problem_detected, severity, confidence_percentage, risk_level, understanding_results, recommendation, visit_dentist, image_url, created_at FROM scan_results WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id": r[0], "score": r[1], "status": r[2], "problem_detected": r[3], "severity": r[4], "confidence_percentage": r[5], "risk_level": r[6], "understanding_results": r[7], "recommendation": r[8], "visit_dentist": r[9], "image_url": r[10], "created_at": r[11].strftime('%Y-%m-%d %H:%M:%S')} for r in rows]), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/upload-photo', methods=['POST'])
def upload_photo():
    try:

        file = request.files['file']
        user_id = request.form.get('user_id')

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['SCAN_UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # ---------- YOLO DETECTION ----------
        results = yolo_model(file_path, conf=0.25, save=True)
        save_dir = results[0].save_dir if len(results) > 0 else ""

        detected = []
        total_conf = 0.0
        count = 0

        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0]) * 100
                label = yolo_model.names[cls]
                detected.append(label)
                total_conf += conf
                count += 1
                
        avg_conf = int(total_conf / count) if count > 0 else 95

        # ---------- ANALYSIS (Dynamic) ----------

        # Build understanding results mapping
        problemExplanations = {
            'calculus': 'Calculus (Tartar): Hardened dental plaque that forms below and above the gum line. It can lead to receding gums and gum disease.',
            'caries': 'Caries (Tooth Decay): Breakdown of teeth due to acids made by bacteria. If untreated, it can cause pain, infection, and tooth loss.',
            'gingivitis': 'Gingivitis: An early stage of gum disease caused by plaque buildup on teeth. Symptoms include red, swollen, and bleeding gums.',
            'hypodontia': 'Hypodontia: A condition where one or more teeth fail to develop, which can affect chewing and jaw alignment.',
            'tooth_discolation': 'Tooth Discoloration: Abnormal color, hue, or translucency of a tooth. Often caused by acidic foods, poor hygiene, or smoking.',
            'ulcer': 'Oral Ulcer: A painful sore that appears inside the mouth. It is typically harmless but can cause discomfort while eating or drinking.'
        }
        
        understanding_results = []
        if len(detected) > 0:
            for p in list(set(detected)):
                if p in problemExplanations:
                    understanding_results.append(problemExplanations[p])
        understanding_text = " | ".join(understanding_results) if understanding_results else "No explanations needed."

        if len(detected) == 0:
            score = 100
            status = "Excellent"
            analysis = {
                "status": status,
                "problem_detected": "None",
                "severity": "Low",
                "confidence_percentage": str(avg_conf),
                "risk_level": "Low",
                "recommendation": "No dental problems detected. Brush twice daily, floss, and visit dentist every 6 months.",
                "visit_dentist": "No",
                "note": understanding_text,
                "score": score
            }
        else:
            problems = list(set(detected))
            # Fix display names for problems
            display_problems = [p.replace("tooth_discolation", "tooth discoloration").capitalize() for p in problems]
            problem_text = ", ".join(display_problems)
            
            high_sev = ["caries", "ulcer", "hypodontia"]
            med_sev = ["calculus", "gingivitis"]
            low_sev = ["tooth_discolation"]
            
            highest_sev_level = "Low"
            base_score = 95
            
            recommendation_text = []

            for p in problems:
                if p in high_sev:
                    base_score -= 30
                    highest_sev_level = "High"
                elif p in med_sev:
                    base_score -= 20
                    if highest_sev_level != "High": highest_sev_level = "Moderate" # Changed from Medium to Moderate for Android
                elif p in low_sev:
                    base_score -= 10

            score = max(0, base_score)
            status = "Fair" if score > 50 else "Poor"

            if "calculus" in problems:
                recommendation_text.append("Calculus detected. Professional cleaning recommended.")
            if "caries" in problems:
                recommendation_text.append("Caries detected. Visit dentist soon for fillings.")
            if "tooth_discolation" in problems:
                recommendation_text.append("Discoloration present. Improve brushing hygiene.")
            if "gingivitis" in problems:
                recommendation_text.append("Gingivitis detected. Improve flossing and use mouthwash.")
            if "ulcer" in problems:
                recommendation_text.append("Oral ulcer detected. Consult doctor if it doesn't heal.")
            if "hypodontia" in problems:
                recommendation_text.append("Missing tooth detected. Consult an orthodontist.")

            analysis = {
                "status": status,
                "problem_detected": problem_text,
                "severity": highest_sev_level,
                "confidence_percentage": str(avg_conf),
                "risk_level": highest_sev_level,
                "recommendation": " | ".join(recommendation_text),
                "visit_dentist": "Yes" if highest_sev_level in ["High", "Moderate"] else "Suggested",
                "note": understanding_text,
                "score": score
            }

        # Handle Annotated Image
        base_name, _ = os.path.splitext(filename)
        annotated_filename = base_name + ".jpg" # Ultralytics typically saves as jpg
        annotated_path = os.path.join(save_dir, annotated_filename) if save_dir else ""
        
        # If the annotated image exists in runs, serve it from an endpoint, or copy it over
        if annotated_path and os.path.exists(annotated_path):
            import shutil
            final_served_name = "annotated_" + annotated_filename
            served_path = os.path.join(app.config['SCAN_UPLOAD_FOLDER'], final_served_name)
            shutil.copy(annotated_path, served_path)
            image_url = f"uploads/scans/{final_served_name}"
        else:
            # Fallback to un-annotated
            image_url = f"uploads/scans/{filename}"

        return jsonify({
            "message": "Analysis completed successfully",
            "analysis": analysis,
            "image_url": image_url,
            "understanding_results": understanding_text
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/save-scan-result', methods=['POST'])
def save_scan_result():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        score = data.get('score')
        status = data.get('status')
        problem_detected = data.get('problem_detected')
        severity = data.get('severity')
        confidence_percentage = data.get('confidence_percentage')
        risk_level = data.get('risk_level')
        understanding_results = data.get('understanding_results')
        recommendation = data.get('recommendation')
        visit_dentist = data.get('visit_dentist')
        image_url = data.get('image_url')

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO scan_results
            (user_id,score,status,problem_detected,severity,confidence_percentage,
            risk_level,understanding_results,recommendation,visit_dentist,image_url)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id, score, status, problem_detected, severity, confidence_percentage,
            risk_level, understanding_results, recommendation, visit_dentist, image_url
        ))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Scan result saved successfully"}), 201
    except Exception as e:
        print("Save Error:", e)
        return jsonify({"error": str(e)}), 500
    
@app.route('/uploads/scans/<filename>')
def serve_scan_image(filename):
    return send_file(os.path.join(app.config['SCAN_UPLOAD_FOLDER'], filename))

@app.route('/uploads/profiles/<filename>')
def serve_profile_image(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/get-latest-assessment/<int:user_id>', methods=['GET'])
def get_latest_assessment(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT oral_score, mental_score FROM daily_results WHERE user_id = %s ORDER BY submission_date DESC LIMIT 1", (user_id,))
        result = cur.fetchone()
        cur.close()
        return jsonify({"oral_score": result[0], "mental_score": result[1]} if result else {"oral_score": 0, "mental_score": 0}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/add-medication', methods=['POST'])
def add_medication():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        name = data.get('medication_name')
        dosage = data.get('dosage')
        frequency = data.get('frequency')
        time = data.get('time')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        instructions = data.get('instructions')

        cur = mysql.connection.cursor()
        # Get user info for email
        cur.execute("SELECT email, full_name FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            cur.close()
            return jsonify({"error": "User not found"}), 404
            
        cur.execute("""
            INSERT INTO medications (user_id, medication_name, dosage, frequency, time, start_date, end_date, instructions)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, name, dosage, frequency, time, start_date, end_date, instructions))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "Medication added successfully"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/delete-medication/<int:med_id>', methods=['DELETE'])
def delete_medication(med_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM medications WHERE id = %s", (med_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Medication deleted successfully"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/add-clinic-visit', methods=['POST'])
def add_clinic_visit():
    try:
        data = request.get_json()
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO clinic_visits (user_id, doctor_name, clinic_hospital, date, time, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (data['user_id'], data['doctor_name'], data.get('clinic_hospital'), data.get('date'), data.get('time'), data.get('notes')))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Visit added successfully"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/delete-clinic-visit/<int:visit_id>', methods=['DELETE'])
def delete_clinic_visit(visit_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM clinic_visits WHERE id = %s", (visit_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Visit deleted successfully"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

def parse_flexible_date(d_str):
    if not d_str: return None
    import datetime as _dt
    if isinstance(d_str, _dt.datetime): return d_str.date()
    if isinstance(d_str, _dt.date): return d_str
    d_str = str(d_str).replace('-', '/')
    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try: return datetime.strptime(d_str, fmt).date()
        except: continue
    return None

def parse_flexible_time(t_str):
    if not t_str: return None
    if isinstance(t_str, timedelta):
        try:
            total_seconds = int(t_str.total_seconds())
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            return datetime.now().replace(hour=h % 24, minute=m, second=0, microsecond=0).time()
        except: return None
    t_str = str(t_str).strip().upper()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"):
        try: return datetime.strptime(t_str, fmt).time()
        except: pass
    if ":" in t_str:
        try:
            parts = t_str.split(":")
            h = int(parts[0])
            m = int(parts[1][:2])
            is_pm = "PM" in t_str
            is_am = "AM" in t_str
            if is_pm and h < 12: h += 12
            if is_am and h == 12: h = 0
            return datetime.now().replace(hour=h, minute=m, second=0, microsecond=0).time()
        except: pass
    return None

def should_trigger_medication(now_dt, m_start_date, m_end_date, base_time_obj, freq_str, m_last_day):
    if not m_start_date or not base_time_obj: return False, None
    
    start_dt = datetime.combine(m_start_date, base_time_obj)
    if now_dt < start_dt:
        return False, None
    if m_end_date:
        end_dt = datetime.combine(m_end_date, time(23, 59, 59))
        if now_dt > end_dt:
            return False, None
            
    interval_hours = 0
    interval_days = 0
    
    fs = (freq_str or "").lower()
    
    if "every 4 hours" in fs: interval_hours = 4
    elif "every 6 hours" in fs: interval_hours = 6
    elif "every 8 hours" in fs: interval_hours = 8
    elif "every 12 hours" in fs: interval_hours = 12
    elif "twice a day" in fs: interval_hours = 12
    elif "three times a day" in fs: interval_hours = 8
    elif "four times a day" in fs: interval_hours = 6
    elif "two days once" in fs: interval_days = 2
    elif "weekly once" in fs or "weekly" == fs: interval_days = 7
    elif "weekly twice" in fs or "bi-weekly" in fs: interval_days = 3.5
    elif "monthly" in fs: interval_days = 30
    else: interval_days = 1 # daily
    
    recent_dt = None
    if interval_hours > 0:
        delta_secs = (now_dt - start_dt).total_seconds()
        occurrences = int(delta_secs // (interval_hours * 3600))
        recent_dt = start_dt + timedelta(hours=occurrences * interval_hours)
    else:
        delta_days = (now_dt.date() - m_start_date).days
        if "monthly" in fs:
            if now_dt.day == m_start_date.day: recent_dt = datetime.combine(now_dt.date(), base_time_obj)
        elif interval_days == 3.5:
            if delta_days % 7 in (0, 3, 4): recent_dt = datetime.combine(now_dt.date(), base_time_obj)
        else:
            if delta_days % interval_days == 0: recent_dt = datetime.combine(now_dt.date(), base_time_obj)

    if recent_dt and recent_dt <= now_dt <= (recent_dt + timedelta(minutes=5)):
        slot_key = recent_dt.strftime('%Y%m%d_%H%M')
        if m_last_day != slot_key:
            return True, slot_key
    return False, None

def check_and_notify_internal():
    """
    Background worker function that checks ALL users for upcoming notifications.
    Triggered by the scheduler every minute.
    Now enhanced with:
    - Modular frequency schedule calculations (should_trigger_medication)
    - Automatic deletion of expired medications
    """
    with app.app_context():
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id, email, full_name FROM users WHERE is_verified = TRUE")
            users = cur.fetchall()
            
            now = datetime.now()
            today_obj = now.date()
            
            for user in users:
                user_id, email, full_name = user
                
                # 0. Daily "Tasks Ready" Notification
                # Check if we already sent the daily tasks notification for today
                cur.execute("""
                    SELECT id FROM user_notifications 
                    WHERE user_id = %s AND title = 'Daily Tasks' AND DATE(created_at) = %s
                """, (user_id, today_obj))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO user_notifications (user_id, title, message, type) 
                        VALUES (%s, %s, %s, %s)
                    """, (user_id, "Daily Tasks", "Good morning! Your daily oral health tasks are ready.", "general"))
                    mysql.connection.commit()
                    send_firebase_push(user_id, "Daily Tasks", "Good morning! Your daily oral health tasks are ready.")

                # 1. Check Clinic Visits
                cur.execute("""
                    SELECT id, doctor_name, clinic_hospital, date, time, reminder_sent
                    FROM clinic_visits 
                    WHERE user_id = %s AND status = 'pending'
                """, (user_id,))
                visits = cur.fetchall()
                
                for visit in visits:
                    v_id, v_doc, v_clinic, v_date, v_time, v_reminder_sent = visit
                    try:
                        v_date_obj = parse_flexible_date(v_date)
                        if not v_date_obj: continue
                        
                        v_time_obj = parse_flexible_time(v_time)
                        if not v_time_obj: continue
                        
                        v_dt = datetime.combine(v_date_obj, v_time_obj)

                        if now >= v_dt and not v_reminder_sent:
                            details = {"doctor_name": v_doc, "clinic_hospital": v_clinic, "time": v_time, "date": v_date}
                            try:
                                cur.execute("UPDATE clinic_visits SET reminder_sent = TRUE WHERE id = %s", (v_id,))
                                cur.execute("INSERT INTO user_notifications (user_id, title, message, type) VALUES (%s, %s, %s, %s)", 
                                          (user_id, "Visit Now", f"Your visit with {v_doc} is scheduled for right now.", "visit_reminder"))
                                mysql.connection.commit()
                            except Exception as inner_e:
                                print(f"Error marking clinic visit as sent: {inner_e}")
                                continue
                            send_visit_reminder_email(email, full_name, details)
                            send_firebase_push(user_id, "Visit Now", f"Your visit with {v_doc} is scheduled for right now.")
                            
                        # Auto-delete if the exact time has passed
                        if today_obj > v_date_obj or (v_date_obj == today_obj and now > v_dt):
                            cur.execute("DELETE FROM clinic_visits WHERE id = %s", (v_id,))
                            mysql.connection.commit()
                            continue
                    except Exception as e: 
                        print(f"Error processing clinic visit {v_id}: {e}")

                # 2. Check Medications
                cur.execute("SELECT id, medication_name, dosage, frequency, time, start_date, end_date, last_notified_day FROM medications WHERE user_id = %s", (user_id,))
                meds = cur.fetchall()
                for med in meds:
                    m_id, m_name, m_dosage, m_freq, m_time, m_start, m_end, m_last_day = med
                    try:
                        s_obj = parse_flexible_date(m_start)
                        e_obj = parse_flexible_date(m_end)
                        t_obj = parse_flexible_time(m_time)
                        
                        if e_obj and today_obj > e_obj:
                            cur.execute("DELETE FROM medications WHERE id = %s", (m_id,))
                            mysql.connection.commit()
                            continue
                        
                        should_trigger, slot_key = should_trigger_medication(now, s_obj, e_obj, t_obj, m_freq, m_last_day)
                        
                        if should_trigger:
                            # 1. DB Update MUST happen to ensure no duplicates, even if email fails
                            try:
                                cur.execute("UPDATE medications SET last_notified_day = %s WHERE id = %s", (slot_key, m_id))
                                cur.execute("INSERT INTO user_notifications (user_id, title, message, type) VALUES (%s, %s, %s, %s)", 
                                          (user_id, "Medication Time", f"Time to take {m_name} ({m_dosage}).", "medication_reminder"))
                                mysql.connection.commit()
                            except Exception as inner_e:
                                print(f"Error updating med status: {inner_e}")
                                continue
                                
                            # 2. Best-effort email
                            med_details = {"name": m_name, "dosage": m_dosage, "frequency": m_freq, "time": m_time, "start_date": m_start, "end_date": m_end}
                            send_medication_reminder_email(email, full_name, med_details)
                            send_firebase_push(user_id, "Medication Time", f"Time to take {m_name} ({m_dosage}).")
                            
                    except Exception as e: 
                        print(f"Error processing medication {m_id}: {e}")
            
            # 3. Daily Cleanup of old notifications (Delete previous day's notifications)
            cur.execute("DELETE FROM user_notifications WHERE created_at < CURDATE()")
            mysql.connection.commit()

            cur.close()
        except Exception as e:
            print(f"Scheduler Error: {e}")

def run_scheduler():
    import time
    print("Background APScheduler Started")
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_and_notify_internal, trigger="interval", minutes=1)
    scheduler.start()
    while True:
        time.sleep(60)

@app.route('/check-and-notify', methods=['POST'])
def check_and_notify():
    # Keep for compatibility, but now triggers the internal check
    check_and_notify_internal()
    return jsonify({"message": "Triggered manual check"}), 200

@app.route('/get-notifications/<int:user_id>', methods=['GET'])
def get_notifications(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, title, message, type, is_read, created_at FROM user_notifications WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id":r[0], "title":r[1], "message":r[2], "type":r[3], "is_read":bool(r[4]), "created_at":r[5].strftime('%Y-%m-%d %H:%M:%S')} for r in rows]), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/mark-notifications-read', methods=['POST'])
def mark_notifications_read():
    try:
        data = request.get_json()
        cur = mysql.connection.cursor()
        cur.execute("UPDATE user_notifications SET is_read = TRUE WHERE user_id = %s", (data['user_id'],))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Success"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get-profile/<int:user_id>', methods=['GET'])
def get_profile(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT full_name, email, phone_number, profile_image FROM users WHERE id = %s", (user_id,))
        u = cur.fetchone()
        cur.close()
        return jsonify({"full_name": u[0], "email": u[1], "phone_number": u[2], "profile_image": u[3]}) if u else (jsonify({"error": "Not found"}), 404)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/update-profile', methods=['POST'])
def update_profile():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        full_name = data.get('full_name')
        phone_number = data.get('phone_number')
        
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET full_name = %s, phone_number = %s WHERE id = %s", (full_name, phone_number, user_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Profile updated successfully"}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/upload-profile-image', methods=['POST'])
def upload_profile_image():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        user_id = request.form.get('user_id')
        
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
            
        filename = secure_filename(file.filename)
        # Add timestamp to filename to avoid caching issues
        filename = f"{int(datetime.now().timestamp())}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        image_db_path = f"uploads/profiles/{filename}"
        
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET profile_image = %s WHERE id = %s", (image_db_path, user_id))
        mysql.connection.commit()
        cur.close()
        
        return jsonify({"message": "Image uploaded successfully", "profile_image": image_db_path}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/update-fcm-token', methods=['POST'])
def update_fcm_token():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        token = data.get('fcm_token')
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET fcm_token = %s WHERE id = %s", (token, user_id))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "FCM Token updated successfully"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get-medications/<int:user_id>', methods=['GET'])
def get_medications(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, medication_name, dosage, frequency, time, end_date FROM medications WHERE user_id = %s", (user_id,))
        rows = cur.fetchall()
        
        valid_meds = []
        today_obj = datetime.now().date()
        
        for r in rows:
            e_obj = parse_flexible_date(r[5])
            if e_obj and today_obj > e_obj:
                cur.execute("DELETE FROM medications WHERE id = %s", (r[0],))
                continue
            valid_meds.append({"id": r[0], "medication_name": r[1], "dosage": r[2], "frequency": r[3], "time": r[4]})
            
        mysql.connection.commit()
        cur.close()
        return jsonify(valid_meds), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get-clinic-visits/<int:user_id>', methods=['GET'])
def get_clinic_visits(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, doctor_name, clinic_hospital, date, time, status FROM clinic_visits WHERE user_id = %s", (user_id,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id": r[0], "doctor_name": r[1], "clinic_hospital": r[2], "date": r[3], "time": r[4], "status": r[5]} for r in rows]), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/add-emergency-contact', methods=['POST'])
def add_emergency_contact():
    try:
        data = request.get_json()
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO emergency_contacts (user_id, full_name, phone_number, relationship)
            VALUES (%s, %s, %s, %s)
        """, (data['user_id'], data['full_name'], data['phone_number'], data.get('relationship')))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Contact added successfully"}), 201
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get-emergency-contacts/<int:user_id>', methods=['GET'])
def get_emergency_contacts(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, full_name, phone_number, relationship FROM emergency_contacts WHERE user_id = %s", (user_id,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id": r[0], "full_name": r[1], "phone_number": r[2], "relationship": r[3]} for r in rows]), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/delete-emergency-contact/<int:contact_id>', methods=['DELETE'])
def delete_emergency_contact(contact_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM emergency_contacts WHERE id = %s", (contact_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Contact deleted successfully"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get-helplines', methods=['GET'])
def get_helplines():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, service_name, phone_number, description FROM helplines")
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id": r[0], "service_name": r[1], "phone_number": r[2], "description": r[3]} for r in rows]), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/update-task-status', methods=['POST'])
def update_task_status():
    try:
        data = request.get_json()
        user_id = data['user_id']
        task_label = data['task_label']
        task_date = data['task_date']
        is_completed = data['is_completed']
        
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO task_completions (user_id, task_label, task_date, is_completed) 
            VALUES (%s, %s, %s, %s) 
            ON DUPLICATE KEY UPDATE is_completed = VALUES(is_completed)
        """, (user_id, task_label, task_date, is_completed))
        
        # If the user marked it as NOT completed (Missed), add a notification
        if not is_completed:
            cur.execute("""
                INSERT INTO user_notifications (user_id, title, message, type) 
                VALUES (%s, %s, %s, %s)
            """, (user_id, "Task Missed", f"Missed {task_label}", "missed_task"))
            
        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Success"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get-task-status/<int:user_id>/<path:task_date>', methods=['GET'])
def get_task_status(user_id, task_date):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT task_label, is_completed FROM task_completions WHERE user_id = %s AND task_date = %s", (user_id, task_date))
        rows = cur.fetchall()
        cur.close()
        return jsonify({r[0]: bool(r[1]) for r in rows}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/voice-assistant', methods=['POST'])
def voice_assistant():
    try:
        data = request.get_json()
        query = data.get('query', '').lower()
        user_id = data.get('user_id')
        
        if not query:
            return jsonify({"response": "I didn't hear anything. How can I help you today?"}), 400

        cur = mysql.connection.cursor()
        response_text = ""

        # 1. Medications Query
        if any(w in query for w in ["medication", "medicine", "tablet", "pill", "drug"]):
            cur.execute("SELECT medication_name, dosage, time FROM medications WHERE user_id = %s", (user_id,))
            meds = cur.fetchall()
            if meds:
                med_list = [f"{m[0]} ({m[1]}) at {m[2]}" for m in meds]
                response_text = "Your medications for today are: " + ", ".join(med_list) + "."
            else:
                response_text = "You have no medications scheduled for today."

        # 2. Oral Scan Results Query
        elif any(w in query for w in ["scan", "result", "analysis", "report"]):
            cur.execute("SELECT status, risk_level, problem_detected FROM scan_results WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,))
            scan = cur.fetchone()
            if scan:
                response_text = f"Your last oral scan status was {scan[0]} with a {scan[1]} risk level. We detected {scan[2] or 'no major issues'}."
            else:
                response_text = "I couldn't find any recent oral scan results for you. Would you like to take a new scan?"

        # 3. Emergency Contact Query
        elif any(w in query for w in ["emergency", "contact", "call", "help"]):
            cur.execute("SELECT full_name, phone_number FROM emergency_contacts WHERE user_id = %s LIMIT 1", (user_id,))
            contact = cur.fetchone()
            if contact:
                response_text = f"Your emergency contact is {contact[0]}. You can reach them at {contact[1]}."
            else:
                response_text = "You haven't added any emergency contacts yet. You can add one in the Emergency Contacts section."

        # 4. Mental Wellness Query
        elif any(w in query for w in ["mental", "wellness", "score", "mood", "feeling"]):
            cur.execute("SELECT mental_score, oral_score FROM daily_results WHERE user_id = %s ORDER BY submission_date DESC LIMIT 1", (user_id,))
            scores = cur.fetchone()
            if scores:
                response_text = f"Your latest mental wellness score is {scores[0]} percent, and your oral health score is {scores[1]} percent."
            else:
                response_text = "I don't have any daily assessment results for you yet. Please complete a health check to see your scores!"

        # 5. Gum Health Specific (Pre-fallback)
        elif "gum" in query and "health" in query:
            response_text = "To improve your gum health, remember to brush twice daily, floss regularly, and use a soft-bristled toothbrush. Massaging your gums while brushing also helps!"

        # 6. Gemini Fallback for General Questions
        else:
            model = get_gemini_model()
            if model:
                try:
                    prompt = f"The user asked: '{query}'. Provide a very short, helpful response (max 2 sentences) about oral health or wellness as a virtual dental assistant named Smilewell."
                    gen_res = model.generate_content(prompt)
                    response_text = gen_res.text.strip()
                except Exception:
                    response_text = "I'm here to help with your medications, scan results, or oral health advice. What can I do for you?"
            else:
                response_text = "I'm your Smilewell assistant. I can help you with your medications, oral scans, or general dental health tips. How can I assist you today?"

        cur.close()
        return jsonify({"response": response_text}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/migrate-db', methods=['GET'])
def migrate_db():
    try:
        cur = mysql.connection.cursor()
        try:
            cur.execute("ALTER TABLE clinic_visits ADD COLUMN notified TINYINT(1) DEFAULT 0")
            mysql.connection.commit()
            message = "Successfully added 'notified' column to clinic_visits."
        except Exception as e:
            if "Duplicate column name" in str(e):
                message = "'notified' column already exists."
            else:
                raise e
        cur.close()
        return jsonify({"message": message}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    import threading
    threading.Thread(target=run_scheduler, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
