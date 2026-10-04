(() => {
  'use strict';

  const STORAGE_KEY = 'dry-socks-theme';
  const THEMES = new Set(['light', 'dark']);
  const colors = {light: '#f6f7f2', dark: '#101713'};

  function normalize(theme) {
    return THEMES.has(theme) ? theme : null;
  }

  function getStoredTheme(storage = window.localStorage) {
    try { return normalize(storage?.getItem(STORAGE_KEY)); } catch (_) { return null; }
  }

  function getSystemTheme(mediaQuery = window.matchMedia?.('(prefers-color-scheme: dark)')) {
    return mediaQuery?.matches ? 'dark' : 'light';
  }

  function applyTheme(theme, {persist = false, button = null, root = document.documentElement, storage = window.localStorage} = {}) {
    const selected = normalize(theme) || 'light';
    root.dataset.theme = selected;
    root.style.colorScheme = selected;
    if (persist) {
      try { storage?.setItem(STORAGE_KEY, selected); } catch (_) { /* Storage can be disabled. */ }
    }
    if (button) {
      const nextLabel = selected === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
      button.setAttribute('aria-label', nextLabel);
      button.setAttribute('aria-pressed', String(selected === 'dark'));
      button.title = nextLabel;
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', colors[selected]);
    return selected;
  }

  function init({button = null, root = document.documentElement, storage = window.localStorage, mediaQuery} = {}) {
    return applyTheme(getStoredTheme(storage) || getSystemTheme(mediaQuery), {button, root, storage});
  }

  function toggle({button = null, root = document.documentElement, storage = window.localStorage} = {}) {
    const current = root.dataset.theme || 'light';
    return applyTheme(current === 'dark' ? 'light' : 'dark', {button, root, storage, persist: true});
  }

  window.DrySocksTheme = {applyTheme, getStoredTheme, getSystemTheme, init, toggle};
  init();
})();
