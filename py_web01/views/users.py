# -*- coding: utf-8 -*-
"""
用户管理 / 订单审核 / 地址管理模块（蓝图：us）
包含用户的增删改查、订单审核流转、地址的 CRUD 及省市区联动
"""

from flask import Blueprint, request, redirect, jsonify, render_template, session
import sys
import os
# 将 utils 目录加入模块搜索路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from db import fetch_all, fetch_one, execute
import json
from regions import REGIONS, get_provinces, get_cities, get_districts, get_streets

us = Blueprint("users", __name__)


# ========== 用户管理 ==========

@us.route('/users/list', methods=["GET", "POST"])
def users_list():
    """
    用户列表页
    支持按加入时间升降序排序（sort 参数）
    排序规则：先按角色（管理员>仓管员>普通用户），再按加入时间
    """
    sort = request.args.get('sort', 'asc')
    if sort not in ('asc', 'desc'):
        sort = 'asc'
    order = "ASC" if sort == 'asc' else "DESC"

    rows = fetch_all(
        f"SELECT id, user, `level`, discount, join_time FROM user_info "
        f"ORDER BY FIELD(`level`, '管理员', '物流仓管员', '普通用户'), join_time {order}, id ASC"
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
    return render_template("users/list.html", users=user_list, sort=sort)


@us.route('/users/create', methods=["GET", "POST"])
def create_user():
    """新增用户（仅管理员）"""
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
        # 默认密码 123456，提示用户修改
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
    """编辑用户（仅管理员，保留的后备页面）"""
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


# ========== 订单审核 ==========

@us.route('/users/audit', methods=["GET"])
def audit_orders():
    """
    订单审核页面（仅管理员）
    列出所有"待处理"状态的订单，管理员可在弹窗中修改商品和折扣率后审核
    """
    rows = fetch_all(
        "SELECT id, customer, product, market_price, discount_price, status, create_time "
        "FROM orders WHERE status='待处理' ORDER BY create_time ASC"
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
    # 传入库存商品列表，供弹窗中下拉选择
    prod_rows = fetch_all(
        "SELECT product, price FROM inventory WHERE audit_status='已通过' ORDER BY product"
    )
    products = [{"product": r[0], "price": float(r[1])} for r in prod_rows]
    return render_template("users/audit.html", orders=orders, products=products)


@us.route('/users/audit/approve/<int:order_id>', methods=["POST"])
def audit_approve(order_id):
    """
    审核通过单个订单
    接收前端弹窗传入的商品/价格信息，更新订单后扣减库存
    库存为 0 时拒绝审核
    """
    order = fetch_one(
        "SELECT id, product FROM orders WHERE id=%s AND status='待处理'",
        (order_id,)
    )
    if not order:
        return jsonify({"success": False, "msg": "订单不存在或已处理"}), 400

    # 获取前端提交的商品和价格（审核弹窗中可修改）
    product = request.form.get("product", order[1])
    market_price_str = request.form.get("market_price")
    discount_price_str = request.form.get("discount_price")

    market_price = float(market_price_str) if market_price_str else None
    discount_price = float(discount_price_str) if discount_price_str else None

    # 如果传入了价格则更新订单，否则只改状态
    if market_price and discount_price:
        execute(
            "UPDATE orders SET product=%s, market_price=%s, discount_price=%s, status='待发货' "
            "WHERE id=%s AND status='待处理'",
            (product, market_price, discount_price, order_id)
        )
    else:
        execute(
            "UPDATE orders SET status='待发货' WHERE id=%s AND status='待处理'",
            (order_id,)
        )

    # 扣减库存
    inv = fetch_one("SELECT remaining_qty FROM inventory WHERE product=%s", (product,))
    stock = inv[0] if inv else 0
    if stock <= 0:
        return jsonify({"success": False, "msg": "该商品库存为0，请补充后再审核"}), 400

    execute(
        "UPDATE inventory SET remaining_qty = remaining_qty - 1, outbound_qty = outbound_qty + 1 "
        "WHERE product=%s AND remaining_qty > 0",
        (product,)
    )
    return jsonify({"success": True})


@us.route('/users/audit/reject/<int:order_id>', methods=["POST"])
def audit_reject(order_id):
    """退回订单：状态设为 已退回"""
    execute(
        "UPDATE orders SET status='已退回' WHERE id=%s AND status='待处理'",
        (order_id,)
    )
    return redirect('/users/audit')


# ========== 用户 API（行内新增/编辑） ==========

@us.route('/users/api_create', methods=["POST"])
def api_create_user():
    """
    API：行内新增用户（仅管理员）
    默认密码 123456，创建成功后弹窗提示
    """
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
    """
    API：行内编辑用户（仅管理员）
    可修改角色和折扣率
    """
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


@us.route('/users/delete/<int:user_id>', methods=["POST"])
def delete_user(user_id):
    """删除用户（仅管理员）"""
    if session.get('user_level') != '管理员':
        return redirect('/users/list')
    execute("DELETE FROM user_info WHERE id = %s", (user_id,))
    return redirect('/users/list')


# ========== 地址管理 ==========

@us.route('/users/address', methods=["GET"])
def address_page():
    """
    地址管理页面
    管理员可查看所有用户的地址，普通用户只看自己的
    省市区数据从 regions.py 读取，前端三级联动
    """
    rows = fetch_all(
        "SELECT a.id, a.username, a.contact, a.phone, a.province, a.city, a.district, "
        "a.street, a.detail, a.is_default, a.create_time "
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

    # 用户列表供下拉选择所属用户（管理员新增地址时可选）
    user_rows = fetch_all("SELECT id, user FROM user_info ORDER BY user")
    user_list = [{"id": r[0], "name": r[1]} for r in user_rows]

    provinces = get_provinces()
    return render_template(
        "users/address.html",
        addresses=addresses,
        users=user_list,
        provinces=provinces,
        regions_json=json.dumps(REGIONS, ensure_ascii=False)
    )


@us.route('/users/address/add', methods=["POST"])
def address_add():
    """
    新增地址
    每人最多 5 条，设为默认时会取消该用户原有默认地址
    """
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

        # 检查每人最多 5 条的限制
        count_row = fetch_one("SELECT COUNT(*) FROM addresses WHERE username=%s", (username,))
        if count_row and count_row[0] >= 5:
            return jsonify({"error": "每个用户最多添加5条地址"}), 400

        # 如果设为默认，先清除该用户的其他默认地址
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
    """获取单条地址详情（JSON）"""
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
    """编辑地址"""
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

        # 获取原地址所属用户，用于处理默认地址的互斥逻辑
        row = fetch_one("SELECT username FROM addresses WHERE id=%s", (addr_id,))
        if not row:
            return jsonify({"error": "地址不存在"}), 404
        username = row[0]

        if is_default:
            execute("UPDATE addresses SET is_default=0 WHERE username=%s", (username,))

        execute(
            "UPDATE addresses SET contact=%s, phone=%s, province=%s, city=%s, district=%s, "
            "street=%s, detail=%s, is_default=%s WHERE id=%s",
            (contact, phone, province, city, district, street, detail, is_default, addr_id)
        )
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error editing address: {e}")
        return jsonify({"error": "编辑失败"}), 500


@us.route('/users/address/delete/<int:addr_id>', methods=["POST"])
def address_delete(addr_id):
    """删除地址"""
    try:
        execute("DELETE FROM addresses WHERE id=%s", (addr_id,))
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error deleting address: {e}")
        return jsonify({"error": "删除失败"}), 500
