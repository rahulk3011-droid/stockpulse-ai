import os
import sqlite3
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import stripe
except Exception:
    stripe = None

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me-in-env")
STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "stockpulse123")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "")
STRIPE_PREMIUM_PRICE_ID = os.getenv("STRIPE_PREMIUM_PRICE_ID", "")

if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

PLANS = {
    "free": {
        "name": "Free",
        "price": "$0",
        "features": [
            "Limited watchlists",
            "Sample signals",
            "Basic access",
        ],
    },
    "pro": {
        "name": "Pro",
        "price": "$29/mo",
        "features": [
            "Full dashboard access",
            "All industry tabs",
            "Daily opportunity brief",
        ],
    },
    "premium": {
        "name": "Premium",
        "price": "$99/mo",
        "features": [
            "Blue alerts",
            "Smart money tracker",
            "IPO radar",
        ],
    },
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT
        )
        """
    )
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


def update_user_plan(user_id: int, plan: str):
    conn = get_db()
    conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
    conn.commit()
    conn.close()


def save_stripe_refs(user_id: int, customer_id: str | None = None, subscription_id: str | None = None):
    conn = get_db()
    if customer_id is not None:
        conn.execute("UPDATE users SET stripe_customer_id = ? WHERE id = ?", (customer_id, user_id))
    if subscription_id is not None:
        conn.execute("UPDATE users SET stripe_subscription_id = ? WHERE id = ?", (subscription_id, user_id))
    conn.commit()
    conn.close()


@app.before_request
def ensure_db():
    init_db()


@app.context_processor
def inject_globals():
    return {
        "current_user": get_current_user(),
        "plans": PLANS,
    }


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
    user = get_current_user()
    return render_template("pricing.html", user=user)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/account")
@login_required
def account():
    user = get_current_user()
    streamlit_url = f"{STREAMLIT_URL}/?token={DASHBOARD_TOKEN}"
    return render_template("account.html", user=user, streamlit_url=streamlit_url)


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

        if not user or not check_password_hash(user["password_hash"], password):
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
    return render_template(
        "dashboard.html",
        user=user,
        streamlit_url=streamlit_secure_url,
        dashboard_cards=dashboard_cards,
    )


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

    # Stripe path if configured
    if stripe and STRIPE_SECRET_KEY:
        price_id = STRIPE_PRO_PRICE_ID if plan == "pro" else STRIPE_PREMIUM_PRICE_ID
        if not price_id:
            flash("Stripe price ID is missing for that plan. Using test upgrade mode instead.", "warning")
        else:
            user = get_current_user()
            try:
                checkout_session = stripe.checkout.Session.create(
                    mode="subscription",
                    line_items=[{"price": price_id, "quantity": 1}],
                    success_url=f"{APP_BASE_URL}/billing/success?plan={plan}",
                    cancel_url=f"{APP_BASE_URL}/pricing",
                    customer_email=user["email"],
                    metadata={"user_id": str(user["id"]), "plan": plan},
                )
                return redirect(checkout_session.url, code=303)
            except Exception as exc:
                flash(f"Stripe checkout could not start: {exc}", "danger")
                return redirect(url_for("pricing"))

    # Local mock upgrade for testing
    return redirect(url_for("mock_upgrade", plan=plan))


@app.route("/mock-upgrade/<plan>")
@login_required
def mock_upgrade(plan):
    if plan not in ("pro", "premium"):
        flash("Invalid plan selected.", "danger")
        return redirect(url_for("pricing"))
    update_user_plan(session["user_id"], plan)
    flash(f"Mock upgrade applied. Your plan is now {plan.capitalize()}.", "success")
    return redirect(url_for("account"))


@app.route("/billing/success")
@login_required
def billing_success():
    plan = request.args.get("plan", "pro")
    if plan not in ("pro", "premium"):
        plan = "pro"
    update_user_plan(session["user_id"], plan)
    flash(f"Payment successful. Your plan is now {plan.capitalize()}.", "success")
    return redirect(url_for("account"))


@app.route("/billing/cancel")
@login_required
def billing_cancel():
    flash("Billing action cancelled.", "warning")
    return redirect(url_for("pricing"))


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
