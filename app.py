import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "data" / "atelierflow.db"))
UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", BASE_DIR / "data" / "uploads"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "atelierflow-change-me-in-production"),
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,
)

INITIAL_USERS = [
    ("Lucien", "000", "Responsable atelier", "LZ", "#f59e0b"),
    ("Arnaud", "111", "Chef de chantier", "AR", "#0ea5e9"),
    ("Justin", "222", "Direction", "JU", "#8b5cf6"),
    ("David", "333", "Menuisier", "DA", "#10b981"),
]
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "doc", "docx", "xls", "xlsx", "txt", "zip"}


def db():
    connection = sqlite3.connect(DB_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
          role TEXT NOT NULL, initials TEXT, color TEXT, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS projects (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, client TEXT,
          location TEXT, description TEXT, status TEXT DEFAULT 'Préparation',
          progress INTEGER DEFAULT 0, due_date TEXT, created_by INTEGER,
          created_at TEXT NOT NULL, FOREIGN KEY(created_by) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,
          author_id INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(author_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,
          title TEXT NOT NULL, assignee_id INTEGER, priority TEXT DEFAULT 'Normale',
          due_date TEXT, done INTEGER DEFAULT 0, created_at TEXT NOT NULL,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(assignee_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS reports (
          id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,
          author_id INTEGER NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
          hours REAL DEFAULT 0, created_at TEXT NOT NULL,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(author_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS files (
          id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,
          uploader_id INTEGER NOT NULL, original_name TEXT NOT NULL,
          stored_name TEXT NOT NULL, size INTEGER DEFAULT 0, created_at TEXT NOT NULL,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(uploader_id) REFERENCES users(id)
        );
        """)
        for index, (name, password, role, initials, color) in enumerate(INITIAL_USERS, 1):
            conn.execute(
                "INSERT OR IGNORE INTO users(id,name,password_hash,role,initials,color) VALUES(?,?,?,?,?,?)",
                (index, name, generate_password_hash(password), role, initials, color),
            )
        if conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            projects = [
                ("Rénovation Chalet Moiry", "Famille B.", "Grimentz", "Menuiseries intérieures et finitions", "En cours", 68, "2026-10-18", 1, now()),
                ("Fenêtres — Immeuble Zinal", "Régie Alpina", "Zinal", "Remplacement de 24 fenêtres", "En cours", 42, "2026-11-05", 1, now()),
                ("Agencement Restaurant", "Le Mélèze", "St-Luc", "Bar, rangements et habillages", "Préparation", 15, "2026-12-12", 1, now()),
            ]
            conn.executemany("INSERT INTO projects(name,client,location,description,status,progress,due_date,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)", projects)
            conn.execute("INSERT INTO messages(project_id,author_id,body,created_at) VALUES(1,1,?,?)", ("Bienvenue sur le fil partagé du chantier. Ajoutez ici les informations utiles à toute l’équipe.", now()))
            conn.execute("INSERT INTO tasks(project_id,title,assignee_id,priority,due_date,created_at) VALUES(1,?,2,'Haute','2026-09-10',?)", ("Valider les mesures de l’escalier", now()))


init_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def current_user():
    if not session.get("user_id"):
        return None
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()


@app.context_processor
def inject_globals():
    return {"current_user": current_user()}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name", "")
        password = request.form.get("password", "")
        with db() as conn:
            user = conn.execute("SELECT * FROM users WHERE name=? AND active=1", (name,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Nom ou code incorrect.", "error")
    return render_template("login.html", users=INITIAL_USERS)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def dashboard():
    with db() as conn:
        projects = conn.execute("""SELECT p.*, COUNT(DISTINCT t.id) task_count,
          SUM(CASE WHEN t.done=1 THEN 1 ELSE 0 END) done_count
          FROM projects p LEFT JOIN tasks t ON t.project_id=p.id GROUP BY p.id ORDER BY p.id DESC""").fetchall()
        tasks = conn.execute("""SELECT t.*, p.name project_name, u.name assignee_name, u.color assignee_color
          FROM tasks t JOIN projects p ON p.id=t.project_id LEFT JOIN users u ON u.id=t.assignee_id
          WHERE t.done=0 ORDER BY CASE t.priority WHEN 'Urgente' THEN 0 WHEN 'Haute' THEN 1 ELSE 2 END, t.due_date LIMIT 8""").fetchall()
        stats = {
            "projects": conn.execute("SELECT COUNT(*) FROM projects WHERE status!='Terminé'").fetchone()[0],
            "tasks": conn.execute("SELECT COUNT(*) FROM tasks WHERE done=0").fetchone()[0],
            "reports": conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
            "files": conn.execute("SELECT COUNT(*) FROM files").fetchone()[0],
        }
    return render_template("dashboard.html", projects=projects, tasks=tasks, stats=stats)


@app.get("/projects")
@login_required
def projects_list():
    return redirect(url_for("dashboard"))


@app.post("/projects")
@login_required
def create_project():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Le nom du projet est obligatoire.", "error")
        return redirect(url_for("dashboard"))
    with db() as conn:
        cursor = conn.execute("""INSERT INTO projects(name,client,location,description,status,progress,due_date,created_by,created_at)
          VALUES(?,?,?,?,?,?,?,?,?)""", (name, request.form.get("client"), request.form.get("location"), request.form.get("description"), "Préparation", 0, request.form.get("due_date"), session["user_id"], now()))
        project_id = cursor.lastrowid
    return redirect(url_for("project", project_id=project_id))


@app.get("/projects/<int:project_id>")
@login_required
def project(project_id):
    with db() as conn:
        project_row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project_row: abort(404)
        users = conn.execute("SELECT * FROM users WHERE active=1 ORDER BY name").fetchall()
        tasks = conn.execute("""SELECT t.*,u.name assignee_name,u.color assignee_color FROM tasks t
          LEFT JOIN users u ON u.id=t.assignee_id WHERE t.project_id=? ORDER BY t.done,t.id DESC""", (project_id,)).fetchall()
        messages = conn.execute("""SELECT m.*,u.name author_name,u.initials,u.color FROM messages m
          JOIN users u ON u.id=m.author_id WHERE m.project_id=? ORDER BY m.id""", (project_id,)).fetchall()
        reports = conn.execute("""SELECT r.*,u.name author_name FROM reports r JOIN users u ON u.id=r.author_id
          WHERE r.project_id=? ORDER BY r.id DESC""", (project_id,)).fetchall()
        files = conn.execute("""SELECT f.*,u.name uploader_name FROM files f JOIN users u ON u.id=f.uploader_id
          WHERE f.project_id=? ORDER BY f.id DESC""", (project_id,)).fetchall()
    return render_template("project.html", project=project_row, users=users, tasks=tasks, messages=messages, reports=reports, files=files)


@app.post("/projects/<int:project_id>/update")
@login_required
def update_project(project_id):
    progress = max(0, min(100, request.form.get("progress", 0, type=int)))
    with db() as conn:
        conn.execute("UPDATE projects SET status=?,progress=?,due_date=? WHERE id=?", (request.form.get("status"), progress, request.form.get("due_date"), project_id))
    flash("Projet mis à jour.", "success")
    return redirect(url_for("project", project_id=project_id))


@app.post("/projects/<int:project_id>/tasks")
@login_required
def add_task(project_id):
    title = request.form.get("title", "").strip()
    if title:
        with db() as conn:
            conn.execute("INSERT INTO tasks(project_id,title,assignee_id,priority,due_date,created_at) VALUES(?,?,?,?,?,?)", (project_id, title, request.form.get("assignee_id") or None, request.form.get("priority"), request.form.get("due_date"), now()))
    return redirect(url_for("project", project_id=project_id) + "#tasks")


@app.post("/tasks/<int:task_id>/toggle")
@login_required
def toggle_task(task_id):
    with db() as conn:
        task = conn.execute("SELECT project_id,done FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not task: abort(404)
        conn.execute("UPDATE tasks SET done=? WHERE id=?", (0 if task["done"] else 1, task_id))
    return redirect(request.referrer or url_for("project", project_id=task["project_id"]))


@app.post("/projects/<int:project_id>/reports")
@login_required
def add_report(project_id):
    title, body = request.form.get("title", "").strip(), request.form.get("body", "").strip()
    if title and body:
        with db() as conn:
            conn.execute("INSERT INTO reports(project_id,author_id,title,body,hours,created_at) VALUES(?,?,?,?,?,?)", (project_id, session["user_id"], title, body, request.form.get("hours", 0, type=float), now()))
    return redirect(url_for("project", project_id=project_id) + "#reports")


@app.route("/api/projects/<int:project_id>/messages", methods=["GET", "POST"])
@login_required
def project_messages(project_id):
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        body = str(payload.get("body", "")).strip()
        if not body: return jsonify({"error": "Message vide"}), 400
        with db() as conn:
            conn.execute("INSERT INTO messages(project_id,author_id,body,created_at) VALUES(?,?,?,?)", (project_id, session["user_id"], body, now()))
    with db() as conn:
        rows = conn.execute("""SELECT m.id,m.body,m.created_at,u.name author_name,u.initials,u.color
          FROM messages m JOIN users u ON u.id=m.author_id WHERE m.project_id=? ORDER BY m.id""", (project_id,)).fetchall()
    return jsonify([dict(row) for row in rows])


@app.post("/projects/<int:project_id>/files")
@login_required
def upload_file(project_id):
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        flash("Choisissez un fichier.", "error")
    else:
        safe = secure_filename(uploaded.filename)
        extension = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
        if extension not in ALLOWED_EXTENSIONS:
            flash("Format de fichier non autorisé.", "error")
        else:
            stored = f"{uuid.uuid4().hex}_{safe}"
            uploaded.save(UPLOAD_FOLDER / stored)
            with db() as conn:
                conn.execute("INSERT INTO files(project_id,uploader_id,original_name,stored_name,size,created_at) VALUES(?,?,?,?,?,?)", (project_id, session["user_id"], uploaded.filename, stored, (UPLOAD_FOLDER / stored).stat().st_size, now()))
    return redirect(url_for("project", project_id=project_id) + "#files")


@app.get("/files/<int:file_id>")
@login_required
def download_file(file_id):
    with db() as conn:
        item = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
    if not item: abort(404)
    return send_from_directory(UPLOAD_FOLDER, item["stored_name"], as_attachment=True, download_name=item["original_name"])


@app.get("/team")
@login_required
def team():
    with db() as conn:
        users = conn.execute("""SELECT u.*,COUNT(t.id) open_tasks FROM users u LEFT JOIN tasks t
          ON t.assignee_id=u.id AND t.done=0 WHERE u.active=1 GROUP BY u.id ORDER BY u.id""").fetchall()
    return render_template("team.html", users=users)


@app.errorhandler(413)
def too_large(_):
    flash("Le fichier dépasse la limite de 20 Mo.", "error")
    return redirect(request.referrer or url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=os.environ.get("FLASK_DEBUG") == "1")
