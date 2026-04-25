import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import bleach
import markdown
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "dev-secret-key"
DATABASE_PATH = Path(__file__).resolve().parent.parent / "app.db"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def render_markdown(text: str) -> Markup:
    raw_html = markdown.markdown(text or "")
    clean_html = bleach.clean(
        raw_html,
        tags=[
            "p",
            "h1",
            "h2",
            "h3",
            "strong",
            "em",
            "ul",
            "ol",
            "li",
            "a",
            "blockquote",
            "code",
            "pre",
            "br",
        ],
        attributes={"a": ["href", "title"]},
    )
    return Markup(clean_html)


def init_db() -> None:
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            bio TEXT NOT NULL DEFAULT ''
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
            visibility TEXT NOT NULL DEFAULT 'public',
            status TEXT NOT NULL DEFAULT 'draft',
            tags TEXT NOT NULL DEFAULT ''
        )
        """
    )
    ensure_posts_visibility_column(conn)
    ensure_posts_status_column(conn)
    ensure_posts_tags_column(conn)
    ensure_users_display_name_column(conn)
    ensure_users_bio_column(conn)
    conn.commit()
    conn.close()


def ensure_posts_visibility_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(posts)").fetchall()
    has_visibility_column = any(column["name"] == "visibility" for column in columns)
    if not has_visibility_column:
        conn.execute(
            "ALTER TABLE posts ADD COLUMN visibility TEXT NOT NULL DEFAULT 'public'"
        )


def ensure_posts_status_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(posts)").fetchall()
    has_status_column = any(column["name"] == "status" for column in columns)
    if not has_status_column:
        conn.execute("ALTER TABLE posts ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")


def ensure_posts_tags_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(posts)").fetchall()
    has_tags_column = any(column["name"] == "tags" for column in columns)
    if not has_tags_column:
        conn.execute("ALTER TABLE posts ADD COLUMN tags TEXT NOT NULL DEFAULT ''")


def ensure_users_display_name_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(users)").fetchall()
    has_display_name_column = any(column["name"] == "display_name" for column in columns)
    if not has_display_name_column:
        conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")


def ensure_users_bio_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(users)").fetchall()
    has_bio_column = any(column["name"] == "bio" for column in columns)
    if not has_bio_column:
        conn.execute("ALTER TABLE users ADD COLUMN bio TEXT NOT NULL DEFAULT ''")


def create_user(username: str, password: str) -> bool:
    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, display_name, bio)
            VALUES (?, ?, ?, ?)
            """,
            (username, password_hash, username, ""),
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
        """
        SELECT id, username, password_hash, display_name, bio
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()
    conn.close()
    return user


def update_profile(username: str, display_name: str, bio: str) -> bool:
    display_name = display_name.strip() or username
    bio = bio.strip()
    conn = get_db_connection()
    result = conn.execute(
        "UPDATE users SET display_name = ?, bio = ? WHERE username = ?",
        (display_name, bio, username),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def get_public_profile(username: str) -> sqlite3.Row | None:
    conn = get_db_connection()
    profile = conn.execute(
        """
        SELECT
            username,
            COALESCE(NULLIF(display_name, ''), username) AS display_name,
            bio
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()
    conn.close()
    return profile


def create_post(
    username: str, title: str, body: str, visibility: str, status: str, tags: str
) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False

    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO posts (user_id, title, body, created_at, visibility, status, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user["id"], title, body, created_at, visibility, status, tags),
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
        SELECT id, title, body, created_at, visibility, status, tags
        FROM posts
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    conn.close()
    return posts


def get_public_posts(query: str = "") -> list[sqlite3.Row]:
    query = query.strip()
    conn = get_db_connection()
    if not query:
        posts = conn.execute(
            """
            SELECT posts.id, posts.title, posts.body, posts.created_at, users.username
                   , COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name
                   , posts.tags
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.visibility = 'public' AND posts.status = 'published'
            ORDER BY posts.created_at DESC
            """
        ).fetchall()
    else:
        like_query = f"%{query}%"
        posts = conn.execute(
            """
            SELECT posts.id, posts.title, posts.body, posts.created_at, users.username
                   , COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name
                   , posts.tags
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.visibility = 'public'
              AND posts.status = 'published'
              AND (posts.title LIKE ? OR posts.body LIKE ? OR posts.tags LIKE ?)
            ORDER BY posts.created_at DESC
            """,
            (like_query, like_query, like_query),
        ).fetchall()
    conn.close()
    return posts


