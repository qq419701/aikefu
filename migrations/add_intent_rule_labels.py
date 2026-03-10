# -*- coding: utf-8 -*-
"""
数据库迁移：为 intent_rules 表新增 intent_code_label 和 action_code_label 字段
执行命令：python migrations/add_intent_rule_labels.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models.database import db


def upgrade():
    app = create_app()
    with app.app_context():
        with db.engine.begin() as conn:
            try:
                conn.execute(db.text(
                    "ALTER TABLE intent_rules ADD COLUMN intent_code_label VARCHAR(200) NULL"
                ))
                print("✅ 已添加 intent_code_label 字段")
            except Exception as e:
                if "Duplicate column" in str(e) or "already exists" in str(e):
                    print("⚠️  intent_code_label 字段已存在，跳过")
                else:
                    raise

            try:
                conn.execute(db.text(
                    "ALTER TABLE intent_rules ADD COLUMN action_code_label VARCHAR(200) NULL"
                ))
                print("✅ 已添加 action_code_label 字段")
            except Exception as e:
                if "Duplicate column" in str(e) or "already exists" in str(e):
                    print("⚠️  action_code_label 字段已存在，跳过")
                else:
                    raise

        print("✅ 迁移完成")


if __name__ == '__main__':
    upgrade()
