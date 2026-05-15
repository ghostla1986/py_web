# -*- coding: utf-8 -*-
"""
库存管理 / 商品审核模块（蓝图：inv）
包含库存商品的增删改查、仓管员添加商品的审核流程、
驳回商品 1 天内可修改重提、超时自动失效
"""

from flask import Blueprint, request, redirect, jsonify, render_template, session
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from db import fetch_all, fetch_one, execute
from datetime import datetime, timedelta

inv = Blueprint("inventory", __name__)

# 驳回后允许修改的天数
REJECT_DEADLINE_DAYS = 1


# ========== 库存列表 ==========

@inv.route('/inventory/list', methods=["GET", "POST"])
def inventory_list():
    """
    库存管理列表页
    仅显示 audit_status='已通过' 的商品
    自动将超时的驳回商品标记为"已失效"
    """
    user_level = session.get('user_level', '')
    if user_level not in ('管理员', '物流仓管员', '物流专员'):
        return redirect('/main/list')

    # 自动标记已过期的驳回商品为"已失效"
    deadline = datetime.now() - timedelta(days=REJECT_DEADLINE_DAYS)
    execute(
        "UPDATE inventory SET audit_status='已失效' "
        "WHERE audit_status='已驳回' AND reject_time IS NOT NULL AND reject_time < %s",
        (deadline,)
    )

    # 只显示审核通过的商品
    rows = fetch_all(
        "SELECT id, product, price, total_qty, outbound_qty, remaining_qty "
        "FROM inventory WHERE audit_status='已通过' ORDER BY id"
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


# ========== 添加商品 ==========

@inv.route('/inventory/create', methods=["GET", "POST"])
def create_item():
    """
    添加商品
    管理员：直接上架（audit_status='已通过'）
    仓管员：需审批（audit_status='待审核'）
    记录提交人（submitted_by）用于后续审核流程
    """
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

        user_name = session.get('user_name', '')
        audit_status = '已通过' if user_level == '管理员' else '待审核'

        execute(
            "INSERT INTO inventory (product, price, total_qty, outbound_qty, remaining_qty, audit_status, submitted_by) "
            "VALUES (%s, %s, %s, 0, %s, %s, %s)",
            (product, price, total_qty, total_qty, audit_status, user_name)
        )
        return redirect('/inventory/list')
    except ValueError:
        return "格式错误", 400
    except Exception as e:
        print(f"Error creating inventory item: {e}")
        return "创建失败", 500


@inv.route('/inventory/edit/<int:item_id>', methods=["GET", "POST"])
def edit_item(item_id):
    """编辑商品（独立后备页面）"""
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

    # POST 处理略（实际通过行内编辑 API 完成）
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
    """删除商品（仅管理员）"""
    execute("DELETE FROM inventory WHERE id = %s", (item_id,))
    return redirect('/inventory/list')


# ========== JSON API ==========

@inv.route('/inventory/get_item/<int:item_id>', methods=["GET"])
def get_item(item_id):
    """获取单条商品详情（JSON）"""
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
    """
    API：添加商品（行内插入时调用）
    管理员直接上架，仓管员需进入审核流程
    """
    user_level = session.get('user_level', '')
    try:
        product = request.form.get("product")
        price_str = request.form.get("price")
        total_str = request.form.get("total_qty")

        if not product or not price_str or not total_str:
            return jsonify({"error": "缺少必要字段"}), 400

        price = float(price_str)
        total_qty = int(total_str)

        user_name = session.get('user_name', '')
        audit_status = '已通过' if user_level == '管理员' else '待审核'

        new_id = execute(
            "INSERT INTO inventory (product, price, total_qty, outbound_qty, remaining_qty, audit_status, submitted_by) "
            "VALUES (%s, %s, %s, 0, %s, %s, %s)",
            (product, price, total_qty, total_qty, audit_status, user_name)
        )
        return jsonify({"success": True, "id": new_id})
    except ValueError:
        return jsonify({"error": "格式错误"}), 400
    except Exception as e:
        print(f"Error creating inventory item: {e}")
        return jsonify({"error": "创建失败"}), 500


@inv.route('/inventory/api_edit/<int:item_id>', methods=["POST"])
def api_edit_item(item_id):
    """API：编辑商品（管理员专用）"""
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


# ========== 商品审核 ==========

@inv.route('/inventory/audit', methods=["GET"])
def audit_items():
    """商品审核入口（仅管理员），重定向到待审批页面"""
    if session.get('user_level') != '管理员':
        return redirect('/inventory/pending')
    return redirect('/inventory/pending')


@inv.route('/inventory/audit/approve/<int:item_id>', methods=["POST"])
def audit_approve(item_id):
    """审核通过：将商品状态设为已通过"""
    if session.get('user_level') != '管理员':
        return jsonify({"error": "无权限"}), 403
    execute(
        "UPDATE inventory SET audit_status='已通过' WHERE id=%s AND audit_status='待审核'",
        (item_id,)
    )
    return jsonify({"success": True})


@inv.route('/inventory/audit/reject/<int:item_id>', methods=["POST"])
def audit_reject(item_id):
    """
    驳回商品：状态设为"已驳回"，记录驳回时间
    仓管员可在 1 天内修改后重新提交
    """
    if session.get('user_level') != '管理员':
        return jsonify({"error": "无权限"}), 403
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute(
        "UPDATE inventory SET audit_status='已驳回', reject_time=%s WHERE id=%s AND audit_status='待审核'",
        (now, item_id)
    )
    return jsonify({"success": True, "rejected_at": now})


# ========== 仓管员：撤回待审核商品 ==========

@inv.route('/inventory/pending/withdraw/<int:item_id>', methods=["POST"])
def withdraw_pending(item_id):
    """
    仓管员撤回自己提交的待审核商品
    撤回后商品进入"被驳回商品"列表，带"撤回商品"标签
    """
    user_level = session.get('user_level', '')
    user_name = session.get('user_name', '')
    if user_level not in ('物流仓管员', '物流专员'):
        return jsonify({"error": "无权限"}), 403

    row = fetch_one(
        "SELECT id, submitted_by FROM inventory WHERE id=%s AND audit_status='待审核'",
        (item_id,)
    )
    if not row:
        return jsonify({"error": "商品不存在或状态异常"}), 404
    if row[1] != user_name:
        return jsonify({"error": "只能撤回自己提交的商品"}), 403

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute(
        "UPDATE inventory SET audit_status='已撤回', reject_time=%s WHERE id=%s AND audit_status='待审核'",
        (now, item_id)
    )
    return jsonify({"success": True})


# ========== 仓管员：删除撤回商品 ==========

@inv.route('/inventory/rejected/delete/<int:item_id>', methods=["POST"])
def delete_rejected(item_id):
    """
    仓管员删除自己撤回的商品
    只能删除 audit_status='已撤回' 的商品
    """
    user_level = session.get('user_level', '')
    user_name = session.get('user_name', '')
    if user_level not in ('物流仓管员', '物流专员'):
        return jsonify({"error": "无权限"}), 403

    row = fetch_one(
        "SELECT id, submitted_by FROM inventory WHERE id=%s AND audit_status='已撤回'",
        (item_id,)
    )
    if not row:
        return jsonify({"error": "商品不存在或状态异常"}), 404
    if row[1] != user_name:
        return jsonify({"error": "只能删除自己的商品"}), 403

    execute("DELETE FROM inventory WHERE id=%s", (item_id,))
    return jsonify({"success": True})


# ========== 待审批商品（管理员 + 仓管员通用） ==========

@inv.route('/inventory/pending', methods=["GET"])
def pending_items():
    """
    待审批商品页面
    管理员：看到所有待审核商品，可审核/驳回
    仓管员：只看到自己提交的，可撤回
    支持提交时间排序
    """
    user_level = session.get('user_level', '')
    if user_level not in ('管理员', '物流仓管员', '物流专员'):
        return redirect('/inventory/list')

    user_name = session.get('user_name', '')
    sort = request.args.get('sort', 'desc')
    if sort not in ('asc', 'desc'):
        sort = 'desc'
    time_order = "ASC" if sort == 'asc' else "DESC"

    if user_level == '管理员':
        rows = fetch_all(
            f"SELECT id, product, price, total_qty, outbound_qty, remaining_qty, submitted_by, create_time "
            f"FROM inventory WHERE audit_status='待审核' ORDER BY create_time {time_order}"
        )
    else:
        rows = fetch_all(
            f"SELECT id, product, price, total_qty, outbound_qty, remaining_qty, submitted_by, create_time "
            f"FROM inventory WHERE audit_status='待审核' AND submitted_by=%s ORDER BY create_time {time_order}",
            (user_name,)
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
            "submitted_by": r[6] or '',
            "create_time": r[7].strftime("%Y-%m-%d %H:%M:%S") if r[7] else ""
        })
    return render_template("inventory/pending.html", items=items, user_level=user_level, sort=sort)


