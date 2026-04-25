from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "dev-secret-key"
registered_users: dict[str, str] = {}


def is_logged_in() -> bool:
    return "username" in session


@app.route("/")
def home() -> str:
    return render_template("home.html")


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
    return render_template("dashboard.html", username=session["username"])


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
        return "Username and password are required"

    registered_users[username] = password
    return redirect(url_for("login"))


@app.route("/login")
def login() -> str:
    return render_template("login.html")


@app.route("/login/submit", methods=["POST"])
def submit_login() -> str:
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if registered_users.get(username) == password:
        session["username"] = username
        return redirect(url_for("dashboard"))

    return "Invalid username or password"


@app.route("/logout")
def logout() -> str:
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
