from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import sqlite3
import hashlib
import hmac
import secrets
import os
from html import escape

app = FastAPI(title="REDNET - Emergency Blood Response Network")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "rednet.db")
SECRET_KEY = "REDNET-DEMO-SECRET-CHANGE-LATER"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_database():
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            dob TEXT,
            gender TEXT,
            district TEXT,
            city TEXT,
            pincode TEXT,
            address TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS donor_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            blood_group TEXT NOT NULL,
            last_donation_date TEXT,
            available INTEGER DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS emergency_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            patient_name TEXT NOT NULL,
            blood_group TEXT NOT NULL,
            units INTEGER NOT NULL,
            hospital_name TEXT NOT NULL,
            hospital_location TEXT NOT NULL,
            emergency_level TEXT NOT NULL,
            additional_info TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    db.commit()
    db.close()


init_database()


# =========================================================
# PASSWORD + SESSION
# =========================================================

def hash_password(password):
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120000
    )
    return salt.hex() + ":" + password_hash.hex()


def verify_password(password, stored_password):
    try:
        salt_hex, hash_hex = stored_password.split(":", 1)
        salt = bytes.fromhex(salt_hex)

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            120000
        )

        return hmac.compare_digest(new_hash.hex(), hash_hex)
    except Exception:
        return False


def create_session(user_id):
    value = str(user_id)

    signature = hmac.new(
        SECRET_KEY.encode(),
        value.encode(),
        hashlib.sha256
    ).hexdigest()

    return value + "." + signature


