import MySQLdb
db = MySQLdb.connect(host='localhost', user='root', passwd='', db='smile_well')
cur = db.cursor()
cur.execute('SELECT notified, doctor_name, date, time FROM clinic_visits WHERE user_id = 44')
rows = cur.fetchall()
print(f"Visits for User 44: {rows}")
cur.close()
db.close()
