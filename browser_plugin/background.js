// 爱客服拼多多采集插件 - background.js (Service Worker)

chrome.runtime.onInstalled.addListener(() => {
  console.log('[爱客服] 插件已安装');
});

// 监听来自 content.js 的消息（备用通道）
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'PING') {
    sendResponse({ type: 'PONG', status: 'ok' });
  }
  return true;
});
