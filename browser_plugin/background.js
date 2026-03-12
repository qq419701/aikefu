// 爱客服AI助手 - Service Worker（背景脚本）
// 功能：作为 content.js 和本地服务之间的中间层，解决CORS问题
// Manifest V3 使用 Service Worker 替代 background page

'use strict';

// ── 监听来自 content.js 的消息 ─────────────────────────────────────────────
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'sendToServer') {
        // 异步转发请求到本地服务（background可绕过CORS限制）
        forwardToServer(message.url, message.payload)
            .then(sendResponse)
            .catch((err) => sendResponse({ success: false, error: err.message }));
        return true; // 保持消息通道开放（异步响应）
    }

    if (message.action === 'testConnection') {
        testServerConnection(message.serverUrl)
            .then(sendResponse)
            .catch(() => sendResponse({ connected: false }));
        return true;
    }
});

// ── 转发消息到本地爱客服服务 ──────────────────────────────────────────────
async function forwardToServer(url, payload) {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10秒超时

        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
            const text = await response.text();
            return { success: false, error: `HTTP ${response.status}: ${text}` };
        }

        const data = await response.json();
        return data;

    } catch (err) {
        if (err.name === 'AbortError') {
            return { success: false, error: '请求超时，请检查爱客服服务是否运行' };
        }
        return { success: false, error: err.message };
    }
}

// ── 测试连接（供弹窗使用）────────────────────────────────────────────────
async function testServerConnection(serverUrl) {
    try {
        const response = await fetch(`${serverUrl}/api/health`, {
            method: 'GET',
            signal: AbortSignal.timeout(5000),
        });
        if (response.ok) {
            const data = await response.json();
            return { connected: true, system: data.system, version: data.version };
        }
        return { connected: false, error: `HTTP ${response.status}` };
    } catch (err) {
        return { connected: false, error: err.message };
    }
}

// ── 插件安装/更新时初始化默认配置 ────────────────────────────────────────
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') {
        chrome.storage.local.set({
            serverUrl: 'http://127.0.0.1:8000',
            shopToken: '',
            autoReply: true,
        });
        console.log('[爱客服] 插件已安装，已设置默认配置');
    }
});

console.log('[爱客服] Service Worker 已启动');
