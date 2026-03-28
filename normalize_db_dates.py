import MySQLdb
import re

def normalize_date(d_str):
    if not d_str: return d_str
    # already MM/DD/YYYY?
    if re.match(r'^\d{2}/\d{2}/\d{4}$', d_str):
        return d_str
    
    # YYYY-MM-DD?
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', d_str)
    if m:
        return f"{m.group(2)}/{m.group(3)}/{m.group(1)}"
    
    # DD-MM-YYYY?
    m = re.match(r'^(\d{2})-(\d{2})-(\d{4})$', d_str)
    if m:
        return f"{m.group(2)}/{m.group(1)}/{m.group(3)}"

    # DD-MM-YY?
    m = re.match(r'^(\d{2})-(\d{2})-(\d{2})$', d_str)
    if m:
        return f"{m.group(2)}/{m.group(1)}/20{m.group(3)}"
    
    return d_str

try:
    db = MySQLdb.connect(host='localhost', user='root', passwd='', db='smile_well')
    cur = db.cursor()
    cur.execute('SELECT id, date FROM clinic_visits')
    rows = cur.fetchall()
    
    updated_count = 0
    for row_id, old_date in rows:
        new_date = normalize_date(old_date)
        if new_date != old_date:
            cur.execute('UPDATE clinic_visits SET date = %s WHERE id = %s', (new_date, row_id))
            updated_count += 1
            print(f"Updated ID {row_id}: {old_date} -> {new_date}")
    
    db.commit()
    print(f"Total rows updated: {updated_count}")
    cur.close()
    db.close()
except Exception as e:
    print(f"Error: {e}")
