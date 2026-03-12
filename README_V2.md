# 爱客服AI智能客服系统 V2/V3 技术架构文档

> 版本：v3.0.0 | 更新时间：2026-03-12 | 语言：Python 3.11+ / Flask 3.x

---

## v3.0 更新说明（知识库 & 学习中心全面升级）

### 🔴 P0 Bug修复

| 编号 | 模块 | 问题 | 状态 |
|------|------|------|------|
| B1 | 学习中心 | `approve()` 入库后无 MaxKB 同步 | ✅ 已修复 |
| B2 | 学习中心 | `modify()` 入库后无 MaxKB 同步 | ✅ 已修复 |
| B3 | 知识库 | `api/batch-save` 批量保存无 MaxKB 同步 | ✅ 已修复 |
| B4 | 学习中心 | 无批量操作（逐条点击效率低） | ✅ 已修复 |
| B5 | 学习中心 | 入库时无重复检测 | ✅ 已修复 |
| B6 | 知识库 | 手动添加/批量保存时无重复检测 | ✅ 已修复 |
| B7 | 系统设置 | 无学习模式配置 | ✅ 已修复 |
| B8 | AI引擎 | `_check_learning_trigger` 触发条件写死 | ✅ 已修复 |

### 🚀 新功能

**批量操作（B4）**
- `POST /learning/batch-approve` - 批量确认入库（含去重+MaxKB同步）
- `POST /learning/batch-reject` - 批量拒绝
- `POST /learning/batch-approve-high` - 一键入库所有高置信度记录
- 学习中心UI：每条记录前增加复选框，支持全选/反选，浮动批量操作工具栏

**学习模式配置（B7/B8）**
- 在系统设置 → 学习中心设置中可动态调整学习模式：
  - 🟢 **全量模式（all）**：所有AI回复都进审核队列（刚上线阶段）
  - 🔵 **阈值模式（threshold）**：低置信度才进审核队列（默认）
  - 🔵 **自动模式（auto）**：高置信度自动入库，低置信度进队列
  - ⚫ **关闭模式（off）**：停止生成学习记录（知识库成熟后）

**新增系统配置项（v3.0）**

| 配置键 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `learning_mode` | string | 学习模式 | `threshold` |
| `learning_confidence_threshold` | float | 进审核队列的置信度上限 | `0.7` |
| `learning_auto_approve_threshold` | float | 自动入库的置信度下限 | `0.85` |
| `learning_dedup_enabled` | bool | 入库前去重检测 | `true` |
| `learning_page_size` | int | 学习中心每页条数 | `20` |
| `learning_maxkb_sync` | bool | 入库后自动同步MaxKB | `true` |
| `kb_dedup_enabled` | bool | 知识库手动添加去重 | `true` |

---

## 1. 系统架构图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       aikefu（服务端大脑）                                 │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │  AI消息处理引擎（modules/ai_engine.py）                             │   │
│  │                                                                   │   │
│  │  买家消息                                                          │   │
│  │      ↓                                                            │   │
│  │  [第〇层] 本地意图识别（数据库规则，可热更新，0成本0延迟）             │   │
│  │      ↓ 命中 action_code → 插件分流 → 立即回复 auto_reply_tpl → 跳过AI│   │
│  │      ↓ 命中 无action_code + 有auto_reply_tpl → 纯文字立即回复 → 跳过AI│   │
│  │      ↓ 无插件接管 / 未命中                                         │   │
│  │  [黑名单检查] → [情绪检测] → [退款AI决策] → [图片分析]              │   │
│  │      ↓                                                            │   │
│  │  [第一层] 知识库引擎（关键词/MaxKB语义，0成本，目标60%覆盖）          │   │
│  │      ↓ 未命中                                                     │   │
│  │  [第二层] 豆包AI（lite/pro/vision多模态，有成本，目标35%兜底）        │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────┐    │
│  │  知识库管理     │  │  实时增量学习   │  │  意图规则管理            │    │
│  │  aikefu后台    │  │  AI回复→待审核  │  │  数据库驱动，后台可配置  │    │
│  │  同步→MaxKB    │  │  运营审核→入库  │  │  关键词/动作/话术全配置  │    │
│  └────────────────┘  └────────────────┘  └─────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  系统设置（/settings/，SystemConfig 数据库表）                     │    │
│  │  豆包/MaxKB/系统行为/安全 四组可视化配置，替代 .env 硬编码          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  插件系统（models/plugin.py + routes/plugin.py）                  │    │
│  │  客户端注册能力 → aikefu下发任务 → 客户端执行 → 完成回调+自动回复   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│                    ↕ HTTP API (X-Shop-Token 鉴权)                        │
└──────────────────────────────────────────────────────────────────────────┘
                                  ↕
┌──────────────────────────────────────────────────────────────────────────┐
│                  dskehuduan（客户端执行层）                                │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  自动换号插件  │  │  退款处理插件  │  │  订单同步插件  │  │  自定义插件  │  │
│  │ auto_exchange │  │ handle_refund │  │  order_sync  │  │   任意码    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘  │
│  每2秒轮询 GET /api/plugin/tasks → 执行 → POST /api/plugin/tasks/<id>/done │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| Web框架 | Flask 3.x | 应用工厂模式，蓝图路由拆分 |
| ORM | Flask-SQLAlchemy | SQLite（开发）/ MySQL 8.0（生产） |
| 认证 | Flask-Login | Session认证，roles：admin/operator |
| AI | 字节跳动火山方舟 | doubao-lite / doubao-pro / doubao-vision-pro |
| 向量检索 | MaxKB（可选） | 语义相似度检索，命中率~85% |
| 定时任务 | APScheduler | 北京时间定时，统计/学习/黑名单 |
| 时区 | pytz Asia/Shanghai | 全系统统一北京时间（UTC+8） |
| 部署 | Gunicorn + Docker | `-w 2 -b 0.0.0.0:8000 "app:create_app()"` |

---

## 3. 目录结构