def get_public_post_by_id(post_id: int) -> sqlite3.Row | None:
    conn = get_db_connection()
    post = conn.execute(
        """
        SELECT posts.id, posts.title, posts.body, posts.created_at, users.username,
               COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name,
               posts.tags
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ? AND posts.visibility = 'public' AND posts.status = 'published'
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
        SELECT id, title, body, created_at, tags
        FROM posts
        WHERE user_id = ? AND visibility = 'public' AND status = 'published'
        ORDER BY created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    conn.close()
    return posts


def get_public_posts_by_tag(tag: str) -> list[sqlite3.Row]:
    normalized_tag = tag.strip().lower().replace(" ", "")
    if not normalized_tag:
        return []

    like_tag = f"%,{normalized_tag},%"
    conn = get_db_connection()
    posts = conn.execute(
        """
        SELECT posts.id, posts.title, posts.body, posts.created_at, posts.tags,
               users.username,
               COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.visibility = 'public'
          AND posts.status = 'published'
          AND (',' || REPLACE(LOWER(posts.tags), ' ', '') || ',') LIKE ?
        ORDER BY posts.created_at DESC
        """,
        (like_tag,),
    ).fetchall()
    conn.close()
    return posts


def get_post_for_owner(post_id: int, username: str) -> sqlite3.Row | None:
    conn = get_db_connection()
    post = conn.execute(
        """
        SELECT posts.id, posts.title, posts.body, posts.created_at, posts.visibility, posts.status, posts.tags
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ? AND users.username = ?
        """,
        (post_id, username),
    ).fetchone()
    conn.close()
    return post


def update_post(
    post_id: int,
    username: str,
    title: str,
    body: str,
    visibility: str,
    status: str,
    tags: str,
) -> bool:
    conn = get_db_connection()
    result = conn.execute(
        """
        UPDATE posts
        SET title = ?, body = ?, visibility = ?, status = ?, tags = ?
        WHERE id = (
            SELECT posts.id
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.id = ? AND users.username = ?
        )
        """,
        (title, body, visibility, status, tags, post_id, username),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def delete_post(post_id: int, username: str) -> bool:
    conn = get_db_connection()
    result = conn.execute(
        """
        DELETE FROM posts
        WHERE id = (
            SELECT posts.id
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.id = ? AND users.username = ?
        )
        """,
        (post_id, username),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def is_logged_in() -> bool:
    return "username" in session


init_db()
app.add_template_filter(render_markdown, "markdown")


@app.route("/")
def home() -> str:
    q = request.args.get("q", "").strip()
    return render_template("home.html", posts=get_public_posts(q), q=q)


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
        tags = request.form.get("tags", "").strip()
        visibility = request.form.get("visibility", "public")
        if visibility not in {"public", "private"}:
            visibility = "public"
        status = request.form.get("status", "draft")
        if status not in {"draft", "published"}:
            status = "draft"

        if not title or not body:
            flash("Title and body are required.")
            return redirect(url_for("new_post"))

        create_post(session["username"], title, body, visibility, status, tags)
        flash("Post created.")
        return redirect(url_for("dashboard"))

    return render_template("new_post.html")


@app.route("/posts/<int:post_id>")
def post_detail(post_id: int):
    post = get_public_post_by_id(post_id)
    if not post:
        abort(404)
    return render_template("post_detail.html", post=post)


@app.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
def edit_post(post_id: int):
    if not is_logged_in():
        return redirect(url_for("login"))

    username = session["username"]
    post = get_post_for_owner(post_id, username)
    if not post:
        abort(404)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        tags = request.form.get("tags", "").strip()
        visibility = request.form.get("visibility", "public")
        if visibility not in {"public", "private"}:
            visibility = "public"
        status = request.form.get("status", "draft")
        if status not in {"draft", "published"}:
            status = "draft"

        if not title or not body:
            flash("Title and body are required.")
            return redirect(url_for("edit_post", post_id=post_id))

        update_post(post_id, username, title, body, visibility, status, tags)
        flash("Post updated.")
        return redirect(url_for("dashboard"))

    return render_template("edit_post.html", post=post)


@app.route("/posts/<int:post_id>/delete", methods=["POST"])
def delete_post_route(post_id: int):
    if not is_logged_in():
        return redirect(url_for("login"))

    username = session["username"]
    if not delete_post(post_id, username):
        abort(404)

    flash("Post deleted.")
    return redirect(url_for("dashboard"))


@app.route("/users/<username>")
def user_blog(username: str):
    profile = get_public_profile(username)
    if profile is None:
        abort(404)
    posts = get_public_posts_for_username(username)
    return render_template("user_blog.html", profile=profile, posts=posts)


@app.route("/tags/<tag>")
def tag_posts(tag: str):
    posts = get_public_posts_by_tag(tag)
    return render_template("tag_posts.html", tag=tag, posts=posts)


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not is_logged_in():
        return redirect(url_for("login"))

    username = session["username"]
    user = get_user_by_username(username)
    if not user:
        abort(404)

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        bio = request.form.get("bio", "")
        update_profile(username, display_name, bio)
        flash("Profile updated.")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)


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
