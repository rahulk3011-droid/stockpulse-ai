import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8501")
DATABASE_PATH = os.getenv("DATABASE_PATH", "stockpulse.db")
TOKEN_EXPIRY_MINUTES = int(os.getenv("TOKEN_EXPIRY_MINUTES", "60"))

LOGIN_PAGE = """
<!doctype html>
<html>
<head>
  <title>StockPulse AI Login</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #0f172a;
      color: white;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: #111827;
      padding: 32px;
      border-radius: 16px;
      width: 380px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    input {
      width: 100%;
      padding: 12px;
      margin: 8px 0;
      border-radius: 8px;
      border: 1px solid #334155;
      background: #0b1220;
      color: white;
      box-sizing: border-box;
    }
    button {
      width: 100%;
      padding: 12px;
      border: none;
      border-radius: 8px;
      background: #2563eb;
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    .error { color: #f87171; margin-bottom: 10px; }
    .success { color: #86efac; margin-bottom: 10px; }
    .note { color: #94a3b8; font-size: 14px; margin-top: 12px; line-height: 1.5; }
    a { color: #93c5fd; text-decoration: none; }
  </style>
</head>
<body>
  <div class="card">
    <h2>StockPulse AI</h2>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if success %}<div class="success">{{ success }}</div>{% endif %}
    <form method="post" action="/login">
      <input type="email" name="email" placeholder="Email" required>
      <input type="password" name="password" placeholder="Password" required>
      <button type="submit">Log In</button>
    </form>
    <div class="note">
      Demo login: demo@stockpulse.ai / demo123<br>
      Need an account? <a href="/signup">Create one</a><br>
      View plans: <a href="/pricing">Pricing</a>
    </div>
  </div>
</body>
</html>
"""

SIGNUP_PAGE = """
<!doctype html>
<html>
<head>
  <title>Create StockPulse AI Account</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #0f172a;
      color: white;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: #111827;
      padding: 32px;
      border-radius: 16px;
      width: 380px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    input {
      width: 100%;
      padding: 12px;
      margin: 8px 0;
      border-radius: 8px;
      border: 1px solid #334155;
      background: #0b1220;
      color: white;
      box-sizing: border-box;
    }
    button {
      width: 100%;
      padding: 12px;
      border: none;
      border-radius: 8px;
      background: #2563eb;
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    .error { color: #f87171; margin-bottom: 10px; }
    .success { color: #86efac; margin-bottom: 10px; }
    .note { color: #94a3b8; font-size: 14px; margin-top: 12px; line-height: 1.5; }
    a { color: #93c5fd; text-decoration: none; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Create Account</h2>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if success %}<div class="success">{{ success }}</div>{% endif %}
    <form method="post" action="/signup">
      <input type="email" name="email" placeholder="Email" required>
      <input type="password" name="password" placeholder="Password (min 8 chars)" required>
      <button type="submit">Create Account</button>
    </form>
    <div class="note">
      Already have an account? <a href="/login">Log in</a>
    </div>
  </div>
</body>
</html>
"""

PRICING_PAGE = """
<!doctype html>
<html>
<head>
  <title>StockPulse AI Pricing</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #0f172a;
      color: white;
      margin: 0;
      padding: 40px 20px;
    }
    .container {
      max-width: 1100px;
      margin: 0 auto;
    }
    h1 {
      text-align: center;
      margin-bottom: 10px;
    }
    .sub {
      text-align: center;
      color: #94a3b8;
      margin-bottom: 40px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;
    }
    .card {
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 18px;
      padding: 28px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.25);
    }
    .plan {
      font-size: 26px;
      font-weight: 700;
      margin-bottom: 10px;
    }
    .price {
      font-size: 34px;
      font-weight: 700;
      margin-bottom: 8px;
    }
    .muted {
      color: #94a3b8;
      font-size: 14px;
      margin-bottom: 20px;
    }
    ul {
      padding-left: 20px;
      line-height: 1.8;
      color: #e5e7eb;
    }
    .btn {
      display: inline-block;
      margin-top: 20px;
      padding: 12px 18px;
      border-radius: 10px;
      background: #2563eb;
      color: white;
      text-decoration: none;
      font-weight: 700;
    }
    .secondary {
      background: #374151;
    }
    .topnav {
      margin-bottom: 28px;
    }
    .topnav a {
      color: #93c5fd;
      text-decoration: none;
      margin-right: 18px;
    }
    .badge {
      display: inline-block;
      font-size: 12px;
      padding: 4px 8px;
      border-radius: 999px;
      background: #1d4ed8;
      margin-left: 8px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="topnav">
      <a href="/login">Login</a>
      <a href="/signup">Signup</a>
      <a href="/account">Account</a>
    </div>

    <h1>StockPulse AI Pricing</h1>
    <div class="sub">Choose the plan that matches your investing workflow.</div>

    <div class="grid">
      <div class="card">
        <div class="plan">Free</div>
        <div class="price">$0</div>
        <div class="muted">For getting started</div>
        <ul>
          <li>Login access</li>
          <li>Basic dashboard access</li>
          <li>Core ETF tracking</li>
          <li>Limited scanner usage</li>
        </ul>
        <a class="btn secondary" href="/signup">Start Free</a>
      </div>

      <div class="card">
        <div class="plan">Pro <span class="badge">Recommended</span></div>
        <div class="price">$19/mo</div>
        <div class="muted">Payments will be connected in Stage 7C-2</div>
        <ul>
          <li>Full dashboard access</li>
          <li>Advanced scanner access</li>
          <li>Portfolio intelligence</li>
          <li>Priority future features</li>
        </ul>
        <a class="btn" href="/upgrade">Upgrade to Pro</a>
      </div>
    </div>
  </div>
</body>
</html>
"""

