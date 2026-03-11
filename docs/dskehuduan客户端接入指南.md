# dskehuduan 客户端接入指南

> 本文档面向 dskehuduan 客户端开发者，说明如何与 aikefu 服务端完整对接。  
> 服务端完整API文档见 README_V2.md 第8章和第16章。  
> 版本：v2.1 | 更新时间：2026-03-11

---

## 快速对接步骤

1. **登录** → `POST /api/client/login`
2. **获取店铺** → `GET /api/client/shops`
3. **注册插件** → `POST /api/plugin/register`（每个 shop_token）
4. **心跳保活** → `POST /api/plugin/heartbeat`（每30秒）
5. **轮询任务** → `GET /api/plugin/tasks`（每2秒）
6. **上报结果** → `POST /api/plugin/tasks/<id>/done` 或 `/fail`

---

## 一、账号登录

### POST `/api/client/login`

客户端启动时，通过管理员账号密码登录，获取 `client_token`。

**请求**：
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**成功响应（200）**：
```json
{
  "success": true,
  "client_token": "a3f8c2d1e9b7...",
  "username": "admin",
  "display_name": "管理员",
  "expires_in": 604800
}
```

**失败响应（401）**：
```json
{"success": false, "message": "用户名或密码错误"}
```

---

## 二、获取名下店铺

### GET `/api/client/shops`

**请求头**：
```
X-Client-Token: <client_token>
```

**成功响应**：
```json
{
  "success": true,
  "shops": [
    {
      "id": 1,
      "name": "程洋游戏",
      "platform": "pdd",
      "shop_token": "d3af8c2e...",
      "is_active": true,
      "auto_reply_enabled": true
    }
  ]
}
```

每个店铺有独立的 `shop_token`，用于后续插件API鉴权（`X-Shop-Token` 请求头）。

---

## 三、插件注册与心跳

### POST `/api/plugin/register`

客户端启动时，为每个店铺注册插件能力（声明支持的 `action_codes`）。

```json
POST /api/plugin/register
X-Shop-Token: <shop_token>

{
  "plugin_id": "pdd_shop",
  "name": "拼多多店铺插件",
  "description": "自动换号、退款处理、订单同步",
  "action_codes": ["auto_exchange", "handle_refund", "order_sync"],
  "client_version": "2.1.0"
}

// 响应
{"success": true, "message": "插件 pdd_shop 注册成功"}
```

### POST `/api/plugin/heartbeat`

每30秒发送一次心跳，超过5分钟无心跳服务端视为离线。

```json
POST /api/plugin/heartbeat
X-Shop-Token: <shop_token>

{"plugin_id": "pdd_shop"}

// 响应
{"success": true, "pending_tasks": 2}
```

---

## 四、轮询与执行任务

### GET `/api/plugin/tasks`

每2秒轮询一次，获取待执行任务（FIFO，最多返回10条）。

```json
GET /api/plugin/tasks?plugin_id=pdd_shop
X-Shop-Token: <shop_token>

// 响应
{
  "success": true,
  "tasks": [
    {
      "id": 42,
      "task_id": "abc-uuid",
      "action_code": "auto_exchange",
      "payload": {
        "buyer_id": "pdd_buyer_xxx",
        "order_id": "202501010001",
        "message": "帮我换号",
        "intent": "exchange"
      },
      "created_at": "2026-03-11T10:00:00"
    }
  ],
  "count": 1
}
```

---

## 五、上报任务结果

### POST `/api/plugin/tasks/<id>/done`

任务执行成功后上报结果。服务端会根据意图规则的 `done_reply_tpl` 生成回复文案。

**请求**：
```json
POST /api/plugin/tasks/42/done
X-Shop-Token: <shop_token>

{
  "result": {
    "success": true,
    "new_account": "GAME_888",
    "new_password": "pass123",
    "order_id": "202501010001"
  }
}
```

**响应**（含自动回复文案）：
```json
{
  "success": true,
  "message": "任务已标记为完成",
  "reply_to_buyer": "已为您换号，新账号：GAME_888，密码：pass123"
}
```

### POST `/api/plugin/tasks/<id>/fail`

任务执行失败时上报。

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

## 六、消息回复上报（v2.1）

任务完成上报后，服务端返回 `reply_to_buyer`，**客户端必须将此文本发送给买家**：

```json
// POST /api/plugin/tasks/42/done 响应示例
{
  "success": true,
  "reply_to_buyer": "换号完成！新账号：GAME_888，如有问题请联系我们😊"
}
```

