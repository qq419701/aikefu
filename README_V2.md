# 爱客服AI智能客服系统 V2 技术架构文档

> 版本：v2.0.0 | 更新时间：2026-03-09 | 语言：Python 3.10+ / Flask

---

## 1. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    aikefu（服务端大脑）                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AI三层处理引擎                                                │   │
│  │                                                              │   │
│  │  买家消息 → [本地意图识别 0成本] → [黑名单检查] → [情绪检测]    │   │
│  │                     ↓                                        │   │
│  │  第一层：规则引擎（关键词匹配，0成本，目标20%覆盖）              │   │
│  │                     ↓ 未命中                                 │   │
│  │  第二层：知识库引擎（关键词/MaxKB语义，0成本，目标55%覆盖）      │   │
│  │                     ↓ 未命中                                 │   │
│  │  第三层：豆包AI（lite/pro/vision，有成本，目标25%覆盖）          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  知识库管理   │  │  实时增量学习  │  │    插件意图注册表          │  │
│  │  aikefu后台  │  │  AI回复→待审核 │  │  客户端能力声明+任务队列   │  │
│  │  同步→MaxKB  │  │  运营审核→入库 │  │  aikefu决策→客户端执行    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                                                                     │
│              ↕ HTTP API (shop_token鉴权)                             │
└─────────────────────────────────────────────────────────────────────┘
                               ↕
┌─────────────────────────────────────────────────────────────────────┐
│               dskehuduan（客户端执行层）                              │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  插件A      │  │  插件B      │  │  插件C      │  │  插件N    │ │
│  │  自动换号   │  │  订单同步   │  │  自动发货   │  │  自定义   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 各模块说明

### 2.1 AI三层引擎（modules/ai_engine.py）

| 层级 | 模块 | 成本 | 目标覆盖率 | 说明 |
|------|------|------|-----------|------|
| 第〇层 | 本地意图识别 | 0 | 80%意图 | 关键词规则，无API调用 |
| 第一层 | 规则引擎 | 0 | 20%消息 | 关键词触发，精确匹配 |
| 第二层 | 知识库引擎 | 0 | 55%消息 | 语义/关键词检索 |
| 第三层 | 豆包AI | 有成本 | 25%消息 | 兜底处理 |

### 2.2 MaxKB向量检索（modules/maxkb_client.py）

可选组件，通过 `MAXKB_ENABLED=true` 启用。启用后知识库检索从关键词匹配升级为语义向量检索，命中率从约60%提升到约85%。

### 2.3 实时增量学习（modules/ai_engine.py + routes/learning.py）

- AI处理完消息后立即触发学习检查
- 触发条件：AI回复包含低置信度词 OR 同一问题≥2次出现
- 自动创建待审核记录，运营人员每天5分钟审核入库

### 2.4 插件系统（models/plugin.py + routes/plugin.py）

- 客户端注册能力：`POST /api/plugin/register`
- aikefu识别意图后下发任务：自动创建 `PluginTask` 记录
- 客户端轮询执行：`GET /api/plugin/tasks`
- 执行完成回调：`POST /api/plugin/tasks/<id>/done`

---

## 3. AI处理完整流程

```
买家发送消息
       ↓
[1] 本地意图识别（0成本，0延迟）
    匹配 LOCAL_INTENT_RULES 关键词规则
    命中 → 返回意图（refund/exchange/login等）
    未命中 → 调豆包lite识别
       ↓
[2] 黑名单检查
    在黑名单 → 转人工（安抚回复）
       ↓
[3] 情绪检测（本地关键词，0成本）
    严重情绪（级别≥3）→ doubao-pro安抚 → 转人工
       ↓
[4] 退款意图特殊处理
    intent==refund → doubao-pro退款决策（approve/reject/human）
       ↓
[5] 图片消息处理
    msg_type==image → doubao-vision-pro图片分析
       ↓
[6] 三层文字处理
    第一层：规则引擎（keywords关键词匹配）→ 命中直接返回
    第二层：知识库（MaxKB语义 或 关键词相似度）→ 命中直接返回
    第三层：豆包AI多轮对话（doubao-lite，带缓存）
       ↓
[7] 实时增量学习触发（AI处理后）
    低置信度OR高频 → 创建LearningRecord（待审核）
       ↓
[8] 插件任务下发（有对应插件时）
    意图=exchange → 创建PluginTask（auto_exchange）
    客户端轮询领取 → 执行 → 回调更新状态
```