# ========== 被驳回商品管理 ==========

@inv.route('/inventory/rejected', methods=["GET"])
def rejected_items():
    """
    被驳回商品页面（仅仓管员可见）
    展示已驳回/已撤回/已失效的商品
    已驳回的商品可在 1 天内修改重提
    已撤回的商品可删除
    支持按驳回时间排序
    """
    user_level = session.get('user_level', '')
    if user_level not in ('物流仓管员', '物流专员'):
        return redirect('/inventory/list')

    user_name = session.get('user_name', '')
    sort = request.args.get('sort', 'desc')
    if sort not in ('asc', 'desc'):
        sort = 'desc'
    time_order = "ASC" if sort == 'asc' else "DESC"

    # 自动标记超时驳回为已失效
    deadline = datetime.now() - timedelta(days=REJECT_DEADLINE_DAYS)
    execute(
        "UPDATE inventory SET audit_status='已失效' "
        "WHERE audit_status='已驳回' AND submitted_by=%s AND reject_time IS NOT NULL AND reject_time < %s",
        (user_name, deadline)
    )

    # 查询自己提交的所有被驳回/已撤回/已失效商品
    rows = fetch_all(
        f"SELECT id, product, price, total_qty, audit_status, create_time, reject_time FROM inventory "
        f"WHERE audit_status IN ('已驳回','已撤回','已失效') AND submitted_by=%s ORDER BY reject_time {time_order}",
        (user_name,)
    )
    items = []
    now = datetime.now()
    for r in rows:
        audit_st = r[4]
        reject_t = r[6]
        # 已驳回/已撤回且在 1 天内的可以修改/删除
        still_valid = (
            audit_st in ('已驳回', '已撤回')
            and reject_t
            and (now - reject_t).days < REJECT_DEADLINE_DAYS
        )
        items.append({
            "id": r[0],
            "product": r[1],
            "price": float(r[2]),
            "total_qty": r[3],
            "audit_status": audit_st,
            "can_edit": still_valid and audit_st == '已驳回',   # 已驳回可修改重提
            "can_delete": audit_st == '已撤回',                 # 已撤回可删除
            "create_time": r[5].strftime("%Y-%m-%d %H:%M:%S") if r[5] else ""
        })
    return render_template(
        "inventory/rejected.html", items=items, deadline_days=REJECT_DEADLINE_DAYS, sort=sort
    )


