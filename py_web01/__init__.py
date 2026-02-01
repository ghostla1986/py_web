from multiprocessing import Pool
from flask import Flask

def create_app():
    app = Flask(__name__)
    app.secret_key = 'py_web01_secret_key_2026'
    from .views import account
    from .views import main
    from .views import game
    from .views import inventory
    from .views import users
    app.register_blueprint(account.ac)
    app.register_blueprint(main.ma)
    app.register_blueprint(game.ga)
    app.register_blueprint(inventory.inv)
    app.register_blueprint(users.us)
    return app