def get_user_id(request: Request):
    token = request.cookies.get("rednet_session")

    if not token:
        return None

    try:
        user_id, signature = token.split(".", 1)

        expected = hmac.new(
            SECRET_KEY.encode(),
            user_id.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return None

        return int(user_id)
    except Exception:
        return None


def require_login(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse("/", status_code=303)

    return user_id


# =========================================================
# UI
# =========================================================

CSS = """
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

:root {
    --red: #d71920;
    --dark-red: #a90f15;
    --light-red: #fff1f2;
    --bg: #f7f8fa;
    --text: #171717;
    --muted: #737373;
    --border: #e7e7e7;
    --green: #168b43;
    --orange: #d98200;
}

body {
    font-family: Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
}

a {
    text-decoration: none;
    color: inherit;
}

button {
    cursor: pointer;
}

.container {
    width: min(1180px, 92%);
    margin: auto;
}

.navbar {
    height: 70px;
    background: white;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 4%;
    position: sticky;
    top: 0;
    z-index: 1000;
}

.logo {
    color: var(--red);
    font-size: 28px;
    font-weight: 900;
}

.nav-links {
    display: flex;
    gap: 24px;
}

.nav-links a {
    color: #444;
    font-size: 14px;
    font-weight: bold;
}

.nav-links a:hover {
    color: var(--red);
}

.profile-button {
    width: 42px;
    height: 42px;
    border: 1px solid #ffd0d2;
    background: var(--light-red);
    border-radius: 50%;
    font-size: 18px;
}

.profile-menu {
    display: none;
    position: absolute;
    top: 62px;
    right: 4%;
    width: 245px;
    background: white;
    border: 1px solid var(--border);
    border-radius: 16px;
    box-shadow: 0 15px 40px rgba(0,0,0,.14);
    overflow: hidden;
}

.profile-menu.show {
    display: block;
}

.profile-menu-header {
    padding: 16px;
    background: var(--light-red);
}

.profile-menu-header strong {
    display: block;
}

.profile-menu-header small {
    color: var(--muted);
}

.profile-menu a {
    display: block;
    padding: 13px 17px;
    font-size: 14px;
}

.profile-menu a:hover {
    background: #fafafa;
    color: var(--red);
}

.hero {
    background: linear-gradient(135deg, #780006, #d71920);
    color: white;
    padding: 80px 0;
}

.hero h1 {
    font-size: clamp(42px, 6vw, 68px);
    line-height: 1.05;
    max-width: 760px;
}

.hero h1 span {
    color: #ffd5d6;
}

.hero p {
    max-width: 650px;
    margin-top: 20px;
    line-height: 1.7;
    color: #ffe5e5;
}

.hero-actions {
    display: flex;
    gap: 12px;
    margin-top: 28px;
    flex-wrap: wrap;
}

.page {
    padding: 45px 0 80px;
}

.page-header {
    margin-bottom: 25px;
}

.page-header h1 {
    font-size: 34px;
}

.page-header p {
    color: var(--muted);
    margin-top: 6px;
}

.card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 25px;
}

.form-card {
    max-width: 760px;
    margin: auto;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0 18px;
}

.full {
    grid-column: 1 / -1;
}

.form-group {
    margin-bottom: 17px;
}

label {
    display: block;
    font-size: 13px;
    font-weight: bold;
    margin-bottom: 7px;
}

input, select, textarea {
    width: 100%;
    padding: 13px;
    border: 1px solid #ddd;
    border-radius: 10px;
    font-size: 14px;
    outline: none;
}

input:focus, select:focus, textarea:focus {
    border-color: var(--red);
}

textarea {
    min-height: 110px;
    resize: vertical;
}

.btn {
    border: none;
    border-radius: 10px;
    padding: 13px 19px;
    font-weight: bold;
    font-size: 14px;
    display: inline-block;
}

.btn-primary {
    background: var(--red);
    color: white;
}

.btn-primary:hover {
    background: var(--dark-red);
}

.btn-white {
    background: white;
    color: var(--red);
}

.btn-outline {
    background: white;
    color: #333;
    border: 1px solid var(--border);
}

.btn-full {
    width: 100%;
}

.cards-4 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 18px;
}

.cards-2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 18px;
}

.feature-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 17px;
    padding: 23px;
    transition: .2s;
}

.feature-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 30px rgba(0,0,0,.08);
}

.feature-icon {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    background: var(--light-red);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 25px;
    margin-bottom: 15px;
}

.feature-card h3 {
    margin-bottom: 7px;
}

.feature-card p {
    color: var(--muted);
    font-size: 13px;
    line-height: 1.6;
}

.stats {
    margin-top: -30px;
    position: relative;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 15px;
}

.stat-card {
    background: white;
    padding: 21px;
    border-radius: 16px;
    border: 1px solid var(--border);
    box-shadow: 0 8px 30px rgba(0,0,0,.07);
}

.stat-number {
    color: var(--red);
    font-size: 27px;
    font-weight: 900;
}

.stat-label {
    color: var(--muted);
    font-size: 12px;
}

.blood-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 12px;
}

.blood-card {
    text-align: center;
    background: white;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px 8px;
}

.blood-type {
    color: var(--red);
    font-size: 21px;
    font-weight: 900;
}

.status-good {
    color: var(--green);
    font-size: 11px;
    font-weight: bold;
}

.status-low {
    color: var(--orange);
    font-size: 11px;
    font-weight: bold;
}

.search-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr auto;
    gap: 12px;
    align-items: end;
}

.donor-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 15px;
    padding: 18px;
    margin-top: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.donor-main {
    display: flex;
    gap: 13px;
    align-items: center;
}

.donor-avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: var(--light-red);
    display: flex;
    align-items: center;
    justify-content: center;
}

.donor-name {
    font-weight: bold;
}

.donor-location {
    color: var(--muted);
    font-size: 13px;
    margin-top: 3px;
}

.badge {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 20px;
    background: var(--light-red);
    color: var(--red);
    font-size: 11px;
    font-weight: bold;
}

.available {
    color: var(--green);
    font-size: 12px;
    font-weight: bold;
}

.warning {
    background: #fff8e8;
    border: 1px solid #ffe0a3;
    padding: 14px;
    border-radius: 11px;
    margin-bottom: 20px;
    font-size: 13px;
}

.profile-top {
    display: flex;
    align-items: center;
    gap: 18px;
}

.avatar-large {
    width: 90px;
    height: 90px;
    border-radius: 50%;
    background: var(--light-red);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 40px;
}

.profile-name {
    font-size: 25px;
    font-weight: 900;
}

.muted {
    color: var(--muted);
}

.info-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    margin-top: 28px;
}

.info-item {
    background: #fafafa;
    padding: 15px;
    border-radius: 11px;
}

.info-item small {
    color: var(--muted);
    font-size: 11px;
}

.info-item strong {
    display: block;
    margin-top: 4px;
}

.empty-state {
    text-align: center;
    padding: 50px 20px;
    color: var(--muted);
}

.empty-icon {
    font-size: 40px;
    margin-bottom: 10px;
}

.login-page {
    min-height: 100vh;
    display: grid;
    grid-template-columns: 1.1fr .9fr;
}

.login-visual {
    background: linear-gradient(145deg, #760006, #d71920);
    color: white;
    display: flex;
    align-items: center;
    padding: 8%;
}

.login-visual h1 {
    font-size: clamp(42px, 5vw, 65px);
    line-height: 1.05;
    margin-top: 30px;
}

.login-visual p {
    color: #ffe3e3;
    line-height: 1.7;
    margin-top: 20px;
    max-width: 580px;
}

.login-area {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 35px;
}

.login-card {
    width: min(420px, 100%);
}

.login-card h2 {
    font-size: 30px;
    margin-bottom: 7px;
}

.login-subtitle {
    color: var(--muted);
    margin-bottom: 28px;
}

.mobile-nav {
    display: none;
}

.request-card {
    margin-bottom: 13px;
}

.request-status {
    color: var(--orange);
    font-size: 12px;
    font-weight: bold;
}

.center {
    text-align: center;
}

@media(max-width: 950px) {
    .nav-links {
        display: none;
    }

    .cards-4 {
        grid-template-columns: repeat(2, 1fr);
    }

    .stats-grid {
        grid-template-columns: repeat(2, 1fr);
    }

    .blood-grid {
        grid-template-columns: repeat(4, 1fr);
    }

    .login-page {
        grid-template-columns: 1fr;
    }

    .login-visual {
        display: none;
    }
}

@media(max-width: 650px) {
    .cards-4,
    .cards-2,
    .form-grid,
    .info-grid {
        grid-template-columns: 1fr;
    }

    .full {
        grid-column: auto;
    }

    .search-grid {
        grid-template-columns: 1fr;
    }

    .donor-card {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
    }

    .login-area {
        padding: 25px;
    }

    .mobile-nav {
        display: flex;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 62px;
        background: white;
        border-top: 1px solid var(--border);
        z-index: 999;
        justify-content: space-around;
        align-items: center;
    }

    .mobile-nav a {
        font-size: 11px;
        text-align: center;
        color: #555;
    }

    .mobile-nav strong {
        display: block;
        font-size: 17px;
    }

    .page {
        padding-bottom: 90px;
    }
}
"""


def page(title, content, navigation=True):
    nav = navbar() if navigation else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
{nav}
{content}
</body>
</html>"""


def navbar():
    return """
<nav class="navbar">
    <a href="/home" class="logo">REDNET</a>

    <div class="nav-links">
        <a href="/home">Home</a>
        <a href="/find-donor">Find Donor</a>
        <a href="/blood-banks">Blood Banks</a>
        <a href="/emergency-request">Emergency</a>
    </div>

    <button class="profile-button" onclick="toggleProfile()">👤</button>

    <div id="profileMenu" class="profile-menu">
        <div class="profile-menu-header">
            <strong>My REDNET Account</strong>
            <small>Profile & Settings</small>
        </div>

        <a href="/profile">👤 My Profile</a>
        <a href="/edit-profile">✏️ Edit Profile</a>
        <a href="/donor-registration">❤️ Become a Donor</a>
        <a href="/donation-history">🩸 Donation History</a>
        <a href="/my-requests">📋 My Requests</a>
        <a href="/notifications">🔔 Notifications</a>
        <a href="/settings">⚙️ Settings</a>
        <a href="/logout">🚪 Logout</a>
    </div>
</nav>

<script>
function toggleProfile() {
    document.getElementById("profileMenu").classList.toggle("show");
}
</script>
"""


def mobile_nav():
    return """
<div class="mobile-nav">
    <a href="/home"><strong>⌂</strong>Home</a>
    <a href="/find-donor"><strong>🔎</strong>Donor</a>
    <a href="/emergency-request"><strong>🚨</strong>Emergency</a>
    <a href="/profile"><strong>👤</strong>Profile</a>
</div>
"""


# =========================================================
# LOGIN
# =========================================================

@app.get("/", response_class=HTMLResponse)
def login():
    content = """
<div class="login-page">
    <div class="login-visual">
        <div>
            <div class="logo" style="color:white;">REDNET</div>
            <h1>Every Drop<br>Can Save<br>a Life.</h1>
            <p>
                Emergency Blood Response Network connecting
                patients, donors, hospitals and blood banks.
            </p>
        </div>
    </div>

    <div class="login-area">
        <div class="login-card">
            <h2>Welcome back</h2>
            <p class="login-subtitle">Login to your REDNET account.</p>

            <form onsubmit="loginUser(event)">
                <div class="form-group">
                    <label>Username or Email</label>
                    <input id="login_username" required placeholder="Username or email">
                </div>

                <div class="form-group">
                    <label>Password</label>
                    <input id="login_password" type="password" required placeholder="Password">
                </div>

                <button class="btn btn-primary btn-full">Login</button>
            </form>

            <p class="center muted" style="margin-top:20px;">
                New to REDNET?
                <a href="/register" style="color:#d71920;font-weight:bold;">
                    Create Account
                </a>
            </p>
        </div>
    </div>
</div>

<script>
async function loginUser(event) {
    event.preventDefault();

    const response = await fetch("/api/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            username: document.getElementById("login_username").value,
            password: document.getElementById("login_password").value
        })
    });

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail || "Login failed.");
        return;
    }

    window.location.href = "/home";
}
</script>
"""
    return page("REDNET - Login", content, False)


# =========================================================
# REGISTER
# =========================================================

@app.get("/register", response_class=HTMLResponse)
def register():
    content = """
