from flask import Blueprint, request, redirect, jsonify, render_template, session
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from db import fetch_all, fetch_one, execute
import json
from regions import REGIONS, get_provinces, get_cities, get_districts, get_streets

us = Blueprint("users", __name__)


@us.route('/users/list', methods=["GET", "POST"])
def users_list():
    rows = fetch_all(
        "SELECT id, user, `level`, discount, join_time FROM user_info ORDER BY FIELD(`level`, '管理员', '物流仓管员', '普通用户'), join_time ASC, id ASC"
    )
    user_list = []
    for r in rows:
        user_list.append({
            "id": r[0],
            "name": r[1],
            "level": r[2],
            "discount": float(r[3]),
            "join_time": r[4].strftime("%Y-%m-%d %H:%M:%S") if r[4] else "",
        })
    return render_template("users/list.html", users=user_list)


@us.route('/users/create', methods=["GET", "POST"])
def create_user():
    if session.get('user_level') != '管理员':
        return redirect('/users/list')
    if request.method == "GET":
        return render_template("users/create.html")

    try:
        name = request.form.get("name")
        level = request.form.get("level")
        discount_str = request.form.get("discount")

        if not name or not level or not discount_str:
            return "缺少必要字段", 400

        discount = float(discount_str)

        execute(
            "INSERT INTO user_info (`user`, `level`, discount, pwd) VALUES (%s, %s, %s, %s)",
            (name, level, discount, "123456")
        )
        return redirect('/users/list')
    except ValueError:
        return "格式错误", 400
    except Exception as e:
        print(f"Error creating user: {e}")
        return "创建失败", 500


@us.route('/users/edit/<int:user_id>', methods=["GET", "POST"])
def edit_user(user_id):
    if session.get('user_level') != '管理员':
        return redirect('/users/list')
    if request.method == "GET":
        row = fetch_one(
            "SELECT id, user, `level`, discount FROM user_info WHERE id=%s",
            (user_id,)
        )
        if not row:
            return "用户不存在", 404
        user_data = {
            "id": row[0],
            "name": row[1],
            "level": row[2],
            "discount": float(row[3]),
        }
        return render_template("users/edit.html", user_data=user_data)

    try:
        name = request.form.get("name")
        level = request.form.get("level")
        discount_str = request.form.get("discount")

        if not name or not level or not discount_str:
            return "缺少必要字段", 400

        discount = float(discount_str)

        execute(
            "UPDATE user_info SET `user`=%s, `level`=%s, discount=%s WHERE id=%s",
            (name, level, discount, user_id)
        )
        return redirect('/users/list')
    except ValueError:
        return "格式错误", 400
    except Exception as e:
        print(f"Error updating user: {e}")
        return "编辑失败", 500


@us.route('/users/audit', methods=["GET"])
def audit_orders():
    rows = fetch_all(
        "SELECT id, customer, product, market_price, discount_price, status, create_time FROM orders WHERE status='待处理' ORDER BY create_time ASC"
    )
    orders = []
    for r in rows:
        orders.append({
            "id": r[0],
            "customer": r[1],
            "product": r[2],
            "market_price": float(r[3]),
            "discount_price": float(r[4]),
            "status": r[5],
            "create_time": r[6].strftime("%Y-%m-%d %H:%M:%S") if r[6] else ""
        })
    return render_template("users/audit.html", orders=orders)


@us.route('/users/audit/approve/<int:order_id>', methods=["POST"])
def audit_approve(order_id):
    order = fetch_one("SELECT product FROM orders WHERE id=%s AND status='待处理'", (order_id,))
    if not order:
        return jsonify({"success": False, "msg": "订单不存在或已处理"}), 400

    product = order[0]
    inv = fetch_one("SELECT remaining_qty FROM inventory WHERE product=%s", (product,))
    stock = inv[0] if inv else 0

    if stock <= 0:
        return jsonify({"success": False, "msg": "该商品库存为0，请补充后再审核"}), 400

    execute("UPDATE orders SET status='待发货' WHERE id=%s AND status='待处理'", (order_id,))
    execute(
        "UPDATE inventory SET remaining_qty = remaining_qty - 1, outbound_qty = outbound_qty + 1 WHERE product=%s AND remaining_qty > 0",
        (product,)
    )
    return jsonify({"success": True})