```
aikefu/
├── app.py                  # Flask工厂函数，蓝图注册
├── config.py               # 全局配置（从.env读取）
├── requirements.txt        # Python依赖
├── Dockerfile              # Docker镜像（python:3.11-slim）
├── docker-compose.yml      # 一键部署（含MySQL）
│
├── models/                 # 数据模型（SQLAlchemy）
│   ├── database.py         # db实例、init_db、默认数据初始化
│   ├── industry.py         # 行业（多租户中心表）
│   ├── shop.py             # 店铺（含shop_token鉴权）
│   ├── user.py             # 用户（admin/operator角色）
│   ├── message.py          # 消息记录（含direction='in'/'out'，完整对话记录）★更新
│   ├── knowledge.py        # 知识库条目
│   ├── intent_rule.py      # 意图规则（可自定义关键词+话术）
│   ├── system_config.py    # 系统配置（可视化编辑替代.env）★新
│   ├── plugin.py           # 插件注册+任务队列
│   ├── conversation.py     # 多轮对话上下文
│   ├── learning.py         # 增量学习记录
│   ├── blacklist.py        # 黑名单
│   ├── pdd_order.py        # 拼多多订单
│   └── stats.py            # 每日统计
│
├── modules/                # 核心业务逻辑
│   ├── ai_engine.py        # 消息处理主引擎（二层+意图+插件）
│   ├── doubao_ai.py        # 火山方舟API客户端
│   ├── emotion_detector.py # 情绪识别（5级，本地规则）
│   ├── knowledge_engine.py # 知识库检索（关键词/MaxKB）
│   ├── maxkb_client.py     # MaxKB语义检索客户端（可选）
│   └── scheduler.py        # APScheduler定时任务
│
├── routes/                 # Flask蓝图路由
│   ├── auth.py             # 登录/登出/改密
│   ├── dashboard.py        # 控制面板首页
│   ├── industry.py         # 行业管理CRUD
│   ├── shop.py             # 店铺管理CRUD
│   ├── knowledge.py        # 知识库管理+AI批量生成
│   ├── intent_rule.py      # 意图规则管理
│   ├── settings.py         # 系统设置页面（/settings/）★新
│   ├── messages.py         # 消息记录管理
│   ├── learning.py         # 学习中心（审核AI回复）
│   ├── blacklist.py        # 黑名单管理
│   ├── risk.py             # 风险管理
│   ├── stats.py            # 数据统计报表
│   ├── pdd_orders.py       # 拼多多订单管理
│   ├── plugin.py           # 插件管理（后台+客户端API）
│   └── api.py              # Webhook/Token/健康检查
│
└── templates/              # Jinja2模板（继承base.html）
    ├── base.html           # 侧边栏布局（Bootstrap 5）
    ├── intent_rule/        # 意图规则管理页面
    │   ├── index.html      # 规则列表（关键词badge、AJAX开关）
    │   └── form.html       # 新增/编辑表单
    ├── settings/           # 系统设置模板★新
    │   └── index.html      # 设置首页（分Tab展示）
    └── plugin/
        ├── index.html      # 插件列表（在线状态、动作码）
        └── tasks.html      # 任务执行记录
```

---

## 4. 数据库表结构

| 表名 | 模型 | 说明 |
|------|------|------|
| `industries` | Industry | 行业（多租户中心表，全局隔离） |
| `shops` | Shop | 店铺（含`shop_token`用于客户端鉴权） |
| `users` | User | 管理员/操作员，绑定行业 |
| `knowledge_base` | KnowledgeBase | 知识库（第一层，关键词+语义） |
| `intent_rules` | IntentRule | **意图规则**（可自定义关键词/动作/话术） |
| `messages` | Message | 消息记录（direction='in'买家消息/'out'AI回复，含process_by、emotion_level）★更新 |
| `message_cache` | MessageCache | AI回复缓存（归一化哈希，24h TTL） |
| `conversation_contexts` | ConversationContext | 多轮对话上下文（30min超时） |
| `learning_records` | LearningRecord | 增量学习待审核记录 |
| `blacklist` | Blacklist | 黑名单（级别1~3，行业内共享） |
| `client_plugins` | ClientPlugin | 客户端插件注册（含心跳、动作码） |
| `plugin_tasks` | PluginTask | 插件任务队列（UUID、FIFO、状态流转） |
| `pdd_orders` | PddOrder | 拼多多订单（多来源：插件/客户端/手动） |
| `system_configs` | SystemConfig | 系统配置KV表（替代.env硬编码）★新 |
| `daily_stats` | DailyStats | 每日统计（消息量/AI成本/各层覆盖率） |

### `intent_rules` 表字段详情（★核心新表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 主键 |
| `industry_id` | Integer FK nullable | 所属行业，NULL=全局规则 |
| `intent_code` | VARCHAR(50) | 意图标识（如 `exchange`） |
| `intent_name` | VARCHAR(100) | 显示名（如 `换号请求`） |
| `keywords` | Text | 触发关键词 JSON数组（`["换号","换个"]`） |
| `action_code` | VARCHAR(50) nullable | 插件动作码（如 `auto_exchange`），空=纯意图 |
| `auto_reply_tpl` | Text nullable | 识别后**立即**发给买家的话术 |
| `done_reply_tpl` | Text nullable | 插件完成后发给买家的话术（支持`{变量}`） |
| `priority` | Integer | 优先级（越小越先匹配） |
| `is_active` | Boolean | 是否启用 |
| `created_at` | DateTime | 创建时间（北京时间） |
| `updated_at` | DateTime | 最后修改时间 |

**系统内置默认规则**（首次启动自动写入，可在后台修改）：

| 优先级 | intent_code | intent_name | action_code |
|--------|-------------|-------------|-------------|
| 0 | `exchange` | 换号请求 | `auto_exchange` |
| 1 | `refund` | 退款申请 | `handle_refund` |
| 2 | `login` | 登录问题 | — |
| 3 | `complaint` | 投诉举报 | — |
| 4 | `query` | 查询咨询 | — |
| 5 | `payment` | 付款问题 | — |