<div class="login-page">
    <div class="login-visual">
        <div>
            <div class="logo" style="color:white;">REDNET</div>
            <h1>Join the<br>Blood<br>Network.</h1>
            <p>
                Create your REDNET account and become part of
                the emergency blood response network.
            </p>
        </div>
    </div>

    <div class="login-area">
        <div class="login-card">
            <h2>Create account</h2>
            <p class="login-subtitle">Create your REDNET account.</p>

            <form onsubmit="registerUser(event)">
                <div class="form-group">
                    <label>Full Name</label>
                    <input id="reg_name" required placeholder="Full name">
                </div>

                <div class="form-group">
                    <label>Username</label>
                    <input id="reg_username" required placeholder="Create username">
                </div>

                <div class="form-group">
                    <label>Email</label>
                    <input id="reg_email" type="email" required placeholder="Email">
                </div>

                <div class="form-group">
                    <label>Mobile Number</label>
                    <input id="reg_phone" required placeholder="Mobile number">
                </div>

                <div class="form-grid">
                    <div class="form-group">
                        <label>Password</label>
                        <input id="reg_password" type="password" required placeholder="Password">
                    </div>

                    <div class="form-group">
                        <label>Confirm Password</label>
                        <input id="reg_confirm" type="password" required placeholder="Confirm password">
                    </div>
                </div>

                <button class="btn btn-primary btn-full">Create Account</button>
            </form>

            <p class="center muted" style="margin-top:20px;">
                Already have an account?
                <a href="/" style="color:#d71920;font-weight:bold;">Login</a>
            </p>
        </div>
    </div>
</div>

<script>
async function registerUser(event) {
    event.preventDefault();

    const password = document.getElementById("reg_password").value;
    const confirm = document.getElementById("reg_confirm").value;

    if (password !== confirm) {
        alert("Passwords do not match.");
        return;
    }

    const response = await fetch("/api/register", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            full_name: document.getElementById("reg_name").value,
            username: document.getElementById("reg_username").value,
            email: document.getElementById("reg_email").value,
            phone: document.getElementById("reg_phone").value,
            password: password
        })
    });

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail || "Registration failed.");
        return;
    }

    alert("Account created successfully!");
    window.location.href = "/";
}
</script>
"""
    return page("REDNET - Create Account", content, False)


# =========================================================
# HOME
# =========================================================

@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    db.close()

    name = escape(user["full_name"])

    content = f"""
<section class="hero">
    <div class="container">
        <p style="font-weight:bold;margin-bottom:15px;">
            Welcome, {name}
        </p>

        <h1>Every Drop Can <span>Save a Life.</span></h1>

        <p>
            REDNET connects patients, blood donors, hospitals
            and blood banks to respond faster when blood is urgently needed.
        </p>

        <div class="hero-actions">
            <a href="/emergency-request" class="btn btn-white">
                🚨 Request Blood
            </a>

            <a href="/donor-registration"
               class="btn"
               style="background:rgba(255,255,255,.12);color:white;border:1px solid rgba(255,255,255,.3);">
                ❤️ Become a Donor
            </a>
        </div>
    </div>
</section>

<section class="stats">
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">8</div>
                <div class="stat-label">Blood Groups</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">DB</div>
                <div class="stat-label">Live Database</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">24/7</div>
                <div class="stat-label">Emergency Response</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">1</div>
                <div class="stat-label">Connected Network</div>
            </div>
        </div>
    </div>
</section>

