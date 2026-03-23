from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_mysqldb import MySQL
from dotenv import load_dotenv
import os
import traceback
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import google.generativeai as genai
from PIL import Image
import io

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
        body = f"Hello {user_name},\n\nYou have a clinic visit scheduled in 10 minutes:\n\n"
        body += f"Doctor: {visit_details['doctor_name']}\n"
        body += f"Clinic/Hospital: {visit_details['clinic_hospital']}\n"
        body += f"Time: {visit_details['time']}\n"
        body += f"Date: {visit_details['date']}\n\n"
        body += "Please arrive on time.\n\nStay healthy,\nSmile Well Team"
        
        msg = MIMEText(body)
        msg['Subject'] = f"Appointment Alert: {visit_details['doctor_name']} in 10 mins"
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

            cur.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS oral_scans (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    status VARCHAR(50),
                    problem_detected TEXT,
                    severity VARCHAR(50),
                    confidence_percentage VARCHAR(20),
                    risk_level VARCHAR(50),
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

            cur.execute("""
                CREATE TABLE IF NOT EXISTS assessment_answers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    result_id INT NOT NULL,
                    question_id INT NOT NULL,
                    choice VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (result_id) REFERENCES daily_results(id) ON DELETE CASCADE
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
        
        # Check if user already exists
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
        existing_user = cur.fetchone()
        cur.close()
        
        if existing_user:
            return jsonify({"error": "User already exists. Please login."}), 400

        otp = str(random.randint(100000, 999999))
        msg = "OTP sent to email"
        if not send_otp_email(email, otp):
            otp = "123456" # Fallback OTP
            msg = "Email failed. Use 123456 for testing."
            print(f"DEBUG: Falling back to OTP 123456 for {email}")

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
        if email in otp_storage and otp_storage[email]['otp'] == otp:
            s = otp_storage[email]
            if s.get("type") == "registration":
                cur = mysql.connection.cursor()
                cur.execute("INSERT INTO users (full_name, email, password, is_verified) VALUES (%s, %s, %s, TRUE)", (s['full_name'], email, s['password']))
                mysql.connection.commit()
                user_id = cur.lastrowid
                full_name = s['full_name']
                cur.close()
                del otp_storage[email]
                return jsonify({"message": "Success", "user_id": user_id, "full_name": full_name}), 201
            else:
                return jsonify({"message": "OTP Verified"}), 200
        return jsonify({"error": "Invalid OTP"}), 400
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
            return jsonify({"error": "User not found"}), 404
            
        otp = str(random.randint(100000, 999999))
        if send_otp_email(email, otp):
            otp_storage[email] = {
                "otp": otp, 
                "type": "forgot_password",
                "expires": datetime.now() + timedelta(minutes=10)
            }
            return jsonify({"message": "Reset OTP sent"}), 200
        return jsonify({"error": "Failed to send OTP"}), 500
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/verify-email', methods=['POST'])
def verify_email():
    try:
        data = request.get_json()
        email, otp = data.get('email'), data.get('otp')
        if email in otp_storage and otp_storage[email]['otp'] == otp and otp_storage[email]['type'] == 'forgot_password':
            return jsonify({"message": "OTP Verified"}), 200
        return jsonify({"error": "Invalid OTP"}), 400
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
        cur.execute("SELECT id, oral_score, mental_score, date, time, created_at FROM daily_results WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id": r[0], "oral_score": r[1], "mental_score": r[2], "date": r[3], "time": r[4], "created_at": r[5].strftime('%Y-%m-%d %H:%M:%S')} for r in rows]), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/submit-assessment', methods=['POST'])
def submit_assessment():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        answers = data.get('answers', []) # List of {question_id, choice}
        date = data.get('date')
        time = data.get('time')

        oral_score = 0
        mental_score = 0

        for ans in answers:
            qid = int(ans.get('question_id', 0))
            choice = ans.get('choice')
            
            points = 0
            if choice == "No": points = 20
            elif choice == "Sometimes": points = 10
            elif choice == "Yes": points = 0

            if 1 <= qid <= 5:
                oral_score += points
            elif 6 <= qid <= 10:
                mental_score += points

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO daily_results (user_id, oral_score, mental_score, date, time)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, oral_score, mental_score, date, time))
        mysql.connection.commit()
        result_id = cur.lastrowid

        # Insert individual answers
        for ans in answers:
            qid = int(ans.get('question_id', 0))
            choice = ans.get('choice')
            cur.execute("""
                INSERT INTO assessment_answers (result_id, question_id, choice)
                VALUES (%s, %s, %s)
            """, (result_id, qid, choice))
        
        mysql.connection.commit()
        cur.close()

        return jsonify({
            "message": "Assessment submitted successfully",
            "oral_score": oral_score,
            "mental_score": mental_score,
            "result_id": result_id
        }), 201
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/get-scan-history/<int:user_id>', methods=['GET'])
def get_scan_history(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, status, problem_detected, severity, confidence_percentage, risk_level, recommendation, visit_dentist, image_url, created_at FROM oral_scans WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id": r[0], "status": r[1], "problem_detected": r[2], "severity": r[3], "confidence_percentage": r[4], "risk_level": r[5], "recommendation": r[6], "visit_dentist": r[7], "image_url": r[8], "created_at": r[9].strftime('%Y-%m-%d %H:%M:%S')} for r in rows]), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/upload-photo', methods=['POST'])
def upload_photo():
    try:
        file = request.files['file']
        user_id = request.form.get('user_id')
        filename = secure_filename(f"scan_{user_id}_{file.filename}")
        file_path = os.path.join(app.config['SCAN_UPLOAD_FOLDER'], filename)
        file.save(file_path)

        model = get_gemini_model()
        img = Image.open(file_path)
        prompt = "Analyze this mouth photo for dental issues. Return JSON with status, problem_detected, severity, confidence_percentage, risk_level, recommendation, visit_dentist."
        response = model.generate_content([prompt, img])

        import json
        try:
            analysis = json.loads(response.text.replace('```json', '').replace('```', '').strip())
        except:
            analysis = {"status": "problem_detected", "problem_detected": "Manual check required", "severity": "Medium", "confidence_percentage": "70", "risk_level": "Moderate", "recommendation": "Consult a dentist", "visit_dentist": "Yes"}

        image_url = f"uploads/scans/{filename}"
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO oral_scans (user_id, status, problem_detected, severity, confidence_percentage, risk_level, recommendation, visit_dentist, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, analysis['status'], analysis['problem_detected'], analysis['severity'], analysis['confidence_percentage'], analysis['risk_level'], analysis['recommendation'], analysis['visit_dentist'], image_url))
        mysql.connection.commit()
        cur.close()

        return jsonify({"analysis": analysis, "image_url": image_url}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/uploads/scans/<filename>')
def serve_scan_image(filename):
    return send_file(os.path.join(app.config['SCAN_UPLOAD_FOLDER'], filename))

@app.route('/get-latest-assessment/<int:user_id>', methods=['GET'])
def get_latest_assessment(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT oral_score, mental_score FROM daily_results WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,))
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

        # Send initial confirmation email
        med_details = {
            "name": name,
            "dosage": dosage,
            "frequency": frequency,
            "time": time,
            "start_date": start_date
        }
        send_medication_reminder_email(user[0], user[1], med_details)

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

@app.route('/check-and-notify', methods=['POST'])
def check_and_notify():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        cur = mysql.connection.cursor()
        
        now = datetime.now()
        today_str = now.strftime('%m/%d/%Y')
        target_time = now + timedelta(minutes=10)
        
        # 1. Check Clinic Visits (10 mins early)
        cur.execute("SELECT id, doctor_name, clinic_hospital, date, time FROM clinic_visits WHERE user_id = %s AND status = 'pending' AND notified = FALSE", (user_id,))
        visits = cur.fetchall()
        
        for visit in visits:
            v_id, v_doc, v_clinic, v_date, v_time = visit
            try:
                v_datetime_str = f"{v_date} {v_time}"
                v_dt = datetime.strptime(v_datetime_str, "%m/%d/%Y %I:%M %p")
                
                # Check if visit is within 10-15 minutes from now
                if now <= v_dt <= (now + timedelta(minutes=11)):
                    cur.execute("SELECT email, full_name FROM users WHERE id = %s", (user_id,))
                    user = cur.fetchone()
                    if user:
                        details = {"doctor_name": v_doc, "clinic_hospital": v_clinic, "time": v_time, "date": v_date}
                        send_visit_reminder_email(user[0], user[1], details)
                        cur.execute("UPDATE clinic_visits SET notified = TRUE WHERE id = %s", (v_id,))
                        cur.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (%s, %s, %s, %s)", 
                                  (user_id, "Upcoming Visit", f"Reminder: Your visit with {v_doc} is in 10 minutes.", "visit_reminder"))
            except Exception as e: print(f"Error parsing visit time: {e}")

        # 2. Check Medications (10 mins early)
        cur.execute("SELECT id, medication_name, dosage, frequency, time, start_date, end_date, last_notified_day FROM medications WHERE user_id = %s", (user_id,))
        meds = cur.fetchall()
        
        for med in meds:
            m_id, m_name, m_dosage, m_freq, m_time, m_start, m_end, m_last_day = med
            try:
                # Check if today is between start and end date
                start_dt = datetime.strptime(m_start, "%m/%d/%Y")
                end_dt = datetime.strptime(m_end, "%m/%d/%Y")
                
                # Filter out expired or future meds
                if not (start_dt.date() <= now.date() <= end_dt.date()):
                    continue
                
                # Notification times for today
                notification_times = []
                
                if m_freq == 'Daily':
                    notification_times.append(m_time)
                elif m_freq == 'Weekly':
                    days_diff = (now.date() - start_dt.date()).days
                    if days_diff % 7 == 0:
                        notification_times.append(m_time)
                elif m_freq == 'Every 6 hours':
                    # Calculate 4 times: base_time, base_time+6, base_time+12, base_time+18
                    base_dt = datetime.strptime(f"{today_str} {m_time}", "%m/%d/%Y %I:%M %p")
                    for i in range(4):
                        slot_dt = base_dt + timedelta(hours=i*6)
                        notification_times.append(slot_dt.strftime("%I:%M %p"))
                elif m_freq == 'Twice a day':
                    base_dt = datetime.strptime(f"{today_str} {m_time}", "%m/%d/%Y %I:%M %p")
                    notification_times.append(m_time)
                    notification_times.append((base_dt + timedelta(hours=12)).strftime("%I:%M %p"))
                elif m_freq == 'Three times a day':
                    base_dt = datetime.strptime(f"{today_str} {m_time}", "%m/%d/%Y %I:%M %p")
                    notification_times.append(m_time)
                    notification_times.append((base_dt + timedelta(hours=8)).strftime("%I:%M %p"))
                    notification_times.append((base_dt + timedelta(hours=16)).strftime("%I:%M %p"))
                elif m_freq == 'Every 4 hours':
                    base_dt = datetime.strptime(f"{today_str} {m_time}", "%m/%d/%Y %I:%M %p")
                    for i in range(6):
                        slot_dt = base_dt + timedelta(hours=i*4)
                        notification_times.append(slot_dt.strftime("%I:%M %p"))

                for target_time_str in notification_times:
                    # Check if target time is within 10-15 minutes from now
                    try:
                        m_time_dt = datetime.strptime(f"{today_str} {target_time_str}", "%m/%d/%Y %I:%M %p")
                        # Check if this specific slot was already notified today
                        slot_key = f"{today_str}_{target_time_str}"
                        
                        if now <= m_time_dt <= (now + timedelta(minutes=11)) and m_last_day != slot_key:
                            cur.execute("SELECT email, full_name FROM users WHERE id = %s", (user_id,))
                            user = cur.fetchone()
                            if user:
                                med_details = {"name": m_name, "dosage": m_dosage, "frequency": m_freq, "time": target_time_str, "start_date": m_start}
                                if send_medication_reminder_email(user[0], user[1], med_details):
                                    cur.execute("UPDATE medications SET last_notified_day = %s WHERE id = %s", (slot_key, m_id))
                                    cur.execute("INSERT INTO notifications (user_id, title, message, type) VALUES (%s, %s, %s, %s)", 
                                              (user_id, "Medication Reminder", f"Time to take {m_name} ({m_dosage}). Due in 10 minutes.", "medication_reminder"))
                    except Exception as e: print(f"Error checking med time slot: {e}")
            except Exception as e: print(f"Error parsing med: {e}")

        mysql.connection.commit()
        cur.close()
        return jsonify({"message": "Check complete"}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/get-notifications/<int:user_id>', methods=['GET'])
def get_notifications(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, title, message, type, is_read, created_at FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id":r[0], "title":r[1], "message":r[2], "type":r[3], "is_read":bool(r[4]), "created_at":r[5].strftime('%Y-%m-%d %H:%M:%S')} for r in rows]), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/mark-notifications-read', methods=['POST'])
def mark_notifications_read():
    try:
        data = request.get_json()
        cur = mysql.connection.cursor()
        cur.execute("UPDATE notifications SET is_read = TRUE WHERE user_id = %s", (data['user_id'],))
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

@app.route('/get-medications/<int:user_id>', methods=['GET'])
def get_medications(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, medication_name, dosage, frequency, time FROM medications WHERE user_id = %s", (user_id,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{"id": r[0], "medication_name": r[1], "dosage": r[2], "frequency": r[3], "time": r[4]} for r in rows]), 200
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

@app.route('/update-task-status', methods=['POST'])
def update_task_status():
    try:
        data = request.get_json()
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO task_completions (user_id, task_label, task_date, is_completed) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE is_completed = VALUES(is_completed)", (data['user_id'], data['task_label'], data['task_date'], data['is_completed']))
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

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
