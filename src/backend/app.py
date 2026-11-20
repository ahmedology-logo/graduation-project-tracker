"""تخرُّج - باك اند Flask بسيط (SQLite). تشغيل:  python app.py"""
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, abort, g, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for, flash)

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "instance", "takharruj.db")
UPLOADS = os.path.join(BASE, "instance", "uploads")
os.makedirs(UPLOADS, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY", "takharruj-dev-key")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

# ------------------------------------------------------------------ الحسابات
STUDENTS = [
    ("S1001", "saad", "saad@ecu.edu.eg.local"),
    ("S1002", "eyad ", "eyad@ecu.edu.eg.local"),
    ("S1003", "Philo ", "philo@ecu.edu.eg.local"),
    ("S1004", "osama", "osama@ecu.edu.eg.local"),
    ("S1005", "ali", "ali@ecu.edu.eg.local"),
]
DOCTORS = [
    ("D01", "د. هبة الشوا", "heba@takharruj.local"),
    ("D02", "د. كريم منصور", "karim@takharruj.local"),
    ("D03", "د. منى السيد", "mona@takharruj.local"),
]
PLAN = [  # مراحل افتراضية تُنشأ عند قبول المشروع
    ("تحليل المتطلبات", 14), ("تصميم قاعدة البيانات", 28), ("الواجهات", 42),
    ("التطوير والبرمجة", 63), ("الاختبار والتوثيق", 84),
]

# ------------------------------------------------------------------ قاعدة البيانات
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT, role TEXT, email TEXT);
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT,
  supervisor_id TEXT, status TEXT DEFAULT 'pending', reject_reason TEXT,
  grade INTEGER, grade_note TEXT, grade_locked INTEGER DEFAULT 0, created_at TEXT);
CREATE TABLE IF NOT EXISTS members(project_id INTEGER, student_id TEXT, is_leader INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS milestones(
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, idx INTEGER, title TEXT, due TEXT,
  status TEXT DEFAULT 'todo', feedback TEXT, file_name TEXT, file_label TEXT, note TEXT,
  round INTEGER DEFAULT 0, submitted_at TEXT);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, sender_id TEXT, body TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, text TEXT, url TEXT, is_read INTEGER DEFAULT 0, created_at TEXT);
