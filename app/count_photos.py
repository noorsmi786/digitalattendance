import sqlite3
import os

conn = sqlite3.connect('app/data/attendance.db')
conn.row_factory = sqlite3.Row
students = conn.execute('SELECT id, student_code, full_name, father_name, class_name, roll_no, gender, photo_url FROM students WHERE is_active = 1 ORDER BY CAST(class_name AS INTEGER), class_name, CAST(roll_no AS INTEGER)').fetchall()

def has_photo(url):
    if not url or not url.strip():
        return False
    path = os.path.join('app', url.lstrip('/'))
    return os.path.exists(path)

total_m = 0
total_f = 0
m_with = 0
m_no = 0
by_cls = {}

for s in students:
    cls = s['class_name']
    if cls not in by_cls:
        by_cls[cls] = {'m_with': 0, 'm_no': 0, 'f': 0}
    g = s['gender']
    ok = has_photo(s['photo_url'])
    if g == 'Female':
        total_f += 1
        by_cls[cls]['f'] += 1
    else:
        total_m += 1
        if ok:
            m_with += 1
            by_cls[cls]['m_with'] += 1
        else:
            m_no += 1
            by_cls[cls]['m_no'] += 1

print(f"TOTAL STUDENTS: {len(students)}")
print(f"TOTAL MALES: {total_m}  -->  Have Photos: {m_with}  |  NEEDS PHOTOS: {m_no}")
print(f"TOTAL FEMALES (No photos needed): {total_f}")
print("-" * 55)
print(f"{'Class':<8} | {'Males With Photo':<17} | {'Males NEED Photo':<17} | {'Females':<8}")
print("-" * 55)
for k, v in by_cls.items():
    print(f"{k:<8} | {v['m_with']:<17} | {v['m_no']:<17} | {v['f']:<8}")
print("-" * 55)
