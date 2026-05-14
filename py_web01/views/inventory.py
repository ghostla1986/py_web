from flask import Blueprint, request, redirect, jsonify, render_template, session
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from db import fetch_all, fetch_one, execute

inv = Blueprint("inventory", __name__)


# ========== 页面路由 ==========

@inv.route('/inventory/list', methods=["GET", "POST"])
def inventory_list():
    user_level = session.get('user_level', '')
    if user_level not in ('管理员', '物流仓管员', '物流专员'):
        return redirect('/main/list')
    # 库存列表只显示已审核通过的商品
    rows = fetch_all(
        "SELECT id, product, price, total_qty, outbound_qty, remaining_qty, audit_status FROM inventory WHERE audit_status='已通过' ORDER BY id"
    )
    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "product": r[1],
            "price": float(r[2]),
            "total_qty": r[3],
            "outbound_qty": r[4],
            "remaining_qty": r[5],
        })
    return render_template("inventory/list.html", inventory=items)


@inv.route('/inventory/create', methods=["GET", "POST"])
def create_item():
    user_level = session.get('user_level', '')
    if user_level not in ('管理员', '物流仓管员', '物流专员'):
        return redirect('/inventory/list')
    if request.method == "GET":
        return render_template("inventory/create.html")

    try:
        product = request.form.get("product")
        price_str = request.form.get("price")
        total_str = request.form.get("total_qty")

        if not product or not price_str or not total_str:
            return "缺少必要字段", 400

        price = float(price_str)
        total_qty = int(total_str)

        # 管理员直接通过，仓管员需要审核
        audit_status = '已通过' if user_level == '管理员' else '待审核'

        execute(
            "INSERT INTO inventory (product, price, total_qty, outbound_qty, remaining_qty, audit_status) VALUES (%s, %s, %s, 0, %s, %s)",
            (product, price, total_qty, total_qty, audit_status)
        )
        return redirect('/inventory/list')
    except ValueError:
        return "格式错误", 400
    except Exception as e:
        print(f"Error creating inventory item: {e}")
        return "创建失败", 500


@inv.route('/inventory/edit/<int:item_id>', methods=["GET", "POST"])
def edit_item(item_id):
    if request.method == "GET":
        row = fetch_one(
            "SELECT id, product, price, total_qty, outbound_qty, remaining_qty FROM inventory WHERE id=%s",
            (item_id,)
        )
        if not row:
            return "商品不存在", 404
        item = {
            "id": row[0],
            "product": row[1],
            "price": float(row[2]),
            "total_qty": row[3],
            "outbound_qty": row[4],
            "remaining_qty": row[5],
        }
        return render_template("inventory/edit.html", item=item)

    try:
        product = request.form.get("product")
        price_str = request.form.get("price")
        total_str = request.form.get("total_qty")
        outbound_str = request.form.get("outbound_qty")

        if not product or not price_str or not total_str:
            return "缺少必要字段", 400

        price = float(price_str)
        total_qty = int(total_str)
        outbound_qty = int(outbound_str) if outbound_str else 0
        remaining_qty = total_qty - outbound_qty

        execute(
            "UPDATE inventory SET product=%s, price=%s, total_qty=%s, outbound_qty=%s, remaining_qty=%s WHERE id=%s",
            (product, price, total_qty, outbound_qty, remaining_qty, item_id)
        )
        return redirect('/inventory/list')
    except ValueError:
        return "格式错误", 400
    except Exception as e:
        print(f"Error updating inventory item: {e}")
        return "编辑失败", 500


@inv.route('/inventory/delete/<int:item_id>', methods=["POST"])
def delete_item(item_id):
    execute("DELETE FROM inventory WHERE id = %s", (item_id,))
    return redirect('/inventory/list')


# ========== JSON API（弹窗使用） ==========

@inv.route('/inventory/get_item/<int:item_id>', methods=["GET"])
def get_item(item_id):
    row = fetch_one(
        "SELECT id, product, price, total_qty, outbound_qty, remaining_qty FROM inventory WHERE id=%s",
        (item_id,)
    )
    if not row:
        return jsonify({"error": "商品不存在"}), 404
    return jsonify({
        "id": row[0],
        "product": row[1],
        "price": float(row[2]),
        "total_qty": row[3],
        "outbound_qty": row[4],
        "remaining_qty": row[5],
    })


