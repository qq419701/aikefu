# -*- coding: utf-8 -*-
"""
店铺管理路由模块
功能说明：多店铺管理，同一行业多个店铺共享知识库
支持拼多多、淘宝等电商平台的店铺配置
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Shop, Industry
from models.database import db, get_beijing_time

# 创建店铺管理蓝图
shop_bp = Blueprint('shop', __name__)


@shop_bp.route('/')
@login_required
def index():
    """
    店铺列表页
    功能：显示用户有权限管理的所有店铺
    """
    if current_user.is_admin():
        shops = Shop.query.order_by(Shop.industry_id, Shop.created_at).all()
    else:
        shops = Shop.query.filter_by(
            industry_id=current_user.industry_id
        ).order_by(Shop.created_at).all()

    # 按行业分组展示
    industry_shops = {}
    for shop in shops:
        ind_name = shop.industry.name if shop.industry else '未知行业'
        ind_icon = shop.industry.icon if shop.industry else '🏢'
        key = (ind_name, ind_icon, shop.industry_id)
        if key not in industry_shops:
            industry_shops[key] = []
        industry_shops[key].append(shop)

    return render_template('shop/index.html', industry_shops=industry_shops)


@shop_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """
    添加店铺
    GET：显示添加表单（含行业选择）
    POST：保存新店铺
    说明：一个行业可以添加多个店铺，共享该行业的知识库
    """
    # 获取可选行业列表（根据权限过滤）
    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id,
            is_active=True
        ).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        industry_id = request.form.get('industry_id', type=int)
        platform = request.form.get('platform', 'pdd')
        platform_shop_id = request.form.get('platform_shop_id', '').strip()
        client_id = request.form.get('client_id', '').strip()
        client_secret = request.form.get('client_secret', '').strip()
        auto_exchange = 'auto_exchange_enabled' in request.form
        uzuzu_account = request.form.get('uzuzu_account', '').strip()
        uzuzu_password = request.form.get('uzuzu_password', '').strip()
        note = request.form.get('note', '').strip()

        if not name or not industry_id:
            flash('店铺名称和所属行业为必填项', 'danger')
            return render_template('shop/add.html', industries=industries)

        # 权限检查
        if not current_user.can_manage_industry(industry_id):
            flash('无权限在该行业下创建店铺', 'danger')
            return render_template('shop/add.html', industries=industries)

        shop = Shop(
            name=name,
            industry_id=industry_id,
            platform=platform,
            platform_shop_id=platform_shop_id,
            client_id=client_id,
            client_secret=client_secret,
            auto_exchange_enabled=auto_exchange,
            uzuzu_account=uzuzu_account,
            uzuzu_password=uzuzu_password,
            note=note,
            auto_reply_enabled=True,
            is_active=True,
            created_at=get_beijing_time(),
        )
        db.session.add(shop)
        db.session.commit()

        flash(f'店铺「{name}」添加成功', 'success')
        return redirect(url_for('shop.index'))

    return render_template('shop/add.html', industries=industries)


@shop_bp.route('/<int:shop_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(shop_id):
    """
    编辑店铺配置
    GET：显示编辑表单
    POST：保存修改
    """
    shop = Shop.query.get_or_404(shop_id)

    # 权限检查
    if not current_user.can_manage_industry(shop.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('shop.index'))

    if current_user.is_admin():
        industries = Industry.query.filter_by(is_active=True).all()
    else:
        industries = Industry.query.filter_by(
            id=current_user.industry_id,
            is_active=True
        ).all()

    if request.method == 'POST':
        shop.name = request.form.get('name', shop.name).strip()
        shop.platform = request.form.get('platform', shop.platform)
        shop.platform_shop_id = request.form.get('platform_shop_id', '').strip()
        shop.client_id = request.form.get('client_id', '').strip()

        # 密码/密钥只在有输入时更新
        new_secret = request.form.get('client_secret', '').strip()
        if new_secret:
            shop.client_secret = new_secret

        shop.auto_reply_enabled = 'auto_reply_enabled' in request.form
        shop.auto_exchange_enabled = 'auto_exchange_enabled' in request.form
        shop.uzuzu_account = request.form.get('uzuzu_account', '').strip()

        new_uzuzu_pwd = request.form.get('uzuzu_password', '').strip()
        if new_uzuzu_pwd:
            shop.uzuzu_password = new_uzuzu_pwd

        shop.custom_prompt = request.form.get('custom_prompt', '').strip()
        shop.note = request.form.get('note', '').strip()
        shop.updated_at = get_beijing_time()

        db.session.commit()
        flash('店铺配置已保存', 'success')
        return redirect(url_for('shop.index'))

    return render_template('shop/edit.html', shop=shop, industries=industries)


@shop_bp.route('/<int:shop_id>/toggle', methods=['POST'])
@login_required
def toggle(shop_id):
    """
    切换店铺启用/禁用状态
    """
    shop = Shop.query.get_or_404(shop_id)

    if not current_user.can_manage_industry(shop.industry_id):
        return jsonify({'success': False, 'message': '无权限'}), 403

    shop.is_active = not shop.is_active
    shop.updated_at = get_beijing_time()
    db.session.commit()

    status = '启用' if shop.is_active else '禁用'
    return jsonify({'success': True, 'message': f'店铺已{status}', 'is_active': shop.is_active})


@shop_bp.route('/<int:shop_id>/delete', methods=['POST'])
@login_required
def delete(shop_id):
    """
    删除店铺
    功能：删除店铺配置（保留消息历史记录）
    """
    shop = Shop.query.get_or_404(shop_id)

    if not current_user.can_manage_industry(shop.industry_id):
        flash('无权限操作', 'danger')
        return redirect(url_for('shop.index'))

    shop_name = shop.name
    db.session.delete(shop)
    db.session.commit()

    flash(f'店铺「{shop_name}」已删除', 'success')
    return redirect(url_for('shop.index'))