客户端收到 `reply_to_buyer` 非空时，通过 Playwright/平台接口将文本发送给买家。  
发送完成后，可以（可选）调用 `POST /api/plugin/tasks/<id>/reply_sent` 通知服务端已发送。

---

## 七、其他常用API

### POST `/api/client/refresh` — 刷新 Token

```
X-Client-Token: <client_token>
// 响应: {"success": true, "expires_in": 604800}
```

### POST `/api/client/logout` — 退出登录

```
X-Client-Token: <client_token>
// 响应: {"success": true}
```

### POST `/api/orders/push` — 推送订单数据

```json
POST /api/orders/push
X-Shop-Token: <shop_token>

{
  "orders": [
    {
      "order_id": "2026031100001",
      "buyer_id": "buyer001",
      "buyer_name": "张三",
      "goods_name": "游戏账号7天",
      "amount": 9900,
      "status": "待发货",
      "created_at": "2026-03-11 10:00:00"
    }
  ],
  "source": "client"
}
```

---

## 八、支持的 action_codes

| action_code | 说明 | 业务场景 |
|-------------|------|----------|
| `auto_exchange` | 自动换号 | 游戏租号行业，买家要求换号 |
| `handle_refund` | 退款处理 | 退款流程自动化 |
| `order_sync` | 订单同步 | 拉取最新订单数据 |
| `fetch_messages` | 消息同步 | 拉取平台消息 |
| `uhaozu_exchange` | U号租换号 | U号租专区自动换号 |
| 自定义 | 任意字符串 | 在意图规则后台配置，注册时声明支持 |

> **注意**：`action_code` 不限于内置值，可在爱客服管理后台 → 意图规则 中自定义，客户端注册时在 `action_codes` 数组中声明即可接收对应任务。

---

## 九、完整接入示例（Python）

```python
import requests
import time
import threading

SERVER = "https://example.com:6000"  # 生产环境请使用 HTTPS

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

def run_shop(shop):
    shop_token = shop["shop_token"]
    headers = {"X-Shop-Token": shop_token}

    # 3. 注册插件
    requests.post(f"{SERVER}/api/plugin/register", headers=headers, json={
        "plugin_id": "pdd_shop",
        "name": "拼多多店铺插件",
        "action_codes": ["auto_exchange", "handle_refund"],
        "client_version": "2.1.0"
    })

    # 4. 心跳线程（每30秒）
    def heartbeat():
        while True:
            requests.post(f"{SERVER}/api/plugin/heartbeat", headers=headers,
                          json={"plugin_id": "pdd_shop"})
            time.sleep(30)

    threading.Thread(target=heartbeat, daemon=True).start()

    # 5. 轮询任务（每2秒）
    while True:
        resp = requests.get(f"{SERVER}/api/plugin/tasks?plugin_id=pdd_shop",
                            headers=headers)
        tasks = resp.json().get("tasks", [])
        for task in tasks:
            # 执行任务（换号/退款等）
            result = execute_task(task)  # 客户端自实现

            if result["success"]:
                # 6. 上报完成，获取回复文案
                done_resp = requests.post(
                    f"{SERVER}/api/plugin/tasks/{task['id']}/done",
                    headers=headers, json={"result": result}
                )
                reply_to_buyer = done_resp.json().get("reply_to_buyer", "")
                if reply_to_buyer:
                    # 通过平台接口发送给买家
                    send_to_buyer(task["payload"]["buyer_id"], reply_to_buyer)
            else:
                requests.post(f"{SERVER}/api/plugin/tasks/{task['id']}/fail",
                              headers=headers, json={"result": result})
        time.sleep(2)

# 3. 为每个店铺启动独立线程
for shop in shops:
    threading.Thread(target=run_shop, args=(shop,), daemon=True).start()
```

---

## 十、常见问题排查

### 插件离线
确认心跳正常（每30秒），服务端超过5分钟无心跳视为离线。  
查看服务端健康状态：`GET /api/health/plugin-status`

### 任务获取为空
确认 `plugin_id` 与注册时一致，且服务端有对应意图规则配置了该 `action_code`。

### reply_to_buyer 为空
检查服务端意图规则是否配置了 `done_reply_tpl`，或检查 `result` 字典中的变量名是否与模板变量一致。

### Token 过期
Token 有效期7天，客户端启动时调用 `POST /api/client/refresh` 自动续期。

---

*文档版本：v2.1 | 最后更新：2026-03-11 北京时间*
