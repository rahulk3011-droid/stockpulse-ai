import json
import os
from datetime import datetime
from pathlib import Path

import stripe
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-later")

stripe.api_key = "sk_test_51TEjsfKiVf8bq1EtPQ6vaIqv9IbSLIqNTtwdbaknGlA4JHCldTVEHjvXEA5HNyq1gKVVqQsM8rd9K8zRtMee92TV00aG85NgiN"
endpoint_secret = "whsec_1d4c00347a857b65222a630ab0c53b68eb0cb228257b4092ce37cf12311917bb"

STREAMLIT_URL = os.getenv("STREAMLIT_URL", "http://localhost:8501")
USER_DB = Path("users.json")


def load_users():
    if USER_DB.exists():
        try:
            return json.loads(USER_DB.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_users(data):
    USER_DB.write_text(json.dumps(data, indent=2), encoding="utf-8")


def upsert_user(email, premium=None):
    users = load_users()
    user = users.get(email, {})
    user["email"] = email
    user["updated_at"] = datetime.now().isoformat()

    if "created_at" not in user:
        user["created_at"] = datetime.now().isoformat()

    if premium is not None:
        user["premium"] = premium

    users[email] = user
    save_users(users)
    return user


@app.route("/")
def home():
    email = session.get("email", "")
    users = load_users()
    user = users.get(email, {}) if email else {}
    premium = bool(user.get("premium", False))
    return render_template("index.html", email=email, premium=premium)


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()

    if not email:
        return render_template(
            "index.html",
            email="",
            premium=False,
            error="Please enter your email.",
        )

    session["email"] = email
    upsert_user(email, premium=None)
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/open-dashboard")
def open_dashboard():
    email = session.get("email", "").strip().lower()
    if not email:
        return redirect(url_for("home"))

    users = load_users()
    user = users.get(email, {})

    if not user.get("premium", False):
        return render_template(
            "index.html",
            email=email,
            premium=False,
            error="Premium access required before opening the dashboard.",
        )

    return redirect(f"{STREAMLIT_URL}/?token={email}")


@app.route("/buy-premium", methods=["POST"])
def buy_premium():
    email = session.get("email", "").strip().lower()
    if not email:
        return redirect(url_for("home"))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            customer_email=email,
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "StockPulse AI Premium",
                        },
                        "unit_amount": 2900,
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "email": email,
                "product": "stockpulse_premium",
            },
            success_url=url_for("payment_success", _external=True),
            cancel_url=url_for("payment_cancel", _external=True),
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return render_template(
            "index.html",
            email=email,
            premium=False,
            error=f"Could not start checkout: {str(e)}",
        )


@app.route("/payment-success")
def payment_success():
    email = session.get("email", "").strip().lower()
    users = load_users()
    user = users.get(email, {}) if email else {}
    premium = bool(user.get("premium", False))
    return render_template("success.html", email=email, premium=premium)


@app.route("/payment-cancel")
def payment_cancel():
    email = session.get("email", "")
    return render_template(
        "index.html",
        email=email,
        premium=False,
        error="Payment was cancelled.",
    )


@app.route("/validate-token")
def validate_token():
    token = request.args.get("token", "").strip().lower()
    users = load_users()

    if token in users and users[token].get("premium"):
        return jsonify({"valid": True, "email": token})

    return jsonify({"valid": False}), 401


@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    print("Webhook hit")
    print("Event received:", event["type"])

    if event["type"] == "checkout.session.completed":
        checkout_session = event["data"]["object"]
        email = None

        customer_details = getattr(checkout_session, "customer_details", None)
        if customer_details is not None:
            email = getattr(customer_details, "email", None)

        if not email:
            email = getattr(checkout_session, "customer_email", None)

        if not email:
            metadata = getattr(checkout_session, "metadata", None)
            if metadata is not None:
                email = metadata.get("email")

        if email:
            upsert_user(email.lower(), premium=True)
            print(f"Premium unlocked for {email}")
        else:
            print("No email found in checkout session")

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(port=5000, debug=False)