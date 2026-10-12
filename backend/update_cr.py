import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "timewise_dev.db")
con = sqlite3.connect(db_path)
cur = con.cursor()

cur.execute("UPDATE users SET full_name = 'Ashutosh' WHERE email = 'cr.cs3a@timewise.edu'")
con.commit()

cur.execute("SELECT id, email, full_name, role FROM users WHERE email = 'cr.cs3a@timewise.edu'")
user = cur.fetchone()
print(f"Updated CR user: {user}")

con.close()
