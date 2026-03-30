import os
import secrets
from datetime import datetime, timedelta
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8501")

USERS = {
    "demo@stockpulse.ai": "demo123",
    "rahul@example.com": "password123",
}

TOKENS = {}
TOKEN_EXPIRY_MINUTES = 60

LOGIN_PAGE = '''
<!doctype html>
<html>
<head>
  <title>StockPulse AI Login</title>
  <style>
    body { font-family: Arial, sans-serif; background:#0f172a; color:white; display:flex; justify-content:center; align-items:center; height:100vh; }
    .card { background:#111827; padding:32px; border-radius:16px; width:360px; box-shadow:0 10px 30px rgba(0,0,0,0.3); }
    input { width:100%; padding:12px; margin:8px 0; border-radius:8px; border:1px solid #334155; background:#0b1220; color:white; }
    button { width:100%; padding:12px; border:none; border-radius:8px; background:#2563eb; color:white; font-weight:700; cursor:pointer; }
    .error { color:#f87171; margin-bottom:10px; }
    .note { color:#94a3b8; font-size:14px; margin-top:12px; }
  </style>
</head>
<body>
  <div class="card">
    <h2>StockPulse AI</h2>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post">
      <input type="email" name="email" placeholder="Email" required>
      <input type="password" name="password" placeholder="Password" required>
      <button type="submit">Log In</button>
    </form>
    <div class="note">Demo login: demo@stockpulse.ai / demo123</div>
  </div>
</body>
</html>
'''

@app.route("/")
def home():
    return render_template_string(LOGIN_PAGE, error=None)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if USERS.get(email) == password:
            session["user_email"] = email
            dashboard_token = secrets.token_urlsafe(24)
            TOKENS[dashboard_token] = {
                "email": email,
                "expires": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
            }
            return redirect(f"{DASHBOARD_URL}/?token={dashboard_token}")

        return render_template_string(LOGIN_PAGE, error="Invalid email or password")

    return render_template_string(LOGIN_PAGE, error=None)

@app.route("/validate-token")
def validate_token():
    token = request.args.get("token", "")
    token_data = TOKENS.get(token)

    if token_data:
        if datetime.utcnow() > token_data["expires"]:
            TOKENS.pop(token, None)
            return jsonify({"valid": False}), 401

        return jsonify({
            "valid": True,
            "email": token_data["email"]
        })

    return jsonify({"valid": False}), 401

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
