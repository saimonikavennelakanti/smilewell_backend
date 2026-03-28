import MySQLdb
db = MySQLdb.connect(host='localhost', user='root', passwd='', db='smile_well')
cur = db.cursor()
cur.execute('SELECT notified FROM clinic_visits WHERE doctor_name = "Test Dr."')
print(cur.fetchall())
cur.close()
db.close()