### `system_configs` 表字段详情（★新表）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 主键 |
| `key` | VARCHAR(100) UNIQUE | 配置键（如 `doubao_api_key`） |
| `value` | Text | 配置值 |
| `value_type` | VARCHAR(20) | 值类型（string/int/float/bool） |
| `group` | VARCHAR(50) | 分组（ai/knowledge/system/security） |
| `label` | VARCHAR(200) | 显示名称（中文） |
| `description` | Text | 配置说明 |
| `updated_at` | DateTime | 最后修改时间 |

---

## 5. 消息处理完整流程（已更新）

```
买家发送消息
       ↓
[0] 本地意图识别（读 intent_rules 表，可热更新，0成本0延迟）
    按行业规则优先→全局规则，按 priority 升序匹配关键词
    命中 → 返回 (intent_code, action_code, auto_reply_tpl)
    未命中 → 调豆包lite识别意图（有成本，兜底）
       ↓
[0.5] 插件任务提前分流
    有 action_code AND 有在线插件
       → 创建 PluginTask（pending）
       → 立即返回 auto_reply_tpl（process_by='plugin'）→ 跳过知识库+AI
    ↓
[0.6] ★ 纯文字意图回复（新增）
    无 action_code BUT 有 auto_reply_tpl（意图识别命中，无需插件）
       → 直接返回 auto_reply_tpl（process_by='intent_reply'）→ 跳过知识库+AI
    ↓
[1] 黑名单检查
    在黑名单 → 转人工（安抚回复）
       ↓
[2] 情绪检测（本地关键词规则，0成本）
    情绪级别≥3（严重）→ doubao-pro 情绪安抚 → 转人工
       ↓
[3] 退款意图特殊处理（无插件接管时）
    intent==refund AND 无 action_code
       → doubao-pro 退款决策（approve/reject/human）
       ↓
[4] 图片消息处理
    msg_type==image → doubao-vision-pro 图片分析
       ↓
[5] 二层文字消息处理（原三层，规则引擎已删除）
    第一层：知识库（MaxKB语义 或 关键词重叠率≥0.6）→ 命中直接返回（process_by='knowledge'）
    第二层：豆包AI多轮对话（doubao-lite，带缓存，带上下文）→ process_by='ai'
       ↓
[6] 消息全记录（★新增）
    买家消息保存 direction='in'
    AI/插件回复保存 direction='out'（与买家消息关联，可在消息管理页查看完整对话）
       ↓
[7] 实时增量学习触发（AI处理后）
    低置信度词 OR 同问题7天内≥2次 → 创建 LearningRecord（待审核）
```

---

## 6. 意图规则系统

### 6.1 设计目标

将原来硬编码在 `ai_engine.py` 中的 `LOCAL_INTENT_RULES` 和 `PLUGIN_INTENT_ACTIONS` 两个字典迁移到数据库，运营人员无需修改代码即可：

- 添加/修改触发关键词
- 调整意图优先级
- 配置插件动作码
- 编写立即回复话术 / 完成回复话术

> v2.1 新增：意图规则现在支持**纯文字回复**（`action_code` 为空，`auto_reply_tpl` 非空），不需要插件也能直接配置意图话术，例如"发货时间咨询"、"营业时间"等FAQ类意图。

### 6.2 识别逻辑

```python
# modules/ai_engine.py
def _recognize_intent_local(self, message: str, industry_id: int = None) -> tuple:
    """从数据库读取规则，返回 (intent_code, action_code)"""
    rules = IntentRule.query.filter(
        IntentRule.is_active.is_(True),
        db.or_(IntentRule.industry_id == industry_id,
               IntentRule.industry_id == None)
    ).order_by(IntentRule.priority.asc()).all()

    msg_lower = message.lower()
    for rule in rules:
        for kw in rule.get_keywords():
            if kw in msg_lower:
                return rule.intent_code, rule.action_code

    return 'other', None   # 未命中，继续调豆包识别
```

**优先级规则**：行业规则和全局规则混排，`priority` 小的优先。

### 6.3 完整意图→插件→买家回复链路

```
买家消息包含"换号"
       ↓
命中 intent_rules: exchange / action_code=auto_exchange
       ↓
查找有 auto_exchange 能力的在线插件
       ↓ 找到
创建 PluginTask（status=pending）
立即回复买家：auto_reply_tpl = "好的，正在为您自动换号，请稍候～"
       ↓
客户端轮询领取任务，执行换号
       ↓
POST /api/plugin/tasks/<id>/done
  {"result": {"success": true, "new_account": "acc---pass"}}
       ↓
服务端查 done_reply_tpl，填充变量
返回 reply_to_buyer = "换号完成！新账号：acc---pass，如有问题请联系我们😊"
客户端收到 reply_to_buyer 后自动发送给买家
```

### 6.4 话术模板变量

`done_reply_tpl` 支持 `{变量名}` 占位符，由客户端上报的 `result` 字典填充：

| 常用变量 | 说明 |
|---------|------|
| `{new_account}` | 换号后的新账号 |
| `{order_id}` | 订单号 |
| `{message}` | 自定义消息 |
| `{error}` | 失败时的错误原因 |

### 6.5 纯文字意图回复（v2.1新增）

```
场景：买家问"你们几点开始营业"
       ↓
命中 intent_rules: business_hours / action_code=NULL / auto_reply_tpl="我们每天9:00-23:00在线，随时为您服务😊"
       ↓
process_by = 'intent_reply'
直接返回话术，跳过知识库和AI（0成本0延迟）
```

说明：`process_by='intent_reply'` 会被统计在控制台的「意图回复」命中率中，适合FAQ类意图（营业时间、发货时间、退款政策等），无需插件即可0成本直接回复。

---

## 7. 插件系统设计

### 7.1 完整生命周期

```
客户端启动
    ↓
POST /api/plugin/register          ← 声明支持的动作码（auto_exchange 等）
    ↓ 每30秒
POST /api/plugin/heartbeat         ← 保持在线（5分钟无心跳视为离线）
    ↓ 每2~10秒轮询
GET  /api/plugin/tasks             ← 获取待执行任务（FIFO，最多返回10条）
    ↓ 领取任务执行
执行本地操作（换号/发货/退款等）
    ↓ 执行完成
POST /api/plugin/tasks/<id>/done   ← 上报成功结果（含 result 字典）
POST /api/plugin/tasks/<id>/fail   ← 上报失败原因
    ↓
服务端自动生成 reply_to_buyer（填充 done_reply_tpl）
客户端收到后发送给买家 ★
```

