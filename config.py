# -*- coding: utf-8 -*-
"""
配置管理模块
配置存储到 ~/.aikefu-client/config.json，密码AES加密保存
"""
import os
import json
from typing import Optional

# aikefu服务器地址
AIKEFU_SERVER = "http://8.145.43.255:5000"

# MySQL默认配置（连接aikefu数据库）
MYSQL_CONFIG = {
    "host": "8.145.43.255",
    "port": 3306,
    "database": "aikefu",
    "charset": "utf8mb4",
}

# 本地配置文件路径
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".aikefu-client")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# 应用版本
APP_VERSION = "1.0.0"
APP_NAME = "爱客服采集客户端"


def load_config() -> dict:
    """从配置文件加载配置"""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict) -> bool:
    """保存配置到文件"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def is_configured() -> bool:
    """检查是否已完成初始配置（MySQL连接信息）"""
    cfg = load_config()
    return bool(cfg.get("mysql", {}).get("user"))


def get_mysql_config() -> Optional[dict]:
    """获取MySQL连接配置（密码已解密）"""
    from core.encrypt import decrypt_password

    cfg = load_config()
    mysql = cfg.get("mysql", {})
    if not mysql.get("user"):
        return None

    result = {
        "host": mysql.get("host", MYSQL_CONFIG["host"]),
        "port": int(mysql.get("port", MYSQL_CONFIG["port"])),
        "database": mysql.get("database", MYSQL_CONFIG["database"]),
        "charset": MYSQL_CONFIG["charset"],
        "user": mysql.get("user", ""),
        "password": "",
    }

    enc_password = mysql.get("password_enc", "")
    if enc_password:
        try:
            result["password"] = decrypt_password(enc_password)
        except Exception:
            result["password"] = ""

    return result


def get_server_url() -> str:
    """获取aikefu服务器地址"""
    cfg = load_config()
    return cfg.get("server_url", AIKEFU_SERVER)


# ── U号租配置 ──────────────────────────────────────────────────────────────

_UHAOZU_SETTINGS_DEFAULT = {
    "max_exchange_per_order": 5,
    "price_markup_rules": [
        {"min": 0.1, "max": 0.5, "markup": 0.5},
        {"min": 0.5, "max": 1.0, "markup": 1.0},
        {"min": 1.0, "max": 10.0, "markup": 2.0},
    ],
    "game_configs": {
        "王者荣耀": {
            "platforms": ["安卓", "苹果"],
            "login_methods": ["微信", "QQ"],
            "filters": {
                "no_deposit": True,
                "time_rental_bonus": True,
                "login_tool": True,
                "anti_addiction": True,
                "non_cloud": True,
                "high_login_rate": True,
                "no_friend_add": False,
                "allow_ranked": True,
            },
        },
    },
}


def get_uhaozu_accounts() -> list:
    """获取U号租账号列表（密码已解密）"""
    from core.encrypt import decrypt_password

    cfg = load_config()
    accounts = cfg.get("uhaozu_accounts", [])
    result = []
    for acc in accounts:
        entry = dict(acc)
        enc = entry.pop("password_enc", "")
        try:
            entry["password"] = decrypt_password(enc) if enc else ""
        except Exception:
            entry["password"] = ""
        result.append(entry)
    return result


def save_uhaozu_accounts(accounts: list) -> bool:
    """保存U号租账号列表（密码加密存储）"""
    from core.encrypt import encrypt_password

    cfg = load_config()
    stored = []
    for acc in accounts:
        entry = {k: v for k, v in acc.items() if k != "password"}
        plain = acc.get("password", "")
        if plain:
            try:
                entry["password_enc"] = encrypt_password(plain)
            except Exception:
                entry["password_enc"] = acc.get("password_enc", "")
        else:
            entry["password_enc"] = acc.get("password_enc", "")
        stored.append(entry)
    cfg["uhaozu_accounts"] = stored
    return save_config(cfg)


def get_uhaozu_settings() -> dict:
    """获取U号租设置（换号次数、加价规则、游戏配置）"""
    import copy
    cfg = load_config()
    saved = cfg.get("uhaozu_settings", {})
    defaults = copy.deepcopy(_UHAOZU_SETTINGS_DEFAULT)
    # 浅层合并，game_configs 单独处理（保留默认游戏配置并覆盖已保存的游戏配置）
    for k, v in saved.items():
        if k == "game_configs":
            merged_games = dict(defaults.get("game_configs", {}))
            merged_games.update(v)
            defaults["game_configs"] = merged_games
        else:
            defaults[k] = v
    return defaults


def save_uhaozu_settings(settings: dict) -> bool:
    """保存U号租设置"""
    cfg = load_config()
    cfg["uhaozu_settings"] = settings
    return save_config(cfg)


def get_default_uhaozu_account() -> Optional[dict]:
    """获取默认U号租账号（密码已解密）"""
    accounts = get_uhaozu_accounts()
    for acc in accounts:
        if acc.get("is_default"):
            return acc
    return accounts[0] if accounts else None
