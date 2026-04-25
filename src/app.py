import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import re

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
            excerpt TEXT NOT NULL DEFAULT '',
            cover_image_url TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'public',
            status TEXT NOT NULL DEFAULT 'draft',
            tags TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            slug TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, post_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, post_id)
        )
        """
    )
    ensure_posts_visibility_column(conn)
    ensure_posts_status_column(conn)
    ensure_posts_tags_column(conn)
    ensure_posts_excerpt_column(conn)
    ensure_posts_cover_image_url_column(conn)
    ensure_posts_category_column(conn)
    ensure_posts_slug_column(conn)
    ensure_posts_slug_unique_index(conn)
    backfill_post_slugs(conn)
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


def ensure_posts_excerpt_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(posts)").fetchall()
    has_excerpt_column = any(column["name"] == "excerpt" for column in columns)
    if not has_excerpt_column:
        conn.execute("ALTER TABLE posts ADD COLUMN excerpt TEXT NOT NULL DEFAULT ''")


def ensure_posts_cover_image_url_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(posts)").fetchall()
    has_cover_image_url_column = any(column["name"] == "cover_image_url" for column in columns)
    if not has_cover_image_url_column:
        conn.execute("ALTER TABLE posts ADD COLUMN cover_image_url TEXT NOT NULL DEFAULT ''")


def ensure_posts_category_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(posts)").fetchall()
    has_category_column = any(column["name"] == "category" for column in columns)
    if not has_category_column:
        conn.execute("ALTER TABLE posts ADD COLUMN category TEXT NOT NULL DEFAULT ''")


def ensure_posts_slug_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(posts)").fetchall()
    has_slug_column = any(column["name"] == "slug" for column in columns)
    if not has_slug_column:
        conn.execute("ALTER TABLE posts ADD COLUMN slug TEXT")


def ensure_posts_slug_unique_index(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_posts_slug_unique
        ON posts(slug)
        WHERE slug IS NOT NULL AND slug != ''
        """
    )


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


def generate_slug(title: str, exclude_post_id: int | None = None) -> str:
    base_slug = re.sub(r"[^a-z0-9]+", "-", (title or "").strip().lower()).strip("-")
    if not base_slug:
        base_slug = "post"

    conn = get_db_connection()
    suffix = 1
    candidate = base_slug
    while True:
        if exclude_post_id is None:
            existing = conn.execute(
                "SELECT id FROM posts WHERE slug = ?",
                (candidate,),
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id FROM posts WHERE slug = ? AND id != ?",
                (candidate, exclude_post_id),
            ).fetchone()

        if not existing:
            conn.close()
            return candidate

        suffix += 1
        candidate = f"{base_slug}-{suffix}"


def backfill_post_slugs(conn: sqlite3.Connection) -> None:
    posts = conn.execute(
        "SELECT id, title FROM posts WHERE slug IS NULL OR slug = '' ORDER BY id ASC"
    ).fetchall()
    existing_slugs = {
        row["slug"]
        for row in conn.execute(
            "SELECT slug FROM posts WHERE slug IS NOT NULL AND slug != ''"
        ).fetchall()
    }
    for post in posts:
        base_slug = re.sub(r"[^a-z0-9]+", "-", (post["title"] or "").strip().lower()).strip("-")
        if not base_slug:
            base_slug = "post"

        slug = base_slug
        suffix = 1
        while slug in existing_slugs:
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        existing_slugs.add(slug)
        conn.execute("UPDATE posts SET slug = ? WHERE id = ?", (slug, post["id"]))


