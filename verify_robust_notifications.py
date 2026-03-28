from datetime import datetime, timedelta

def parse_flexible_date(d_str):
    if not d_str: return None
    d_str = d_str.replace('-', '/')
    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"):
        try: return datetime.strptime(d_str, fmt).date()
        except: continue
    return None

def parse_flexible_time(t_str):
    if not t_str: return None
    t_str = t_str.strip().upper()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(t_str, fmt).time()
        except:
            continue
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

def test_scenario():
    start_date_str = "26-03-2026"
    end_date_str = "29-04-2026"
    med_time_str = "8:00Am"
    
    s_obj = parse_flexible_date(start_date_str)
    e_obj = parse_flexible_date(end_date_str)
    t_obj = parse_flexible_time(med_time_str)
    
    print(f"Parsed Start: {s_obj}")
    print(f"Parsed End: {e_obj}")
    print(f"Parsed Time: {t_obj}")
    
    # Test for several dates in the range
    test_dates = ["26-03-2026", "27-03-2026", "15-04-2026", "29-04-2026"]
    
    for d_str in test_dates:
        today_obj = parse_flexible_date(d_str)
        is_in_range = s_obj <= today_obj <= e_obj
        
        # Simulate scheduler check
        now = datetime.combine(today_obj, t_obj) # Exactly at the time
        m_dt = datetime.combine(today_obj, t_obj)
        
        should_notify = is_in_range and (m_dt <= now <= (m_dt + timedelta(minutes=5)))
        
        print(f"Date {d_str}: In Range? {is_in_range}, Should Notify? {should_notify}")

if __name__ == "__main__":
    test_scenario()