<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>What do you need?</h1>
            <p>Choose an action to continue.</p>
        </div>

        <div class="cards-4">
            <a href="/find-donor" class="feature-card">
                <div class="feature-icon">🔎</div>
                <h3>Find a Donor</h3>
                <p>Search available donors by blood group and location.</p>
            </a>

            <a href="/emergency-request" class="feature-card">
                <div class="feature-icon">🚨</div>
                <h3>Emergency Request</h3>
                <p>Create an urgent blood requirement.</p>
            </a>

            <a href="/blood-banks" class="feature-card">
                <div class="feature-icon">🏥</div>
                <h3>Blood Banks</h3>
                <p>Explore connected blood bank locations.</p>
            </a>

            <a href="/donor-registration" class="feature-card">
                <div class="feature-icon">❤️</div>
                <h3>Become a Donor</h3>
                <p>Register yourself as an emergency blood donor.</p>
            </a>
        </div>

        <div style="margin-top:35px;">
            <div class="page-header">
                <h1>Blood Availability</h1>
                <p>Dashboard overview.</p>
            </div>

            <div class="blood-grid">
                <div class="blood-card"><div class="blood-type">A+</div><div class="status-good">Available</div></div>
                <div class="blood-card"><div class="blood-type">A-</div><div class="status-good">Available</div></div>
                <div class="blood-card"><div class="blood-type">B+</div><div class="status-good">Available</div></div>
                <div class="blood-card"><div class="blood-type">B-</div><div class="status-low">Low Stock</div></div>
                <div class="blood-card"><div class="blood-type">O+</div><div class="status-good">Available</div></div>
                <div class="blood-card"><div class="blood-type">O-</div><div class="status-low">Low Stock</div></div>
                <div class="blood-card"><div class="blood-type">AB+</div><div class="status-good">Available</div></div>
                <div class="blood-card"><div class="blood-type">AB-</div><div class="status-low">Low Stock</div></div>
            </div>
        </div>
    </div>
</div>

{mobile_nav()}
"""
    return page("REDNET - Home", content)


# =========================================================
# PROFILE
# =========================================================

@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    profile_data = db.execute(
        "SELECT * FROM profiles WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    donor = db.execute(
        "SELECT * FROM donor_profiles WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    db.close()

    dob = profile_data["dob"] if profile_data else "Not added"
    gender = profile_data["gender"] if profile_data else "Not added"
    district = profile_data["district"] if profile_data else "Not added"
    city = profile_data["city"] if profile_data else "Not added"
    blood = donor["blood_group"] if donor else "Not registered"

    if donor:
        donor_status = "Active Donor" if donor["available"] else "Unavailable"
    else:
        donor_status = "Not registered"

    content = f"""
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>My Profile</h1>
            <p>Your REDNET account information.</p>
        </div>

        <div class="card">
            <div class="profile-top">
                <div class="avatar-large">👤</div>
                <div>
                    <div class="profile-name">{escape(user["full_name"])}</div>
                    <div class="muted">@{escape(user["username"])}</div>
                </div>
            </div>

            <div class="info-grid">
                <div class="info-item"><small>Email</small><strong>{escape(user["email"])}</strong></div>
                <div class="info-item"><small>Mobile</small><strong>{escape(user["phone"] or "Not added")}</strong></div>
                <div class="info-item"><small>Date of Birth</small><strong>{escape(dob)}</strong></div>
                <div class="info-item"><small>Gender</small><strong>{escape(gender)}</strong></div>
                <div class="info-item"><small>District</small><strong>{escape(district)}</strong></div>
                <div class="info-item"><small>City</small><strong>{escape(city)}</strong></div>
                <div class="info-item"><small>Blood Group</small><strong>{escape(blood)}</strong></div>
                <div class="info-item"><small>Donor Status</small><strong>{escape(donor_status)}</strong></div>
            </div>

            <div style="display:flex;gap:10px;margin-top:25px;flex-wrap:wrap;">
                <a href="/edit-profile" class="btn btn-primary">✏️ Edit Profile</a>
                <a href="/donor-registration" class="btn btn-outline">❤️ Become a Donor</a>
            </div>
        </div>
    </div>
</div>

{mobile_nav()}
"""
    return page("REDNET - Profile", content)


# =========================================================
# EDIT PROFILE
# =========================================================

@app.get("/edit-profile", response_class=HTMLResponse)
def edit_profile(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    profile_data = db.execute(
        "SELECT * FROM profiles WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    db.close()

    dob = profile_data["dob"] if profile_data else ""
    gender = profile_data["gender"] if profile_data else ""
    district = profile_data["district"] if profile_data else ""
    city = profile_data["city"] if profile_data else ""
    pincode = profile_data["pincode"] if profile_data else ""
    address = profile_data["address"] if profile_data else ""

    selected_male = "selected" if gender == "Male" else ""
    selected_female = "selected" if gender == "Female" else ""
    selected_other = "selected" if gender == "Other" else ""

    content = f"""
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>Edit Profile</h1>
            <p>Update your personal information.</p>
        </div>

        <div class="card form-card">
            <form onsubmit="saveProfile(event)">
                <div class="form-grid">
                    <div class="form-group full">
                        <label>Full Name</label>
                        <input id="full_name" value="{escape(user["full_name"])}" required>
                    </div>

                    <div class="form-group">
                        <label>Email</label>
                        <input value="{escape(user["email"])}" readonly>
                    </div>

                    <div class="form-group">
                        <label>Mobile</label>
                        <input value="{escape(user["phone"] or "")}" readonly>
                    </div>

                    <div class="form-group">
                        <label>Date of Birth</label>
                        <input id="dob" type="date" value="{escape(dob)}">
                    </div>

                    <div class="form-group">
                        <label>Gender</label>
                        <select id="gender">
                            <option value="">Select Gender</option>
                            <option value="Male" {selected_male}>Male</option>
                            <option value="Female" {selected_female}>Female</option>
                            <option value="Other" {selected_other}>Other</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>District</label>
                        <input id="district" value="{escape(district)}" placeholder="District">
                    </div>

                    <div class="form-group">
                        <label>City</label>
                        <input id="city" value="{escape(city)}" placeholder="City">
                    </div>

                    <div class="form-group">
                        <label>Pincode</label>
                        <input id="pincode" value="{escape(pincode)}" placeholder="Pincode">
                    </div>

                    <div class="form-group full">
                        <label>Address</label>
                        <textarea id="address" placeholder="Address">{escape(address)}</textarea>
                    </div>
                </div>

                <button class="btn btn-primary">Save Changes</button>
            </form>
        </div>
    </div>
</div>

{mobile_nav()}