CREATE TABLE IF NOT EXISTS reads(user_id TEXT, channel TEXT, last_id INTEGER, PRIMARY KEY(user_id, channel));
"""


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d:
        d.close()


def q(sql, *a, one=False):
    cur = db().execute(sql, a)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def ex(sql, *a):
    cur = db().execute(sql, a)
    db().commit()
    return cur.lastrowid


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    for uid, name, email in STUDENTS:
        con.execute("INSERT OR IGNORE INTO users VALUES(?,?,?,?)", (uid, name, "student", email))
    for uid, name, email in DOCTORS:
        con.execute("INSERT OR IGNORE INTO users VALUES(?,?,?,?)", (uid, name, "doctor", email))
    con.commit()
    con.close()


# ------------------------------------------------------------------ مساعدات
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def notify(user_id, text, url="#"):
    ex("INSERT INTO notifications(user_id,text,url,created_at) VALUES(?,?,?,?)", user_id, text, url, now())


def grade_label(n):
    if n is None:
        return "-"
    return "ممتاز" if n >= 90 else "جيد جداً" if n >= 80 else "جيد" if n >= 70 else "مقبول" if n >= 60 else "راسب"


def current_user():
    uid = session.get("uid")
    return q("SELECT * FROM users WHERE id=?", uid, one=True) if uid else None


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrap(*a, **kw):
            u = current_user()
            if not u:
                return redirect(url_for("login"))
            if role and u["role"] != role:
                return redirect(url_for("home_redirect"))
            g.user = u
            return fn(*a, **kw)
        return wrap
    return deco


def student_project(sid):
    """مشروع الطالب الحالي (آخر مشروع غير مرفوض)."""
    return q("""SELECT p.* FROM projects p JOIN members m ON m.project_id=p.id
                WHERE m.student_id=? AND p.status!='rejected' ORDER BY p.id DESC LIMIT 1""", sid, one=True)


def last_rejected(sid):
    return q("""SELECT p.* FROM projects p JOIN members m ON m.project_id=p.id
                WHERE m.student_id=? AND p.status='rejected' ORDER BY p.id DESC LIMIT 1""", sid, one=True)


def team_of(pid):
    return q("""SELECT u.*, m.is_leader FROM members m JOIN users u ON u.id=m.student_id
                WHERE m.project_id=? ORDER BY m.is_leader DESC, u.name""", pid)


def progress_of(pid):
    ms = q("SELECT status FROM milestones WHERE project_id=?", pid)
    if not ms:
        return 0
    return round(100 * sum(1 for m in ms if m["status"] == "approved") / len(ms))


def can_chat(user, channel):
    """مين يقدر يدخل أي قناة."""
    kind, _, rest = channel.partition(":")
    if kind == "team":  # نقاش الفريق خاص بالطلاب فقط
        return user["role"] == "student" and q(
            "SELECT 1 FROM members WHERE project_id=? AND student_id=?", rest, user["id"], one=True) is not None
    if kind == "dm":  # محادثة مباشرة بين طالب ودكتور
        a, _, b = rest.partition(":")
        if user["id"] not in (a, b):
            return False
        other = q("SELECT role FROM users WHERE id=?", b if user["id"] == a else a, one=True)
        return other is not None and other["role"] != user["role"]
    return False


def dm_channel(a, b):
    return "dm:" + ":".join(sorted([a, b]))


@app.context_processor
def inject():
    u = current_user()
    ctx = {"me": u, "grade_label": grade_label}
    if u:
        ctx["unread"] = q("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", u["id"], one=True)["c"]
        if u["role"] == "student":
            p = student_project(u["id"])
            ctx["side_project"] = p
            ctx["side_progress"] = progress_of(p["id"]) if p and p["status"] == "approved" else None
        else:
            ctx["pending_count"] = q("SELECT COUNT(*) c FROM projects WHERE supervisor_id=? AND status='pending'",
                                     u["id"], one=True)["c"]
            ctx["review_count"] = q("""SELECT COUNT(*) c FROM milestones ms JOIN projects p ON p.id=ms.project_id
                                       WHERE p.supervisor_id=? AND ms.status='submitted'""", u["id"], one=True)["c"]
    return ctx


# ------------------------------------------------------------------ الدخول
@app.route("/")
def landing():
    return send_from_directory(os.path.join(BASE, "static", "site"), "index.html")


@app.route("/_next/<path:p>")
def next_assets(p):
    return send_from_directory(os.path.join(BASE, "static", "site", "_next"), p)


@app.route("/api/send", methods=["POST"])
def contact_send():
    """فورم التواصل في اللاندنج: يُحفظ في ملف نصي بسيط."""
    data = request.get_json(silent=True) or {}
    with open(os.path.join(BASE, "instance", "contact_messages.txt"), "a", encoding="utf-8") as f:
        f.write(f"{now()} | {data}\n")
    return jsonify(ok=True)


@app.route("/site/<path:p>")
def site_files(p):
    return send_from_directory(os.path.join(BASE, "static", "site"), p)


@app.route("/home")
def home_redirect():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    return redirect(url_for("student_dashboard" if u["role"] == "student" else "doctor_dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uid = request.form.get("identify", "").strip().upper()
        u = q("SELECT * FROM users WHERE id=?", uid, one=True)
        if not u:
            return render_template("login.html", fail="الرقم غير مسجّل في النظام، راجع رقمك وحاول مرة أخرى.",
                                   students=STUDENTS, doctors=DOCTORS)
        session["uid"] = u["id"]
        return redirect(url_for("home_redirect"))
    if current_user():
        return redirect(url_for("home_redirect"))
    return render_template("login.html", fail=None, students=STUDENTS, doctors=DOCTORS)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------ الطالب
@app.route("/student")
@login_required("student")
def student_dashboard():
    p = student_project(g.user["id"])
    ctx = {"project": p, "rejected": None}
    if p:
        ctx.update(team=team_of(p["id"]), progress=progress_of(p["id"]),
                   sup=q("SELECT * FROM users WHERE id=?", p["supervisor_id"], one=True),
                   milestones=q("SELECT * FROM milestones WHERE project_id=? ORDER BY idx", p["id"]),
                   is_leader=bool(q("SELECT 1 FROM members WHERE project_id=? AND student_id=? AND is_leader=1",
                                    p["id"], g.user["id"], one=True)))
    else:
        ctx["rejected"] = last_rejected(g.user["id"])
    return render_template("student/dashboard.html", **ctx)


@app.route("/student/team")
@login_required("student")
def student_team():
    p = student_project(g.user["id"])
    if p:
        return redirect(url_for("student_dashboard"))
    free = q("""SELECT * FROM users WHERE role='student' AND id!=? AND id NOT IN
                (SELECT m.student_id FROM members m JOIN projects p ON p.id=m.project_id WHERE p.status!='rejected')
                ORDER BY name""", g.user["id"])
    docs = q("SELECT * FROM users WHERE role='doctor' ORDER BY name")
    return render_template("student/project_form.html", free=free, docs=docs, rejected=last_rejected(g.user["id"]))


@app.route("/student/project", methods=["POST"])
@login_required("student")
def student_create_project():
    if student_project(g.user["id"]):
        return redirect(url_for("student_dashboard"))
    title = request.form.get("title", "").strip()
    desc = request.form.get("description", "").strip()
    sup = request.form.get("supervisor_id", "")
    mates = request.form.getlist("members")
    if not title or not q("SELECT 1 FROM users WHERE id=? AND role='doctor'", sup, one=True):
        flash("اكتب عنوان المشروع واختر مشرفاً.", "danger")
        return redirect(url_for("student_team"))
    if len(mates) > 4:
        flash("الحد الأقصى لأعضاء الفريق 5 طلاب.", "danger")
        return redirect(url_for("student_team"))
    pid = ex("INSERT INTO projects(title,description,supervisor_id,created_at) VALUES(?,?,?,?)",
             title, desc, sup, now())
    ex("INSERT INTO members VALUES(?,?,1)", pid, g.user["id"])
    for m in mates:
        busy = q("""SELECT 1 FROM members m JOIN projects p ON p.id=m.project_id
                    WHERE m.student_id=? AND p.status!='rejected' AND p.id!=?""", m, pid, one=True)
        if not busy and q("SELECT 1 FROM users WHERE id=? AND role='student'", m, one=True):
            ex("INSERT INTO members VALUES(?,?,0)", pid, m)
            notify(m, f"أضافك {g.user['name']} إلى فريق «{title}»", url_for("student_dashboard"))
    notify(sup, f"طلب إشراف جديد: «{title}»", url_for("doctor_requests"))
    flash("أُرسل طلبك إلى المشرف، سيصلك إشعار عند الرد.", "success")
    return redirect(url_for("student_dashboard"))


@app.route("/student/milestone/<int:mid>/submit", methods=["POST"])
@login_required("student")
def student_submit(mid):
    ms = q("SELECT * FROM milestones WHERE id=?", mid, one=True) or abort(404)
    if not q("SELECT 1 FROM members WHERE project_id=? AND student_id=?", ms["project_id"], g.user["id"], one=True):
        abort(403)
    if ms["status"] in ("submitted", "approved"):
        flash("لا يمكن التسليم الآن.", "danger")
        return redirect(url_for("student_dashboard") + "#milestones")
    f = request.files.get("file")
    fname, label = ms["file_name"], ms["file_label"]
    if f and f.filename:
        label = f.filename
        fname = uuid.uuid4().hex + os.path.splitext(f.filename)[1][:10]
        f.save(os.path.join(UPLOADS, fname))
    elif not fname:
        flash("ارفع ملف المرحلة أولاً.", "danger")
        return redirect(url_for("student_dashboard") + "#milestones")
    ex("""UPDATE milestones SET status='submitted', file_name=?, file_label=?, note=?, round=round+1,
          submitted_at=? WHERE id=?""", fname, label, request.form.get("note", "").strip(), now(), mid)
    proj = q("SELECT * FROM projects WHERE id=?", ms["project_id"], one=True)
    notify(proj["supervisor_id"], f"تسليم جديد: «{ms['title']}» في «{proj['title']}»",
           url_for("doctor_project", pid=proj["id"]))
    flash("تم التسليم، بانتظار مراجعة المشرف.", "success")
    return redirect(url_for("student_dashboard") + "#milestones")


# ------------------------------------------------------------------ الدكتور
@app.route("/doctor")
@login_required("doctor")
def doctor_dashboard():
    uid = g.user["id"]
    pending = q("SELECT * FROM projects WHERE supervisor_id=? AND status='pending' ORDER BY id", uid)
    reviews = q("""SELECT ms.*, p.title ptitle, p.id pid FROM milestones ms JOIN projects p ON p.id=ms.project_id
                   WHERE p.supervisor_id=? AND ms.status='submitted' ORDER BY ms.submitted_at""", uid)
    projects = q("SELECT * FROM projects WHERE supervisor_id=? AND status='approved' ORDER BY id", uid)
    prog = {p["id"]: progress_of(p["id"]) for p in projects}
    teams = {p["id"]: team_of(p["id"]) for p in list(projects) + list(pending)}
    return render_template("doctor/dashboard.html", pending=pending, reviews=reviews, projects=projects,
                           prog=prog, teams=teams)


@app.route("/doctor/requests")
@login_required("doctor")
def doctor_requests():
    pending = q("SELECT * FROM projects WHERE supervisor_id=? AND status='pending' ORDER BY id", g.user["id"])
    return render_template("doctor/requests.html", pending=pending, teams={p["id"]: team_of(p["id"]) for p in pending})


@app.route("/doctor/request/<int:pid>", methods=["POST"])
@login_required("doctor")
def doctor_decide(pid):
    p = q("SELECT * FROM projects WHERE id=? AND supervisor_id=? AND status='pending'", pid, g.user["id"], one=True) or abort(404)
    members = team_of(pid)
    if request.form.get("decision") == "accept":
        ex("UPDATE projects SET status='approved' WHERE id=?", pid)
        today = datetime.now()
        for i, (title, days) in enumerate(PLAN, 1):
            ex("INSERT INTO milestones(project_id,idx,title,due) VALUES(?,?,?,?)",
               pid, i, title, (today + timedelta(days=days)).strftime("%Y-%m-%d"))
        for m in members:
            notify(m["id"], f"وافق {g.user['name']} على الإشراف على «{p['title']}» 🎉", url_for("student_dashboard"))
        flash("تم قبول المشروع وإنشاء خطة المراحل.", "success")
    else:
        reason = request.form.get("reason", "").strip()
        ex("UPDATE projects SET status='rejected', reject_reason=? WHERE id=?", reason, pid)
        for m in members:
            notify(m["id"], f"رُفض طلب «{p['title']}»" + (f": {reason}" if reason else ""), url_for("student_team"))
        flash("تم رفض الطلب وإبلاغ الفريق.", "success")
    return redirect(url_for("doctor_requests"))


@app.route("/doctor/project/<int:pid>")
@login_required("doctor")
def doctor_project(pid):
    p = q("SELECT * FROM projects WHERE id=? AND supervisor_id=? AND status='approved'", pid, g.user["id"], one=True) or abort(404)
    return render_template("doctor/project.html", p=p, team=team_of(pid), progress=progress_of(pid),
                           milestones=q("SELECT * FROM milestones WHERE project_id=? ORDER BY idx", pid))


@app.route("/doctor/milestone/<int:mid>/review", methods=["POST"])
@login_required("doctor")
def doctor_review(mid):
    ms = q("SELECT * FROM milestones WHERE id=?", mid, one=True) or abort(404)
    p = q("SELECT * FROM projects WHERE id=? AND supervisor_id=?", ms["project_id"], g.user["id"], one=True) or abort(403)
    if ms["status"] != "submitted":
        return redirect(url_for("doctor_project", pid=p["id"]))
    fb = request.form.get("feedback", "").strip()
    if request.form.get("decision") == "approve":
        ex("UPDATE milestones SET status='approved', feedback=? WHERE id=?", fb, mid)
        msg = f"اعتُمدت مرحلة «{ms['title']}» ✓"
    else:
        if not fb:
            flash("اكتب سبب طلب التعديل.", "danger")
            return redirect(url_for("doctor_project", pid=p["id"]))
        ex("UPDATE milestones SET status='revise', feedback=? WHERE id=?", fb, mid)
        msg = f"مطلوب تعديل في «{ms['title']}»: {fb}"
    for m in team_of(p["id"]):
        notify(m["id"], msg, url_for("student_dashboard") + "#milestones")
    flash("تم حفظ قرارك.", "success")
    return redirect(url_for("doctor_project", pid=p["id"]))


@app.route("/doctor/project/<int:pid>/grade", methods=["POST"])
@login_required("doctor")
def doctor_grade(pid):
    p = q("SELECT * FROM projects WHERE id=? AND supervisor_id=?", pid, g.user["id"], one=True) or abort(404)
    if p["grade_locked"]:
        flash("الدرجة معتمدة ومقفلة.", "danger")
        return redirect(url_for("doctor_project", pid=pid))
    try:
        score = max(0, min(100, int(request.form.get("grade", ""))))
    except ValueError:
        flash("أدخل درجة صحيحة من 0 إلى 100.", "danger")
        return redirect(url_for("doctor_project", pid=pid))
    lock = 1 if request.form.get("lock") else 0
    ex("UPDATE projects SET grade=?, grade_note=?, grade_locked=? WHERE id=?",
       score, request.form.get("note", "").strip(), lock, pid)
    if lock:
        for m in team_of(pid):
            notify(m["id"], f"اعتُمدت درجة مشروعك: {score}/100 ({grade_label(score)})", url_for("student_dashboard"))
    flash("تم اعتماد الدرجة." if lock else "تم حفظ الدرجة.", "success")
    return redirect(url_for("doctor_project", pid=pid))


# ------------------------------------------------------------------ الملفات والإشعارات
@app.route("/files/<name>")
@login_required()
def get_file(name):
    ms = q("SELECT * FROM milestones WHERE file_name=?", name, one=True) or abort(404)
    p = q("SELECT * FROM projects WHERE id=?", ms["project_id"], one=True)
    ok = p["supervisor_id"] == g.user["id"] or q(
        "SELECT 1 FROM members WHERE project_id=? AND student_id=?", p["id"], g.user["id"], one=True)
    if not ok:
        abort(403)
    return send_from_directory(UPLOADS, name, as_attachment=True, download_name=ms["file_label"] or name)


@app.route("/notifications")
@login_required()
def notifications():
    items = q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 60", g.user["id"])
    ex("UPDATE notifications SET is_read=1 WHERE user_id=?", g.user["id"])
    return render_template("notifications.html", items=items)


# ------------------------------------------------------------------ الشات
@app.route("/discussion")
@login_required()
def discussion():
    u = g.user
    contacts = q("SELECT * FROM users WHERE role=? ORDER BY name", "doctor" if u["role"] == "student" else "student")
    chans = []
    if u["role"] == "student":
        p = student_project(u["id"])
        if p:
            chans.append({"key": f"team:{p['id']}", "title": "نقاش الفريق", "sub": "خاص بالطلاب فقط، لا يراه المشرف",
                          "icon": "ti-users-group", "private": True})
    for c in contacts:
        key = dm_channel(u["id"], c["id"])
        last = q("SELECT MAX(id) m FROM messages WHERE channel=?", key, one=True)["m"] or 0
        seen = q("SELECT last_id FROM reads WHERE user_id=? AND channel=?", u["id"], key, one=True)
        unread = q("SELECT COUNT(*) c FROM messages WHERE channel=? AND id>? AND sender_id!=?",
                   key, seen["last_id"] if seen else 0, u["id"], one=True)["c"]
        chans.append({"key": key, "title": c["name"], "sub": "مشرف أكاديمي" if c["role"] == "doctor" else f"طالب · {c['id']}",
                      "icon": "ti-user", "unread": unread})
    active = request.args.get("c") or (chans[0]["key"] if chans else None)
    if active and not can_chat(u, active):
        abort(403)
    title = next((c["title"] for c in chans if c["key"] == active), "")
    return render_template("chat.html", chans=chans, active=active, title=title)


@app.route("/api/chat/<path:channel>", methods=["GET", "POST"])
@login_required()
def chat_api(channel):
    if not can_chat(g.user, channel):
        abort(403)
    if request.method == "POST":
        body = (request.get_json(silent=True) or {}).get("body", "").strip()
        if body:
            ex("INSERT INTO messages(channel,sender_id,body,created_at) VALUES(?,?,?,?)",
               channel, g.user["id"], body[:2000], now())
            if channel.startswith("dm:"):
                a, b = channel[3:].split(":")
                other = b if g.user["id"] == a else a
                notify(other, f"رسالة جديدة من {g.user['name']}", url_for("discussion", c=channel))
            else:
                pid = channel.split(":")[1]
                for m in team_of(pid):
                    if m["id"] != g.user["id"]:
                        notify(m["id"], f"رسالة جديدة في نقاش الفريق من {g.user['name']}", url_for("discussion", c=channel))
    after = int(request.args.get("after", 0))
    rows = q("""SELECT m.id, m.body, m.created_at, m.sender_id, u.name, u.role FROM messages m
                JOIN users u ON u.id=m.sender_id WHERE m.channel=? AND m.id>? ORDER BY m.id""", channel, after)
    if rows:
        ex("INSERT OR REPLACE INTO reads VALUES(?,?,?)", g.user["id"], channel, rows[-1]["id"])
    return jsonify([{**dict(r), "mine": r["sender_id"] == g.user["id"]} for r in rows])


@app.route("/api/live")
@login_required()
def live():
    """عدّادات الإشعارات (تُستعمل للتحديث التلقائي)."""
    return jsonify({"unread": q("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0",
                                g.user["id"], one=True)["c"]})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
