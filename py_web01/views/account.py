# -*- coding: utf-8 -*-
"""
登录 / 登出模块（蓝图：ac）
用户通过用户名和密码进行身份认证，登录成功后写入 session
"""

from flask import Blueprint, render_template, request, redirect, session
from utils import db

ac = Blueprint("account", __name__)


@ac.route('/login', methods=["GET", "POST"])
def login():
    """
    登录页面
    GET  — 返回登录表单
    POST — 验证用户名和密码，成功则跳转到用户管理页
    """
    if request.method == "GET":
        return render_template("index.html")

    # 获取表单提交的用户名和密码
    user = request.form.get("user")
    pwd = request.form.get("pwd")

    # 查询匹配的用户记录
    user_data = db.fetch_one(
        "SELECT * FROM user_info WHERE user=%s AND pwd=%s",
        [user, pwd]
    )

    if user_data:
        # 登录成功，将用户信息存入 session
        session['user_id'] = user_data[0]        # 用户 ID
        session['user_name'] = user_data[2]      # 用户名
        session['user_level'] = user_data[4]     # 角色：管理员/物流仓管员/普通用户
        return redirect('/users/list')  # 登录后默认跳转到用户管理页

    # 登录失败，返回错误提示
    return render_template("index.html", error="用户名或密码错误！")


@ac.route('/logout', methods=["GET"])
def logout():
    """登出：清除 session，跳转到登录页"""
    session.clear()
    return redirect('/login')
