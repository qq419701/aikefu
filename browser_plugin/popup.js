// 爱客服采集插件 - popup.js

const enableToggle = document.getElementById('enableToggle');
const shopTokenInput = document.getElementById('shopTokenInput');
const serverUrlInput = document.getElementById('serverUrlInput');
const saveBtn = document.getElementById('saveBtn');
const statusMsg = document.getElementById('statusMsg');

// 加载已保存的配置
chrome.storage.sync.get(['shopToken', 'serverUrl', 'isEnabled'], (result) => {
  shopTokenInput.value = result.shopToken || '';
  serverUrlInput.value = result.serverUrl || 'http://8.145.43.255:6000';
  enableToggle.checked = result.isEnabled !== false;
});

// 保存配置
saveBtn.addEventListener('click', () => {
  const shopToken = shopTokenInput.value.trim();
  const serverUrl = serverUrlInput.value.trim() || 'http://8.145.43.255:6000';
  const isEnabled = enableToggle.checked;

  if (!shopToken) {
    showStatus('请填写 Shop Token', 'error');
    return;
  }

  chrome.storage.sync.set({ shopToken, serverUrl, isEnabled }, () => {
    showStatus('✅ 设置已保存', 'success');
    setTimeout(() => hideStatus(), 3000);
  });
});

function showStatus(text, type) {
  statusMsg.textContent = text;
  statusMsg.className = `status ${type}`;
}

function hideStatus() {
  statusMsg.className = 'status hidden';
}
