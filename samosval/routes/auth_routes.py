from flask import Blueprint, redirect, render_template, request, url_for, flash
from flask_login import login_required, login_user, logout_user

from ..auth import authenticate


auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login():
    return render_template("auth/login.html")


@auth_bp.post("/login")
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = authenticate(username, password)
    if not user:
        flash("Неверный логин/пароль или пользователь заблокирован", "error")
        return render_template(
            "auth/login.html",
            username=username,
        )
    login_user(user)
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


