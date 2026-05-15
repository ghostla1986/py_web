from flask import Blueprint, request, redirect, jsonify, render_template, session
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from db import fetch_all, fetch_one, execute

ma = Blueprint("main", __name__)

# ========== 页面路由 ==========

@ma.route('/main/list', methods=["GET", "POST"])
def main_list():
    user_name = session.get('user_name', '')
    user_level = session.get('user_level', '')
    if user_level in ('物流仓管员', '物流专员'):
        return redirect('/main/ship_list')
    if user_level == '管理员':
        rows = fetch_all("SELECT id, customer, product, amount, status, create_time FROM orders ORDER BY FIELD(status, '待处理', '待发货', '已配送', '已送达', '已退回'), create_time DESC")
    else:
        rows = fetch_all("SELECT id, customer, product, amount, status, create_time FROM orders WHERE customer=%s ORDER BY create_time DESC", (user_name,))
    # 将元组转为模板友好的字典列表，并格式化时间
    orders = []
    for r in rows:
        orders.append({
            "id": r[0],
            "customer": r[1],
            "product": r[2],
            "amount": r[3],
            "status": r[4],
            "create_time": r[5].strftime("%Y-%m-%d %H:%M:%S") if r[5] else ""
        })
    prod_rows = fetch_all("SELECT product, price FROM inventory WHERE audit_status='已通过' ORDER BY product")
    products = [{"product": r[0], "price": float(r[1])} for r in prod_rows]
    return render_template("orders/list.html", orders=orders, products=products)

@ma.route('/main/create', methods=["GET", "POST"])
def create_order():
    if request.method == "GET":
        prod_rows = fetch_all("SELECT product, price FROM inventory ORDER BY product")
        products = [{"product": r[0], "price": float(r[1])} for r in prod_rows]
        return render_template("orders/create.html", products=products)

    try:
        customer = request.form.get("customer")
        product = request.form.get("product")
        amount_str = request.form.get("amount")

        if not customer or not product or not amount_str:
            return "缺少必要字段", 400

        amount = float(amount_str)

        execute(
            "INSERT INTO orders (customer, product, amount, status) VALUES (%s, %s, %s, '待处理')",
            (customer, product, amount)
        )
        return redirect('/main/list')
    except ValueError:
        return "金额格式错误", 400
    except Exception as e:
        print(f"Error creating order: {e}")
        return "创建订单失败", 500

@ma.route('/main/edit/<int:order_id>', methods=["GET", "POST"])
def edit_order(order_id):
    user_level = session.get('user_level', '')
    is_regular = (user_level not in ('管理员',))

    if request.method == "GET":
        row = fetch_one("SELECT id, customer, product, amount, status, create_time FROM orders WHERE id=%s", (order_id,))
        if not row:
            return "订单不存在", 404
        order = {
            "id": row[0],
            "customer": row[1],
            "product": row[2],
            "amount": row[3],
            "status": row[4],
            "create_time": row[5]
        }
        return render_template("orders/edit.html", order=order, is_regular=is_regular)

    try:
        customer = request.form.get("customer")
        product = request.form.get("product")
        amount_str = request.form.get("amount")
        status = request.form.get("status")

        if not customer or not product or not amount_str:
            return "缺少必要字段", 400

        amount = float(amount_str)

        if is_regular:
            # 普通用户：只更新提单人和商品，金额和状态保持原值
            row = fetch_one("SELECT amount, status FROM orders WHERE id=%s", (order_id,))
            if row:
                amount = float(row[0])
                status = row[1]

        execute(
            "UPDATE orders SET customer=%s, product=%s, amount=%s, status=%s WHERE id=%s",
            (customer, product, amount, status, order_id)
        )
        return redirect('/main/list')
    except ValueError:
        return "金额格式错误", 400
    except Exception as e:
        print(f"Error updating order: {e}")
        return "编辑订单失败", 500


@ma.route('/main/delete/<int:order_id>', methods=["POST"])
def delete_order(order_id):
    user_level = session.get('user_level', '')
    if user_level not in ('管理员',):
        row = fetch_one("SELECT status FROM orders WHERE id=%s", (order_id,))
        if row and row[0] not in ('待处理', '待发货'):
            return "当前状态不允许删除", 403
    execute("DELETE FROM orders WHERE id = %s", (order_id,))
    return redirect('/main/list')


# ========== JSON API（弹窗使用） ==========

@ma.route('/main/get_order/<int:order_id>', methods=["GET"])
def get_order(order_id):
    row = fetch_one("SELECT id, customer, product, amount, status FROM orders WHERE id=%s", (order_id,))
    if not row:
        return jsonify({"error": "订单不存在"}), 404
    return jsonify({
        "id": row[0],
        "customer": row[1],
        "product": row[2],
        "amount": float(row[3]),
        "status": row[4]
    })


@ma.route('/main/api_create', methods=["POST"])
def api_create_order():
    try:
        customer = request.form.get("customer")
        product = request.form.get("product")
        amount_str = request.form.get("amount")

        if not customer or not product or not amount_str:
            return jsonify({"error": "缺少必要字段"}), 400

        amount = float(amount_str)
        new_id = execute(
            "INSERT INTO orders (customer, product, amount, status) VALUES (%s, %s, %s, '待处理')",
            (customer, product, amount)
        )
        return jsonify({"success": True, "id": new_id})
    except ValueError:
        return jsonify({"error": "金额格式错误"}), 400
    except Exception as e:
        print(f"Error creating order: {e}")
        return jsonify({"error": "创建订单失败"}), 500


@ma.route('/main/ship_list', methods=["GET"])
def logistics_ship():
    user_level = session.get('user_level', '')
    if user_level not in ('管理员', '物流仓管员', '物流专员'):
        return redirect('/main/list')
    rows = fetch_all(
        "SELECT id, customer, product, amount, create_time FROM orders WHERE status='待发货' ORDER BY create_time DESC"
    )
    orders = []
    for r in rows:
        orders.append({
            "id": r[0],
            "customer": r[1],
            "product": r[2],
            "amount": float(r[3]),
            "create_time": r[4].strftime("%Y-%m-%d %H:%M:%S") if r[4] else ""
        })
    return render_template("logistics/index.html", orders=orders)


@ma.route('/main/ship/<int:order_id>', methods=["POST"])
def ship_order(order_id):
    try:
        execute("UPDATE orders SET status='已配送' WHERE id=%s AND status='待发货'", (order_id,))
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error shipping order: {e}")
        return jsonify({"error": "发货失败"}), 500


@ma.route('/main/api_edit/<int:order_id>', methods=["POST"])
def api_edit_order(order_id):
    user_level = session.get('user_level', '')
    is_regular = (user_level not in ('管理员',))

    try:
        customer = request.form.get("customer")
        product = request.form.get("product")
        amount_str = request.form.get("amount")
        status = request.form.get("status")

        if not customer or not product or not amount_str:
            return jsonify({"error": "缺少必要字段"}), 400

        amount = float(amount_str)

        if is_regular:
            # 普通用户：从数据库读取原金额和状态
            row = fetch_one("SELECT amount, status FROM orders WHERE id=%s", (order_id,))
            if row:
                amount = float(row[0])
                status = row[1]

        execute(
            "UPDATE orders SET customer=%s, product=%s, amount=%s, status=%s WHERE id=%s",
            (customer, product, amount, status, order_id)
        )
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"error": "金额格式错误"}), 400
    except Exception as e:
        print(f"Error updating order: {e}")
        return jsonify({"error": "编辑订单失败"}), 500