@us.route('/users/audit/reject/<int:order_id>', methods=["POST"])
def audit_reject(order_id):
    execute("UPDATE orders SET status='已退回' WHERE id=%s AND status='待处理'", (order_id,))
    return redirect('/users/audit')


@us.route('/users/api_create', methods=["POST"])
def api_create_user():
    if session.get('user_level') != '管理员':
        return jsonify({"error": "无权限"}), 403
    try:
        name = request.form.get("name")
        level = request.form.get("level")
        discount_str = request.form.get("discount")

        if not name or not level or not discount_str:
            return jsonify({"error": "缺少必要字段"}), 400

        discount = float(discount_str)

        new_id = execute(
            "INSERT INTO user_info (`user`, `level`, discount, pwd) VALUES (%s, %s, %s, %s)",
            (name, level, discount, "123456")
        )
        return jsonify({"success": True, "id": new_id})
    except ValueError:
        return jsonify({"error": "格式错误"}), 400
    except Exception as e:
        print(f"Error creating user: {e}")
        return jsonify({"error": "创建失败"}), 500


@us.route('/users/api_edit/<int:user_id>', methods=["POST"])
def api_edit_user(user_id):
    if session.get('user_level') != '管理员':
        return jsonify({"error": "无权限"}), 403
    try:
        level = request.form.get("level")
        discount_str = request.form.get("discount")

        if not level or not discount_str:
            return jsonify({"error": "缺少必要字段"}), 400

        discount = float(discount_str)

        execute(
            "UPDATE user_info SET `level`=%s, discount=%s WHERE id=%s",
            (level, discount, user_id)
        )
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"error": "格式错误"}), 400
    except Exception as e:
        print(f"Error updating user: {e}")
        return jsonify({"error": "编辑失败"}), 500


# ========== 地址管理 ==========

@us.route('/users/address', methods=["GET"])
def address_page():
    rows = fetch_all(
        "SELECT a.id, a.username, a.contact, a.phone, a.province, a.city, a.district, a.street, a.detail, a.is_default, a.create_time "
        "FROM addresses a ORDER BY a.username, a.is_default DESC, a.create_time DESC"
    )
    addresses = []
    for r in rows:
        addresses.append({
            "id": r[0],
            "username": r[1],
            "contact": r[2],
            "phone": r[3],
            "province": r[4],
            "city": r[5],
            "district": r[6],
            "street": r[7],
            "detail": r[8],
            "is_default": r[9],
            "create_time": r[10].strftime("%Y-%m-%d %H:%M:%S") if r[10] else ""
        })

    # 获取用户列表供新增下拉选择
    user_rows = fetch_all("SELECT id, user FROM user_info ORDER BY user")
    user_list = [{"id": r[0], "name": r[1]} for r in user_rows]

    provinces = get_provinces()
    return render_template("users/address.html",
        addresses=addresses,
        users=user_list,
        provinces=provinces,
        regions_json=json.dumps(REGIONS, ensure_ascii=False)
    )


@us.route('/users/address/add', methods=["POST"])
def address_add():
    try:
        username = request.form.get("username")
        contact = request.form.get("contact")
        phone = request.form.get("phone")
        province = request.form.get("province", "")
        city = request.form.get("city", "")
        district = request.form.get("district", "")
        street = request.form.get("street", "")
        detail = request.form.get("detail", "")
        is_default = 1 if request.form.get("is_default") else 0

        if not username or not contact or not phone or not province or not city or not district:
            return jsonify({"error": "请填写完整地址信息"}), 400

        # 检查上限：每个用户最多5条
        count_row = fetch_one("SELECT COUNT(*) FROM addresses WHERE username=%s", (username,))
        if count_row and count_row[0] >= 5:
            return jsonify({"error": "每个用户最多添加5条地址"}), 400

        # 如果设为默认，先取消该用户的其他默认地址
        if is_default:
            execute("UPDATE addresses SET is_default=0 WHERE username=%s", (username,))

        new_id = execute(
            "INSERT INTO addresses (username, contact, phone, province, city, district, street, detail, is_default) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (username, contact, phone, province, city, district, street, detail, is_default)
        )
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        print(f"Error adding address: {e}")
        return jsonify({"error": "添加地址失败"}), 500


