from flask import Flask, render_template, request, redirect, url_for, session
import json
import os

app = Flask(__name__)
app.config.from_pyfile("config.py")

USER_FILE = "users.json"

def load_users():
    if not os.path.exists(USER_FILE):
        return []
    with open(USER_FILE, "r") as f:
        return json.load(f)


def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=4)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        users = load_users()

        for user in users:
            if user["username"] == username and user["password"] == password:
                session["user"] = username
                return redirect(url_for("dashboard"))

        return render_template("login.html", error="Username atau password salah")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        users = load_users()

        for user in users:
            if user["username"] == username:
                return render_template("register.html", error="Username sudah dipakai!")

        users.append({"username": username, "password": password})
        save_users(users)

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/topup", methods=["GET", "POST"])
def topup():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        game_id = request.form["game_id"]
        nominal = request.form["nominal"]
        return render_template("topup.html", success=True, game_id=game_id, nominal=nominal)

    return render_template("topup.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)

