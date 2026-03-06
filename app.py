# -*- coding: utf-8 -*-
"""
爱客服AI智能客服系统 - 主应用入口
功能说明：Flask Web应用主文件，注册路由、初始化组件
服务端口：6000
目录：aikefu
时间：使用北京时间（Asia/Shanghai，UTC+8）
"""

import os
import logging
import logging.handlers
from flask import Flask
from flask_login import LoginManager

# 导入配置
import config

# 导入数据库
from models.database import db, init_db

# 导入登录管理
login_manager = LoginManager()


def create_app():
    """
    创建并配置Flask应用
    功能：工厂模式创建应用，注册所有蓝图和扩展
    返回：配置好的Flask应用实例
    """
    app = Flask(__name__, template_folder='templates', static_folder='static')

    # ---- 基本配置 ----
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['DEBUG'] = config.DEBUG

    # ---- 初始化日志 ----
    _setup_logging(app)

    # ---- 初始化数据库 ----
    init_db(app)

    # ---- 初始化登录管理 ----
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '请先登录'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        """Flask-Login用户加载回调"""
        from models.user import User
        return User.query.get(int(user_id))

    # ---- 注册蓝图（路由模块）----
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.industry import industry_bp
    from routes.shop import shop_bp
    from routes.knowledge import knowledge_bp
    from routes.rules import rules_bp
    from routes.messages import messages_bp
    from routes.blacklist import blacklist_bp
    from routes.stats import stats_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(industry_bp, url_prefix='/industry')
    app.register_blueprint(shop_bp, url_prefix='/shop')
    app.register_blueprint(knowledge_bp, url_prefix='/knowledge')
    app.register_blueprint(rules_bp, url_prefix='/rules')
    app.register_blueprint(messages_bp, url_prefix='/messages')
    app.register_blueprint(blacklist_bp, url_prefix='/blacklist')
    app.register_blueprint(stats_bp, url_prefix='/stats')
    app.register_blueprint(api_bp, url_prefix='/api')

    # ---- 启动定时任务调度器 ----
    from modules.scheduler import TaskScheduler
    scheduler = TaskScheduler()
    scheduler.init_app(app)

    # ---- 注册全局模板变量 ----
    @app.context_processor
    def inject_globals():
        """
        注入全局模板变量
        功能：在所有模板中可直接使用这些变量
        """
        from models.database import get_beijing_time
        return {
            'system_name': config.SYSTEM_NAME,
            'system_version': config.SYSTEM_VERSION,
            'now': get_beijing_time(),
        }

    app.logger.info(f"[启动] {config.SYSTEM_NAME} {config.SYSTEM_VERSION} 启动成功")
    app.logger.info(f"[启动] 服务端口：{config.PORT}，数据库：{config.DATABASE_PATH}")

    return app


def _setup_logging(app):
    """
    配置日志系统
    功能：设置文件日志和控制台日志，按日期轮转
    日志目录：logs/
    """
    # 创建日志目录
    os.makedirs(config.LOG_DIR, exist_ok=True)

    # 日志格式（包含北京时间）
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 文件日志处理器（按大小轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(config.LOG_DIR, 'aikefu.log'),
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding='utf-8',
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # 控制台日志处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if config.DEBUG else logging.INFO)

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


# ============================================================
# 程序入口
# ============================================================
if __name__ == '__main__':
    app = create_app()
    print(f"""
╔══════════════════════════════════════════════╗
║       爱客服AI智能客服系统 已启动              ║
║  系统版本：{config.SYSTEM_VERSION}                          ║
║  访问地址：http://0.0.0.0:{config.PORT}           ║
║  管理后台：http://localhost:{config.PORT}/         ║
║  默认账号：admin / admin123                  ║
║  请及时修改默认密码！                         ║
╚══════════════════════════════════════════════╝
    """)
    app.run(
        host='0.0.0.0',
        port=config.PORT,
        debug=config.DEBUG,
    )