### 7.2 任务状态流转

```
pending（待领取）→ claimed（执行中）→ done（完成）
                                   → failed（失败）
```

### 7.3 task_done 响应格式（新增 reply_to_buyer）

```json
POST /api/plugin/tasks/123/done
Request:
{
  "result": {
    "success": true,
    "new_account": "user123---pass456"
  }
}

Response:
{
  "success": true,
  "message": "任务已标记为完成",
  "reply_to_buyer": "换号完成！新账号：user123---pass456，如有问题请联系我们😊"
}
```

客户端收到 `reply_to_buyer` 非空时，需将其发送给买家（通过浏览器插件/平台消息接口）。

### 7.4 动作码（可在意图规则后台配置，不限于内置值）

| 动作码 | 说明 |
|--------|------|
| `auto_exchange` | 自动换号（游戏租号行业） |
| `handle_refund` | 退款处理 |
| `order_sync` | 订单同步 |
| 自定义 | 在意图规则后台填写，客户端注册时声明支持 |

---

## 8. 全量路由 & API 接口

### 8.1 管理后台页面（需要登录，Session认证）

| 方法 | 路径 | 蓝图 | 说明 |
|------|------|------|------|
| GET | `/` | dashboard | 控制面板（实时统计） |
| GET/POST | `/login` | auth | 登录 |
| GET | `/logout` | auth | 登出 |
| GET/POST | `/change-password` | auth | 修改密码 |
| GET | `/industry/` | industry | 行业列表 |
| GET/POST | `/industry/add` | industry | 新增行业 |
| GET/POST | `/industry/<id>/edit` | industry | 编辑行业 |
| POST | `/industry/<id>/toggle` | industry | 启用/禁用 |
| POST | `/industry/<id>/delete` | industry | 删除行业 |
| GET | `/shop/` | shop | 店铺列表 |
| GET/POST | `/shop/add` | shop | 新增店铺 |
| GET/POST | `/shop/<id>/edit` | shop | 编辑店铺 |
| POST | `/shop/<id>/toggle` | shop | 启用/禁用 |
| POST | `/shop/<id>/delete` | shop | 删除店铺 |
| GET | `/knowledge/` | knowledge | 知识库列表 |
| GET/POST | `/knowledge/add` | knowledge | 新增条目 |
| GET/POST | `/knowledge/<id>/edit` | knowledge | 编辑条目 |
| POST | `/knowledge/<id>/delete` | knowledge | 删除条目 |
| GET | `/knowledge/generate` | knowledge | AI批量生成页 |
| POST | `/knowledge/api/generate` | knowledge | AI生成（JSON） |
| POST | `/knowledge/api/batch-save` | knowledge | 批量保存（JSON） |
| GET | `/intent-rules/` | intent_rule | 意图规则列表 |
| GET/POST | `/intent-rules/add` | intent_rule | 新增意图规则 |
| GET/POST | `/intent-rules/<id>/edit` | intent_rule | 编辑意图规则 |
| POST | `/intent-rules/<id>/toggle` | intent_rule | 启用/禁用（JSON） |
| POST | `/intent-rules/<id>/delete` | intent_rule | 删除意图规则 |
| GET | `/settings/` | settings | 系统设置首页 ★新 |
| POST | `/settings/save` | settings | 保存配置 ★新 |
| POST | `/settings/test-doubao` | settings | 测试豆包连接 ★新 |
| POST | `/settings/test-maxkb` | settings | 测试MaxKB连接 ★新 |
| GET | `/messages/` | messages | 消息记录 |
| POST | `/messages/<id>/mark-handled` | messages | 标记处理 |
| GET | `/messages/api/stats` | messages | 实时统计（JSON） |
| GET | `/messages/<buyer_id>/conversation` | messages | 查看某买家完整对话（气泡视图）★新 |
| GET | `/messages/api/conversation/<buyer_id>` | messages | 获取对话JSON ★新 |
| GET | `/learning/` | learning | 学习中心 |
| POST | `/learning/<id>/approve` | learning | 审核通过入库 |
| POST | `/learning/<id>/modify` | learning | 修改后入库 |
| POST | `/learning/<id>/reject` | learning | 审核拒绝 |
| POST | `/learning/generate` | learning | AI批量生成学习记录 |
| GET | `/blacklist/` | blacklist | 黑名单列表 |
| GET/POST | `/blacklist/add` | blacklist | 手动添加 |
| POST | `/blacklist/<id>/remove` | blacklist | 移除 |
| GET | `/risk/` | risk | 风险管理首页 |
| POST | `/risk/blacklist/<id>/upgrade` | risk | 升级黑名单等级 |
| POST | `/risk/blacklist/<id>/remove` | risk | 移除黑名单 |
| GET | `/risk/api/summary` | risk | 风险摘要（JSON） |
| GET | `/stats/` | stats | 统计报表（近30天） |
| GET | `/stats/api/chart-data` | stats | 近7天图表（JSON） |
| GET | `/pdd-orders/` | pdd_orders | 拼多多订单列表 |
| GET | `/pdd-orders/<order_id>` | pdd_orders | 订单详情+聊天记录 |
| GET | `/plugins/` | plugin | 插件管理列表 |
| GET | `/plugins/tasks` | plugin | 任务执行记录 |
| GET | `/api/health/dashboard` | api | 健康状态汇总JSON ★新 |
| GET | `/api/health/plugin-status` | api | 各店铺插件在线状态 ★新 |

