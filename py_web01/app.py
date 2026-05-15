# -*- coding: utf-8 -*-
"""
Project Hana — 订单管理系统入口文件
Flask 应用初始化，注册蓝图，启动开发服务器
端口：43210（后期改为 43220 时请同步更新）
"""

from py_web01 import create_app
from flask_cors import CORS

app = create_app()
app.config['TEMPLATES_AUTO_RELOAD'] = True  # 模板修改后自动重载，方便开发调试
CORS(app)

if __name__ == '__main__':
    # host='0.0.0.0' 允许局域网内其他设备访问
    app.run(host='0.0.0.0', port=43220)