<script>
async function saveProfile(event) {{
    event.preventDefault();

    const response = await fetch("/api/profile", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{
            full_name: document.getElementById("full_name").value,
            dob: document.getElementById("dob").value,
            gender: document.getElementById("gender").value,
            district: document.getElementById("district").value,
            city: document.getElementById("city").value,
            pincode: document.getElementById("pincode").value,
            address: document.getElementById("address").value
        }})
    }});

    const data = await response.json();

    if (!response.ok) {{
        alert(data.detail || "Unable to update profile.");
        return;
    }}

    alert("Profile updated successfully!");
    window.location.href = "/profile";
}}
</script>
"""
    return page("REDNET - Edit Profile", content)


# =========================================================
# DONOR REGISTRATION
# =========================================================

@app.get("/donor-registration", response_class=HTMLResponse)
def donor_registration(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    db = get_db()

    profile_data = db.execute(
        "SELECT * FROM profiles WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    donor = db.execute(
        "SELECT * FROM donor_profiles WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    db.close()

    dob = profile_data["dob"] if profile_data else ""
    gender = profile_data["gender"] if profile_data else ""
    blood = donor["blood_group"] if donor else ""
    last_donation = donor["last_donation_date"] if donor else ""
    available = bool(donor["available"]) if donor else True

    selected_gender = {
        "Male": "Male",
        "Female": "Female",
        "Other": "Other"
    }

    gender_options = f"""
        <option value="">Select Gender</option>
        <option value="Male" {"selected" if gender == "Male" else ""}>Male</option>
        <option value="Female" {"selected" if gender == "Female" else ""}>Female</option>
        <option value="Other" {"selected" if gender == "Other" else ""}>Other</option>
    """

    blood_options = ""
    for group in ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]:
        selected = "selected" if blood == group else ""
        blood_options += f'<option value="{group}" {selected}>{group}</option>'

    checked = "checked" if available else ""

    content = f"""
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>❤️ Become a Blood Donor</h1>
            <p>Complete your donor profile.</p>
        </div>

        <div class="card form-card">
            <div class="warning">
                <strong>Important:</strong>
                Final donor eligibility is determined by applicable
                medical and blood-bank requirements.
            </div>

            <form onsubmit="registerDonor(event)">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Date of Birth</label>
                        <input id="dob" type="date" value="{escape(dob)}" required>
                    </div>

                    <div class="form-group">
                        <label>Age</label>
                        <input id="age" readonly placeholder="Auto calculated">
                    </div>

                    <div class="form-group">
                        <label>Gender</label>
                        <select id="gender" required>
                            {gender_options}
                        </select>
                    </div>

                    <div class="form-group">
                        <label>Blood Group</label>
                        <select id="blood_group" required>
                            <option value="">Select Blood Group</option>
                            {blood_options}
                        </select>
                    </div>

                    <div class="form-group">
                        <label>Last Donation Date</label>
                        <input id="last_donation_date"
                               type="date"
                               value="{escape(last_donation)}">
                    </div>
                </div>

                <div style="background:#fafafa;padding:15px;border-radius:11px;margin-bottom:20px;">
                    <label style="display:flex;gap:8px;align-items:flex-start;">
                        <input id="available"
                               type="checkbox"
                               {checked}
                               style="width:auto;">
                        I am willing to receive emergency blood donation requests.
                    </label>
                </div>

                <button class="btn btn-primary">
                    Complete Donor Registration
                </button>
            </form>
        </div>
    </div>
</div>

{mobile_nav()}

<script>
function calculateAge() {{
    const value = document.getElementById("dob").value;

    if (!value) {{
        document.getElementById("age").value = "";
        return;
    }}

    const dob = new Date(value);
    const today = new Date();

    let age = today.getFullYear() - dob.getFullYear();
    const month = today.getMonth() - dob.getMonth();

    if (month < 0 || (month === 0 && today.getDate() < dob.getDate())) {{
        age--;
    }}

    document.getElementById("age").value = age;
}}

document.getElementById("dob").addEventListener("change", calculateAge);
calculateAge();

async function registerDonor(event) {{
    event.preventDefault();

    const response = await fetch("/api/donor", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{
            dob: document.getElementById("dob").value,
            gender: document.getElementById("gender").value,
            blood_group: document.getElementById("blood_group").value,
            last_donation_date: document.getElementById("last_donation_date").value,
            available: document.getElementById("available").checked
        }})
    }});

    const data = await response.json();

    if (!response.ok) {{
        alert(data.detail || "Registration failed.");
        return;
    }}

    alert("Donor profile saved successfully!");
    window.location.href = "/profile";
}}
</script>
"""
    return page("REDNET - Become a Donor", content)


# =========================================================
# FIND DONOR
# =========================================================

@app.get("/find-donor", response_class=HTMLResponse)
def find_donor(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    content = """
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>🔎 Find a Blood Donor</h1>
            <p>Search donors from the REDNET database.</p>
        </div>

        <div class="card">
            <div class="search-grid">
                <div class="form-group">
                    <label>Blood Group</label>
                    <select id="blood">
                        <option value="">Select</option>
                        <option>A+</option><option>A-</option>
                        <option>B+</option><option>B-</option>
                        <option>O+</option><option>O-</option>
                        <option>AB+</option><option>AB-</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>District</label>
                    <input id="district" placeholder="District">
                </div>

                <div class="form-group">
                    <label>City</label>
                    <input id="city" placeholder="City">
                </div>

                <button class="btn btn-primary" onclick="searchDonors()">
                    Search
                </button>
            </div>
        </div>

        <div id="results" style="margin-top:20px;"></div>
    </div>
</div>

{mobile_nav()}

