"""
DEEPFACE-ASD  -  ASD-related pattern screening website (academic research prototype)

Start the website with:      python app.py
Then open:                   http://127.0.0.1:5000
"""
import functools
import os
import re
import secrets
import time
from datetime import datetime

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template, request,
                   send_file, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db
import ml
import reports

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR = where the database (and fallback secret key) live. On a host with a
# persistent disk, point this at the disk (e.g. /var/data).
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(BASE_DIR, "instance")
os.makedirs(DATA_DIR, exist_ok=True)

DISCLAIMER = reports.DISCLAIMER
ALLOWED_IMAGE = {"jpg", "jpeg", "png"}
ALLOWED_AUDIO = {"wav", "mp3"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB per request
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Secure cookies on the live (HTTPS) site; off for local http://127.0.0.1 use.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"


def _secret_key():
    env_key = os.environ.get("SECRET_KEY")
    if env_key:  # production: set as a private environment variable on the host
        return env_key
    path = os.path.join(DATA_DIR, "secret_key")
    if not os.path.exists(path):
        with open(path, "w") as fh:
            fh.write(secrets.token_hex(32))
    with open(path) as fh:
        return fh.read().strip()


app.secret_key = _secret_key()
app.teardown_appcontext(db.close_db)
db.init_db()
ml.load_models()


# ------------------------------------------------------------------ helpers
def now():
    return datetime.now().strftime("%d %b %Y, %H:%M")


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def protect_forms():
    if request.method == "POST":
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not sent or sent != session.get("csrf"):
            if request.path.startswith("/api/"):
                return jsonify(ok=False, error="Your session expired. Please refresh the page and try again."), 400
            flash("Your session expired. Please try again.", "error")
            return redirect(request.referrer or url_for("home"))


@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = db.get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if g.user is None:
            session.clear()


@app.context_processor
def inject_globals():
    return {"disclaimer": DISCLAIMER, "system": ml.status(), "user": g.get("user")}


def login_required(view):
    @functools.wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


def safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_failed = {}  # very small login-attempt limiter (resets when the server restarts)


def too_many_attempts(key):
    entries = [t for t in _failed.get(key, []) if time.time() - t < 300]
    _failed[key] = entries
    return len(entries) >= 5


def validate_password(pw, pw2):
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Password must contain at least one letter and one number."
    if pw != pw2:
        return "Password and confirm password do not match."
    return None


def clean_mobile(raw):
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits


# ------------------------------------------------------------------ public pages
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("dashboard"))
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("full_name", "age", "gender", "email", "mobile")}
        pw, pw2 = request.form.get("password", ""), request.form.get("confirm_password", "")
        errors = []
        if not 2 <= len(form["full_name"]) <= 80:
            errors.append("Please enter your full name (2 to 80 characters).")
        if not form["age"].isdigit() or not 1 <= int(form["age"]) <= 120:
            errors.append("Please enter a valid age between 1 and 120.")
        if form["gender"] not in ("Male", "Female", "Other", "Prefer not to say"):
            errors.append("Please select a gender option.")
        if not EMAIL_RE.match(form["email"]):
            errors.append("Please enter a valid email address.")
        mobile = clean_mobile(form["mobile"])
        if not re.fullmatch(r"\d{10}", mobile):
            errors.append("Please enter a valid 10-digit mobile number.")
        pw_err = validate_password(pw, pw2)
        if pw_err:
            errors.append(pw_err)
        if not errors:
            con = db.get_db()
            exists = con.execute("SELECT 1 FROM users WHERE email = ? OR mobile = ?",
                                 (form["email"].lower(), mobile)).fetchone()
            if exists:
                errors.append("An account with this email or mobile number already exists.")
            else:
                cur = con.execute(
                    "INSERT INTO users (full_name, age, gender, email, mobile, password_hash, created_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (form["full_name"], int(form["age"]), form["gender"], form["email"].lower(), mobile,
                     generate_password_hash(pw), now()))
                con.commit()
                session.clear()
                session["uid"] = cur.lastrowid
                flash("Welcome to DEEPFACE-ASD! Your account has been created.", "success")
                return redirect(url_for("dashboard"))
        for e in errors:
            flash(e, "error")
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        ident = request.form.get("identifier", "").strip().lower()
        pw = request.form.get("password", "")
        key = ident or request.remote_addr
        if too_many_attempts(key):
            flash("Too many failed attempts. Please wait 5 minutes and try again.", "error")
            return render_template("login.html")
        mob = clean_mobile(ident)
        row = db.get_db().execute("SELECT * FROM users WHERE email = ? OR mobile = ?", (ident, mob)).fetchone()
        if row and check_password_hash(row["password_hash"], pw):
            session.clear()
            session["uid"] = row["id"]
            _failed.pop(key, None)
            return redirect(safe_next(request.args.get("next")) or url_for("dashboard"))
        _failed.setdefault(key, []).append(time.time())
        flash("Incorrect email / mobile number or password.", "error")
    return render_template("login.html")


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    """Offline-friendly reset: the user proves identity with BOTH registered email and mobile."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        mobile = clean_mobile(request.form.get("mobile", ""))
        pw, pw2 = request.form.get("password", ""), request.form.get("confirm_password", "")
        err = validate_password(pw, pw2)
        if too_many_attempts("reset:" + email):
            flash("Too many attempts. Please wait 5 minutes and try again.", "error")
        elif err:
            flash(err, "error")
        else:
            con = db.get_db()
            row = con.execute("SELECT id FROM users WHERE email = ? AND mobile = ?", (email, mobile)).fetchone()
            if row:
                con.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(pw), row["id"]))
                con.commit()
                flash("Password updated. You can now log in.", "success")
                return redirect(url_for("login"))
            _failed.setdefault("reset:" + email, []).append(time.time())
            flash("We could not find an account with that email and mobile number together.", "error")
    return render_template("forgot.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# ------------------------------------------------------------------ user area
def history_rows(user_id, limit=None):
    sql = "SELECT * FROM screenings WHERE user_id = ? ORDER BY id DESC"
    if limit:
        sql += " LIMIT %d" % limit
    return db.get_db().execute(sql, (user_id,)).fetchall()


def summary(row):
    """One short line for the history table."""
    parts = []
    for name, st, lab in (("Face", row["image_status"], row["image_label"]), ("Voice", row["audio_status"], row["audio_label"])):
        if st == "analysed":
            parts.append("%s: %s" % (name, "pattern detected" if lab == ml.POSITIVE else "no pattern detected"))
        elif st == "demo":
            parts.append("%s: demo only" % name)
        elif st == "not_provided":
            parts.append("%s: not provided" % name)
        else:
            parts.append("%s: failed" % name)
    return " | ".join(parts)


app.jinja_env.globals["summary"] = summary


@app.route("/dashboard")
@login_required
def dashboard():
    rows = history_rows(g.user["id"], 5)
    total = db.get_db().execute("SELECT COUNT(*) c FROM screenings WHERE user_id = ?", (g.user["id"],)).fetchone()["c"]
    return render_template("dashboard.html", rows=rows, total=total)


@app.route("/screen")
@login_required
def screen():
    return render_template("screen.html")


@app.route("/api/analyse", methods=["POST"])
@login_required
def api_analyse():
    img = request.files.get("image")
    aud = request.files.get("audio")
    has_img = bool(img and img.filename)
    has_aud = bool(aud and aud.filename)
    if not (has_img or has_aud):
        return jsonify(ok=False, error="Please upload a facial image, a voice recording, or both."), 400

    image_res = {"status": "not_provided", "label": None, "prob": None}
    audio_res = {"status": "not_provided", "label": None, "prob": None}

    if has_img:
        ext = img.filename.rsplit(".", 1)[-1].lower() if "." in img.filename else ""
        if ext not in ALLOWED_IMAGE:
            return jsonify(ok=False, error="The image must be a JPG, JPEG or PNG file."), 400
        data = img.read()
        try:
            from PIL import Image
            import io
            Image.open(io.BytesIO(data)).verify()
        except Exception:
            return jsonify(ok=False, error="That file could not be read as an image. Please choose another one."), 400
        image_res = ml.analyse_image(data)

    if has_aud:
        ext = aud.filename.rsplit(".", 1)[-1].lower() if "." in aud.filename else ""
        if ext not in ALLOWED_AUDIO:
            return jsonify(ok=False, error="The voice recording must be a WAV or MP3 file."), 400
        audio_res = ml.analyse_audio(aud.read(), "." + ext)

    demo = "demo" in (image_res["status"], audio_res["status"])
    analysed = "analysed" in (image_res["status"], audio_res["status"])
    mode = "trained" if analysed and not demo else ("demo" if demo and not analysed else "mixed")

    subject_name = (request.form.get("subject_name") or "").strip()[:80] or None
    subject_age = (request.form.get("subject_age") or "").strip()[:10] or None
    con = db.get_db()
    cur = con.execute(
        "INSERT INTO screenings (user_id, created_at, subject_name, subject_age, image_status, image_label, image_prob,"
        " audio_status, audio_label, audio_prob, combined_status, mode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (g.user["id"], now(), subject_name, subject_age,
         image_res["status"], image_res["label"], image_res["prob"],
         audio_res["status"], audio_res["label"], audio_res["prob"], "not_available", mode))
    con.commit()
    return jsonify(ok=True, redirect=url_for("result", sid=cur.lastrowid))


def get_screening_or_404(sid):
    row = db.get_db().execute("SELECT * FROM screenings WHERE id = ? AND user_id = ?", (sid, g.user["id"])).fetchone()
    if row is None:
        abort(404)
    return row


@app.route("/results/<int:sid>")
@login_required
def result(sid):
    row = get_screening_or_404(sid)
    return render_template(
        "result.html", s=row, metrics=ml.load_metrics(), positive=ml.POSITIVE,
        conf_image=ml.confidence_of_prediction(row["image_label"], row["image_prob"]),
        conf_audio=ml.confidence_of_prediction(row["audio_label"], row["audio_prob"]))


@app.route("/history")
@login_required
def history():
    return render_template("history.html", rows=history_rows(g.user["id"]))


@app.route("/history/<int:sid>/delete", methods=["POST"])
@login_required
def delete_screening(sid):
    get_screening_or_404(sid)
    con = db.get_db()
    con.execute("DELETE FROM screenings WHERE id = ? AND user_id = ?", (sid, g.user["id"]))
    con.commit()
    flash("Screening record deleted.", "info")
    return redirect(url_for("history"))


@app.route("/report/<int:sid>.pdf")
@login_required
def report_pdf(sid):
    row = get_screening_or_404(sid)
    buf = reports.build_pdf(
        row, g.user,
        ml.confidence_of_prediction(row["image_label"], row["image_prob"]),
        ml.confidence_of_prediction(row["audio_label"], row["audio_prob"]),
        ml.load_metrics())
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                     download_name="DEEPFACE-ASD_report_%d.pdf" % sid)


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, message="We could not find that page."), 404


@app.errorhandler(413)
def too_large(_e):
    return jsonify(ok=False, error="The files are too large. Please keep the total below 25 MB."), 413


@app.errorhandler(500)
def server_error(_e):
    return render_template("error.html", code=500, message="Something went wrong on our side."), 500


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=False)
