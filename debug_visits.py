import MySQLdb
try:
    db = MySQLdb.connect(host='localhost', user='root', passwd='', db='smile_well')
    cur = db.cursor()
    cur.execute('SELECT user_id, doctor_name, date, time FROM clinic_visits')
    rows = cur.fetchall()
    print("All Clinic Visits:")
    for r in rows:
        print(f"User: {r[0]}, Doc: {r[1]}, Date: '{r[2]}', Time: '{r[3]}'")
    cur.close()
    db.close()
except Exception as e:
    print(f"Error: {e}")
