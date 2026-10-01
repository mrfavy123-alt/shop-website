#!/usr/bin/env python3
"""Small standard-library backend for the Zamac Füds demo shop."""
import json
import os
import re
import sqlite3
import hashlib
import hmac
import secrets
from datetime import date, datetime, timezone
import urllib.parse
import urllib.error
import urllib.request
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("ZAMAC_DB_PATH", ROOT / "zamac_fuds.sqlite3"))


def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


@contextmanager
def db_session():
    db = connect_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def send_confirmation(to_email, customer_name, order_id, total_minor, items):
    domain = os.environ.get("MAILGUN_DOMAIN")
    api_key = os.environ.get("MAILGUN_API_KEY")
    sender = os.environ.get("MAILGUN_FROM", f"Zamac Füds <orders@{domain}>" if domain else "")
    if not (domain and api_key and sender):
        return False
    item_lines = "\n".join(f"• {item['quantity']} × {item['product_name']} — ₦{item['quantity'] * item['unit_price_minor'] / 100:,.0f}" for item in items)
    body = (f"Hi {customer_name},\n\nThanks for your order #{order_id}!\n\n{item_lines}\n\n"
            f"Total: ₦{total_minor / 100:,.0f}\n\nWe’ll be in touch when your food is on its way.\n\nZamac Füds")
    payload = urllib.parse.urlencode({
        "from": sender,
        "to": to_email,
        "subject": f"Your Zamac Füds order #{order_id} is confirmed",
        "text": body,
    }).encode()
    request = urllib.request.Request(
        f"https://api.mailgun.net/v3/{domain}/messages",
        data=payload,
        headers={"Authorization": "Basic " + __import__("base64").b64encode(f"api:{api_key}".encode()).decode()},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return 200 <= response.status < 300
    except Exception as exc:
        print(f"Mailgun confirmation failed for order {order_id}: {exc}")
        return False


def supabase_settings():
    public_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return (os.environ.get("SUPABASE_URL", "").rstrip("/"), public_key, secret_key)


def supabase_request(method, path, payload=None, token=None):
    url, anon_key, service_key = supabase_settings()
    key = service_key if path.startswith("/rest/v1/") else anon_key
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"apikey": key, "Content-Type": "application/json", "Prefer": "return=representation"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif not (path.startswith("/rest/v1/") and service_key.startswith("sb_secret_")):
        # Legacy service-role keys are JWTs; the newer secret keys belong only in apikey.
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        if path.startswith("/auth/v1/user") and exc.code in (401, 403):
            raise PermissionError("Your Google session expired. Sign in again.") from exc
        raise RuntimeError(f"Supabase request failed ({exc.code}): {detail[:500]}") from exc


def create_supabase_order(payload, access_token):
    url, anon_key, service_key = supabase_settings()
    if not (url and anon_key and service_key):
        raise RuntimeError("Supabase is not configured")
    user = supabase_request("GET", "/auth/v1/user", token=access_token)
    email = str(user.get("email", "")).strip().lower()
    user_id = user.get("id")
    if not email or not user_id:
        raise PermissionError("Google sign-in is required")
    name = str(payload.get("name") or user.get("user_metadata", {}).get("full_name") or user.get("user_metadata", {}).get("name") or email.split("@")[0]).strip()
    address = str(payload.get("address", "")).strip()
    lines = payload.get("items")
    if not name or len(name) > 120:
        raise ValueError("Enter your name.")
    if not address or len(address) > 500:
        raise ValueError("Enter a delivery address.")
    if not isinstance(lines, list) or not lines or len(lines) > 50:
        raise ValueError("Your basket is empty.")
    quantities = {}
    for line in lines:
        product_id, quantity = int(line["id"]), int(line["qty"])
        if product_id <= 0 or quantity <= 0 or quantity > 100:
            raise ValueError("Invalid cart item")
        quantities[product_id] = quantities.get(product_id, 0) + quantity
    rpc = supabase_request("POST", "/rest/v1/rpc/create_order", {
        "p_user_id": user_id,
        "p_name": name,
        "p_email": email,
        "p_address": address,
        "p_items": [{"id": pid, "qty": qty} for pid, qty in quantities.items()],
    })
    result = rpc[0] if isinstance(rpc, list) else rpc
    if not result or not result.get("id"):
        raise RuntimeError("Supabase did not return the saved order")
    order_id, total_minor = result["id"], int(result["total_minor"])
    # The RPC has committed the order before any external email request is made.
    items = supabase_request("GET", f"/rest/v1/order_items?select=product_name,unit_price_minor,quantity&order_id=eq.{order_id}")
    email_sent = send_confirmation(email, name, order_id, total_minor, items or [])
    try:
        supabase_request("PATCH", f"/rest/v1/orders?id=eq.{order_id}", {"confirmation_email_status": "sent" if email_sent else "failed"})
    except Exception as exc:
        # The committed order must still be reported as successful if status logging fails.
        print(f"Could not update email status for order {order_id}: {exc}")
    return {"orderId": order_id, "total": total_minor, "emailSent": email_sent, "customerName": name, "email": email}


def paystack_request(method, path, payload=None):
    secret = os.environ.get("PAYSTACK_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("Paystack payments are not configured")
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        "https://api.paystack.co" + path,
        data=data,
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.loads(response.read())
    if not result.get("status"):
        raise RuntimeError(result.get("message", "Payment provider rejected the request"))
    return result.get("data", {})


def initialize_training_payment(enrollment_id, installment_number, payment_token, request_host):
    if installment_number not in (1, 2):
        raise ValueError("Choose a valid instalment.")
    token_hash = hashlib.sha256(payment_token.encode()).hexdigest()
    url, anon_key, service_key = supabase_settings()
    if url and anon_key and service_key:
        enrollments = supabase_request("GET", f"/rest/v1/training_enrollments?select=id,email,payment_token_hash&id=eq.{enrollment_id}")
        payments = supabase_request("GET", f"/rest/v1/training_payments?select=id,amount_minor,status&enrollment_id=eq.{enrollment_id}&installment_number=eq.{installment_number}")
        if not enrollments or not payments or not hmac.compare_digest(enrollments[0]["payment_token_hash"], token_hash):
            raise PermissionError("That training payment link is invalid.")
        enrollment, payment = enrollments[0], payments[0]
        pay_id, amount, status, email = payment["id"], int(payment["amount_minor"]), payment["status"], enrollment["email"]
        patch_payment = lambda values: supabase_request("PATCH", f"/rest/v1/training_payments?id=eq.{pay_id}", values)
    else:
        with db_session() as db:
            enrollment = db.execute("SELECT id,email,payment_token_hash FROM training_enrollments WHERE id=?", (enrollment_id,)).fetchone()
            payment = db.execute("SELECT id,amount_minor,status FROM training_payments WHERE enrollment_id=? AND installment_number=?", (enrollment_id, installment_number)).fetchone()
            if not enrollment or not payment or not hmac.compare_digest(enrollment["payment_token_hash"], token_hash):
                raise PermissionError("That training payment link is invalid.")
            pay_id, amount, status, email = payment["id"], payment["amount_minor"], payment["status"], enrollment["email"]
    if status == "paid":
        raise ValueError("This instalment has already been paid.")
    reference = "zamac-" + secrets.token_urlsafe(20)
    base_url = os.environ.get("PUBLIC_BASE_URL", f"http://{request_host}").rstrip("/")
    callback_url = os.environ.get("PAYSTACK_CALLBACK_URL", base_url + "/?training_payment=verify")
    transaction = paystack_request("POST", "/transaction/initialize", {
        "email": email,
        "amount": str(amount),
        "currency": "NGN",
        "reference": reference,
        "callback_url": callback_url,
        "metadata": {"enrollment_id": int(enrollment_id), "installment_number": installment_number},
    })
    if not transaction.get("authorization_url") or transaction.get("reference") != reference:
        raise RuntimeError("The payment page could not be created.")
    if url and anon_key and service_key:
        patch_payment({"status": "pending", "payment_reference": reference})
    else:
        with db_session() as db:
            db.execute("UPDATE training_payments SET status='pending', payment_reference=? WHERE id=?", (reference, pay_id))
    return {"authorizationUrl": transaction["authorization_url"], "reference": reference}


def verify_training_payment(reference, payment_token):
    if not reference or len(reference) > 120 or not payment_token:
        raise ValueError("The payment reference is missing.")
    token_hash = hashlib.sha256(payment_token.encode()).hexdigest()
    url, anon_key, service_key = supabase_settings()
    if url and anon_key and service_key:
        payments = supabase_request("GET", f"/rest/v1/training_payments?select=id,enrollment_id,installment_number,amount_minor,status,payment_reference&payment_reference=eq.{urllib.parse.quote(reference)}")
        if not payments:
            raise PermissionError("That payment reference was not found.")
        payment = payments[0]
        enrollments = supabase_request("GET", f"/rest/v1/training_enrollments?select=id,payment_token_hash&id=eq.{payment['enrollment_id']}")
        if not enrollments or not hmac.compare_digest(enrollments[0]["payment_token_hash"], token_hash):
            raise PermissionError("That training payment link is invalid.")
        update_payment = lambda values: supabase_request("PATCH", f"/rest/v1/training_payments?id=eq.{payment['id']}", values)
        update_enrollment = lambda status: supabase_request("PATCH", f"/rest/v1/training_enrollments?id=eq.{payment['enrollment_id']}", {"status": status})
    else:
        with db_session() as db:
            row = db.execute("SELECT p.*,e.payment_token_hash FROM training_payments p JOIN training_enrollments e ON e.id=p.enrollment_id WHERE p.payment_reference=?", (reference,)).fetchone()
            if not row:
                raise PermissionError("That payment reference was not found.")
            payment = dict(row)
            if not hmac.compare_digest(payment["payment_token_hash"], token_hash):
                raise PermissionError("That training payment link is invalid.")
        update_payment = lambda values: _update_local_payment(payment["id"], values)
        update_enrollment = lambda status: _update_local_enrollment(payment["enrollment_id"], status)
    if payment["status"] != "paid":
        verified = paystack_request("GET", "/transaction/verify/" + urllib.parse.quote(reference, safe=""))
        if verified.get("status") != "success" or int(verified.get("amount", -1)) != int(payment["amount_minor"]) or verified.get("currency") != "NGN" or verified.get("reference") != reference:
            return {"paid": False, "enrollmentId": payment["enrollment_id"], "installment": payment["installment_number"], "message": "Payment has not been confirmed. You can try again."}
        update_payment({"status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()})
        next_payment_status = None
        if url:
            rows = supabase_request("GET", f"/rest/v1/training_payments?select=status&enrollment_id=eq.{payment['enrollment_id']}&installment_number=eq.2")
            next_payment_status = rows[0]["status"] if rows else None
        else:
            with db_session() as db:
                row = db.execute("SELECT status FROM training_payments WHERE enrollment_id=? AND installment_number=2", (payment["enrollment_id"],)).fetchone()
                next_payment_status = row["status"] if row else None
        update_enrollment("paid" if payment["installment_number"] == 2 else "part_paid")
    else:
        next_payment_status = None
    next_amount = 0
    if payment["installment_number"] == 1:
        if url:
            rows = supabase_request("GET", f"/rest/v1/training_payments?select=amount_minor,status&enrollment_id=eq.{payment['enrollment_id']}&installment_number=eq.2")
            if rows and rows[0]["status"] != "paid": next_amount = int(rows[0]["amount_minor"])
        else:
            with db_session() as db:
                row = db.execute("SELECT amount_minor,status FROM training_payments WHERE enrollment_id=? AND installment_number=2", (payment["enrollment_id"],)).fetchone()
                if row and row["status"] != "paid": next_amount = int(row["amount_minor"])
    return {"paid": True, "enrollmentId": payment["enrollment_id"], "installment": payment["installment_number"], "nextAmount": next_amount}


def _update_local_payment(payment_id, values):
    with db_session() as db:
        paid_at = date.today().isoformat() if values.get("paid_at") else None
        if paid_at:
            db.execute("UPDATE training_payments SET status=?,paid_at=? WHERE id=?", (values["status"], paid_at, payment_id))
        else:
            db.execute("UPDATE training_payments SET status=?,payment_reference=? WHERE id=?", (values["status"], values["payment_reference"], payment_id))


def _update_local_enrollment(enrollment_id, status):
    with db_session() as db:
        db.execute("UPDATE training_enrollments SET status=? WHERE id=?", (status, enrollment_id))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def json_response(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/api/config":
            url, anon_key, service_key = supabase_settings()
            return self.json_response(200, {"supabaseUrl": url, "supabaseAnonKey": anon_key, "authEnabled": bool(url and anon_key and service_key), "paymentsEnabled": bool(os.environ.get("PAYSTACK_SECRET_KEY"))})
        if self.path == "/api/products":
            url, anon_key, service_key = supabase_settings()
            if url and anon_key and service_key:
                try:
                    products = supabase_request("GET", "/rest/v1/products?select=id,name,category,description,size,badge,image_url,price_minor&active=eq.true&order=id.asc")
                    return self.json_response(200, products or [])
                except Exception as exc:
                    print(f"Menu load error: {exc}")
                    return self.json_response(503, {"error": "Menu is temporarily unavailable."})
            return self.json_response(404, {"error": "Supabase menu is not configured"})
        return super().do_GET()

    def do_POST(self):
        route = self.path.split("?", 1)[0]
        allowed_routes = {"/api/checkout", "/api/bookings", "/api/contact", "/api/training-enrollments", "/api/training-payments/initialize", "/api/training-payments/verify"}
        if route not in allowed_routes:
            return self.json_response(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 32_000:
                return self.json_response(413, {"error": "Checkout request is too large"})
            payload = json.loads(self.rfile.read(length))
            url, anon_key, service_key = supabase_settings()
            if route == "/api/training-payments/initialize":
                if (url or anon_key or service_key) and not (url and anon_key and service_key):
                    return self.json_response(503, {"error": "Supabase setup is incomplete."})
                enrollment_id = int(payload.get("enrollmentId", 0))
                installment = int(payload.get("installmentNumber", 0))
                payment_token = str(payload.get("paymentToken", ""))
                if enrollment_id <= 0 or not payment_token:
                    return self.json_response(400, {"error": "The training payment details are incomplete."})
                payment = initialize_training_payment(enrollment_id, installment, payment_token, self.headers.get("Host", "localhost:8000"))
                return self.json_response(200, payment)
            if route == "/api/training-payments/verify":
                result = verify_training_payment(str(payload.get("reference", "")), str(payload.get("paymentToken", "")))
                return self.json_response(200, result)
            if route != "/api/checkout":
                if url or anon_key or service_key:
                    if not (url and anon_key and service_key):
                        return self.json_response(503, {"error": "Supabase setup is incomplete. Check the server environment."})
                name = str(payload.get("name", "")).strip()
                email = str(payload.get("email", "")).strip().lower()
                if not name or len(name) > 120 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
                    return self.json_response(400, {"error": "Enter a valid name and email address."})
                if route == "/api/bookings":
                    phone = str(payload.get("phone", "")).strip()
                    occasion = str(payload.get("occasion", "")).strip()
                    event_date = str(payload.get("event_date", "")).strip()
                    guest_count = int(payload.get("guest_count", 0))
                    small_chops = str(payload.get("small_chops", "")).strip()
                    notes = str(payload.get("notes", "")).strip()
                    budget = str(payload.get("budget", "")).strip()
                    allowed_occasions = {"Birthday", "Wedding", "Naming ceremony", "Graduation", "Corporate event", "Other celebration"}
                    if len(phone) < 7 or len(phone) > 40 or occasion not in allowed_occasions or len(small_chops) > 160 or len(notes) > 1500 or len(budget) > 100 or not small_chops:
                        return self.json_response(400, {"error": "Please check your booking details."})
                    if budget:
                        notes = f"Budget: {budget}" + (f"\n{notes}" if notes else "")
                    if guest_count < 5 or guest_count > 2000:
                        return self.json_response(400, {"error": "Bookings are for 5 to 2,000 guests."})
                    parsed_date = date.fromisoformat(event_date)
                    if parsed_date < date.today():
                        return self.json_response(400, {"error": "Choose a future event date."})
                    booking = {"name": name, "email": email, "phone": phone, "occasion": occasion, "event_date": event_date, "guest_count": guest_count, "small_chops": small_chops, "notes": notes}
                    if url:
                        saved = supabase_request("POST", "/rest/v1/bookings", booking)
                        booking_id = saved[0]["id"]
                    else:
                        with db_session() as db:
                            cursor = db.execute("INSERT INTO bookings (name,email,phone,occasion,event_date,guest_count,small_chops,notes) VALUES (?,?,?,?,?,?,?,?)", tuple(booking.values()))
                            booking_id = cursor.lastrowid
                    return self.json_response(201, {"id": booking_id, "message": "Booking request received. We’ll contact you to confirm availability and pricing."})
                if route == "/api/contact":
                    topic = str(payload.get("topic", "General enquiry")).strip()[:80]
                    message = str(payload.get("message", "")).strip()
                    if not message or len(message) > 2000:
                        return self.json_response(400, {"error": "Write a message of up to 2,000 characters."})
                    contact = {"name": name, "email": email, "topic": topic, "message": message}
                    if url:
                        saved = supabase_request("POST", "/rest/v1/contact_messages", contact)
                        message_id = saved[0]["id"]
                    else:
                        with db_session() as db:
                            cursor = db.execute("INSERT INTO contact_messages (name,email,topic,message) VALUES (?,?,?,?)", tuple(contact.values()))
                            message_id = cursor.lastrowid
                    return self.json_response(201, {"id": message_id, "message": "Thanks for writing. Your message is with our team."})
                program_code = str(payload.get("program", "")).strip()
                phone = str(payload.get("phone", "")).strip()
                if program_code not in {"chef", "nutrition"} or len(phone) < 7 or len(phone) > 40:
                    return self.json_response(400, {"error": "Choose a course and enter a valid phone number."})
                if url:
                    payment_token = secrets.token_urlsafe(32)
                    result = supabase_request("POST", "/rest/v1/rpc/create_training_enrollment", {"p_program_code": program_code, "p_name": name, "p_email": email, "p_phone": phone, "p_payment_token_hash": hashlib.sha256(payment_token.encode()).hexdigest()})
                    result = result[0] if isinstance(result, list) else result
                    return self.json_response(201, {"id": result["enrollment_id"], "firstPayment": result["first_payment_minor"], "balance": result["balance_minor"], "total": result["total_minor"], "paymentToken": payment_token})
                payment_token = secrets.token_urlsafe(32)
                with db_session() as db:
                    program = db.execute("SELECT id, course_fee_minor, materials_fee_minor FROM training_programs WHERE code = ? AND active = 1", (program_code,)).fetchone()
                    if program is None:
                        return self.json_response(400, {"error": "That training course is not available."})
                    total = program["course_fee_minor"] + program["materials_fee_minor"]
                    first = (total + 1) // 2
                    balance = total - first
                    cursor = db.execute("INSERT INTO training_enrollments (program_id,name,email,phone,payment_token_hash,total_minor,installment_count) VALUES (?,?,?,?,?,?,2)", (program["id"], name, email, phone, hashlib.sha256(payment_token.encode()).hexdigest(), total))
                    enrollment_id = cursor.lastrowid
                    db.executemany("INSERT INTO training_payments (enrollment_id,installment_number,amount_minor,due_note) VALUES (?,?,?,?)", [(enrollment_id, 1, first, "Due after your training place is confirmed"), (enrollment_id, 2, balance, "Balance due before the course midpoint")])
                return self.json_response(201, {"id": enrollment_id, "firstPayment": first, "balance": balance, "total": total, "paymentToken": payment_token})
            if url and anon_key and service_key:
                authorization = self.headers.get("Authorization", "")
                if not authorization.startswith("Bearer "):
                    return self.json_response(401, {"error": "Sign in with Google before checkout."})
                result = create_supabase_order(payload, authorization[7:])
                return self.json_response(201, result)
            if url or anon_key or service_key:
                return self.json_response(503, {"error": "Supabase setup is incomplete. Check the server environment."})
            name = str(payload.get("name", "")).strip()
            email = str(payload.get("email", "")).strip().lower()
            address = str(payload.get("address", "")).strip()
            lines = payload.get("items")
            if not name or len(name) > 120 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
                return self.json_response(400, {"error": "Enter a valid name and email address."})
            if not address or len(address) > 500:
                return self.json_response(400, {"error": "Enter a delivery address."})
            if not isinstance(lines, list) or not lines or len(lines) > 50:
                return self.json_response(400, {"error": "Your basket is empty."})
            quantities = {}
            for line in lines:
                product_id, quantity = int(line["id"]), int(line["qty"])
                if product_id <= 0 or quantity <= 0 or quantity > 100:
                    raise ValueError("Invalid cart item")
                quantities[product_id] = quantities.get(product_id, 0) + quantity
            with db_session() as db:
                # Prices and names come from the database, never from the browser.
                products = {}
                for product_id in quantities:
                    row = db.execute("SELECT id, name, price_minor FROM products WHERE id = ? AND active = 1", (product_id,)).fetchone()
                    if row is None:
                        return self.json_response(400, {"error": "A product in your basket is no longer available."})
                    products[product_id] = dict(row)
                db.execute("INSERT INTO users (name, email) VALUES (?, ?) ON CONFLICT(email) DO UPDATE SET name = excluded.name", (name, email))
                user_id = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()["id"]
                db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
                for product_id, quantity in quantities.items():
                    db.execute("INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)", (user_id, product_id, quantity))
                total_minor = sum(products[pid]["price_minor"] * qty for pid, qty in quantities.items())
                cursor = db.execute("INSERT INTO orders (user_id, total_minor, shipping_address) VALUES (?, ?, ?)", (user_id, total_minor, address))
                order_id = cursor.lastrowid
                order_items = []
                for product_id, quantity in quantities.items():
                    product = products[product_id]
                    db.execute("INSERT INTO order_items (order_id, product_id, product_name, unit_price_minor, quantity) VALUES (?, ?, ?, ?, ?)",
                               (order_id, product_id, product["name"], product["price_minor"], quantity))
                    order_items.append({**product, "quantity": quantity})
                db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
            email_sent = send_confirmation(email, name, order_id, total_minor, order_items)
            with db_session() as db:
                db.execute("UPDATE orders SET confirmation_email_status = ? WHERE id = ?", ("sent" if email_sent else "failed", order_id))
            return self.json_response(201, {"orderId": order_id, "total": total_minor, "emailSent": email_sent})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return self.json_response(400, {"error": str(exc) or "Please check your checkout details and basket."})
        except PermissionError as exc:
            return self.json_response(401, {"error": str(exc)})
        except Exception as exc:
            print(f"Checkout error: {exc}")
            return self.json_response(500, {"error": "We could not complete checkout. Please try again."})


if __name__ == "__main__":
    with db_session() as db:
        db.executescript((ROOT / "schema.sql").read_text())
    port = int(os.environ.get("PORT", "8000"))
    print(f"Zamac Füds running at http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
