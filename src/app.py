import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "dev-secret-key"
DATABASE_PATH = Path(__file__).resolve().parent.parent / "app.db"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'public'
        )
        """
    )
    ensure_posts_visibility_column(conn)
    conn.commit()
    conn.close()


def ensure_posts_visibility_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(posts)").fetchall()
    has_visibility_column = any(column["name"] == "visibility" for column in columns)
    if not has_visibility_column:
        conn.execute(
            "ALTER TABLE posts ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'"
        )


def create_user(username: str, password: str) -> bool:
    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user_by_username(username: str) -> sqlite3.Row | None:
    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()
    return user


def create_post(username: str, title: str, body: str, visibility: str) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False

    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO posts (user_id, title, body, created_at, visibility)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user["id"], title, body, created_at, visibility),
    )
    conn.commit()
    conn.close()
    return True


def get_posts_for_user(username: str) -> list[sqlite3.Row]:
    user = get_user_by_username(username)
    if not user:
        return []

    conn = get_db_connection()
    posts = conn.execute(
        """
        SELECT id, title, body, created_at, visibility
        FROM posts
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    conn.close()
    return posts


def get_public_posts() -> list[sqlite3.Row]:
    conn = get_db_connection()
    posts = conn.execute(
        """
        SELECT posts.id, posts.title, posts.body, posts.created_at, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.visibility = 'public'
        ORDER BY posts.created_at DESC
        """
    ).fetchall()
    conn.close()
    return posts


def get_public_post_by_id(post_id: int) -> sqlite3.Row | None:
    conn = get_db_connection()
    post = conn.execute(
        """
        SELECT posts.id, posts.title, posts.body, posts.created_at, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ? AND posts.visibility = 'public'
        """,
        (post_id,),
    ).fetchone()
    conn.close()
    return post


def get_public_posts_for_username(username: str) -> list[sqlite3.Row] | None:
    user = get_user_by_username(username)
    if not user:
        return None

    conn = get_db_connection()
    posts = conn.execute(
        """
        SELECT id, title, body, created_at
        FROM posts
        WHERE user_id = ? AND visibility = 'public'
        ORDER BY created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    conn.close()
    return posts


def is_logged_in() -> bool:
    return "username" in session


init_db()


@app.route("/")
def home() -> str:
    return render_template("home.html", posts=get_public_posts())


@app.route("/about")
def about() -> str:
    return render_template("about.html")


@app.route("/features")
def features():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("features.html")


@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template(
        "dashboard.html",
        username=session["username"],
        blog_posts=get_posts_for_user(session["username"]),
    )


@app.route("/posts/new", methods=["GET", "POST"])
def new_post():
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        visibility = request.form.get("visibility", "public")
        if visibility not in {"public", "private"}:
            visibility = "public"

        if not title or not body:
            flash("Title and body are required.")
            return redirect(url_for("new_post"))

        create_post(session["username"], title, body, visibility)
        flash("Post created.")
        return redirect(url_for("dashboard"))

    return render_template("new_post.html")


@app.route("/posts/<int:post_id>")
def post_detail(post_id: int):
    post = get_public_post_by_id(post_id)
    if not post:
        abort(404)
    return render_template("post_detail.html", post=post)


@app.route("/users/<username>")
def user_blog(username: str):
    posts = get_public_posts_for_username(username)
    if posts is None:
        abort(404)
    return render_template("user_blog.html", username=username, posts=posts)


@app.route("/contact")
def contact() -> str:
    return render_template("contact.html")


@app.route("/register")
def register() -> str:
    return render_template("register.html")


@app.route("/register/submit", methods=["POST"])
def submit_registration() -> str:
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        flash("Username and password are required.")
        return redirect(url_for("register"))

    if not create_user(username, password):
        flash("Username already exists.")
        return redirect(url_for("register"))

    return redirect(url_for("login"))


@app.route("/login")
def login() -> str:
    return render_template("login.html")


@app.route("/login/submit", methods=["POST"])
def submit_login() -> str:
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = get_user_by_username(username)

    if user and check_password_hash(user["password_hash"], password):
        session["username"] = username
        return redirect(url_for("dashboard"))

    flash("Invalid username or password.")
    return redirect(url_for("login"))


@app.route("/logout")
def logout() -> str:
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