### 8.2 客户端插件API（X-Shop-Token 鉴权，无需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/plugin/register` | 注册插件能力 |
| POST | `/api/plugin/heartbeat` | 心跳保活（30秒/次） |
| GET | `/api/plugin/tasks` | 轮询待执行任务（FIFO，最多10条） |
| POST | `/api/plugin/tasks/<id>/done` | 上报完成 → 返回 `reply_to_buyer` ★ |
| POST | `/api/plugin/tasks/<id>/fail` | 上报失败 |
| POST | `/api/orders/push` | 推送订单数据 |

### 8.3 Webhook / AI 接口

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/webhook/message` | 无（内部） | 通用消息处理（二层AI） |
| POST | `/api/webhook/pdd` | shop_token（Body） | 拼多多浏览器插件推送 |
| POST | `/api/test-message` | 登录 | 后台测试消息处理 |
| POST | `/api/ai-assistant/chat` | 登录 | 知识库AI助手（doubao-lite） |
| GET | `/api/shop/token` | 登录 | 获取店铺 shop_token |
| POST | `/api/shop/token/regenerate` | 登录 | 重新生成 shop_token |
| GET | `/api/pdd/orders` | 登录 | 获取订单列表（分页） |
| GET | `/api/health` | 无 | 健康检查（宝塔监控用） |

### 8.4 完整请求/响应示例

**注册插件**
```json
POST /api/plugin/register
X-Shop-Token: <shop_token>
{
  "plugin_id": "auto_exchange",
  "name": "自动换号",
  "description": "自动执行换号操作",
  "action_codes": ["auto_exchange"],
  "client_version": "1.0.0"
}
// 响应
{"success": true, "message": "插件 auto_exchange 注册成功"}
```

**轮询任务**
```json
GET /api/plugin/tasks?plugin_id=auto_exchange
X-Shop-Token: <shop_token>
// 响应
{
  "success": true,
  "count": 1,
  "tasks": [
    {
      "id": 42,
      "task_id": "abc-uuid",
      "action_code": "auto_exchange",
      "payload": {
        "buyer_id": "buyer001",
        "order_id": "2026030900001",
        "message": "帮我换号",
        "intent": "exchange"
      },
      "created_at": "2026-03-09 15:00:00"
    }
  ]
}
```

**上报完成（含自动回复）**
```json
POST /api/plugin/tasks/42/done
X-Shop-Token: <shop_token>
{
  "result": {
    "success": true,
    "new_account": "gamer123---pass456"
  }
}
// 响应
{
  "success": true,
  "message": "任务已标记为完成",
  "reply_to_buyer": "换号完成！新账号：gamer123---pass456，如有问题请联系我们😊"
}
```

**拼多多插件Webhook**
```json
POST /api/webhook/pdd
{
  "shop_token": "<shop_token>",
  "buyer_id": "buyer001",
  "buyer_name": "张三",
  "content": "帮我换个号",
  "msg_type": "text",
  "order_id": "2026030900001",
  "order_info": {
    "goods_name": "游戏账号7天",
    "amount": 9.9,
    "status": "已付款"
  }
}
// 响应
{
  "success": true,
  "reply": "好的，正在为您自动换号，请稍候～",
  "process_by": "plugin",
  "intent": "exchange"
}
```

**推送订单**
```json
POST /api/orders/push
X-Shop-Token: <shop_token>
{
  "orders": [
    {
      "order_id": "2026030900001",
      "buyer_id": "buyer001",
      "buyer_name": "张三",
      "goods_name": "商品名称",
      "amount": 9900,
      "status": "待发货",
      "created_at": "2026-03-09 10:00:00"
    }
  ],
  "source": "client"
}
```

---

## 9. MaxKB向量检索接入

### 9.1 部署MaxKB

```bash
# Docker方式
docker run -d \
  --name maxkb \
  -p 8080:8080 \
  -v ~/.maxkb:/var/lib/postgresql/data \
  1panel/maxkb:latest
```

### 9.2 .env 配置

```env
MAXKB_ENABLED=true
MAXKB_API_URL=http://localhost:8080
MAXKB_API_KEY=<在MaxKB后台生成>
MAXKB_DATASET_ID=<创建数据集后获取>
MAXKB_MIN_SIMILARITY=0.6          # 最低相似度（可选，默认0.6）
```

### 9.3 效果对比

| 检索方式 | 命中率 | 成本 | 适用场景 |
|---------|-------|------|---------|
| 关键词重叠率（默认） | ~60% | 0 | 小型知识库，关键词明确 |
| MaxKB语义检索 | ~85% | 极低 | 大型知识库，问法多样 |

### 9.4 知识库同步

后台保存/修改/删除知识库条目时，自动同步到MaxKB数据集。

---

## 10. 缓存归一化优化

原缓存按原始消息MD5存储，"登不上"/"进不去"/"打不开"是3个不同缓存键，命中率仅5%。
归一化后将语义等价的说法统一为标准写法再哈希：

| 原始说法 | 归一化为 |
|---------|--------|
| 登不上/进不去/打不开/登录不了 | 无法登录 |
| 换号/换个/换一个/换账号 | 申请换号 |
| 退款/退钱/不要了/申请退 | 申请退款 |
| 密码忘了/密码不对/忘记密码 | 密码问题 |
| 发货/什么时候到/多久到 | 催发货 |
| 怎么用/如何操作/怎么玩 | 使用方法 |

**效果**：缓存命中率 5% → 60%，节省约60% AI API调用费用。

---

## 11. 实时增量学习机制

### 11.1 触发条件（AI处理后立即检查）

1. **低置信度**：回复含"不确定"、"我是AI"、"转人工"等兜底词
2. **高频问题**：同问题（归一化后前20字）7天内出现≥2次

### 11.2 审核流程

```
AI回复 → 触发检查 → 创建 LearningRecord（review_status=pending）
                                  ↓
                          /learning/ 学习中心
                                  ↓
         ✅ approve  → 写入 KnowledgeBase（+同步MaxKB）
         ✏️ modify   → 运营修正答案后写入
         ❌ reject   → review_status=rejected
