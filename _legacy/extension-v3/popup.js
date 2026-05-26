const api = typeof browser !== 'undefined' ? browser : chrome;

document.getElementById('openSidebar').onclick = async () => {
  // For Chrome sidePanel, opening the panel is handled by action click behavior
  // For Firefox sidebar_action, just open chatgpt.com
  const tabs = await api.tabs.query({ url: 'https://chatgpt.com/*' });
  if (tabs.length) {
    await api.tabs.update(tabs[0].id, { active: true });
  } else {
    await api.tabs.create({ url: 'https://chatgpt.com' });
  }
  window.close();
};

document.getElementById('openChatGPT').onclick = () => {
  api.tabs.create({ url: 'https://chatgpt.com' });
  window.close();
};
