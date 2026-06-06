# -*- coding: utf-8 -*-
"""
Flask 应用工厂
注册所有蓝图并返回 app 实例
"""

from flask import Flask


def create_app():
    """创建并配置 Flask 应用"""
    app = Flask(__name__)
    app.secret_key = 'py_web01_secret_key_2026'  # Session 加密密钥

    # 导入并注册各蓝图
    from .views import account  # 登录/登出
    from .views import main     # 订单管理 / 物流管理
    from .views import inventory  # 库存管理 / 商品审核
    from .views import users    # 用户管理 / 订单审核 / 地址管理

    app.register_blueprint(account.ac)
    app.register_blueprint(main.ma)
    app.register_blueprint(inventory.inv)
    app.register_blueprint(users.us)

    # 全局认证拦截：未登录用户强制跳转登录页
    from flask import session, request, redirect

    @app.before_request
    def require_login():
        """除登录页和静态资源外，所有路由均需登录"""
        path = request.path
        if path in ('/', '/login') or path.startswith('/static'):
            return None
        if not session.get('user_id'):
            return redirect('/login')

    return app
