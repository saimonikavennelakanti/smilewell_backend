import MySQLdb
db = MySQLdb.connect(host='localhost', user='root', passwd='', db='smile_well')
cur = db.cursor()
# Add a visit for 2:30 PM today for User 50
cur.execute("""
    INSERT INTO clinic_visits (user_id, doctor_name, clinic_hospital, date, time, status, notified)
    VALUES (50, 'Test Dr.', 'Test Clinic', '03/26/2026', '02:30 PM', 'pending', FALSE)
""")
db.commit()
print("Test visit added for 2:30 PM")
cur.close()
db.close()
