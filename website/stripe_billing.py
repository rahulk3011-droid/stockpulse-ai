import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps

import stripe
from flask import Blueprint, redirect, render_template, request, session

billing_bp = Blueprint("billing", __name__, template_folder="templates")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

PRICE_MAP = {
    "pro_monthly": os.getenv("STRIPE_PRICE_PRO_MONTHLY", ""),
    "premium_monthly": os.getenv("STRIPE_PRICE_PREMIUM_MONTHLY", ""),
}

PRICE_TO_PLAN = {
    os.getenv("STRIPE_PRICE_PRO_MONTHLY", ""): "pro",
    os.getenv("STRIPE_PRICE_PREMIUM_MONTHLY", ""): "premium",
}


def get_db_path():
    return os.getenv("DATABASE_PATH", r"C:\Users\rahul\Desktop\website\stockpulse.db")


def get_conn():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_email" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


def get_user_by_email(email):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email.lower().strip(),)
    ).fetchone()
    conn.close()
    return row


def get_user_by_customer_id(customer_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE stripe_customer_id = ?",
        (customer_id,)
    ).fetchone()
    conn.close()
    return row


def get_or_create_customer(user_row):
    conn = get_conn()

    if user_row["stripe_customer_id"]:
        conn.close()
        return user_row["stripe_customer_id"]

    customer = stripe.Customer.create(email=user_row["email"])

    conn.execute(
        "UPDATE users SET stripe_customer_id = ? WHERE email = ?",
        (customer.id, user_row["email"])
    )
    conn.commit()
    conn.close()
    return customer.id


def unix_to_iso(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def update_user_subscription_by_customer(customer_id, subscription_obj):
    if not customer_id:
        return

    items = subscription_obj.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None
    plan = PRICE_TO_PLAN.get(price_id, "free")

    status = subscription_obj.get("status", "inactive")
    current_period_end = unix_to_iso(subscription_obj.get("current_period_end"))
    subscription_id = subscription_obj.get("id")

    is_active = 1 if status in {"active", "trialing"} else 0

    conn = get_conn()
    conn.execute(
        """
        UPDATE users
        SET plan = ?,
            is_active = ?,
            billing_status = ?,
            stripe_subscription_id = ?,
            stripe_price_id = ?,
            current_period_end = ?
        WHERE stripe_customer_id = ?
        """,
        (
            plan,
            is_active,
            status,
            subscription_id,
            price_id,
            current_period_end,
            customer_id,
        ),
    )
    conn.commit()
    conn.close()


def deactivate_user_by_customer(customer_id):
    if not customer_id:
        return

    conn = get_conn()
    conn.execute(
        """
        UPDATE users
        SET plan = 'free',
            is_active = 1,
            billing_status = 'canceled',
            stripe_subscription_id = NULL,
            stripe_price_id = NULL,
            current_period_end = NULL
        WHERE stripe_customer_id = ?
        """,
        (customer_id,),
    )
    conn.commit()
    conn.close()


@billing_bp.route("/pricing")
def pricing():
    return render_template("pricing.html")


@billing_bp.route("/billing/create-checkout-session", methods=["POST"])
@require_login
def create_checkout_session():
    plan = request.form.get("plan", "").strip()

    if plan not in PRICE_MAP or not PRICE_MAP[plan]:
        return "Invalid plan", 400

    user_email = session["user_email"]
    user_row = get_user_by_email(user_email)

    if not user_row:
        return "User not found", 404

    customer_id = get_or_create_customer(user_row)

    checkout_session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{
            "price": PRICE_MAP[plan],
            "quantity": 1,
        }],
        success_url=f"{APP_BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{APP_BASE_URL}/pricing",
        metadata={
            "user_email": user_email,
            "selected_plan_key": plan,
        },
    )

    return redirect(checkout_session.url, code=303)


@billing_bp.route("/billing/portal", methods=["GET", "POST"])
@require_login
def billing_portal():
    user_email = session["user_email"]
    user_row = get_user_by_email(user_email)

    if not user_row:
        return "User not found", 404

    customer_id = user_row["stripe_customer_id"]

    if not customer_id:
        return "No Stripe customer found yet. Please subscribe first.", 400

    portal = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{APP_BASE_URL}/account"
    )
    return redirect(portal.url, code=303)


@billing_bp.route("/success")
@require_login
def billing_success():
    return render_template("billing_success.html")


@billing_bp.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    if not WEBHOOK_SECRET:
        return "Missing STRIPE_WEBHOOK_SECRET", 500

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=WEBHOOK_SECRET,
        )
    except ValueError:
        return "Invalid payload", 400
    except stripe.error.SignatureVerificationError:
        return "Invalid signature", 400

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        customer_id = data_object.get("customer")
        subscription_id = data_object.get("subscription")

        if customer_id and subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            update_user_subscription_by_customer(customer_id, subscription)

    elif event_type == "customer.subscription.created":
        customer_id = data_object.get("customer")
        update_user_subscription_by_customer(customer_id, data_object)

    elif event_type == "customer.subscription.updated":
        customer_id = data_object.get("customer")
        update_user_subscription_by_customer(customer_id, data_object)

    elif event_type == "customer.subscription.deleted":
        customer_id = data_object.get("customer")
        deactivate_user_by_customer(customer_id)

    elif event_type == "invoice.payment_failed":
        customer_id = data_object.get("customer")
        if customer_id:
            conn = get_conn()
            conn.execute(
                """
                UPDATE users
                SET billing_status = 'past_due'
                WHERE stripe_customer_id = ?
                """,
                (customer_id,),
            )
            conn.commit()
            conn.close()

    return "", 200