---

## 4. 插件系统设计

### 4.1 完整生命周期

```
客户端启动
    ↓
POST /api/plugin/register    ← 声明支持的动作码（exchange/login等）
    ↓ 每30秒
POST /api/plugin/heartbeat   ← 保持在线状态（5分钟无心跳视为离线）
    ↓ 每5-10秒轮询
GET  /api/plugin/tasks       ← 获取待执行任务
    ↓ 领取任务执行
执行本地操作（换号/发货等）
    ↓ 执行完成
POST /api/plugin/tasks/<id>/done  ← 上报成功结果
POST /api/plugin/tasks/<id>/fail  ← 上报失败原因
```

### 4.2 任务状态流转

```
pending（待领取）→ claimed（执行中）→ done（完成）
                                    → failed（失败）
```

### 4.3 支持的动作码

| 动作码 | 触发意图 | 说明 |
|--------|---------|------|
| `auto_exchange` | exchange | 自动换号 |
| `handle_refund` | refund | 退款处理 |
| `send_message` | - | 发送消息 |

---

## 5. MaxKB接入说明

### 5.1 部署MaxKB

```bash
# Docker方式部署MaxKB
docker run -d \
  --name maxkb \
  -p 8080:8080 \
  -v ~/.maxkb:/var/lib/postgresql/data \
  1panel/maxkb:latest
```

### 5.2 配置说明

在 `.env` 文件中添加：

```env
# 启用MaxKB向量检索
MAXKB_ENABLED=true
MAXKB_API_URL=http://localhost:8080
MAXKB_API_KEY=<在MaxKB后台生成>
MAXKB_DATASET_ID=<创建数据集后获取>
```

### 5.3 效果对比

| 检索方式 | 命中率 | 成本 | 适用场景 |
|---------|-------|------|---------|
| 关键词重叠率（默认） | ~60% | 0 | 小型知识库，关键词明确 |
| MaxKB语义检索 | ~85% | 低 | 大型知识库，问法多样 |

### 5.4 自动同步

aikefu后台正常管理知识库，保存/修改/删除时自动同步到MaxKB。

---

## 6. 缓存归一化优化

### 6.1 问题背景

原缓存按原始消息MD5哈希存储，"登不上"、"进不去"、"打不开"是3个不同哈希，命中率仅5%。

### 6.2 优化方案

在计算哈希前先做语义归一化替换：

| 原始消息变体 | 归一化后 |
|------------|--------|
| 登不上/进不去/打不开/登录不了 | 无法登录 |
| 换号/换个/换一个/换账号 | 申请换号 |
| 退款/退钱/不要了/申请退 | 申请退款 |
| 密码忘了/密码不对/忘记密码 | 密码问题 |
| 发货/什么时候到/多久到 | 催发货 |
| 怎么用/如何操作/怎么玩 | 使用方法 |

### 6.3 效果

缓存命中率从约5%提升到约60%，减少约60%的AI API调用费用。

---

## 7. 实时学习机制

### 7.1 触发条件

AI处理完消息后，满足以下任一条件时自动创建待审核记录：

1. **低置信度**：AI回复包含兜底词（"不确定"、"我是AI"、"转人工"等）
2. **高频问题**：同一问题（归一化后）在7天内出现≥2次

### 7.2 审核流程

```
AI回复 → 触发检查 → 创建LearningRecord（status=pending）
                              ↓
                      运营人员在学习中心审核
                              ↓
       ✅ 确认入库 → 自动写入KnowledgeBase（+同步MaxKB）
       ✏️ 修改入库 → 修正答案后写入KnowledgeBase
       ❌ 丢弃    → status=rejected，不入库
```

### 7.3 每日补充统计

除实时触发外，每日凌晨1点的统计任务还会批量检查当日高频AI消息，补充创建学习记录。

---

## 8. API接口列表

### 8.1 插件相关API（shop_token鉴权）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/plugin/register | 客户端注册插件能力 |
| POST | /api/plugin/heartbeat | 客户端心跳保活 |
| GET | /api/plugin/tasks | 获取待执行任务列表 |
| POST | /api/plugin/tasks/\<id\>/done | 上报任务完成 |
| POST | /api/plugin/tasks/\<id\>/fail | 上报任务失败 |

### 8.2 订单推送API（shop_token鉴权）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/orders/push | 客户端推送订单数据 |