@us.route('/users/address/get/<int:addr_id>', methods=["GET"])
def address_get(addr_id):
    row = fetch_one(
        "SELECT id, username, contact, phone, province, city, district, street, detail, is_default "
        "FROM addresses WHERE id=%s", (addr_id,)
    )
    if not row:
        return jsonify({"error": "地址不存在"}), 404
    return jsonify({
        "id": row[0],
        "username": row[1],
        "contact": row[2],
        "phone": row[3],
        "province": row[4],
        "city": row[5],
        "district": row[6],
        "street": row[7],
        "detail": row[8],
        "is_default": row[9]
    })


@us.route('/users/address/edit/<int:addr_id>', methods=["POST"])
def address_edit(addr_id):
    try:
        contact = request.form.get("contact")
        phone = request.form.get("phone")
        province = request.form.get("province", "")
        city = request.form.get("city", "")
        district = request.form.get("district", "")
        street = request.form.get("street", "")
        detail = request.form.get("detail", "")
        is_default = 1 if request.form.get("is_default") else 0

        if not contact or not phone or not province or not city or not district:
            return jsonify({"error": "请填写完整地址信息"}), 400

        # 获取原地址所属用户，用于处理默认地址
        row = fetch_one("SELECT username FROM addresses WHERE id=%s", (addr_id,))
        if not row:
            return jsonify({"error": "地址不存在"}), 404
        username = row[0]

        if is_default:
            execute("UPDATE addresses SET is_default=0 WHERE username=%s", (username,))

        execute(
            "UPDATE addresses SET contact=%s, phone=%s, province=%s, city=%s, district=%s, street=%s, detail=%s, is_default=%s WHERE id=%s",
            (contact, phone, province, city, district, street, detail, is_default, addr_id)
        )
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error editing address: {e}")
        return jsonify({"error": "编辑失败"}), 500


@us.route('/users/address/delete/<int:addr_id>', methods=["POST"])
def address_delete(addr_id):
    try:
        execute("DELETE FROM addresses WHERE id=%s", (addr_id,))
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting address: {e}")
        return jsonify({"error": "删除失败"}), 500


@us.route('/users/delete/<int:user_id>', methods=["POST"])
def delete_user(user_id):
    if session.get('user_level') != '管理员':
        return redirect('/users/list')
    execute("DELETE FROM user_info WHERE id = %s", (user_id,))
    return redirect('/users/list')


# ========== 折扣申请与审批 ==========

