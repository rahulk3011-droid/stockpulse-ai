import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8501")
DATABASE_PATH = os.getenv("DATABASE_PATH", "stockpulse.db")
TOKEN_EXPIRY_MINUTES = int(os.getenv("TOKEN_EXPIRY_MINUTES", "60"))

LOGIN_PAGE = '''
<!doctype html>
<html>
<head>
  <title>StockPulse AI Login</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0f172a; color:white; display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }
    .card { background:#111827; padding:32px; border-radius:16px; width:380px; box-shadow:0 10px 30px rgba(0,0,0,0.3); }
    input { width:100%; padding:12px; margin:8px 0; border-radius:8px; border:1px solid #334155; background:#0b1220; color:white; box-sizing:border-box; }
    button { width:100%; padding:12px; border:none; border-radius:8px; background:#2563eb; color:white; font-weight:700; cursor:pointer; }
    .error { color:#f87171; margin-bottom:10px; }
    .note { color:#94a3b8; font-size:14px; margin-top:12px; line-height:1.45; }
    a { color:#93c5fd; text-decoration:none; }
  </style>
</head>
<body>
  <div class="card">
    <h2>StockPulse AI</h2>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post" action="/login">
      <input type="email" name="email" placeholder="Email" required>
      <input type="password" name="password" placeholder="Password" required>
      <button type="submit">Log In</button>
    </form>
    <div class="note">
      Demo login: demo@stockpulse.ai / demo123<br>
      Need an account? <a href="/signup">Create one</a>
    </div>
  </div>
</body>
</html>
'''

SIGNUP_PAGE = '''
<!doctype html>
<html>
<head>
  <title>StockPulse AI Signup</title>
</head>
<body style="background:#0f172a;color:white;display:flex;justify-content:center;align-items:center;height:100vh;">
  <div style="background:#111827;padding:30px;border-radius:12px;">
    <h2>Signup</h2>
    {% if error %}<p style="color:red;">{{ error }}</p>{% endif %}
    <form method="post">
      <input type="email" name="email" placeholder="Email" required><br><br>
      <input type="password" name="password" placeholder="Password" required><br><br>
      <button type="submit">Create Account</button>
    </form>
  </div>
</body>
</html>
'''
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def utc_now():
    return datetime.now(timezone.utc)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            user_email TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()

    demo_email = "demo@stockpulse.ai"
    demo_password = "demo123"

    existing = cur.execute("SELECT id FROM users WHERE email = ?", (demo_email,)).fetchone()
    if not existing:
        cur.execute(
            "INSERT INTO users (email, password_hash, plan, is_active, created_at) VALUES (?, ?, ?, ?, ?)",
            (demo_email, generate_password_hash(demo_password), "pro", 1, utc_now().isoformat())
        )
        conn.commit()

    conn.close()

def create_token(email: str) -> str:
    token = secrets.token_urlsafe(24)
    expires_at = utc_now() + timedelta(minutes=TOKEN_EXPIRY_MINUTES)

    conn = get_db()
    conn.execute(
        "INSERT INTO tokens (token, user_email, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, email, expires_at.isoformat(), utc_now().isoformat())
    )
    conn.commit()
    conn.close()
    return token

def get_token_row(token: str):
    conn = get_db()
    row = conn.execute(
        "SELECT token, user_email, expires_at FROM tokens WHERE token = ?",
        (token,)
    ).fetchone()
    conn.close()
    return row

def delete_token(token: str):
    conn = get_db()
    conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def cleanup_expired_tokens():
    conn = get_db()
    conn.execute("DELETE FROM tokens WHERE expires_at <= ?", (utc_now().isoformat(),))
    conn.commit()
    conn.close()

@app.before_request
def _cleanup_tokens():
    cleanup_expired_tokens()

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT email, password_hash, is_active FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        conn.close()

        if user and user["is_active"] == 1 and check_password_hash(user["password_hash"], password):
            session["user_email"] = email
            dashboard_token = create_token(email)
            return redirect(f"{DASHBOARD_URL}/?token={dashboard_token}")

        return render_template_string(LOGIN_PAGE, error="Invalid email or password")

    return render_template_string(LOGIN_PAGE, error=None)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template_string(SIGNUP_PAGE, error="All fields required")

        conn = sqlite3.connect("app.db")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            return render_template_string(SIGNUP_PAGE, error="User already exists")

        conn.execute(
            "INSERT INTO users (email, password_hash, plan, is_active, created_at) VALUES (?, ?, ?, ?, ?)",
            (email, generate_password_hash(password), "free", 1, utc_now().isoformat())
        )
        conn.commit()
        conn.close()

        return render_template_string(SIGNUP_PAGE, error=None, success="Account created. You can now log in.")

    return render_template_string(SIGNUP_PAGE, error=None)

@app.route("/validate-token")
def validate_token():
    token = request.args.get("token", "")
    token_row = get_token_row(token)

    if token_row:
        expires_at = datetime.fromisoformat(token_row["expires_at"])
        if utc_now() > expires_at:
            delete_token(token)
            return jsonify({"valid": False}), 401

        return jsonify({
            "valid": True,
            "email": token_row["user_email"]
        })

    return jsonify({"valid": False}), 401

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
else:
    init_db()
