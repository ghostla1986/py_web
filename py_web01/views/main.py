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
    sort = request.args.get('sort', 'desc')
    if sort not in ('asc', 'desc'):
        sort = 'desc'
    time_order = "ASC" if sort == 'asc' else "DESC"
    if user_level in ('物流仓管员', '物流专员'):
        return redirect('/main/ship_list')
    if user_level == '管理员':
        rows = fetch_all(f"SELECT id, customer, product, market_price, discount_price, status, create_time FROM orders ORDER BY FIELD(status, '待处理', '待发货', '已配送', '已送达', '已退回'), create_time {time_order}")
    else:
        rows = fetch_all(f"SELECT id, customer, product, market_price, discount_price, status, create_time FROM orders WHERE customer=%s ORDER BY create_time {time_order}", (user_name,))
    orders = []
    for r in rows:
        market_price = float(r[3])
        discount_price = float(r[4])
        # 折扣率 = 优惠售价 / 市场售价
        discount_rate = round(discount_price / market_price, 2) if market_price > 0 else 1.0
        orders.append({
            "id": r[0],
            "customer": r[1],
            "product": r[2],
            "market_price": market_price,
            "discount_price": discount_price,
            "discount_rate": discount_rate,
            "status": r[5],
            "create_time": r[6].strftime("%Y-%m-%d %H:%M:%S") if r[6] else ""
        })
    prod_rows = fetch_all("SELECT product, price FROM inventory WHERE audit_status='已通过' ORDER BY product")
    products = [{"product": r[0], "price": float(r[1])} for r in prod_rows]
    # 当前用户折扣率
    disc_row = fetch_one("SELECT discount FROM user_info WHERE user=%s", (user_name,))
    user_discount = float(disc_row[0]) if disc_row else 1.0
    return render_template("orders/list.html", orders=orders, products=products, user_discount=user_discount, sort=sort)


@ma.route('/main/create', methods=["GET", "POST"])
def create_order():
    if request.method == "GET":
        prod_rows = fetch_all("SELECT product, price FROM inventory ORDER BY product")
        products = [{"product": r[0], "price": float(r[1])} for r in prod_rows]
        return render_template("orders/create.html", products=products)

    try:
        customer = request.form.get("customer")
        product = request.form.get("product")
        market_price_str = request.form.get("market_price")
        discount_price_str = request.form.get("discount_price")

        if not customer or not product or not market_price_str:
            return "缺少必要字段", 400

        market_price = float(market_price_str)
        discount_price = float(discount_price_str) if discount_price_str else market_price

        user_level = session.get('user_level', '')
        status = '待发货' if user_level == '管理员' else '待处理'
        execute(
            "INSERT INTO orders (customer, product, market_price, discount_price, status) VALUES (%s, %s, %s, %s, %s)",
            (customer, product, market_price, discount_price, status)
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
        row = fetch_one("SELECT id, customer, product, market_price, discount_price, status, create_time FROM orders WHERE id=%s", (order_id,))
        if not row:
            return "订单不存在", 404
        order = {
            "id": row[0],
            "customer": row[1],
            "product": row[2],
            "market_price": float(row[3]),
            "discount_price": float(row[4]),
            "status": row[5],
            "create_time": row[6]
        }
        return render_template("orders/edit.html", order=order, is_regular=is_regular)

    try:
        customer = request.form.get("customer")
        product = request.form.get("product")
        market_price_str = request.form.get("market_price")
        discount_price_str = request.form.get("discount_price")
        status = request.form.get("status")

        if not customer or not product or not market_price_str:
            return "缺少必要字段", 400

        market_price = float(market_price_str)
        discount_price = float(discount_price_str) if discount_price_str else market_price

        if is_regular:
            row = fetch_one("SELECT market_price, discount_price, status FROM orders WHERE id=%s", (order_id,))
            if row:
                market_price = float(row[0])
                discount_price = float(row[1])
                status = row[2]

        execute(
            "UPDATE orders SET customer=%s, product=%s, market_price=%s, discount_price=%s, status=%s WHERE id=%s",
            (customer, product, market_price, discount_price, status, order_id)
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


# ========== JSON API ==========

@ma.route('/main/get_order/<int:order_id>', methods=["GET"])
def get_order(order_id):
    row = fetch_one("SELECT id, customer, product, market_price, discount_price, status FROM orders WHERE id=%s", (order_id,))
    if not row:
        return jsonify({"error": "订单不存在"}), 404
    return jsonify({
        "id": row[0],
        "customer": row[1],
        "product": row[2],
        "market_price": float(row[3]),
        "discount_price": float(row[4]),
        "status": row[5]
    })


@ma.route('/main/api_create', methods=["POST"])
def api_create_order():
    try:
        customer = request.form.get("customer")
        product = request.form.get("product")
        market_price_str = request.form.get("market_price")
        discount_price_str = request.form.get("discount_price")

        if not customer or not product or not market_price_str:
            return jsonify({"error": "缺少必要字段"}), 400

        market_price = float(market_price_str)
        discount_price = float(discount_price_str) if discount_price_str else market_price

        user_level = session.get('user_level', '')
        status = '待发货' if user_level == '管理员' else '待处理'
        new_id = execute(
            "INSERT INTO orders (customer, product, market_price, discount_price, status) VALUES (%s, %s, %s, %s, %s)",
            (customer, product, market_price, discount_price, status)
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
    sort = request.args.get('sort', 'desc')
    if sort not in ('asc', 'desc'):
        sort = 'desc'
    time_order = "ASC" if sort == 'asc' else "DESC"
    rows = fetch_all(
        f"SELECT id, customer, product, market_price, discount_price, create_time FROM orders WHERE status='待发货' ORDER BY create_time {time_order}"
    )
    orders = []
    for r in rows:
        orders.append({
            "id": r[0],
            "customer": r[1],
            "product": r[2],
            "market_price": float(r[3]),
            "discount_price": float(r[4]),
            "create_time": r[5].strftime("%Y-%m-%d %H:%M:%S") if r[5] else ""
        })
    return render_template("logistics/index.html", orders=orders, sort=sort)


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
        # 先读取订单原值
        row = fetch_one("SELECT customer, product, market_price, discount_price, status FROM orders WHERE id=%s", (order_id,))
        if not row:
            return jsonify({"error": "订单不存在"}), 404

        customer = request.form.get("customer") or row[0]
        product = request.form.get("product") or row[1]
        market_price_str = request.form.get("market_price")
        discount_price_str = request.form.get("discount_price")
        status = request.form.get("status") or row[4]

        if is_regular:
            # 普通用户：只更新 discount_price，其他字段保持原值
            market_price = float(row[2])
            # discount_price 为 0 或空时保持原值（避免前端空传）
            if discount_price_str and float(discount_price_str) > 0:
                discount_price = float(discount_price_str)
            else:
                discount_price = float(row[3])
            customer = row[0]
            product = row[1]
        else:
            if not market_price_str:
                return jsonify({"error": "缺少必要字段"}), 400
            market_price = float(market_price_str)
            discount_price = float(discount_price_str) if discount_price_str else market_price

        execute(
            "UPDATE orders SET customer=%s, product=%s, market_price=%s, discount_price=%s, status=%s WHERE id=%s",
            (customer, product, market_price, discount_price, status, order_id)
        )
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"error": "金额格式错误"}), 400
    except Exception as e:
        print(f"Error updating order: {e}")
        return jsonify({"error": "编辑订单失败"}), 500
