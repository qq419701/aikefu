# 爱客服AI智能客服系统

> 版本：v3.0.0 | 更新日期：2026-03-12

## 🆕 v3.0.0 更新日志（2026-03-12）

### 🔴 紧急Bug修复
- **修复 `MaxKBClient.health_check()` 方法不存在**：`routes/settings.py` 第87行调用该方法时报 `AttributeError` 500，现已补全

### 🔧 后端新增

#### `modules/maxkb_client.py` 补全4个缺失方法
- `health_check()` — 连接健康检测
- `list_documents()` — 列出MaxKB文档列表
- `search_similar()` — 语义相似搜索（用于语义级查重）
- `get_stats()` — 获取MaxKB数据集统计

#### `models/knowledge.py` 新增3个字段
- `maxkb_synced` (Boolean) — 是否已同步到MaxKB
- `maxkb_synced_at` (DateTime) — 最后同步时间
- `source` (String) — 来源标记（manual/ai_learning/ai_generated）

#### `models/database.py` 补入3个默认配置
- `learning_dedup_similarity` = 0.8
- `learning_auto_keywords` = false
- `kb_maxkb_full_sync_on_save` = false

### 🌐 新增6个API路由

| 路由 | 方法 | 功能 |
|------|------|------|
| `/learning/api/pending-count` | GET | 侧边栏角标待审核数量 |
| `/learning/history` | GET | 审核历史页面 |
| `/knowledge/stats` | GET | 知识库健康仪表盘 |
| `/knowledge/api/check-duplicate` | POST | 双层去重检测（精确+语义） |
| `/settings/maxkb` | GET | MaxKB管理面板 |
| `/settings/maxkb/sync-all` | POST | 一键全量同步到MaxKB |

### 🎨 前端优化

#### 侧边栏
- 修复侧边栏无法滚动问题（`height: 100vh` + `overflow-y: auto`）
- 删除重复的「AI批量生成」「健康仪表盘」子菜单（知识库页面顶部按钮已有）
- 删除「审核历史」侧边栏子菜单，改为学习中心页面内按钮
- 新增管理员专属「MaxKB管理」子菜单（系统设置下方）

#### 学习中心页面
- 工具栏新增「审核历史」按钮（AI助手左侧）
- 置信度颜色分层：`<30%` 🔴红 / `30-60%` 🟡黄 / `≥60%` 🟢绿
- 侧边栏学习中心角标每30秒自动刷新（待审核数量）
- 键盘快捷键：`Y`=确认入库 / `N`=拒绝 / `→`=下一页

#### 知识库页面
- 新增「命中次数」列（彩色显示）
- 新增「MaxKB」同步状态列（✅已同步 / ❌未同步）
- 右上角新增「健康仪表盘」「AI批量生成」快速入口按钮

#### 新建3个页面
- `📊 /knowledge/stats` — 知识库健康仪表盘（总条数、死条目数、命中TOP10、MaxKB对比）
- `📋 /learning/history` — 审核历史（支持行业/状态筛选+分页）
- `⚙️ /settings/maxkb` — MaxKB管理面板（连接测试、一键全量同步、按行业同步进度）

### 🚀 部署说明

```bash
# 正确重启命令（supervisor管理）
supervisorctl restart aikefu:aikefu_00

# 查看日志
tail -50 /www/wwwroot/aikefu/logs/error.log
```

服务运行在端口 **5000**，由 supervisor + gunicorn 管理。

---

## 系统架构

- **Python Flask** + Gunicorn（2 workers，4 threads）
- **MySQL** (port 3306, database: aikefu)
- **MaxKB** 语义知识库（可选集成）
- **豆包 AI**（doubao-lite / doubao-pro）

## 功能模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 控制面板 | `/` | 系统概览 |
| 消息管理 | `/messages/` | 买家消息处理 |
| 学习中心 | `/learning/` | AI回复审核 |
| 审核历史 | `/learning/history` | 已处理记录查询 |
| 知识库 | `/knowledge/` | 问答对管理 |
| 健康仪表盘 | `/knowledge/stats` | 知识库数据分析 |
| AI批量生成 | `/knowledge/generate` | AI生成知识库条目 |
| 系统设置 | `/settings/` | AI参数、学习模式等配置 |
| MaxKB管理 | `/settings/maxkb` | MaxKB连接与同步（管理员） |