```

### 11.3 定时补充（每日）

| 时间 | 任务 | 说明 |
|------|------|------|
| 凌晨1点 | 每日统计 | 写入 DailyStats |
| 凌晨3点 | 学习任务 | 批量检查当日高频AI消息，补充 LearningRecord |
| 每小时 | 黑名单检查 | 30天内退款≥3次自动加入黑名单 |
| 每5分钟 | 清理过期缓存 | 清除 MessageCache 过期条目 |

## 12. 权限体系

| 角色 | 数据可见范围 |
|------|------------|
| `admin`（超级管理员） | 所有行业、所有店铺、所有数据 |
| `operator`（操作员） | 仅自己行业的店铺、知识库、规则、意图规则 |

意图规则页面：非管理员只能查看/编辑**本行业规则**和**全局规则**（不能修改其他行业规则）。

---

## 13. .env 完整配置说明

> ⚠️ v2.1起，以下参数已可在后台 `/settings/` 页面可视化配置，无需手动编辑 `.env`。`.env` 仍作为首次部署初始化使用。

```env
# ============================
# 基础配置
# ============================
SECRET_KEY=your-secret-key-here          # 应用密钥（生产必须修改）
DEBUG=false                              # 调试模式

# ============================
# 数据库（优先MySQL，回退SQLite）
# ============================
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=aikefu
MYSQL_PASSWORD=your-db-password          # 空=自动用SQLite
MYSQL_DATABASE=aikefu
USE_MYSQL=false                          # 强制使用MySQL（密码为空时也用）

# ============================
# 豆包AI（字节跳动火山方舟）
# ============================
DOUBAO_API_KEY=your-ark-api-key
DOUBAO_LITE_MODEL=doubao-lite-32k        # 意图/FAQ/多轮/知识生成
DOUBAO_PRO_MODEL=doubao-pro-32k          # 退款决策/情绪安抚
DOUBAO_VISION_MODEL=doubao-vision-pro-32k  # 图片分析（多模态）

# ============================
# MaxKB向量检索（可选）
# ============================
MAXKB_ENABLED=false
MAXKB_API_URL=http://localhost:8080
MAXKB_API_KEY=
MAXKB_DATASET_ID=
MAXKB_MIN_SIMILARITY=0.6
```

---

## 14. 部署说明

### 14.1 Docker Compose（推荐）

```yaml
services:
  web:
    build: .
    ports:
      - "8000:8000"        # 宿主机8000 → 容器8000
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    depends_on:
      - mysql

  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root123
      MYSQL_DATABASE: aikefu
      MYSQL_USER: aikefu
      MYSQL_PASSWORD: aikefu123
    volumes:
      - mysql_data:/var/lib/mysql

  # MaxKB（可选）
  # maxkb:
  #   image: 1panel/maxkb:latest
  #   ports:
  #     - "8080:8080"

volumes:
  mysql_data:
```

```bash
# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f web
```

### 14.2 宝塔面板部署（推荐生产）

```bash
# 1. 克隆代码
git clone https://github.com/qq419701/aikefu.git /www/wwwroot/aikefu
cd /www/wwwroot/aikefu

# 2. 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 3. 配置环境变量
cp .env.example .env   # 编辑 .env 填写数据库/API密钥

# 4. 启动（宝塔Python项目管理器配置）
gunicorn -w 2 -b 0.0.0.0:8000 --timeout 120 "app:create_app()"