def create_post(
    username: str,
    title: str,
    body: str,
    excerpt: str,
    cover_image_url: str,
    visibility: str,
    status: str,
    tags: str,
    category: str,
) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False

    created_at = datetime.now(timezone.utc).isoformat()
    slug = generate_slug(title)
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO posts (user_id, title, body, excerpt, cover_image_url, created_at, visibility, status, tags, category, slug)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user["id"], title, body, excerpt, cover_image_url, created_at, visibility, status, tags, category, slug),
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
        SELECT id, title, body, excerpt, cover_image_url, created_at, visibility, status, tags, category
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
                   , posts.excerpt
                   , posts.cover_image_url
                   , COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name
                   , posts.tags
                   , posts.category
                   , posts.slug
                   , (
                       SELECT COUNT(*)
                       FROM comments
                       WHERE comments.post_id = posts.id
                   ) AS comment_count
                   , (
                       SELECT COUNT(*)
                       FROM likes
                       WHERE likes.post_id = posts.id
                   ) AS like_count
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
                   , posts.excerpt
                   , posts.cover_image_url
                   , COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name
                   , posts.tags
                   , posts.category
                   , posts.slug
                   , (
                       SELECT COUNT(*)
                       FROM comments
                       WHERE comments.post_id = posts.id
                   ) AS comment_count
                   , (
                       SELECT COUNT(*)
                       FROM likes
                       WHERE likes.post_id = posts.id
                   ) AS like_count
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
               posts.excerpt,
               posts.cover_image_url,
               COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name,
               posts.tags, posts.category, posts.slug,
               (
                   SELECT COUNT(*)
                   FROM likes
                   WHERE likes.post_id = posts.id
               ) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ? AND posts.visibility = 'public' AND posts.status = 'published'
        """,
        (post_id,),
    ).fetchone()
    conn.close()
    return post


def get_public_post_by_slug(slug: str) -> sqlite3.Row | None:
    conn = get_db_connection()
    post = conn.execute(
        """
        SELECT posts.id, posts.title, posts.body, posts.created_at, users.username,
               posts.excerpt,
               posts.cover_image_url,
               COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name,
               posts.tags, posts.category, posts.slug,
               (
                   SELECT COUNT(*)
                   FROM likes
                   WHERE likes.post_id = posts.id
               ) AS like_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.slug = ? AND posts.visibility = 'public' AND posts.status = 'published'
        """,
        (slug,),
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
        SELECT posts.id, posts.title, posts.body, posts.excerpt, posts.cover_image_url, posts.created_at, posts.tags, posts.category, posts.slug,
               (
                   SELECT COUNT(*)
                   FROM comments
                   WHERE comments.post_id = posts.id
               ) AS comment_count,
               (
                   SELECT COUNT(*)
                   FROM likes
                   WHERE likes.post_id = posts.id
               ) AS like_count
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
        SELECT posts.id, posts.title, posts.body, posts.excerpt, posts.cover_image_url, posts.created_at, posts.tags, posts.category, posts.slug,
               (
                   SELECT COUNT(*)
                   FROM comments
                   WHERE comments.post_id = posts.id
               ) AS comment_count,
               (
                   SELECT COUNT(*)
                   FROM likes
                   WHERE likes.post_id = posts.id
               ) AS like_count,
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


def get_public_posts_by_category(category: str) -> list[sqlite3.Row]:
    normalized = category.strip()
    if not normalized:
        return []

    conn = get_db_connection()
    posts = conn.execute(
        """
        SELECT posts.id, posts.title, posts.body, posts.excerpt, posts.cover_image_url, posts.created_at, posts.tags, posts.category, posts.slug,
               (
                   SELECT COUNT(*)
                   FROM comments
                   WHERE comments.post_id = posts.id
               ) AS comment_count,
               (
                   SELECT COUNT(*)
                   FROM likes
                   WHERE likes.post_id = posts.id
               ) AS like_count,
               users.username,
               COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.visibility = 'public'
          AND posts.status = 'published'
          AND TRIM(posts.category) != ''
          AND LOWER(TRIM(posts.category)) = LOWER(?)
        ORDER BY posts.created_at DESC
        """,
        (normalized,),
    ).fetchall()
    conn.close()
    return posts


def get_post_for_owner(post_id: int, username: str) -> sqlite3.Row | None:
    conn = get_db_connection()
    post = conn.execute(
        """
        SELECT posts.id, posts.title, posts.body, posts.excerpt, posts.cover_image_url, posts.created_at, posts.visibility, posts.status, posts.tags, posts.category, posts.slug
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ? AND users.username = ?
        """,
        (post_id, username),
    ).fetchone()
    conn.close()
    return post


def is_post_bookmarked(post_id: int, username: str) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False

    conn = get_db_connection()
    bookmark = conn.execute(
        "SELECT id FROM bookmarks WHERE user_id = ? AND post_id = ?",
        (user["id"], post_id),
    ).fetchone()
    conn.close()
    return bookmark is not None


def add_bookmark(post_id: int, username: str) -> bool:
    user = get_user_by_username(username)
    post = get_public_post_by_id(post_id)
    if not user or not post:
        return False

    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO bookmarks (user_id, post_id, created_at)
            VALUES (?, ?, ?)
            """,
            (user["id"], post_id, created_at),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_bookmark(post_id: int, username: str) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False

    conn = get_db_connection()
    result = conn.execute(
        "DELETE FROM bookmarks WHERE user_id = ? AND post_id = ?",
        (user["id"], post_id),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def get_bookmarked_posts_for_user(username: str) -> list[sqlite3.Row]:
    user = get_user_by_username(username)
    if not user:
        return []

    conn = get_db_connection()
    posts = conn.execute(
        """
        SELECT posts.id, posts.title, posts.created_at, posts.slug,
               users.username,
               COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name
        FROM bookmarks
        JOIN posts ON bookmarks.post_id = posts.id
        JOIN users ON posts.user_id = users.id
        WHERE bookmarks.user_id = ?
          AND posts.visibility = 'public'
          AND posts.status = 'published'
        ORDER BY bookmarks.created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    conn.close()
    return posts


def is_post_liked(post_id: int, username: str) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False

    conn = get_db_connection()
    like = conn.execute(
        "SELECT id FROM likes WHERE user_id = ? AND post_id = ?",
        (user["id"], post_id),
    ).fetchone()
    conn.close()
    return like is not None


def add_like(post_id: int, username: str) -> bool:
    user = get_user_by_username(username)
    post = get_public_post_by_id(post_id)
    if not user or not post:
        return False

    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO likes (user_id, post_id, created_at)
            VALUES (?, ?, ?)
            """,
            (user["id"], post_id, created_at),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_like(post_id: int, username: str) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False

    conn = get_db_connection()
    result = conn.execute(
        "DELETE FROM likes WHERE user_id = ? AND post_id = ?",
        (user["id"], post_id),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def create_comment(post_id: int, username: str, body: str) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False

    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO comments (post_id, user_id, body, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (post_id, user["id"], body, created_at),
    )
    conn.commit()
    conn.close()
    return True


def get_comments_for_post(post_id: int) -> list[sqlite3.Row]:
    conn = get_db_connection()
    comments = conn.execute(
        """
        SELECT comments.id, comments.body, comments.created_at, users.username,
               COALESCE(NULLIF(users.display_name, ''), users.username) AS display_name
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.post_id = ?
        ORDER BY comments.created_at ASC
        """,
        (post_id,),
    ).fetchall()
    conn.close()
    return comments


def delete_comment(comment_id: int, username: str) -> bool:
    conn = get_db_connection()
    result = conn.execute(
        """
        DELETE FROM comments
        WHERE id = (
            SELECT comments.id
            FROM comments
            JOIN users ON comments.user_id = users.id
            WHERE comments.id = ? AND users.username = ?
        )
        """,
        (comment_id, username),
    )
    conn.commit()
    conn.close()
    return result.rowcount > 0


def update_post(
    post_id: int,
    username: str,
    title: str,
    body: str,
    excerpt: str,
    cover_image_url: str,
    visibility: str,
    status: str,
    tags: str,
    category: str,
) -> bool:
    slug = generate_slug(title, exclude_post_id=post_id)
    conn = get_db_connection()
    result = conn.execute(
        """
        UPDATE posts
        SET title = ?, body = ?, excerpt = ?, cover_image_url = ?, visibility = ?, status = ?, tags = ?, category = ?, slug = ?
        WHERE id = (
            SELECT posts.id
            FROM posts
            JOIN users ON posts.user_id = users.id
            WHERE posts.id = ? AND users.username = ?
        )
        """,
        (title, body, excerpt, cover_image_url, visibility, status, tags, category, slug, post_id, username),
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
        bookmarked_posts=get_bookmarked_posts_for_user(session["username"]),
    )


@app.route("/posts/new", methods=["GET", "POST"])
def new_post():
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        cover_image_url = request.form.get("cover_image_url", "").strip()
        tags = request.form.get("tags", "").strip()
        category = request.form.get("category", "").strip()
        visibility = request.form.get("visibility", "public")
        if visibility not in {"public", "private"}:
            visibility = "public"
        status = request.form.get("status", "draft")
        if status not in {"draft", "published"}:
            status = "draft"

        if not title or not body:
            flash("Title and body are required.")
            return redirect(url_for("new_post"))

        create_post(
            session["username"],
            title,
            body,
            excerpt,
            cover_image_url,
            visibility,
            status,
            tags,
            category,
        )
        flash("Post created.")
        return redirect(url_for("dashboard"))

    return render_template("new_post.html")


@app.route("/posts/<slug>", methods=["GET", "POST"])
def post_detail(slug: str):
    post = get_public_post_by_slug(slug)
    if not post:
        abort(404)

    if request.method == "POST":
        if not is_logged_in():
            flash("Please log in to comment.")
            return redirect(url_for("login"))

        comment_body = request.form.get("body", "").strip()
        if not comment_body:
            flash("Comment cannot be empty.")
            return redirect(url_for("post_detail", slug=slug))

        create_comment(post["id"], session["username"], comment_body)
        flash("Comment added.")
        return redirect(url_for("post_detail", slug=slug))

    comments = get_comments_for_post(post["id"])
    bookmarked = False
    liked = False
    if is_logged_in():
        bookmarked = is_post_bookmarked(post["id"], session["username"])
        liked = is_post_liked(post["id"], session["username"])
    return render_template(
        "post_detail.html",
        post=post,
        comments=comments,
        is_bookmarked=bookmarked,
        is_liked=liked,
    )


@app.route("/posts/<int:post_id>")
def post_detail_by_id_redirect(post_id: int):
    post = get_public_post_by_id(post_id)
    if not post or not post["slug"]:
        abort(404)
    return redirect(url_for("post_detail", slug=post["slug"]))


@app.route("/posts/<int:post_id>/like", methods=["POST"])
def like_post(post_id: int):
    if not is_logged_in():
        flash("Please log in to like posts.")
        return redirect(url_for("login"))

    post = get_public_post_by_id(post_id)
    if not post:
        abort(404)

    if add_like(post_id, session["username"]):
        flash("Post liked.")
    else:
        flash("Post is already liked.")
    return redirect(url_for("post_detail", slug=post["slug"]))


@app.route("/posts/<int:post_id>/unlike", methods=["POST"])
def unlike_post(post_id: int):
    if not is_logged_in():
        flash("Please log in to manage likes.")
        return redirect(url_for("login"))

    post = get_public_post_by_id(post_id)
    if not post:
        abort(404)

    if remove_like(post_id, session["username"]):
        flash("Like removed.")
    else:
        flash("Like not found.")
    return redirect(url_for("post_detail", slug=post["slug"]))


@app.route("/posts/<int:post_id>/bookmark", methods=["POST"])
def bookmark_post(post_id: int):
    if not is_logged_in():
        flash("Please log in to bookmark posts.")
        return redirect(url_for("login"))

    post = get_public_post_by_id(post_id)
    if not post:
        abort(404)

    if add_bookmark(post_id, session["username"]):
        flash("Post bookmarked.")
    else:
        flash("Post is already bookmarked.")
    return redirect(url_for("post_detail", slug=post["slug"]))


@app.route("/posts/<int:post_id>/unbookmark", methods=["POST"])
def unbookmark_post(post_id: int):
    if not is_logged_in():
        flash("Please log in to manage bookmarks.")
        return redirect(url_for("login"))

    post = get_public_post_by_id(post_id)
    if not post:
        abort(404)

    if remove_bookmark(post_id, session["username"]):
        flash("Bookmark removed.")
    else:
        flash("Bookmark not found.")
    return redirect(url_for("post_detail", slug=post["slug"]))


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
        excerpt = request.form.get("excerpt", "").strip()
        cover_image_url = request.form.get("cover_image_url", "").strip()
        tags = request.form.get("tags", "").strip()
        category = request.form.get("category", "").strip()
        visibility = request.form.get("visibility", "public")
        if visibility not in {"public", "private"}:
            visibility = "public"
        status = request.form.get("status", "draft")
        if status not in {"draft", "published"}:
            status = "draft"

        if not title or not body:
            flash("Title and body are required.")
            return redirect(url_for("edit_post", post_id=post_id))

        update_post(
            post_id,
            username,
            title,
            body,
            excerpt,
            cover_image_url,
            visibility,
            status,
            tags,
            category,
        )
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


@app.route("/comments/<int:comment_id>/delete", methods=["POST"])
def delete_comment_route(comment_id: int):
    if not is_logged_in():
        return redirect(url_for("login"))

    if not delete_comment(comment_id, session["username"]):
        abort(404)

    flash("Comment deleted.")
    return redirect(request.referrer or url_for("home"))


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


@app.route("/categories/<category>")
def category_posts(category: str):
    posts = get_public_posts_by_category(category)
    return render_template("category_posts.html", category=category, posts=posts)


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
