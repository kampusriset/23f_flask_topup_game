from werkzeug.security import generate_password_hash
from db import get_db

db = get_db()
cur = db.cursor()

cur.execute(
    "INSERT INTO users (username, password, role) VALUES (%s,%s,%s)",
    ("admin", generate_password_hash("123"), "admin")
)

db.commit()
cur.close()
db.close()

print("Admin berhasil dibuat")
