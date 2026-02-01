from flask import Blueprint,render_template,request,redirect,session
from utils import db

#蓝图对象
ac = Blueprint("account",__name__)

@ac.route('/login',methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("index.html")

    user = request.form.get("user")
    pwd = request.form.get("pwd")
    print(user, pwd)

    user_data = db.fetch_one("select * from user_info where user=%s and pwd=%s", [user, pwd])
    if user_data:
        session['user_id'] = user_data[0]
        session['user_name'] = user_data[2]
        session['user_level'] = user_data[4]
        return redirect('/users/list')
    return render_template("index.html",error="用户名或密码错误！")



@ac.route('/lk',methods=["GET","POST"])
def lk():
    return "list"