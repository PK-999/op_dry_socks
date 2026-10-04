const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const themePath = path.join(__dirname, '..', 'web', 'theme.js');
const indexPath = path.join(__dirname, '..', 'web', 'index.html');

function loadTheme({stored = null, systemDark = false} = {}) {
  assert.ok(fs.existsSync(themePath), 'web/theme.js must exist');

  const values = new Map(stored === null ? [] : [['dry-socks-theme', stored]]);
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  const root = {dataset: {}, style: {}};
  const context = {
    window: {
      localStorage: storage,
      matchMedia: () => ({matches: systemDark}),
    },
    document: {
      documentElement: root,
      querySelector: () => null,
    },
  };
  vm.runInNewContext(fs.readFileSync(themePath, 'utf8'), context, {filename: themePath});
  return {api: context.window.DrySocksTheme, root, storage};
}

test('saved preference wins over the system theme and is applied to the document', () => {
  const {api, root} = loadTheme({stored: 'dark', systemDark: false});

  assert.equal(api.init(), 'dark');
  assert.equal(root.dataset.theme, 'dark');
  assert.equal(root.style.colorScheme, 'dark');
});

test('unset preference follows the system theme', () => {
  const {api, root} = loadTheme({systemDark: true});

  assert.equal(api.init(), 'dark');
  assert.equal(root.dataset.theme, 'dark');
});

test('toggle persists the new theme', () => {
  const {api, root, storage} = loadTheme({stored: 'light'});

  api.init();
  assert.equal(api.toggle(), 'dark');
  assert.equal(root.dataset.theme, 'dark');
  assert.equal(storage.getItem('dry-socks-theme'), 'dark');
});

test('dashboard exposes an accessible theme toggle', () => {
  const html = fs.readFileSync(indexPath, 'utf8');

  assert.match(html, /id="theme-toggle"/);
  assert.match(html, /src="theme\.js"/);
});
