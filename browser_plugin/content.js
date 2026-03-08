// 爱客服拼多多采集插件 - content.js
// 监听拼多多商家后台DOM变化，采集买家消息并推送到aikefu服务器

(function () {
  'use strict';

  // ────────────── 配置 ──────────────
  const AIKEFU_SERVER = 'http://8.145.43.255:6000';
  const WEBHOOK_URL = `${AIKEFU_SERVER}/api/webhook/pdd`;
  const PUSH_INTERVAL_MS = 500;   // 消息推送间隔
  const MAX_FINGERPRINT_SIZE = 2000; // 去重集合最大条数

  // ────────────── 状态 ──────────────
  let shopToken = '';
  let isEnabled = false;
  const seenFingerprints = new Set();
  const messageQueue = [];
  let processingQueue = false;

  // ────────────── 初始化 ──────────────
  chrome.storage.sync.get(['shopToken', 'isEnabled'], (result) => {
    shopToken = result.shopToken || '';
    isEnabled = result.isEnabled !== false;
    if (isEnabled && shopToken) {
      startObserver();
    }
  });

  chrome.storage.onChanged.addListener((changes) => {
    if (changes.shopToken) shopToken = changes.shopToken.newValue || '';
    if (changes.isEnabled) isEnabled = changes.isEnabled.newValue !== false;
    if (isEnabled && shopToken) startObserver();
  });

  // ────────────── DOM 选择器（适配拼多多2026年版本）──────────────
  const CHAT_CONTAINER_SELECTORS = [
    '.message-list',
    '.chat-message-list',
    '[class*="MessageList"]',
    '[class*="messageList"]',
    '[class*="chatList"]',
    '.im-chat-content',
  ];

  const BUYER_MESSAGE_SELECTORS = [
    '.message-item.message-left',
    '.chat-item[data-direction="left"]',
    '[class*="MessageItem"][class*="left"]',
    '[class*="buyerMessage"]',
    '[class*="receiveMessage"]',
  ];

  const INPUT_BOX_SELECTORS = [
    'div[contenteditable="true"][class*="input"]',
    'div[contenteditable="true"][class*="editor"]',
    'div[contenteditable="true"][class*="chat"]',
    'div[contenteditable="true"]',
    'textarea[class*="input"]',
  ];

  const SEND_BTN_SELECTORS = [
    'button:contains("发送")',
    '[class*="sendBtn"]',
    '[class*="send-btn"]',
    'button[class*="send"]',
  ];

  // ────────────── MutationObserver ──────────────
  let observer = null;

  function startObserver() {
    if (observer) return;

    observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) {
            scanForMessages(node);
          }
        }
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    // 初始扫描已有消息
    scanForMessages(document.body);
    console.log('[爱客服] 消息监听已启动');
  }

  // ────────────── 消息扫描 ──────────────
  function scanForMessages(root) {
    for (const selector of BUYER_MESSAGE_SELECTORS) {
      const items = root.querySelectorAll ? root.querySelectorAll(selector) : [];
      for (const item of items) {
        processMessageElement(item);
      }
    }
  }

  function processMessageElement(el) {
    try {
      const data = extractMessageData(el);
      if (!data) return;

      const fingerprint = makeFingerprint(data);
      if (seenFingerprints.has(fingerprint)) return;

      // 去重集合大小控制：超出限制时批量清除20%最旧条目
      if (seenFingerprints.size >= MAX_FINGERPRINT_SIZE) {
        const removeCount = Math.ceil(MAX_FINGERPRINT_SIZE * 0.2);
        const iter = seenFingerprints.values();
        for (let i = 0; i < removeCount; i++) {
          const next = iter.next();
          if (next.done) break;
          seenFingerprints.delete(next.value);
        }
      }
      seenFingerprints.add(fingerprint);

      messageQueue.push(data);
      if (!processingQueue) {
        processQueue();
      }
    } catch (e) {
      console.debug('[爱客服] 处理消息元素失败:', e);
    }
  }

  // ────────────── 数据提取 ──────────────
  function extractMessageData(el) {
    // 提取买家ID
    const buyerId = extractBuyerId(el);
    // 提取消息内容
    const content = extractContent(el);
    // 提取消息类型
    const msgType = extractMsgType(el);
    // 提取订单信息
    const orderInfo = extractOrderInfo(el);
    // 提取买家昵称
    const buyerName = extractBuyerName(el);

    if (!content && !orderInfo) return null;

    return {
      buyer_id: buyerId,
      buyer_name: buyerName,
      content: content || '',
      msg_type: msgType,
      order_id: orderInfo ? (orderInfo.order_sn || '') : '',
      order_info: orderInfo || {},
      timestamp: Date.now(),
    };
  }

  function extractBuyerId(el) {
    // 尝试从 data 属性提取
    const candidates = [
      el.dataset.buyerId,
      el.dataset.uid,
      el.dataset.userId,
      el.closest('[data-buyer-id]')?.dataset.buyerId,
      el.closest('[data-uid]')?.dataset.uid,
    ];
    for (const c of candidates) {
      if (c) return String(c);
    }

    // 尝试从 URL 提取当前会话买家ID
    const match = location.href.match(/[?&]uid=([^&]+)/);
    if (match) return match[1];

    return '';
  }

  function extractBuyerName(el) {
    const nameEl = el.querySelector('[class*="nickname"], [class*="userName"], [class*="buyerName"]');
    return nameEl ? nameEl.textContent.trim() : '';
  }

  function extractContent(el) {
    // 文字内容
    const textEl = el.querySelector(
      '[class*="textContent"], [class*="msgText"], [class*="content"] span, p'
    );
    if (textEl) return textEl.textContent.trim();

    // 图片消息
    const imgEl = el.querySelector('img[src*="pinduoduo"], img[class*="msgImg"]');
    if (imgEl) return '[图片]';

    // 直接取文本（去掉时间戳等）
    const text = el.textContent.trim();
    if (text && text.length < 500) return text;

    return '';
  }

  function extractMsgType(el) {
    if (el.querySelector('img[class*="msgImg"], [class*="imageMsg"]')) return 'image';
    if (el.querySelector('[class*="goodsCard"], [class*="goodsMsg"]')) return 'goods';
    if (el.querySelector('[class*="orderCard"], [class*="orderMsg"]')) return 'order';
    return 'text';
  }

  function extractOrderInfo(el) {
    const orderEl = el.querySelector('[class*="orderCard"], [class*="orderMsg"]');
    if (!orderEl) return null;

    const orderSn = orderEl.dataset.orderSn
      || orderEl.querySelector('[class*="orderSn"]')?.textContent?.trim()
      || '';
    const goodsName = orderEl.querySelector('[class*="goodsName"]')?.textContent?.trim() || '';

    return { order_sn: orderSn, goods_name: goodsName };
  }

  function makeFingerprint(data) {
    return `${data.buyer_id}|${data.content}|${data.timestamp}`;
  }

  // ────────────── 消息队列处理 ──────────────
  async function processQueue() {
    if (processingQueue) return;
    processingQueue = true;

    while (messageQueue.length > 0) {
      const msg = messageQueue.shift();
      await sendToServer(msg);
      await sleep(PUSH_INTERVAL_MS);
    }

    processingQueue = false;
  }

  async function sendToServer(data) {
    if (!shopToken || !isEnabled) return;

    try {
      const resp = await fetch(WEBHOOK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          shop_token: shopToken,
          buyer_id: data.buyer_id,
          buyer_name: data.buyer_name,
          content: data.content,
          msg_type: data.msg_type,
          order_id: data.order_id,
          order_info: data.order_info,
        }),
      });

      if (!resp.ok) {
        console.warn('[爱客服] 推送消息失败:', resp.status);
        return;
      }

      const result = await resp.json();
      if (result.success && result.reply && !result.needs_human) {
        await injectReply(result.reply);
      } else if (result.needs_human) {
        showHumanBanner();
      }
    } catch (e) {
      console.debug('[爱客服] 推送消息异常:', e);
    }
  }

  // ────────────── 注入AI回复 ──────────────
  async function injectReply(replyText) {
    const inputBox = findInputBox();
    if (!inputBox) {
      console.warn('[爱客服] 找不到输入框，无法注入回复');
      return;
    }

    inputBox.focus();

    if (inputBox.tagName === 'TEXTAREA' || inputBox.tagName === 'INPUT') {
      inputBox.value = replyText;
      inputBox.dispatchEvent(new Event('input', { bubbles: true }));
    } else {
      // contenteditable
      inputBox.innerText = replyText;
      inputBox.dispatchEvent(new InputEvent('input', { bubbles: true }));
    }

    // 短暂延迟后尝试自动发送
    await sleep(300);
    const sent = clickSendButton();
    if (!sent) {
      // 按回车发送
      inputBox.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true,
      }));
    }
  }

  function findInputBox() {
    for (const selector of INPUT_BOX_SELECTORS) {
      const el = document.querySelector(selector);
      if (el && isVisible(el)) return el;
    }
    return null;
  }

  function clickSendButton() {
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
      if (btn.textContent.includes('发送') && isVisible(btn)) {
        btn.click();
        return true;
      }
    }
    return false;
  }

  // ────────────── 人工介入提示横幅 ──────────────
  function showHumanBanner() {
    const existing = document.getElementById('aikefu-human-banner');
    if (existing) return;

    const banner = document.createElement('div');
    banner.id = 'aikefu-human-banner';
    banner.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; z-index: 99999;
      background: #ff4d4f; color: white; text-align: center;
      padding: 10px; font-size: 14px; font-weight: bold;
      box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    `;
    banner.innerHTML = `
      ⚠️ 需要人工客服介入！
      <button onclick="this.parentElement.remove()" style="
        margin-left: 16px; background: white; color: #ff4d4f;
        border: none; padding: 2px 10px; border-radius: 4px; cursor: pointer;
      ">关闭</button>
    `;
    document.body.prepend(banner);

    // 10秒后自动关闭
    setTimeout(() => banner.remove(), 10000);
  }

  // ────────────── 工具函数 ──────────────
  function isVisible(el) {
    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

})();