**请求示例：**
```json
POST /api/orders/push
Header: X-Shop-Token: <shop_token>
{
  "orders": [
    {
      "order_id": "2026030900001",
      "buyer_id": "buyer123",
      "buyer_name": "买家昵称",
      "goods_name": "商品名称",
      "amount": 9900,
      "status": "待发货",
      "created_at": "2026-03-09 10:00:00"
    }
  ],
  "source": "client"
}
```

### 8.3 消息处理API（内部API）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/message | 处理买家消息（三层AI） |
| GET | /api/health | 系统健康检查 |

---

## 9. .env 配置说明

```env
# ============================
# 基础配置
# ============================
SECRET_KEY=your-secret-key-here          # 应用密钥（生产环境必须修改）
DEBUG=false                              # 调试模式（生产设false）

# ============================
# 数据库配置
# ============================
MYSQL_HOST=localhost                     # MySQL主机地址
MYSQL_PORT=3306                         # MySQL端口
MYSQL_USER=aikefu                       # MySQL用户名
MYSQL_PASSWORD=your-db-password         # MySQL密码
MYSQL_DATABASE=aikefu                   # MySQL数据库名
# 不配置MySQL密码则自动使用SQLite（开发环境）

# ============================
# 豆包AI配置（字节跳动火山方舟）
# ============================
DOUBAO_API_KEY=your-ark-api-key         # 火山方舟API密钥
DOUBAO_LITE_MODEL=doubao-lite-32k       # 意图识别/FAQ/多轮对话模型
DOUBAO_PRO_MODEL=doubao-pro-32k        # 退款决策/情绪安抚模型
DOUBAO_VISION_MODEL=doubao-vision-pro-32k  # 图片分析模型

# ============================
# MaxKB向量检索配置（可选）
# ============================
MAXKB_ENABLED=false                     # 是否启用MaxKB（默认false）
MAXKB_API_URL=http://localhost:8080     # MaxKB服务地址
MAXKB_API_KEY=                          # MaxKB API密钥
MAXKB_DATASET_ID=                       # MaxKB数据集ID
```

---

## 10. 部署说明

### 10.1 Docker Compose 部署

```yaml
version: '3.8'
services:
  # aikefu 主服务
  aikefu:
    build: .
    ports:
      - "6000:6000"
    environment:
      - MYSQL_HOST=mysql
      - MYSQL_PASSWORD=aikefu123
      - DOUBAO_API_KEY=${DOUBAO_API_KEY}
      - MAXKB_ENABLED=false
    depends_on:
      - mysql
    volumes:
      - ./logs:/app/logs

  # MySQL 数据库
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root123
      MYSQL_DATABASE: aikefu
      MYSQL_USER: aikefu
      MYSQL_PASSWORD: aikefu123
    volumes:
      - mysql_data:/var/lib/mysql

  # MaxKB 向量检索（可选，需要时取消注释）
  # maxkb:
  #   image: 1panel/maxkb:latest
  #   ports:
  #     - "8080:8080"
  #   volumes:
  #     - maxkb_data:/var/lib/postgresql/data

volumes:
  mysql_data:
  # maxkb_data:
```

### 10.2 启动命令

```bash
# 开发环境（SQLite）
python app.py

# 生产环境（MySQL + Gunicorn）
gunicorn -w 4 -b 0.0.0.0:6000 "app:create_app()"

# Docker Compose
docker-compose up -d
```

### 10.3 默认账号

```
管理员：admin / admin123
（首次登录后请立即修改密码！）
```

---

## 11. V2版本变更日志

### 新增功能

- ✅ MaxKB向量检索接入（可选，配置MAXKB_ENABLED=true启用）
- ✅ 实时增量学习（AI回复后自动触发，替代每日定时假学习）
- ✅ 缓存归一化（命中率5% → 60%）
- ✅ 本地意图识别（0成本覆盖80%意图判断场景）
- ✅ 插件系统（注册/心跳/任务下发/执行/回调完整闭环）
- ✅ 订单推送API（POST /api/orders/push，客户端直接推送）
- ✅ 订单来源字段（client/browser_plugin/manual）

### 删除功能

- ❌ 退款管理模块（/refund/）已删除
- ❌ 每日AI学习定时任务（改为实时触发）

### 优化功能

- 店铺管理表单简化（删除平台API配置和游戏租号配置）
- 店铺编辑页新增shop_token只读显示
- 风险管理只保留黑名单功能（退款统计已删除）
- 侧边栏新增插件管理菜单，删除退款管理菜单