# 5. 以后更新代码只需
git pull origin main
# 宝塔面板点重启
```

### 14.3 默认账号

```
管理员：admin / admin123
（首次登录后请立即修改密码！）
```

---

## 15. 版本变更日志

### v2.1.0（2026-03-11）

#### 新增功能

- ✅ **规则引擎已删除**：`rules` 表、`modules/rules_engine.py`、`routes/rules.py` 全部移除，功能由意图规则+知识库完全覆盖
- ✅ **意图规则纯文字回复**：`action_code` 为空时，`auto_reply_tpl` 可直接回复买家（`process_by='intent_reply'`），0成本0延迟，适合FAQ类意图
- ✅ **系统设置页面**（`/settings/`）：配置项从 `.env` 迁移到数据库 `system_configs` 表，支持可视化编辑，含豆包/MaxKB/系统行为四个分组
- ✅ **消息对话全记录**：AI回复现在以 `direction='out'` 保存到 `messages` 表，消息管理页支持气泡对话视图，一键将AI对话加入学习记录
- ✅ **控制台健康状态**：控制面板新增插件在线状态、MaxKB连接、豆包API状态、今日各层命中率饼图，30秒自动刷新
- ✅ **页面帮助悬浮卡片**：每个后台页面右下角新增「❓ 帮助」按钮，点击显示该页面专属说明

#### 删除/移除

- ❌ **规则引擎完全删除**（`models/rule.py`、`routes/rules.py`、`modules/rules_engine.py`、相关模板）
- ❌ 侧边栏「规则引擎」菜单项已移除

#### 优化改进

- 消息处理从"三层"调整为"二层"（去掉规则引擎层，知识库为第一层，豆包AI为第二层）
- `process_by` 新增 `intent_reply` 值，统计更精确
  - `intent_reply` — 意图规则纯文字回复（新增）
  - `plugin` — 意图规则插件任务回复
  - `knowledge` — 知识库命中
  - `ai` — 豆包AI回复
  - `human` — 转人工
- 系统设置支持豆包/MaxKB连接测试，实时反馈配置是否有效
- 控制台今日统计饼图新增 `intent_reply` 占比维度

---

### v2.0.0（2026-03-09）

#### 新增功能

- ✅ **意图规则数据库化**（`intent_rules` 表）：关键词/动作/话术全配置，无需改代码，可热更新
- ✅ **插件完成自动回复买家**：`task_done` 接口返回 `reply_to_buyer`，填充 `done_reply_tpl` 变量
- ✅ **插件提前分流**：意图命中 `action_code` 时立即下发任务+回复话术，跳过三层AI，节省成本
- ✅ **意图规则管理后台**（`/intent-rules/`）：增删改查、AJAX开关、行业筛选
- ✅ MaxKB向量检索接入（可选，`MAXKB_ENABLED=true` 启用）
- ✅ 实时增量学习（AI回复后立即触发，替代每日定时假学习）
- ✅ 缓存归一化（命中率 5% → 60%）
- ✅ 插件系统完整闭环（注册/心跳/任务下发/执行/回调）
- ✅ 订单推送API（`POST /api/orders/push`，客户端直接推送）
- ✅ 订单来源字段（client/browser_plugin/manual）
- ✅ 三种豆包模型分工（lite/pro/vision-pro）
- ✅ 多轮对话上下文（30分钟内保持对话连续性）

#### 删除/移除

- ❌ 退款管理模块（`/refund/`）已移除
- ❌ 意图规则硬编码（原 `LOCAL_INTENT_RULES` / `PLUGIN_INTENT_ACTIONS`）→ 改为数据库驱动

#### 优化改进

- 店铺管理表单简化（删除平台API/游戏租号冗余配置）
- 风险管理简化为黑名单管理
- 侧边栏新增🔌插件管理、🎯意图规则菜单
- `process_message` 返回 `process_by='plugin'` 标识插件处理路径
- 所有布尔查询改为 SQLAlchemy `.is_(True)` 语法

---

## 17. 系统设置（/settings/，v2.1新增）

### 17.1 功能说明

将原来散落在 `.env` 和 `config.py` 中的配置项迁移到数据库 `system_configs` 表，
支持通过后台管理界面可视化修改，无需重启服务（部分配置热生效，AI配置需重启）。

入口：管理后台侧边栏 → ⚙️ 系统设置

### 17.2 配置分组

| 分组 | Tab名 | 说明 |
|------|-------|------|
| `ai` | 🤖 AI参数 | 豆包模型名、温度、上下文轮次、超时等 |
| `knowledge` | 📚 知识库 | MaxKB地址/Key/数据集ID/相似度阈值 |
| `system` | ⚙️ 系统行为 | 回复延迟、数据保留天数、黑名单阈值 |
| `security` | 🔒 安全设置 | API Key加密存储、会话超时 |

### 17.3 可配置的AI参数

所有参数均支持**后台热更新**（无需重启服务），每次处理消息时从数据库动态读取：

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `doubao_api_key` | string | — | 火山方舟 API Key（加密存储） |
| `doubao_lite_model` | string | doubao-lite-32k | Lite模型名（意图/多轮/知识生成） |
| `doubao_pro_model` | string | doubao-pro-32k | Pro模型名（情绪安抚/退款决策） |
| `doubao_temperature` | float | 0.3 | AI温度（0-1，越低越稳定） |
| `doubao_max_tokens` | int | 500 | 单次回复最大Token |
| `max_context_turns` | int | 10 | 多轮对话保留轮次 |
| `context_timeout_minutes` | int | 30 | 会话超时分钟数 |
| `knowledge_similarity` | float | 0.6 | 知识库相似度阈值 |
| `auto_reply_delay_min` | int | 1 | 自动回复最小延迟（秒，模拟人工） |
| `auto_reply_delay_max` | int | 3 | 自动回复最大延迟（秒，模拟人工） |
| `human_intervention_level` | int | 3 | 触发转人工的情绪级别（0-4） |

### 17.4 可配置的知识库参数

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `maxkb_enabled` | bool | false | 是否启用MaxKB语义检索 |
| `maxkb_api_url` | string | — | MaxKB服务地址 |
| `maxkb_api_key` | string | — | MaxKB API Key |
| `maxkb_dataset_id` | string | — | MaxKB数据集ID |

### 17.5 相关路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/settings/` | 系统设置首页（分Tab展示） |
| POST | `/settings/save` | 保存配置（JSON，支持批量） |
| POST | `/settings/test-doubao` | 测试豆包API连接 |
| POST | `/settings/test-maxkb` | 测试MaxKB连接 |
| GET | `/settings/api/config` | 获取当前配置（JSON，敏感项脱敏） |

---

## 18. 控制台健康状态卡片（v2.1新增）

控制面板（`/`）新增「系统健康状态」区块，每30秒自动刷新：

| 卡片 | 数据来源 | 说明 |
|------|----------|------|
| 🔌 插件在线状态 | `ClientPlugin.is_online()` | 各店铺插件是否在线，显示最后心跳时间 |
| 📚 MaxKB连接 | `/settings/test-maxkb` | MaxKB服务是否可达，响应延迟 |
| 🤖 豆包API状态 | `/settings/test-doubao` | API Key是否有效，最近调用时间 |
| 📊 今日命中率 | `Message.process_by` | 饼图：意图回复/插件/知识库/AI/人工 各占比 |

相关API：
- `GET /api/health/dashboard` — 返回健康状态汇总JSON（30秒轮询）
- `GET /api/health/plugin-status` — 各店铺插件在线状态

---

## 16. 客户端接入指南

> 本章节说明桌面客户端（dskehuduan）如何通过账号密码登录、自动同步多店铺 Token、接入插件化体系，实现**一个客户端管理多个店铺**。

---

### 16.1 账号登录流程

```
客户端启动
    ↓
填写服务器地址（如 https://example.com:8000，生产环境请使用 HTTPS）
    ↓
填写账号/密码（与爱客服管理后台账号相同）
    ↓
POST /api/client/login
    ↓
返回 client_token（有效期 7 天，自动续期）
    ↓
GET /api/client/shops（带 X-Client-Token 请求头）
    ↓
自动获取名下所有激活店铺列表（含 shop_token）
    ↓
为每个店铺启动独立的插件任务执行器
```

**权限说明：**

| 账号类型 | 可见店铺范围 |
|----------|-------------|
| 管理员（admin） | 所有激活店铺 |
| 普通用户（operator） | 与其 industry_id 匹配的激活店铺 |

---

### 16.2 多店铺管理说明

- 客户端登录一次，自动获取名下**全部**激活店铺及其 `shop_token`
- 每个店铺独立运行一个任务轮询器（`AikefuTaskRunner`），互不干扰
- Token 有效期 7 天，客户端启动时自动调用 `/api/client/refresh` 续期
- 无需手动复制粘贴 `shop_token`，完全自动化

---

### 16.3 客户端账号 API 接口文档

#### POST `/api/client/login` — 账号登录