@inv.route('/inventory/rejected/resubmit/<int:item_id>', methods=["POST"])
def resubmit_rejected(item_id):
    """
    仓管员修改被驳回商品后重新提交
    可修改：商品名、单价、总量
    提交后状态回到"待审核"并清空驳回时间
    """
    user_level = session.get('user_level', '')
    user_name = session.get('user_name', '')
    if user_level not in ('物流仓管员', '物流专员'):
        return jsonify({"error": "无权限"}), 403

    # 校验：只能修改自己的驳回商品，且在 1 天有效期内
    deadline = datetime.now() - timedelta(days=REJECT_DEADLINE_DAYS)
    row = fetch_one(
        "SELECT id, submitted_by, reject_time FROM inventory WHERE id=%s AND audit_status='已驳回'",
        (item_id,)
    )
    if not row:
        return jsonify({"error": "商品不存在或状态异常"}), 404
    if row[1] != user_name:
        return jsonify({"error": "只能修改自己提交的商品"}), 403
    if row[2] and row[2] < deadline:
        return jsonify({"error": "已超过修改时限，无法重新提交"}), 400

    try:
        product = request.form.get("product")
        price_str = request.form.get("price")
        total_str = request.form.get("total_qty")

        if not product or not price_str or not total_str:
            return jsonify({"error": "缺少必要字段"}), 400

        new_price = float(price_str)
        new_total = int(total_str)

        # 更新商品信息，重置为待审核
        execute(
            "UPDATE inventory SET product=%s, price=%s, total_qty=%s, remaining_qty=%s, "
            "audit_status='待审核', reject_time=NULL WHERE id=%s",
            (product, new_price, new_total, new_total, item_id)
        )
        return jsonify({"success": True})
    except ValueError:
        return jsonify({"error": "格式错误"}), 400
    except Exception as e:
        print(f"Error resubmitting inventory item: {e}")
        return jsonify({"error": "提交失败"}), 500


# ========== 仓管员编辑库存（价格和总量，仅能增加） ==========

@inv.route('/inventory/api_warehouse_edit/<int:item_id>', methods=["POST"])
def api_warehouse_edit_item(item_id):
    """
    API：仓管员编辑库存
    仅能修改 单价 和 总数量，且只能增不能减
    前端和后端双重校验
    """
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

        # 读取当前值做增量校验
        row = fetch_one(
            "SELECT price, total_qty FROM inventory WHERE id=%s",
            (item_id,)
        )
        if not row:
            return jsonify({"error": "商品不存在"}), 404

        old_price = float(row[0])
        old_total = int(row[1])

        # 只能增加不能减少
        if new_price < old_price:
            return jsonify({"error": "单价只能增加，不能减少"}), 400
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