@inv.route('/inventory/api_create', methods=["POST"])
def api_create_item():
    user_level = session.get('user_level', '')
    try:
        product = request.form.get("product")
        price_str = request.form.get("price")
        total_str = request.form.get("total_qty")

        if not product or not price_str or not total_str:
            return jsonify({"error": "缺少必要字段"}), 400

        price = float(price_str)
        total_qty = int(total_str)

        audit_status = '已通过' if user_level == '管理员' else '待审核'

        new_id = execute(
            "INSERT INTO inventory (product, price, total_qty, outbound_qty, remaining_qty, audit_status) VALUES (%s, %s, %s, 0, %s, %s)",
            (product, price, total_qty, total_qty, audit_status)
        )
        return jsonify({"success": True, "id": new_id})
    except ValueError:
        return jsonify({"error": "格式错误"}), 400
    except Exception as e:
        print(f"Error creating inventory item: {e}")
        return jsonify({"error": "创建失败"}), 500


@inv.route('/inventory/api_edit/<int:item_id>', methods=["POST"])
def api_edit_item(item_id):
    try:
        product = request.form.get("product")
        price_str = request.form.get("price")
        total_str = request.form.get("total_qty")
        outbound_str = request.form.get("outbound_qty")

        if not product or not price_str or not total_str:
            return jsonify({"error": "缺少必要字段"}), 400

        price = float(price_str)
        total_qty = int(total_str)
        outbound_qty = int(outbound_str) if outbound_str else 0
        remaining_qty = total_qty - outbound_qty

        execute(
            "UPDATE inventory SET product=%s, price=%s, total_qty=%s, outbound_qty=%s, remaining_qty=%s WHERE id=%s",
            (product, price, total_qty, outbound_qty, remaining_qty, item_id)
        )
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"error": "格式错误"}), 400
    except Exception as e:
        print(f"Error updating inventory item: {e}")
        return jsonify({"error": "编辑失败"}), 500


# ========== 商品审核（仓管员添加后管理员审批） ==========

@inv.route('/inventory/audit', methods=["GET"])
def audit_items():
    if session.get('user_level') != '管理员':
        return redirect('/inventory/list')
    rows = fetch_all(
        "SELECT id, product, price, total_qty, outbound_qty, remaining_qty, create_time FROM inventory WHERE audit_status='待审核' ORDER BY create_time ASC"
    )
    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "product": r[1],
            "price": float(r[2]),
            "total_qty": r[3],
            "outbound_qty": r[4],
            "remaining_qty": r[5],
            "create_time": r[6].strftime("%Y-%m-%d %H:%M:%S") if r[6] else ""
        })
    return render_template("inventory/audit.html", items=items)


@inv.route('/inventory/audit/approve/<int:item_id>', methods=["POST"])
def audit_approve(item_id):
    if session.get('user_level') != '管理员':
        return jsonify({"error": "无权限"}), 403
    execute("UPDATE inventory SET audit_status='已通过' WHERE id=%s AND audit_status='待审核'", (item_id,))
    return jsonify({"success": True})


@inv.route('/inventory/audit/reject/<int:item_id>', methods=["POST"])
def audit_reject(item_id):
    if session.get('user_level') != '管理员':
        return jsonify({"error": "无权限"}), 403
    execute("UPDATE inventory SET audit_status='已驳回' WHERE id=%s AND audit_status='待审核'", (item_id,))
    return jsonify({"success": True})


@inv.route('/inventory/api_warehouse_edit/<int:item_id>', methods=["POST"])
def api_warehouse_edit_item(item_id):
    user_level = session.get('user_level', '')
    if user_level not in ('物流仓管员', '物流专员'):
        return jsonify({"error": "无权限"}), 403

    try:
        price_str = request.form.get("price")
        total_str = request.form.get("total_qty")

        if not price_str or not total_str:
            return jsonify({"error": "缺少必要字段"}), 400

        new_price = float(price_str)
        new_total = int(total_str)

        # 读取当前值做校验
        row = fetch_one(
            "SELECT price, total_qty FROM inventory WHERE id=%s",
            (item_id,)
        )
        if not row:
            return jsonify({"error": "商品不存在"}), 404

        old_price = float(row[0])
        old_total = int(row[1])

        # 单价只能增不能减
        if new_price < old_price:
            return jsonify({"error": "单价只能增加，不能减少"}), 400

        # 总数量只能增不能减
        if new_total < old_total:
            return jsonify({"error": "总数量只能增加，不能减少"}), 400

        execute(
            "UPDATE inventory SET price=%s, total_qty=%s WHERE id=%s",
            (new_price, new_total, item_id)
        )
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"error": "格式错误"}), 400
    except Exception as e:
        print(f"Error updating inventory item by warehouser: {e}")
        return jsonify({"error": "编辑失败"}), 500
