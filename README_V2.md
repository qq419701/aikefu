# 爱客服AI智能客服系统 V2 技术架构文档

> 版本：v2.0.0 | 更新时间：2026-03-09 | 语言：Python 3.11+ / Flask 3.x

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
│  │      ↓ 命中 action_code                                           │   │
│  │  [插件分流] 下发PluginTask → 立即回复 auto_reply_tpl → 跳过AI      │   │
│  │      ↓ 无插件接管 / 纯意图                                         │   │
│  │  [黑名单检查] → [情绪检测] → [退款AI决策] → [图片分析]              │   │
│  │      ↓                                                            │   │
│  │  [第一层] 规则引擎（关键词匹配，0成本，目标20%覆盖）                  │   │
│  │      ↓ 未命中                                                     │   │
│  │  [第二层] 知识库引擎（关键词/MaxKB语义，0成本，目标55%覆盖）          │   │
│  │      ↓ 未命中                                                     │   │
│  │  [第三层] 豆包AI（lite/pro/vision多模态，有成本，目标25%覆盖）        │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────┐    │
│  │  知识库管理     │  │  实时增量学习   │  │  意图规则管理（新）      │    │
│  │  aikefu后台    │  │  AI回复→待审核  │  │  数据库驱动，后台可配置  │    │
│  │  同步→MaxKB    │  │  运营审核→入库  │  │  关键词/动作/话术全配置  │    │
│  └────────────────┘  └────────────────┘  └─────────────────────────┘    │
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
| 部署 | Gunicorn + Docker | `-w 2 -b 0.0.0.0:6000 "app:create_app()"` |

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
│   ├── message.py          # 消息记录
│   ├── knowledge.py        # 知识库条目
│   ├── rule.py             # 规则引擎条目
│   ├── intent_rule.py      # 意图规则（可自定义关键词+话术）★新
│   ├── plugin.py           # 插件注册+任务队列
│   ├── conversation.py     # 多轮对话上下文
│   ├── learning.py         # 增量学习记录
│   ├── blacklist.py        # 黑名单
│   ├── pdd_order.py        # 拼多多订单
│   └── stats.py            # 每日统计
│
├── modules/                # 核心业务逻辑
│   ├── ai_engine.py        # 消息处理主引擎（三层+意图+插件）
│   ├── doubao_ai.py        # 火山方舟API客户端
│   ├── emotion_detector.py # 情绪识别（5级，本地规则）
│   ├── knowledge_engine.py # 知识库检索（关键词/MaxKB）
│   ├── maxkb_client.py     # MaxKB语义检索客户端（可选）
│   ├── rules_engine.py     # 规则引擎（any/all/exact匹配）
│   └── scheduler.py        # APScheduler定时任务
│
├── routes/                 # Flask蓝图路由
│   ├── auth.py             # 登录/登出/改密
│   ├── dashboard.py        # 控制面板首页
│   ├── industry.py         # 行业管理CRUD
│   ├── shop.py             # 店铺管理CRUD
│   ├── knowledge.py        # 知识库管理+AI批量生成
│   ├── rules.py            # 规则引擎管理
│   ├── intent_rule.py      # 意图规则管理★新
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
    ├── intent_rule/        # 意图规则管理页面★新
    │   ├── index.html      # 规则列表（关键词badge、AJAX开关）
    │   └── form.html       # 新增/编辑表单
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
| `rules` | Rule | 规则引擎条目（第一层） |
| `knowledge_base` | KnowledgeBase | 知识库（第二层，关键词+语义） |
| `intent_rules` | IntentRule | **意图规则**（可自定义关键词/动作/话术）★新 |
| `messages` | Message | 消息记录（含处理方式、情绪级别） |
| `message_cache` | MessageCache | AI回复缓存（归一化哈希，24h TTL） |
| `conversation_contexts` | ConversationContext | 多轮对话上下文（30min超时） |
| `learning_records` | LearningRecord | 增量学习待审核记录 |
| `blacklist` | Blacklist | 黑名单（级别1~3，行业内共享） |
| `client_plugins` | ClientPlugin | 客户端插件注册（含心跳、动作码） |
| `plugin_tasks` | PluginTask | 插件任务队列（UUID、FIFO、状态流转） |
| `pdd_orders` | PddOrder | 拼多多订单（多来源：插件/客户端/手动） |
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

---

## 5. 消息处理完整流程（已更新）

```
买家发送消息
       ↓
[0] 本地意图识别（读 intent_rules 表，可热更新，0成本0延迟）
    按行业规则优先→全局规则，按 priority 升序匹配关键词
    命中 → 返回 (intent_code, action_code)
    未命中 → 调豆包lite识别意图（有成本）
       ↓
[0.5] ★ 插件任务提前分流（新逻辑）
    有 action_code AND 有在线插件
       → 创建 PluginTask（pending）
       → 立即返回 auto_reply_tpl 发给买家（跳过三层AI）
    无可用插件 OR 无 action_code → 继续后续流程
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
[5] 三层文字消息处理
    第一层：规则引擎（关键词精确匹配）→ 命中直接返回
    第二层：知识库（MaxKB语义 或 关键词重叠率≥0.6）→ 命中直接返回
    第三层：豆包AI多轮对话（doubao-lite，带缓存，带上下文）
       ↓
[6] 实时增量学习触发（AI处理后）
    低置信度词 OR 同问题7天内≥2次 → 创建 LearningRecord（待审核）
```

---

## 6. 意图规则系统（★新功能）

### 6.1 设计目标

将原来硬编码在 `ai_engine.py` 中的 `LOCAL_INTENT_RULES` 和 `PLUGIN_INTENT_ACTIONS` 两个字典迁移到数据库，运营人员无需修改代码即可：

- 添加/修改触发关键词
- 调整意图优先级
- 配置插件动作码
- 编写立即回复话术 / 完成回复话术

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
| GET | `/rules/` | rules | 规则列表 |
| GET/POST | `/rules/add` | rules | 新增规则 |
| GET/POST | `/rules/<id>/edit` | rules | 编辑规则 |
| POST | `/rules/<id>/toggle` | rules | 启用/禁用 |
| POST | `/rules/<id>/delete` | rules | 删除规则 |
| GET | `/intent-rules/` | intent_rule | **意图规则列表** ★新 |
| GET/POST | `/intent-rules/add` | intent_rule | **新增意图规则** ★新 |
| GET/POST | `/intent-rules/<id>/edit` | intent_rule | **编辑意图规则** ★新 |
| POST | `/intent-rules/<id>/toggle` | intent_rule | **启用/禁用（JSON）** ★新 |
| POST | `/intent-rules/<id>/delete` | intent_rule | **删除意图规则** ★新 |
| GET | `/messages/` | messages | 消息记录 |
| POST | `/messages/<id>/mark-handled` | messages | 标记处理 |
| GET | `/messages/api/stats` | messages | 实时统计（JSON） |
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
| POST | `/api/webhook/message` | 无（内部） | 通用消息处理（三层AI） |
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
      - "8081:6000"        # 宿主机8081 → 容器6000
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
gunicorn -w 2 -b 0.0.0.0:6000 --timeout 120 "app:create_app()"

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

### v2.0.0（当前版本）

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
