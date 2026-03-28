import MySQLdb
db = MySQLdb.connect(host='localhost', user='root', passwd='', db='smile_well')
cur = db.cursor()
cur.execute('SELECT id, user_id, doctor_name, date, time, notified FROM clinic_visits ORDER BY id DESC')
rows = cur.fetchall()
print(f"All Clinic Visits (latest first):")
for r in rows:
    print(r)
cur.close()
db.close()
