(function () {
  const api = typeof browser !== 'undefined' ? browser : chrome;
  let aborted = false;

  api.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === 'submitPrompt') {
      aborted = false;
      processPrompt(msg.prompt).then(sendResponse);
      return true;
    }
    if (msg.action === 'abortPrompt') {
      aborted = true;
      sendResponse({ ok: 1 });
    }
    if (msg.action === 'doReload') {
      setTimeout(() => location.reload(), 800);
      sendResponse({ ok: 1 });
    }
  });

  async function processPrompt(prompt) {
    try {
      const input = findInput();
      if (!input) return { error: 'ChatGPT input field not found' };

      if (input.tagName === 'TEXTAREA') {
        setReactValue(input, prompt);
      } else if (input.isContentEditable) {
        input.textContent = prompt;
        input.dispatchEvent(new Event('input', { bubbles: true }));
      } else {
        input.value = prompt;
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }

      await sleep(800);
      if (aborted) return { aborted: true };

      const btn = findSendButton();
      if (btn) {
        btn.click();
      } else {
        const ta = findTextarea();
        if (ta) {
          ta.dispatchEvent(new KeyboardEvent('keydown', {
            key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
            bubbles: true, cancelable: true
          }));
        }
      }

      const ok = await waitForImage(60000);
      if (aborted) return { aborted: true };

      if (ok) {
        await sleep(1000);
        const imgUrl = await getImageUrl();
        await downloadImage(prompt);
        await sleep(1500);
        return { success: true, image: true, imageUrl: imgUrl };
      }
      await sleep(2000);
      return { success: true, image: false };
    } catch (e) {
      return { error: e.message };
    }
  }

  function findInput() {
    return document.querySelector('#prompt-textarea')
      || document.querySelector('div[contenteditable="true"]')
      || document.querySelector('[role="textbox"]')
      || document.querySelector('textarea:not([hidden])');
  }

  function findTextarea() {
    return document.querySelector('#prompt-textarea')
      || document.querySelector('textarea:not([hidden])');
  }

  function setReactValue(el, val) {
    try {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype, 'value'
      ).set;
      setter.call(el, val);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    } catch {
      el.value = val;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  function findSendButton() {
    const selectors = [
      'button[data-testid="send-button"]',
      'button[aria-label*="Send"]',
      'button[aria-label*="send"]',
      'button:not([disabled]) svg[viewBox]'
    ];
    for (const s of selectors) {
      const el = document.querySelector(s);
      if (el) return el.closest('button') || el;
    }
    return Array.from(document.querySelectorAll('button:not([disabled])'))
      .find(b => b.offsetParent !== null && (
        b.innerHTML.includes('➤') ||
        b.innerHTML.includes('arrow') ||
        b.innerHTML.includes('send') ||
        b.innerHTML.includes('▶') ||
        b.querySelector('svg')
      ));
  }

  async function waitForImage(timeout) {
    const start = Date.now();

    // Wait for stop button to appear (generation started)
    while (Date.now() - start < timeout) {
      if (aborted) return false;
      const stop = document.querySelector(
        'button[aria-label*="Stop"], button[aria-label*="stop"]'
      );
      if (stop) break;
      await sleep(500);
    }

    // Wait for stop button to disappear + extra time for image render
    while (Date.now() - start < timeout) {
      if (aborted) return false;
      const stop = document.querySelector(
        'button[aria-label*="Stop"], button[aria-label*="stop"]'
      );
      if (!stop) {
        await sleep(3000);
        // Check for image
        const img = document.querySelector(
          'img[src*="oaidalle"], img[src*="dalle"], img[alt*="Generated"]'
        );
        if (img && img.complete && img.naturalWidth > 0) return true;
        // Check again after a bit more time
        await sleep(2000);
        const img2 = document.querySelector(
          'img[src*="oaidalle"], img[src*="dalle"], img[alt*="Generated"]'
        );
        if (img2 && img2.complete && img2.naturalWidth > 0) return true;
        return false;
      }
      await sleep(1000);
    }
    return false;
  }

  async function downloadImage(prompt) {
    await sleep(2000);
    const imgs = document.querySelectorAll(
      'img[src*="oaidalle"], img[src*="dalle"], img[alt*="Generated"]'
    );
    if (!imgs.length) return;
    const img = imgs[imgs.length - 1];
    const src = img.src || img.getAttribute('src');
    if (!src || src.startsWith('blob:')) return;

    const safe = (prompt || 'img').replace(/[^a-zA-Z0-9]/g, '_').substring(0, 25);
    const fn = safe + '_' + Date.now() + '.png';

    try {
      const resp = await fetch(src);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = fn;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
    } catch {
      api.runtime.sendMessage({ action: 'downloadImage', url: src, filename: fn }).catch(() => {});
    }
  }

  function getImageUrl() {
    const imgs = document.querySelectorAll(
      'img[src*="oaidalle"], img[src*="dalle"], img[alt*="Generated"]'
    );
    if (!imgs.length) return null;
    const src = imgs[imgs.length - 1].src;
    return src && !src.startsWith('blob:') ? src : null;
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
})();
