const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function load({reducedMotion = false} = {}) {
  let scheduled = 0;
  const context = {
    document: {readyState: 'loading', addEventListener() {}, getElementById() { return null; }},
    window: {matchMedia: () => ({matches: reducedMotion, addEventListener() {}})},
    requestAnimationFrame: () => ++scheduled, cancelAnimationFrame() {}, Date, Intl,
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('web/ambient.js', 'utf8'), context);
  return {api: vm.runInContext('Ambient', context), scheduled: () => scheduled};
}

test('ambient scenery uses Bengaluru time regardless of the host clock', () => {
  const {api} = load();
  assert.equal(api.periodAt(new Date('2026-10-12T02:00:00Z')), 'dawn');
  assert.equal(api.periodAt(new Date('2026-10-12T14:30:00Z')), 'night');
});

test('reduced motion disables canvas rain animation', () => {
  const {api, scheduled} = load({reducedMotion: true});
  api.setWeather('rain');
  assert.equal(scheduled(), 0);
});

test('leaving scenery preview restores the latest forecast', () => {
  const {api} = load();
  api.fromWeatherData({waypoints: [{mins_to_rain: 60}]});
  for (let i = 0; i < 5; i++) api.cycle();
  assert.equal(api.getWeather(), 'rain');
});