**请求体**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**成功响应（200）**
```json
{
  "success": true,
  "client_token": "a3f8c2d1e9b7...",
  "username": "admin",
  "display_name": "管理员",
  "expires_in": 604800
}
```

**失败响应（401）**
```json
{"success": false, "message": "用户名或密码错误"}
```

---

#### GET `/api/client/shops` — 获取名下店铺列表

**请求头**
```
X-Client-Token: <client_token>
```

**成功响应（200）**
```json
{
  "success": true,
  "shops": [
    {
      "id": 1,
      "name": "程洋游戏",
      "platform": "pdd",
      "platform_shop_id": "123456",
      "shop_token": "d3af8c2e...",
      "is_active": true,
      "auto_reply_enabled": true
    },
    {
      "id": 2,
      "name": "店铺二号",
      "platform": "pdd",
      "platform_shop_id": "654321",
      "shop_token": "f9c1b7a3...",
      "is_active": true,
      "auto_reply_enabled": false
    }
  ]
}
```

**失败响应（401）**
```json
{"success": false, "message": "token 无效或已过期，请重新登录"}
```

---

#### POST `/api/client/logout` — 退出登录

**请求头**
```
X-Client-Token: <client_token>
```

**成功响应（200）**
```json
{"success": true}
```

---

#### POST `/api/client/refresh` — 刷新 Token 有效期

**请求头**
```
X-Client-Token: <client_token>
```

**成功响应（200）**
```json
{"success": true, "expires_in": 604800}
```

**失败响应（401）**
```json
{"success": false, "message": "token 无效或已过期，请重新登录"}
```

---

### 16.4 插件化接入完整说明

客户端获得 `shop_token` 后，即可接入插件系统。完整生命周期：

```
1. 注册插件能力（启动时调用一次）
2. 发送心跳（每 30 秒一次，保活）
3. 轮询任务（每 2 秒一次，获取待执行任务）
4. 执行任务（换号/退款/订单等业务逻辑）
5. 回报结果（成功 /done，失败 /fail）
```

#### 第一步：注册插件

```json
POST /api/plugin/register
X-Shop-Token: <shop_token>

{
  "plugin_id": "pdd_shop",
  "name": "拼多多店铺插件",
  "description": "自动换号、退款处理、订单同步",
  "action_codes": ["auto_exchange", "handle_refund", "order_sync"],
  "client_version": "2.0.0"
}

// 响应
{"success": true, "message": "插件 pdd_shop 注册成功"}
```

#### 第二步：心跳保活

```json
POST /api/plugin/heartbeat
X-Shop-Token: <shop_token>

{"plugin_id": "pdd_shop"}

// 响应
{"success": true, "pending_tasks": 2}
```

#### 第三步：轮询任务

```json
GET /api/plugin/tasks?plugin_id=pdd_shop
X-Shop-Token: <shop_token>

// 响应
{
  "success": true,
  "tasks": [
    {
      "id": 42,
      "action_code": "auto_exchange",
      "payload": {"buyer_id": "pdd_buyer_xxx", "order_id": "202501010001"},
      "created_at": "2025-01-01T10:00:00"
    }
  ],
  "count": 1
}
```

#### 第四步：上报完成

```json
POST /api/plugin/tasks/42/done
X-Shop-Token: <shop_token>

{
  "result": {
    "new_account": "GAME_888",
    "new_password": "pass123",
    "order_id": "202501010001"
  }
}

// 响应（含自动回复给买家的文案）
{
  "success": true,
  "reply_to_buyer": "已为您换号，新账号：GAME_888，密码：pass123"
}
```

#### 上报失败

```json
POST /api/plugin/tasks/42/fail
X-Shop-Token: <shop_token>

{
  "result": {
    "error": "U号租平台登录超时",
    "order_id": "202501010001"
  }
}

// 响应
{"success": true}
```

---

### 16.5 插件 action_codes 列表

| action_code | 说明 | 业务场景 |
|-------------|------|----------|
| `auto_exchange` | 自动换号 | 游戏租号行业，买家要求换号 |
| `handle_refund` | 退款处理 | 退款流程自动化 |
| `order_sync` | 订单同步 | 拉取最新订单数据 |
| `fetch_messages` | 消息同步 | 拉取平台消息 |
| `uhaozu_exchange` | U号租换号 | U号租专区自动换号（预留） |
| `uhaozu_select` | U号租选号 | U号租专区自动选号（预留） |
| `uhaozu_order` | U号租下单 | U号租专区自动下单（预留） |
| 自定义 | 任意字符串 | 在意图规则后台配置，客户端注册时声明支持 |

> **注意**：`action_code` 不限于内置值，可在爱客服管理后台 → 意图规则 中自定义，客户端注册时在 `action_codes` 数组中声明即可接收对应任务。

---

### 16.6 客户端完整接入示例（Python）

```python
import requests

SERVER = "https://example.com:8000"  # 生产环境请使用 HTTPS

# 1. 登录获取 client_token
resp = requests.post(f"{SERVER}/api/client/login", json={
    "username": "admin",
    "password": "admin123"
})
data = resp.json()
client_token = data["client_token"]

# 2. 获取名下所有店铺
resp = requests.get(f"{SERVER}/api/client/shops", headers={
    "X-Client-Token": client_token
})
shops = resp.json()["shops"]

# 3. 为每个店铺注册插件并启动任务轮询
for shop in shops:
    shop_token = shop["shop_token"]
    headers = {"X-Shop-Token": shop_token}

    # 注册插件
    requests.post(f"{SERVER}/api/plugin/register", headers=headers, json={
        "plugin_id": "pdd_shop",
        "name": "拼多多店铺插件",
        "action_codes": ["auto_exchange", "handle_refund"],
        "client_version": "2.0.0"
    })

    # 启动该店铺的心跳 + 任务轮询（每个店铺独立协程/线程）
    # start_shop_runner(shop_token)  ← 客户端实现

# 4. 客户端退出时登出
requests.post(f"{SERVER}/api/client/logout", headers={
    "X-Client-Token": client_token
})
```
