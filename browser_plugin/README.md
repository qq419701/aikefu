# 爱客服 - 拼多多AI助手 Chrome插件

拼多多商家后台AI客服助手，自动抓取买家消息、调用本地AI引擎处理，并将回复注入输入框。

---

## 功能特性

- 🔍 **自动监听**：通过 MutationObserver 监听聊天窗口 DOM 变化，检测新买家消息
- 📦 **订单抓取**：从侧边栏提取订单号、商品名、金额、状态等信息
- 🤖 **AI回复**：消息推送到本地爱客服服务，AI自动生成回复
- ✅ **自动发送**：AI回复自动填入输入框并发送（可配置关闭）
- 🚨 **人工提醒**：AI判断需要人工时，显示橙色提示横幅，不自动发送
- 🔒 **Token鉴权**：通过店铺 Token 与服务端鉴权，保证数据安全

---

## 安装步骤

### 1. 加载插件到 Chrome

1. 打开 Chrome 浏览器，地址栏输入：`chrome://extensions/`
2. 右上角开启 **「开发者模式」**（Developer mode）
3. 点击 **「加载已解压的扩展程序」**（Load unpacked）
4. 选择本目录（`browser_plugin/`）
5. 插件图标 🤖 出现在工具栏，安装成功

### 2. 配置插件

1. 点击工具栏中的插件图标，打开弹窗
2. **服务器地址**：填写爱客服服务的地址（默认 `http://127.0.0.1:8000`）
3. **店铺 Token**：
   - 登录爱客服管理后台
   - 进入 **店铺管理** → 点击对应店铺
   - 或调用接口 `GET /api/shop/token?shop_id=1` 获取
   - 复制 Token 粘贴到插件弹窗
4. 点击 **「保存设置」**，绿色状态表示连接成功

### 3. 开始使用

1. 打开拼多多商家后台：[https://mms.pinduoduo.com/](https://mms.pinduoduo.com/)
2. 进入消息/聊天页面
3. 插件自动开始监听买家消息，AI回复会自动出现

---

## 工作流程

```
买家发消息
    ↓
content.js 检测到新消息（MutationObserver）
    ↓
提取: 买家ID、消息内容、订单信息
    ↓
background.js 转发到: POST /api/webhook/pdd
    ↓
爱客服 AI 引擎处理（三层: 规则→知识库→豆包AI）
    ↓
返回回复 + needs_human 标志
    ↓
needs_human=false → 自动填入并发送
needs_human=true  → 填入输入框 + 显示橙色提示横幅
```

---

## 推送数据格式

```json
{
  "shop_token": "从插件配置中读取的店铺token",
  "buyer_id": "买家用户ID",
  "buyer_name": "买家昵称",
  "content": "消息内容",
  "msg_type": "text",
  "order_id": "订单号",
  "order_info": {
    "order_id": "订单号",
    "goods_name": "商品名",
    "amount": 99.00,
    "status": "待发货",
    "create_time": "2026-03-06"
  }
}
```

---

## 注意事项

- 插件通过本地 HTTP 接口与爱客服服务通信，**不会将数据传输到任何第三方**
- 首次使用请确保爱客服服务 (`python app.py`) 已启动
- 拼多多后台页面结构可能随版本更新变化，如消息检测失效，请检查 `content.js` 中的 CSS 选择器
- Token 一旦泄露可在后台重新生成（旧 Token 立即失效）

---

## 其他平台扩展（预留）

本插件仅支持拼多多。如需接入淘宝、京东、抖店，可参照：
- `content_scripts.matches` 添加对应平台域名
- 复制 `content.js`，修改 DOM 选择器适配对应平台
- 服务端 `/api/webhook/pdd` 可扩展为统一接口

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `manifest.json` | Chrome Extension 配置文件 |
| `content.js` | 注入拼多多页面的内容脚本，监听消息 |
| `background.js` | Service Worker，转发请求处理CORS |
| `popup.html` | 插件弹窗页面 |
| `popup.js` | 弹窗交互逻辑 |
| `README.md` | 本文档 |