ACCOUNT_PAGE = """
<!doctype html>
<html>
<head>
  <title>StockPulse AI Account</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #0f172a;
      color: white;
      margin: 0;
      padding: 40px 20px;
    }
    .container {
      max-width: 720px;
      margin: 0 auto;
    }
    .card {
      background: #111827;
      border-radius: 18px;
      padding: 30px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.25);
    }
    .row {
      margin-bottom: 16px;
    }
    .label {
      color: #94a3b8;
      font-size: 14px;
      margin-bottom: 4px;
    }
    .value {
      font-size: 18px;
      font-weight: 700;
    }
    .btn {
      display: inline-block;
      margin-right: 12px;
      margin-top: 20px;
      padding: 12px 18px;
      border-radius: 10px;
      background: #2563eb;
      color: white;
      text-decoration: none;
      font-weight: 700;
    }
    .secondary {
      background: #374151;
    }
    .note {
      color: #94a3b8;
      margin-top: 20px;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h1>My Account</h1>

      <div class="row">
        <div class="label">Email</div>
        <div class="value">{{ email }}</div>
      </div>

      <div class="row">
        <div class="label">Current Plan</div>
        <div class="value">{{ plan|upper }}</div>
      </div>

      <div class="row">
        <div class="label">Account Status</div>
        <div class="value">{{ "ACTIVE" if is_active else "INACTIVE" }}</div>
      </div>

      <a class="btn" href="/pricing">View Plans</a>
      <a class="btn secondary" href="/logout">Logout</a>

      <div class="note">
        Stripe checkout and automatic plan upgrades are coming in Stage 7C-2.
      </div>
    </div>
  </div>
</body>
</html>
"""

UPGRADE_PAGE = """
<!doctype html>
<html>
<head>
  <title>Upgrade Coming Soon</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #0f172a;
      color: white;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: #111827;
      padding: 32px;
      border-radius: 16px;
      width: 420px;
      text-align: center;
      box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    a {
      color: #93c5fd;
      text-decoration: none;
    }
  </style>
</head>
<body>
  <div class="card">
    <h2>Upgrade to Pro</h2>
    <p>Stripe checkout will be connected in Stage 7C-2.</p>
    <p><a href="/pricing">Back to Pricing</a></p>
  </div>
</body>
</html>
"""

LOCKED_PAGE = """
<!doctype html>
<html>
<head>
  <title>Pro Plan Required</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #0f172a;
      color: white;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: #111827;
      padding: 32px;
      border-radius: 16px;
      width: 420px;
      text-align: center;
      box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    a {
      color: #93c5fd;
      text-decoration: none;
    }
  </style>
</head>
<body>
  <div class="card">
    <h2>Pro Plan Required</h2>
    <p>This feature is available on the Pro plan.</p>
    <p><a href="/pricing">View Pricing</a></p>
  </div>
</body>
</html>
"""


def utc_now():
    return datetime.now(timezone.utc)


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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

    existing = cur.execute(
        "SELECT id FROM users WHERE email = ?",
        (demo_email,)
    ).fetchone()

    if not existing:
        cur.execute(
            "INSERT INTO users (email, password_hash, plan, is_active, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                demo_email,
                generate_password_hash(demo_password),
                "pro",
                1,
                utc_now().isoformat(),
            ),
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
    conn.execute(
        "DELETE FROM tokens WHERE expires_at <= ?",
        (utc_now().isoformat(),)
    )
    conn.commit()
    conn.close()


def get_current_user():
    email = session.get("user_email")
    if not email:
        return None

    conn = get_db()
    user = conn.execute(
        "SELECT email, plan, is_active, created_at FROM users WHERE email = ?",
        (email,)
    ).fetchone()
    conn.close()
    return user


def login_required(route_func):
    @wraps(route_func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("login"))
        return route_func(*args, **kwargs)
    return wrapper


def pro_required(route_func):
    @wraps(route_func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect(url_for("login"))
        if user["plan"] != "pro":
            return render_template_string(LOCKED_PAGE)
        return route_func(*args, **kwargs)
    return wrapper


@app.before_request
def before_request_cleanup():
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

        return render_template_string(LOGIN_PAGE, error="Invalid email or password", success=None)

    return render_template_string(LOGIN_PAGE, error=None, success=None)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or "@" not in email:
            return render_template_string(
                SIGNUP_PAGE,
                error="Please enter a valid email",
                success=None
            )

        if len(password) < 8:
            return render_template_string(
                SIGNUP_PAGE,
                error="Password must be at least 8 characters",
                success=None
            )

        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:
            conn.close()
            return render_template_string(
                SIGNUP_PAGE,
                error="An account already exists for this email",
                success=None
            )

        conn.execute(
            "INSERT INTO users (email, password_hash, plan, is_active, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                email,
                generate_password_hash(password),
                "free",
                1,
                utc_now().isoformat()
            )
        )
        conn.commit()
        conn.close()

        return render_template_string(
            SIGNUP_PAGE,
            error=None,
            success="Account created. You can now log in."
        )

    return render_template_string(SIGNUP_PAGE, error=None, success=None)


@app.route("/pricing")
def pricing():
    return render_template_string(PRICING_PAGE)


@app.route("/account")
@login_required
def account():
    user = get_current_user()
    return render_template_string(
        ACCOUNT_PAGE,
        email=user["email"],
        plan=user["plan"],
        is_active=bool(user["is_active"])
    )


@app.route("/upgrade")
@login_required
def upgrade():
    return render_template_string(UPGRADE_PAGE)


@app.route("/pro-demo")
@pro_required
def pro_demo():
    return "<h1>Pro feature unlocked</h1><p>This is a placeholder gated feature.</p>"


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


init_db()

if __name__ == "__main__":
    app.run(debug=True)
