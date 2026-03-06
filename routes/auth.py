# -*- coding: utf-8 -*-
"""
认证路由模块
功能说明：处理用户登录、登出、密码修改等认证相关功能
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models.user import User
from models.database import db, get_beijing_time

# 创建认证蓝图
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    用户登录
    GET：显示登录页面
    POST：处理登录表单提交
    """
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('请输入用户名和密码', 'danger')
            return render_template('login.html')

        # 查询用户
        user = User.query.filter_by(username=username, is_active=True).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('用户名或密码错误', 'danger')
            return render_template('login.html')

        # 登录成功，记录登录时间
        user.last_login_at = get_beijing_time()
        db.session.commit()

        login_user(user, remember=True)
        flash(f'欢迎回来，{user.display_name or user.username}！', 'success')

        # 跳转到原始请求页面或首页
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.index'))

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """
    用户登出
    功能：清除登录状态，跳转到登录页
    """
    logout_user()
    flash('已安全退出', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    修改密码
    GET：显示修改密码页面
    POST：处理密码修改请求
    """
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # 验证旧密码
        if not check_password_hash(current_user.password_hash, old_password):
            flash('当前密码错误', 'danger')
            return render_template('change_password.html')

        # 验证新密码
        if len(new_password) < 6:
            flash('新密码长度不能少于6位', 'danger')
            return render_template('change_password.html')

        if new_password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return render_template('change_password.html')

        # 更新密码
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        flash('密码修改成功，请重新登录', 'success')
        logout_user()
        return redirect(url_for('auth.login'))

    return render_template('change_password.html')
