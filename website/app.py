import os
import sqlite3
from functools import wraps
from pathlib import Path

import stripe
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"

app = Flask(__name__)

PLANS = {
    "free": {"price": 0, "features": ["Limited dashboard", "Sample alerts", "Basic watchlists"]},
    "pro": {"price": 29, "features": ["Full dashboard", "Industry tabs", "Daily opportunity brief"]},
    "premium": {"price": 99, "features": ["Blue alerts", "Smart money tracker", "IPO radar"]},
}

app.secret_key = os.getenv("SECRET_KEY", "change-me-in-env")
STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "stockpulse123")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "")
STRIPE_PREMIUM_PRICE_ID = os.getenv("STRIPE_PREMIUM_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

stripe.api_key = STRIPE_SECRET_KEY

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free'
        )
    """)
    cols = [row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "stripe_customer_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    if "stripe_subscription_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT")
    conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def paid_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        if user["plan"] not in ("pro", "premium"):
            flash("Upgrade required to access the full dashboard.", "warning")
            return redirect(url_for("pricing"))
        return fn(*args, **kwargs)
    return wrapper

def get_current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute(
        "SELECT id, email, plan, stripe_customer_id, stripe_subscription_id FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()
    return user

def update_user_plan(user_id, plan, customer_id=None, subscription_id=None):
    conn = get_db()
    if customer_id is not None and subscription_id is not None:
        conn.execute(
            "UPDATE users SET plan = ?, stripe_customer_id = ?, stripe_subscription_id = ? WHERE id = ?",
            (plan, customer_id, subscription_id, user_id),
        )
    else:
        conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
    conn.commit()
    conn.close()

@app.before_request
def ensure_db():
    init_db()

@app.context_processor
def inject_globals():
    return {"current_user": get_current_user()}

@app.route("/")
def home():
    sample_alerts = [
        {"ticker": "PLTR", "signal": "🟢 Buy Zone", "reason": "AI / software strength"},
        {"ticker": "RKLB", "signal": "🔵 Watch Closely", "reason": "space trend + momentum"},
        {"ticker": "BRN.AX", "signal": "🟡 Wait", "reason": "speculative AI chip setup"},
    ]
    faqs = [
        {"q": "What do I get with Pro?", "a": "Full dashboard access, industry tabs, and daily opportunity workflow."},
        {"q": "Is this personal financial advice?", "a": "No. The platform is designed for general market research and educational use."},
        {"q": "Can I upgrade later?", "a": "Yes. Start free, then upgrade when you want deeper access."},
    ]
    return render_template("home.html", sample_alerts=sample_alerts, faqs=faqs)

@app.route("/pricing")
def pricing():
    return render_template("pricing.html", user=get_current_user(), plans=PLANS)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/account")
@login_required
def account():
    return render_template("account.html", user=get_current_user(), streamlit_url=f"{STREAMLIT_URL}/?token={DASHBOARD_TOKEN}")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/risk-disclaimer")
def risk_disclaimer():
    return render_template("risk_disclaimer.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("signup.html")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("signup.html")
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, plan) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), "free"),
            )
            conn.commit()
            session["user_id"] = cur.lastrowid
            flash("Account created successfully.", "success")
            return redirect(url_for("pricing"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "danger")
            return render_template("signup.html")
        finally:
            conn.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute(
            "SELECT id, email, password_hash, plan FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        conn.close()
        if not user:
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        if not user["password_hash"] or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        session["user_id"] = user["id"]
        flash("Logged in successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    if user["plan"] == "free":
        return render_template("dashboard_locked.html", user=user)
    streamlit_secure_url = f"{STREAMLIT_URL}/?token={DASHBOARD_TOKEN}"
    dashboard_cards = [
        {"title": "Best Picks", "body": "See strongest opportunities first."},
        {"title": "Industries", "body": "AI, chips, biotech, space, energy, crypto."},
        {"title": "Portfolio", "body": "Track holdings, value, and signals."},
    ]
    return render_template("dashboard.html", user=user, streamlit_url=streamlit_secure_url, dashboard_cards=dashboard_cards)

@app.route("/go-to-dashboard")
@paid_required
def go_to_dashboard():
    return redirect(f"{STREAMLIT_URL}/?token={DASHBOARD_TOKEN}")

@app.route("/upgrade/<plan>")
@login_required
def upgrade(plan):
    if plan not in ("pro", "premium"):
        flash("Invalid plan selected.", "danger")
        return redirect(url_for("pricing"))
    price_id = STRIPE_PRO_PRICE_ID if plan == "pro" else STRIPE_PREMIUM_PRICE_ID
    if not STRIPE_SECRET_KEY or not price_id:
        flash("Stripe is not configured yet. Add your Stripe keys and price IDs.", "danger")
        return redirect(url_for("pricing"))
    user = get_current_user()
    try:
        checkout_session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{APP_BASE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{APP_BASE_URL}/billing/cancel",
            customer_email=user["email"],
            metadata={"user_id": str(user["id"]), "plan": plan},
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        flash(f"Stripe checkout error: {str(e)}", "danger")
        return redirect(url_for("pricing"))

@app.route("/billing/success")
@login_required
def billing_success():
    session_id = request.args.get("session_id")
    if not session_id:
        flash("Missing checkout session.", "danger")
        return redirect(url_for("pricing"))
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        metadata = checkout_session.get("metadata", {})
        plan = metadata.get("plan", "free")
        user_id = metadata.get("user_id")
        customer_id = checkout_session.get("customer")
        subscription_id = checkout_session.get("subscription")
        if not user_id:
            flash("Could not verify payment session.", "danger")
            return redirect(url_for("pricing"))
        update_user_plan(int(user_id), plan, customer_id=customer_id, subscription_id=subscription_id)
        flash(f"Payment successful. Your plan is now {plan.capitalize()}.", "success")
        return redirect(url_for("account"))
    except Exception as e:
        flash(f"Could not verify Stripe payment: {str(e)}", "danger")
        return redirect(url_for("pricing"))

@app.route("/billing/cancel")
@login_required
def billing_cancel():
    flash("Checkout cancelled.", "warning")
    return redirect(url_for("pricing"))

@app.route("/billing/portal")
@login_required
def billing_portal():
    user = get_current_user()
    if not STRIPE_SECRET_KEY:
        flash("Stripe is not configured yet.", "danger")
        return redirect(url_for("account"))
    if not user["stripe_customer_id"]:
        flash("No Stripe customer found for this account yet.", "warning")
        return redirect(url_for("account"))
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=user["stripe_customer_id"],
            return_url=url_for("account", _external=True),
        )
        return redirect(portal_session.url, code=303)
    except Exception as e:
        flash(f"Could not open billing portal: {str(e)}", "danger")
        return redirect(url_for("account"))

@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    if not STRIPE_WEBHOOK_SECRET:
        return "Webhook secret not configured", 400
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception:
        return "Invalid webhook", 400
    event_type = event["type"]
    data_object = event["data"]["object"]
    if event_type == "checkout.session.completed":
        metadata = data_object.get("metadata", {})
        user_id = metadata.get("user_id")
        plan = metadata.get("plan", "free")
        customer_id = data_object.get("customer")
        subscription_id = data_object.get("subscription")
        if user_id:
            update_user_plan(int(user_id), plan, customer_id=customer_id, subscription_id=subscription_id)
    elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        subscription_id = data_object.get("id")
        status = data_object.get("status", "")
        customer_id = data_object.get("customer")
        conn = get_db()
        user = conn.execute(
            "SELECT id FROM users WHERE stripe_subscription_id = ? OR stripe_customer_id = ?",
            (subscription_id, customer_id),
        ).fetchone()
        if user:
            new_plan = "free" if status in ("canceled", "unpaid", "incomplete_expired") else None
            if new_plan:
                conn.execute(
                    "UPDATE users SET plan = ?, stripe_subscription_id = ?, stripe_customer_id = ? WHERE id = ?",
                    (new_plan, None, customer_id, user["id"]),
                )
                conn.commit()
        conn.close()
    return "OK", 200

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
