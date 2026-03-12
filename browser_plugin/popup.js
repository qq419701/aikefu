'use strict';

document.addEventListener('DOMContentLoaded', () => {
    chrome.storage.local.get(['serverUrl', 'shopToken', 'autoReply'], (result) => {
        document.getElementById('serverUrl').value = result.serverUrl || 'http://127.0.0.1:8000';
        document.getElementById('shopToken').value = result.shopToken || '';
        document.getElementById('autoReply').checked = result.autoReply !== false;
    });
    setTimeout(testConnection, 300);

    document.getElementById('btnSave').addEventListener('click', saveSettings);
    document.getElementById('btnRecheck').addEventListener('click', testConnection);
    document.getElementById('btnToggleToken').addEventListener('click', toggleTokenVisibility);
    document.getElementById('btnDashboard').addEventListener('click', openDashboard);
});

function saveSettings() {
    const serverUrl = document.getElementById('serverUrl').value.trim().replace(/\/$/, '');
    const shopToken = document.getElementById('shopToken').value.trim();
    const autoReply = document.getElementById('autoReply').checked;

    if (!serverUrl) { alert('请填写服务器地址'); return; }

    chrome.storage.local.set({ serverUrl, shopToken, autoReply }, () => {
        const btn = document.getElementById('btnSave');
        btn.textContent = '✅ 已保存';
        btn.disabled = true;
        setTimeout(() => { btn.textContent = '💾 保存设置'; btn.disabled = false; }, 1500);
        testConnection();
    });
}

function testConnection() {
    const serverUrl = document.getElementById('serverUrl').value.trim().replace(/\/$/, '') || 'http://127.0.0.1:8000';
    setStatus('checking', '检测中...');
    chrome.runtime.sendMessage({ action: 'testConnection', serverUrl }, (response) => {
        if (chrome.runtime.lastError) { setStatus('disconnected', '插件通信错误'); return; }
        if (response && response.connected) {
            setStatus('connected', `已连接 · ${response.system || ''} ${response.version || ''}`);
        } else {
            setStatus('disconnected', `未连接 · ${response && response.error ? response.error : '无法连接'}`);
        }
    });
}

function setStatus(type, text) {
    const dot = document.getElementById('statusDot');
    const label = document.getElementById('statusText');
    dot.className = 'status-dot';
    if (type === 'connected') dot.classList.add('status-connected');
    else if (type === 'disconnected') dot.classList.add('status-disconnected');
    else dot.classList.add('status-checking');
    label.textContent = text;
}

function toggleTokenVisibility() {
    const input = document.getElementById('shopToken');
    input.type = input.type === 'password' ? 'text' : 'password';
}

function openDashboard() {
    chrome.storage.local.get(['serverUrl'], (result) => {
        const url = (result.serverUrl || 'http://127.0.0.1:6000').replace(/\/$/, '');
        chrome.tabs.create({ url });
    });
}
