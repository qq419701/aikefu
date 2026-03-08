# 爱客服采集客户端

`qq419701/aikefu`（爱客服AI客服系统）配套的 **Windows桌面采集客户端**。

## 架构关系

```
dskehuduan（本项目/桌面客户端）
    ↓ 直接读写
MySQL数据库（aikefu共享，8.145.43.255）
    ↑ 读取处理
aikefu（AI客服服务器，Flask Web系统）
```

## 功能特性

- 🏪 **多店铺管理**：从 aikefu MySQL 数据库读取店铺列表，一键启动/停止采集
- 💬 **实时消息采集**：WebSocket 直连 `wss://m-ws.pinduoduo.com/`，支持文本/图片/订单/商品咨询
- 🤖 **AI回复自动发送**：调用 aikefu API 获取 AI 回复，通过 Playwright 自动回复买家
- 📦 **订单自动同步**：定时采集拼多多订单写入 MySQL `pdd_orders` 表
- 📊 **数据统计面板**：实时显示今日消息数、AI处理数、转人工数
- 🔔 **桌面通知提醒**：新消息和需人工介入时发送系统通知
- 🔒 **密码AES加密存储**：MySQL密码用 AES-CBC 加密后存储到本地配置文件
- 🌐 **Chrome插件辅助**：提供 Chrome 扩展作为备用采集方案
- 📦 **Windows安装包**：支持 PyInstaller 打包 + Inno Setup 生成安装程序

## 技术栈

| 组件 | 技术 |
|------|------|
| UI框架 | PyQt6 + PyQt6-Fluent-Widgets (qfluentwidgets) |
| 消息采集 | WebSocket (`websockets`) 直连拼多多 |
| 浏览器自动化 | Playwright（登录 + 自动发送消息） |
| 数据库 | PyMySQL + SQLAlchemy（直连 aikefu MySQL） |
| 服务器通信 | HTTP REST API（`requests`） |
| 加密 | PyCryptodome（AES-CBC） |
| 打包 | PyInstaller + Inno Setup |

## 项目结构

```
dskehuduan/
├── app.py                      # 主入口
├── config.py                   # 配置管理
├── pyproject.toml              # 项目依赖
├── requirements.txt            # pip依赖清单
├── build.py                    # PyInstaller打包脚本
├── installer.iss               # Inno Setup安装包脚本
│
├── core/
│   ├── db_client.py            # MySQL连接客户端
│   ├── server_api.py           # aikefu REST API客户端
│   └── encrypt.py              # AES加密工具
│
├── channel/
│   ├── base_channel.py         # 渠道基类（含自动重连）
│   └── pinduoduo/
│       ├── pdd_login.py        # Playwright登录
│       ├── pdd_channel.py      # WebSocket直连采集
│       ├── pdd_message.py      # 消息格式解析
│       ├── pdd_order.py        # 订单采集与同步
│       ├── pdd_product.py      # 商品信息采集
│       └── pdd_sender.py       # 通过Playwright发送AI回复
│
├── ui/
│   ├── main_window.py          # FluentWindow主窗口
│   ├── login_ui.py             # MySQL配置向导（首次运行）
│   ├── shop_ui.py              # 店铺管理界面
│   ├── dashboard_ui.py         # 数据统计面板
│   ├── message_ui.py           # 实时消息监控
│   └── setting_ui.py           # 设置界面
│
├── utils/
│   ├── logger.py               # 日志工具
│   └── notifier.py             # 桌面通知
│
└── browser_plugin/             # Chrome插件（辅助方案）
    ├── manifest.json
    ├── content.js
    ├── background.js
    ├── popup.html
    └── popup.js
```

## 安装与部署

### 方式一：源码运行（开发模式）

```bash
# 1. 克隆仓库
git clone https://github.com/qq419701/dskehuduan.git
cd dskehuduan

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装 Playwright 浏览器
playwright install chromium

# 4. 启动客户端
python app.py
```

### 方式二：Windows安装包

```bash
# 打包
python build.py
# 然后用 Inno Setup 编译 installer.iss
```

## MySQL 连接配置

首次运行弹出配置向导，填写以下信息：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| MySQL 主机 | 8.145.43.255 | aikefu 服务器IP |
| MySQL 端口 | 3306 | 默认端口 |
| 数据库名 | aikefu | aikefu 数据库 |
| 用户名 | *(必填)* | 数据库账号 |
| 密码 | *(必填)* | 密码将AES加密存储 |

配置文件：`~/.aikefu-client/config.json`

## 拼多多店铺管理

1. 在 **aikefu 后台**（`http://8.145.43.255:6000`）添加拼多多店铺
2. 在客户端「店铺管理」点击「刷新店铺列表」
3. 点击「▶ 启动采集」，Chromium 浏览器将自动打开
4. 完成拼多多商家后台登录后，自动开始消息采集

## Chrome 插件使用

1. 打开 `chrome://extensions/` 开启开发者模式
2. 加载 `browser_plugin/` 目录
3. 填写从 aikefu 后台获取的 `shop_token`
4. 在拼多多商家后台正常使用，插件自动采集消息

## 常见问题

**Q: 数据库连接失败？**
- 确认 MySQL 服务器可访问（ping 8.145.43.255）
- 检查账号密码及数据库读写权限
- 防火墙确认放行 3306 端口

**Q: 日志文件在哪里？**
- `~/.aikefu-client/logs/aikefu-client.log`（按天轮转，保留30天）