<script>
async function searchDonors() {
    const blood = document.getElementById("blood").value;
    const district = document.getElementById("district").value.trim();
    const city = document.getElementById("city").value.trim();

    if (!blood || !district || !city) {
        alert("Enter blood group, district and city.");
        return;
    }

    const results = document.getElementById("results");
    results.innerHTML = '<div class="card">Searching...</div>';

    const response = await fetch(
        "/donors/search?blood_group=" +
        encodeURIComponent(blood) +
        "&district=" +
        encodeURIComponent(district) +
        "&city=" +
        encodeURIComponent(city)
    );

    const data = await response.json();

    if (!response.ok) {
        results.innerHTML = '<div class="card">Unable to search donors.</div>';
        return;
    }

    if (data.count === 0) {
        results.innerHTML =
            '<div class="card empty-state">' +
            '<div class="empty-icon">🩸</div>' +
            '<h3>No donor found</h3>' +
            '<p>Try another location.</p>' +
            '</div>';
        return;
    }

    let html = "";

    data.donors.forEach(function(donor) {
        html +=
            '<div class="donor-card">' +
                '<div class="donor-main">' +
                    '<div class="donor-avatar">👤</div>' +
                    '<div>' +
                        '<div class="donor-name">' +
                            donor.name +
                            ' <span class="badge">' +
                            donor.blood_group +
                            '</span>' +
                        '</div>' +
                        '<div class="donor-location">' +
                            '📍 ' + donor.city + ', ' + donor.district +
                        '</div>' +
                    '</div>' +
                '</div>' +
                '<div class="available">● Available</div>' +
            '</div>';
    });

    results.innerHTML = html;
}
</script>
"""
    return page("REDNET - Find Donor", content)


# =========================================================
# EMERGENCY REQUEST
# =========================================================

@app.get("/emergency-request", response_class=HTMLResponse)
def emergency_request(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    content = """
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1 style="color:#d71920;">🚨 Emergency Blood Request</h1>
            <p>Create an urgent blood requirement.</p>
        </div>

        <div class="card form-card">
            <div class="warning">
                <strong>Important:</strong>
                Enter accurate patient and hospital information.
            </div>

            <form onsubmit="submitRequest(event)">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Patient Name</label>
                        <input id="patient_name" required placeholder="Patient name">
                    </div>

                    <div class="form-group">
                        <label>Blood Group</label>
                        <select id="blood_group" required>
                            <option value="">Select</option>
                            <option>A+</option><option>A-</option>
                            <option>B+</option><option>B-</option>
                            <option>O+</option><option>O-</option>
                            <option>AB+</option><option>AB-</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label>Units Required</label>
                        <input id="units" type="number" min="1" required placeholder="Units">
                    </div>

                    <div class="form-group">
                        <label>Emergency Level</label>
                        <select id="emergency_level" required>
                            <option>Critical</option>
                            <option>Urgent</option>
                            <option>Normal</option>
                        </select>
                    </div>

                    <div class="form-group full">
                        <label>Hospital Name</label>
                        <input id="hospital_name" required placeholder="Hospital name">
                    </div>

                    <div class="form-group full">
                        <label>Hospital Location</label>
                        <input id="hospital_location" required placeholder="Hospital location">
                    </div>

                    <div class="form-group full">
                        <label>Additional Information</label>
                        <textarea id="additional_info" placeholder="Additional information"></textarea>
                    </div>
                </div>

                <button class="btn btn-primary">
                    🚨 Submit Emergency Request
                </button>
            </form>
        </div>
    </div>
</div>

{mobile_nav()}

<script>
async function submitRequest(event) {
    event.preventDefault();

    const units = Number(document.getElementById("units").value);

    const response = await fetch("/api/emergency-request", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            patient_name: document.getElementById("patient_name").value,
            blood_group: document.getElementById("blood_group").value,
            units: units,
            hospital_name: document.getElementById("hospital_name").value,
            hospital_location: document.getElementById("hospital_location").value,
            emergency_level: document.getElementById("emergency_level").value,
            additional_info: document.getElementById("additional_info").value
        })
    });

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail || "Request failed.");
        return;
    }

    alert("Emergency request created successfully!");
    window.location.href = "/my-requests";
}
</script>
"""
    return page("REDNET - Emergency Request", content)


# =========================================================
# MY REQUESTS
# =========================================================

@app.get("/my-requests", response_class=HTMLResponse)
def my_requests(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    db = get_db()

    rows = db.execute(
        """
        SELECT *
        FROM emergency_requests
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    db.close()

    if not rows:
        request_html = """
        <div class="card empty-state">
            <div class="empty-icon">📋</div>
            <h3>No requests yet</h3>
            <p>Your emergency requests will appear here.</p>
            <br>
            <a href="/emergency-request" class="btn btn-primary">
                Create Emergency Request
            </a>
        </div>
        """
    else:
        request_html = ""

        for item in rows:
            request_html += f"""
            <div class="card request-card">
                <div style="display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap;">
                    <div>
                        <h3>🚨 {escape(item["patient_name"])}</h3>

                        <p class="muted" style="margin-top:5px;">
                            🩸 {escape(item["blood_group"])}
                            &nbsp; | &nbsp;
                            {item["units"]} unit(s)
                        </p>

                        <p class="muted" style="margin-top:5px;">
                            🏥 {escape(item["hospital_name"])}
                        </p>
                    </div>

                    <div>
                        <div class="badge">
                            {escape(item["emergency_level"])}
                        </div>

                        <div class="request-status" style="margin-top:7px;">
                            ● {escape(item["status"])}
                        </div>
                    </div>
                </div>
            </div>
            """

    content = f"""
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>📋 My Requests</h1>
            <p>Your emergency blood requests.</p>
        </div>

        {request_html}
    </div>
</div>

{mobile_nav()}
"""
    return page("REDNET - My Requests", content)


# =========================================================
# BLOOD BANKS
# =========================================================