@us.route('/users/discount_request', methods=["GET", "POST"])
def discount_request():
    """普通用户：查看/提交折扣申请"""
    user_id = session.get('user_id')
    user_name = session.get('user_name', '')

    if request.method == "GET":
        row = fetch_one("SELECT discount FROM user_info WHERE id=%s", (user_id,))
        current_discount = float(row[0]) if row else 1.0
        # 查自己最近5条申请记录
        rows = fetch_all(
            "SELECT id, requested_discount, reason, status, create_time, audit_time, audit_comment "
            "FROM discount_requests WHERE user_id=%s ORDER BY create_time DESC LIMIT 5",
            (user_id,)
        )
        records = []
        for r in rows:
            records.append({
                "id": r[0],
                "requested_discount": float(r[1]),
                "reason": r[2] or '',
                "status": r[3],
                "create_time": r[4].strftime("%Y-%m-%d %H:%M:%S") if r[4] else '',
                "audit_time": r[5].strftime("%Y-%m-%d %H:%M:%S") if r[5] else '',
                "audit_comment": r[6] or ''
            })
        return render_template("users/discount_request.html", current_discount=current_discount, records=records)

    # POST：提交申请
    try:
        requested_str = request.form.get("requested_discount")
        reason = request.form.get("reason", '').strip()

        if not requested_str:
            return jsonify({"error": "请选择申请折扣"}), 400

        requested = float(requested_str)
        if requested <= 0 or requested > 1:
            return jsonify({"error": "折扣率无效"}), 400

        row = fetch_one("SELECT discount FROM user_info WHERE id=%s", (user_id,))
        current_discount = float(row[0]) if row else 1.0

        # 不能申请比当前更低的折扣（更优惠的折扣 = 更小的值）
        if requested > current_discount:
            return jsonify({"error": "申请折扣不能低于当前折扣率（更低的数字代表更高优惠）"}), 400

        # 检查是否有待审核的申请
        pending = fetch_one(
            "SELECT COUNT(*) FROM discount_requests WHERE user_id=%s AND status='待审核'",
            (user_id,)
        )
        if pending and pending[0] > 0:
            return jsonify({"error": "你已有一笔待审核的申请，请等待处理"}), 400

        execute(
            "INSERT INTO discount_requests (user_id, username, current_discount, requested_discount, reason) VALUES (%s, %s, %s, %s, %s)",
            (user_id, user_name, current_discount, requested, reason)
        )
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"error": "格式错误"}), 400
    except Exception as e:
        print(f"Error submitting discount request: {e}")
        return jsonify({"error": "提交失败"}), 500


@us.route('/users/discount_audit', methods=["GET"])
def discount_audit():
    """管理员：审核折扣申请列表"""
    if session.get('user_level') != '管理员':
        return redirect('/users/list')

    rows = fetch_all(
        "SELECT id, user_id, username, current_discount, requested_discount, reason, status, create_time, audit_time, audit_comment "
        "FROM discount_requests WHERE status='待审核' ORDER BY create_time ASC"
    )
    requests = []
    for r in rows:
        requests.append({
            "id": r[0],
            "user_id": r[1],
            "username": r[2],
            "current_discount": float(r[3]),
            "requested_discount": float(r[4]),
            "reason": r[5] or '',
            "status": r[6],
            "create_time": r[7].strftime("%Y-%m-%d %H:%M:%S") if r[7] else '',
            "audit_time": r[8].strftime("%Y-%m-%d %H:%M:%S") if r[8] else '',
            "audit_comment": r[9] or ''
        })
    return render_template("users/discount_audit.html", requests=requests)


@us.route('/users/discount_audit/approve/<int:req_id>', methods=["POST"])
def discount_audit_approve(req_id):
    if session.get('user_level') != '管理员':
        return jsonify({"error": "无权限"}), 403

    row = fetch_one(
        "SELECT id, user_id, requested_discount FROM discount_requests WHERE id=%s AND status='待审核'",
        (req_id,)
    )
    if not row:
        return jsonify({"error": "申请不存在或已处理"}), 404

    requested = float(row[2])

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 更新用户折扣
    execute("UPDATE user_info SET discount=%s WHERE id=%s", (requested, row[1]))
    # 更新申请状态
    execute(
        "UPDATE discount_requests SET status='已通过', audit_time=%s WHERE id=%s",
        (now, req_id)
    )
    return jsonify({"success": True})


@us.route('/users/discount_audit/reject/<int:req_id>', methods=["POST"])
def discount_audit_reject(req_id):
    if session.get('user_level') != '管理员':
        return jsonify({"error": "无权限"}), 403

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    comment = request.form.get("comment", '').strip()

    execute(
        "UPDATE discount_requests SET status='已驳回', audit_time=%s, audit_comment=%s WHERE id=%s AND status='待审核'",
        (now, comment, req_id)
    )
    return jsonify({"success": True})
