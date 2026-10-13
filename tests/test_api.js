const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function load(fetch) {
  const context = {window: {}, fetch, AbortController, setTimeout, clearTimeout, Error, SyntaxError};
  vm.runInNewContext(fs.readFileSync('web/api.js', 'utf8'), context);
  return context.window.DrySocksAPI.request;
}

test('HTTP errors retain actionable server messages', async () => {
  const request = load(async () => new Response(JSON.stringify({error: 'Places quota reached.'}), {status: 503}));
  await assert.rejects(request('/api/search'), /Places quota reached/);
});

test('invalid JSON is reported as an unreadable local response', async () => {
  const request = load(async () => new Response('not json'));
  await assert.rejects(request('/api/config'), /unreadable response/);
});

test('a timeout is actionable while user cancellation remains AbortError', async () => {
  const request = load((_url, options) => new Promise((_resolve, reject) => {
    const abort = () => reject(new DOMException('Aborted', 'AbortError'));
    if (options.signal.aborted) abort();
    else options.signal.addEventListener('abort', abort, {once: true});
  }));
  await assert.rejects(request('/api/weather', {timeout: 1}), /took too long/);
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(request('/api/weather', {signal: controller.signal}), {name: 'AbortError'});
});