@app.get("/blood-banks", response_class=HTMLResponse)
def blood_banks(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    content = f"""
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>🏥 Blood Banks</h1>
            <p>Connected blood bank network.</p>
        </div>

        <div class="cards-2">
            <div class="card">
                <h2>🏥</h2>
                <h3 style="margin-top:10px;">Demo Blood Bank</h3>
                <p class="muted" style="margin-top:7px;">📍 Thiruvarur</p>
                <br>
                <span class="badge">✓ Verified</span>
            </div>

            <div class="card">
                <h2>🏥</h2>
                <h3 style="margin-top:10px;">Demo Blood Bank</h3>
                <p class="muted" style="margin-top:7px;">📍 Thanjavur</p>
                <br>
                <span class="badge">✓ Verified</span>
            </div>
        </div>
    </div>
</div>

{mobile_nav()}
"""
    return page("REDNET - Blood Banks", content)


# =========================================================
# DONATION HISTORY
# =========================================================

@app.get("/donation-history", response_class=HTMLResponse)
def donation_history(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    content = f"""
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>🩸 Donation History</h1>
            <p>Your completed blood donations.</p>
        </div>

        <div class="card empty-state">
            <div class="empty-icon">🩸</div>
            <h3>No donation history yet</h3>
            <p>Completed donations will appear here.</p>
            <br>
            <a href="/donor-registration" class="btn btn-primary">
                Become a Donor
            </a>
        </div>
    </div>
</div>

{mobile_nav()}
"""
    return page("REDNET - Donation History", content)


# =========================================================
# NOTIFICATIONS
# =========================================================

@app.get("/notifications", response_class=HTMLResponse)
def notifications(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    content = f"""
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>🔔 Notifications</h1>
            <p>REDNET updates and alerts.</p>
        </div>

        <div class="card">
            <p style="padding:15px 0;">🔔 Welcome to REDNET.</p>
            <p style="padding:15px 0;border-top:1px solid #eee;">
                ❤️ Complete your donor profile to become an active donor.
            </p>
        </div>
    </div>
</div>

{mobile_nav()}
"""
    return page("REDNET - Notifications", content)


# =========================================================
# SETTINGS
# =========================================================

@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    user_id = require_login(request)

    if not isinstance(user_id, int):
        return user_id

    content = f"""
<div class="page">
    <div class="container">
        <div class="page-header">
            <h1>⚙️ Settings</h1>
            <p>Manage your REDNET preferences.</p>
        </div>

        <div class="card">
            <p style="padding:17px 0;">🔔 Notification Settings</p>
            <p style="padding:17px 0;border-top:1px solid #eee;">🔐 Privacy & Security</p>
            <p style="padding:17px 0;border-top:1px solid #eee;">🌐 Language</p>
            <p style="padding:17px 0;border-top:1px solid #eee;">❓ Help & Support</p>
        </div>
    </div>
</div>

{mobile_nav()}
"""
    return page("REDNET - Settings", content)


# =========================================================
# LOGOUT
# =========================================================

@app.get("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("rednet_session")
    return response


# =========================================================
# API - REGISTER
# =========================================================

@app.post("/api/register")
async def api_register(request: Request):
    data = await request.json()

    full_name = str(data.get("full_name", "")).strip()
    username = str(data.get("username", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))

    if not full_name:
        return JSONResponse({"detail": "Full name is required."}, status_code=400)

    if not username:
        return JSONResponse({"detail": "Username is required."}, status_code=400)

    if not email:
        return JSONResponse({"detail": "Email is required."}, status_code=400)

    if len(password) < 6:
        return JSONResponse(
            {"detail": "Password must contain at least 6 characters."},
            status_code=400
        )

    db = get_db()

    existing = db.execute(
        """
        SELECT id
        FROM users
        WHERE username = ? OR email = ?
        """,
        (username, email)
    ).fetchone()

    if existing:
        db.close()
        return JSONResponse(
            {"detail": "Username or email already exists."},
            status_code=409
        )

    password_hash = hash_password(password)

    cursor = db.execute(
        """
        INSERT INTO users
        (full_name, username, email, phone, password_hash)
        VALUES (?, ?, ?, ?, ?)
        """,
        (full_name, username, email, phone, password_hash)
    )

    user_id = cursor.lastrowid

    db.execute(
        "INSERT INTO profiles (user_id) VALUES (?)",
        (user_id,)
    )

    db.commit()
    db.close()

    return {
        "success": True,
        "message": "Account created successfully."
    }


# =========================================================
# API - LOGIN
# =========================================================

@app.post("/api/login")
async def api_login(request: Request):
    data = await request.json()

    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", ""))

    db = get_db()

    user = db.execute(
        """
        SELECT *
        FROM users
        WHERE username = ? OR email = ?
        """,
        (username, username)
    ).fetchone()

    db.close()

    if not user:
        return JSONResponse(
            {"detail": "Invalid username or password."},
            status_code=401
        )

    if not verify_password(password, user["password_hash"]):
        return JSONResponse(
            {"detail": "Invalid username or password."},
            status_code=401
        )

    token = create_session(user["id"])

    response = JSONResponse({
        "success": True,
        "message": "Login successful."
    })

    response.set_cookie(
        key="rednet_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30
    )

    return response


# =========================================================
# API - PROFILE
# =========================================================

@app.post("/api/profile")
async def api_profile(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return JSONResponse(
            {"detail": "Please login first."},
            status_code=401
        )

    data = await request.json()

    full_name = str(data.get("full_name", "")).strip()
    dob = str(data.get("dob", "")).strip()
    gender = str(data.get("gender", "")).strip()
    district = str(data.get("district", "")).strip()
    city = str(data.get("city", "")).strip()
    pincode = str(data.get("pincode", "")).strip()
    address = str(data.get("address", "")).strip()

    if not full_name:
        return JSONResponse(
            {"detail": "Full name is required."},
            status_code=400
        )

    db = get_db()

    db.execute(
        """
        UPDATE users
        SET full_name = ?
        WHERE id = ?
        """,
        (full_name, user_id)
    )

    db.execute(
        """
        INSERT INTO profiles
        (user_id, dob, gender, district, city, pincode, address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            dob = excluded.dob,
            gender = excluded.gender,
            district = excluded.district,
            city = excluded.city,
            pincode = excluded.pincode,
            address = excluded.address
        """,
        (
            user_id,
            dob,
            gender,
            district,
            city,
            pincode,
            address
        )
    )

    db.commit()
    db.close()

    return {
        "success": True,
        "message": "Profile updated."
    }


# =========================================================
# API - DONOR
# =========================================================

@app.post("/api/donor")
async def api_donor(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return JSONResponse(
            {"detail": "Please login first."},
            status_code=401
        )

    data = await request.json()

    dob = str(data.get("dob", "")).strip()
    gender = str(data.get("gender", "")).strip()
    blood_group = str(data.get("blood_group", "")).strip().upper()
    last_donation_date = str(data.get("last_donation_date", "")).strip()
    available = 1 if data.get("available", True) else 0

    allowed_groups = {
        "A+", "A-", "B+", "B-",
        "O+", "O-", "AB+", "AB-"
    }

    if blood_group not in allowed_groups:
        return JSONResponse(
            {"detail": "Invalid blood group."},
            status_code=400
        )

    db = get_db()

    db.execute(
        """
        INSERT INTO donor_profiles
        (user_id, blood_group, last_donation_date, available)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            blood_group = excluded.blood_group,
            last_donation_date = excluded.last_donation_date,
            available = excluded.available
        """,
        (
            user_id,
            blood_group,
            last_donation_date,
            available
        )
    )

    db.execute(
        """
        INSERT INTO profiles (user_id, dob, gender)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            dob = excluded.dob,
            gender = excluded.gender
        """,
        (user_id, dob, gender)
    )

    db.commit()
    db.close()

    return {
        "success": True,
        "message": "Donor profile saved."
    }


# =========================================================
# API - EMERGENCY REQUEST
# =========================================================

@app.post("/api/emergency-request")
async def api_emergency_request(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return JSONResponse(
            {"detail": "Please login first."},
            status_code=401
        )

    data = await request.json()

    patient_name = str(data.get("patient_name", "")).strip()
    blood_group = str(data.get("blood_group", "")).strip().upper()
    hospital_name = str(data.get("hospital_name", "")).strip()
    hospital_location = str(data.get("hospital_location", "")).strip()
    emergency_level = str(data.get("emergency_level", "")).strip()
    additional_info = str(data.get("additional_info", "")).strip()

    try:
        units = int(data.get("units", 0))
    except (TypeError, ValueError):
        units = 0

    allowed_groups = {
        "A+", "A-", "B+", "B-",
        "O+", "O-", "AB+", "AB-"
    }

    if not patient_name:
        return JSONResponse(
            {"detail": "Patient name is required."},
            status_code=400
        )

    if blood_group not in allowed_groups:
        return JSONResponse(
            {"detail": "Invalid blood group."},
            status_code=400
        )

    if units < 1:
        return JSONResponse(
            {"detail": "Units must be at least 1."},
            status_code=400
        )

    if not hospital_name:
        return JSONResponse(
            {"detail": "Hospital name is required."},
            status_code=400
        )

    if not hospital_location:
        return JSONResponse(
            {"detail": "Hospital location is required."},
            status_code=400
        )

    db = get_db()

    cursor = db.execute(
        """
        INSERT INTO emergency_requests
        (
            user_id,
            patient_name,
            blood_group,
            units,
            hospital_name,
            hospital_location,
            emergency_level,
            additional_info
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            patient_name,
            blood_group,
            units,
            hospital_name,
            hospital_location,
            emergency_level,
            additional_info
        )
    )

    request_id = cursor.lastrowid

    db.commit()
    db.close()

    return {
        "success": True,
        "request_id": request_id,
        "message": "Emergency request created."
    }


# =========================================================
# API - ALL DONORS
# =========================================================

@app.get("/donors")
def get_donors(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return JSONResponse(
            {"detail": "Please login first."},
            status_code=401
        )

    db = get_db()

    rows = db.execute(
        """
        SELECT
            users.id,
            users.full_name,
            profiles.district,
            profiles.city,
            donor_profiles.blood_group,
            donor_profiles.available
        FROM donor_profiles
        JOIN users ON users.id = donor_profiles.user_id
        LEFT JOIN profiles ON profiles.user_id = users.id
        WHERE donor_profiles.available = 1
        ORDER BY users.id DESC
        """
    ).fetchall()

    db.close()

    donors = []

    for row in rows:
        donors.append({
            "id": row["id"],
            "name": row["full_name"],
            "blood_group": row["blood_group"],
            "district": row["district"] or "",
            "city": row["city"] or "",
            "available": bool(row["available"])
        })

    return {
        "count": len(donors),
        "donors": donors
    }


# =========================================================
# API - SEARCH DONORS
# =========================================================

@app.get("/donors/search")
def search_donors(
    request: Request,
    blood_group: str,
    district: str,
    city: str
):
    user_id = get_user_id(request)

    if user_id is None:
        return JSONResponse(
            {"detail": "Please login first."},
            status_code=401
        )

    db = get_db()

    rows = db.execute(
        """
        SELECT
            users.id,
            users.full_name,
            profiles.district,
            profiles.city,
            donor_profiles.blood_group,
            donor_profiles.available
        FROM donor_profiles
        JOIN users ON users.id = donor_profiles.user_id
        LEFT JOIN profiles ON profiles.user_id = users.id
        WHERE donor_profiles.available = 1
          AND LOWER(donor_profiles.blood_group) = LOWER(?)
          AND LOWER(COALESCE(profiles.district, '')) = LOWER(?)
          AND LOWER(COALESCE(profiles.city, '')) = LOWER(?)
        ORDER BY users.id DESC
        """,
        (
            blood_group.strip(),
            district.strip(),
            city.strip()
        )
    ).fetchall()

    db.close()

    results = []

    for row in rows:
        results.append({
            "id": row["id"],
            "name": row["full_name"],
            "blood_group": row["blood_group"],
            "district": row["district"] or "",
            "city": row["city"] or "",
            "available": bool(row["available"])
        })

    return {
        "count": len(results),
        "donors": results
    }


# =========================================================
# API - CURRENT USER
# =========================================================

@app.get("/api/me")
def api_me(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return JSONResponse(
            {"detail": "Not logged in."},
            status_code=401
        )

    db = get_db()

    user = db.execute(
        """
        SELECT
            id,
            full_name,
            username,
            email,
            phone,
            created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    donor = db.execute(
        """
        SELECT
            blood_group,
            last_donation_date,
            available
        FROM donor_profiles
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    db.close()

    return {
        "user": dict(user) if user else None,
        "donor": dict(donor) if donor else None
    }
