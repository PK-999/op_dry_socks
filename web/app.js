'use strict';

// Server credentials stay private. Only a dedicated, referrer-restricted Maps browser key is public.
const $ = id => document.getElementById(id);
const fields = ['origin', 'destination'];
const state = {
  origin: null, destination: null, travelMode: 'TWO_WHEELER', activeField: null,
  routes: [], selectedRoute: 0, weather: null, reports: null, config: null,
  routeVersion: 0, insightVersion: 0, routesLoading: false, weatherLoading: false,
  reportsLoading: false, userEdited: false, saving: false, savedFingerprint: null,
};
const requests = {};
const searches = Object.fromEntries(fields.map(field => [field, {version: 0, timer: null, features: [], active: -1}]));
let map = null;
let routeLayer = null;
let markerLayer = null;
let weatherLayer = null;
let toastTimer;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = String(text);
  return element;
}
function finite(value) { return typeof value === 'number' && Number.isFinite(value); }
function cleanLocation(value) {
  return value && finite(value.lat) && finite(value.lon)
    ? {name: String(value.name || `${value.lat.toFixed(4)}, ${value.lon.toFixed(4)}`), lat: value.lat, lon: value.lon}
    : null;
}
function shortName(value) { return String(value || '').split(',')[0]; }
function clockTime(value, options = {}) {
  const date = value ? new Date(value) : new Date();
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString('en-IN', {timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit', ...options});
}
function routeNow() { return state.routes[state.selectedRoute]; }
function fingerprint() {
  return JSON.stringify({origin: state.origin, destination: state.destination, travel_mode: state.travelMode, geometry: routeNow()?.geometry || null});
}
function stopRequest(name) {
  requests[name]?.abort();
  delete requests[name];
}
async function api(path, {body, signal, timeout = 70000} = {}) {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener('abort', cancel, {once: true});
  const timer = setTimeout(cancel, timeout);
  try {
    const response = await fetch(path, {
      method: body === undefined ? 'GET' : 'POST',
      ...(body === undefined ? {} : {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}),
      signal: controller.signal,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `The server returned ${response.status}. Please try again.`);
    return result;
  } catch (error) {
    if (error.name === 'AbortError' && !signal?.aborted) throw new Error('This check took too long. Please refresh to try again.');
    if (error instanceof SyntaxError) throw new Error('The local server returned an unreadable response. Please try again.');
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}
function message(error, fallback) {
  return error?.message === 'Failed to fetch' ? 'Could not reach the local server. Check that it is running and try again.' : error?.message || fallback;
}
function showToast(text, isError = false) {
  clearTimeout(toastTimer);
  $('toast').textContent = text;
  $('toast').className = `toast${isError ? ' error' : ''}`;
  $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 5500);
}
function setNotice(text = '') {
  $('app-notice').textContent = text;
  $('app-notice').hidden = !text;
}
function renderClock() {
  $('local-time').textContent = clockTime();
  $('local-date').textContent = new Date().toLocaleDateString('en-IN', {timeZone: 'Asia/Kolkata', weekday: 'short', day: 'numeric', month: 'short'});
}
function setHero({status, title, subtitle, body, tone = 'neutral', source = 'Route-based weather outlook'}) {
  $('outlook-status-text').textContent = status;
  $('advice-title').textContent = title;
  $('advice-subtitle').textContent = subtitle;
  $('advice-body').textContent = body;
  $('departure-card').dataset.tone = tone;
  $('forecast-source').textContent = source;
  $('departure-window').hidden = true;
}
function loadingContent(target, copy) {
  const row = node('div', 'loading-copy');
  const spinner = node('span', 'spinner');
  spinner.setAttribute('aria-hidden', 'true');
  row.append(spinner, node('span', '', copy));
  target.replaceChildren(row);
}
function emptyContent(target, title, body) {
  const wrapper = node('div', 'section-empty');
  const line = node('span', 'empty-line');
  line.setAttribute('aria-hidden', 'true');
  wrapper.append(line, node('h3', '', title), node('p', '', body));
  target.replaceChildren(wrapper);
}
function updateButtons() {
  const complete = !!(state.origin && state.destination);
  $('find-routes-btn').disabled = !complete || state.routesLoading;
  $('find-routes-btn').firstElementChild.textContent = state.routesLoading ? 'Finding routes…' : state.routes.length ? 'Update routes' : 'Find routes';
  $('save-btn').disabled = !complete || state.saving || state.routesLoading;
  $('save-btn').lastElementChild.textContent = state.saving ? 'Saving…' : 'Save commute';
  $('refresh-btn').disabled = !complete || state.routesLoading;
  $('refresh-btn').classList.toggle('loading', state.routesLoading || state.weatherLoading || state.reportsLoading);
  $('save-status').textContent = state.savedFingerprint && state.savedFingerprint === fingerprint() ? 'Saved for your next check.' : 'Keep this route for your next check.';
  fields.forEach(field => { document.querySelector(`[data-clear="${field}"]`).hidden = !$(field + '-input').value; });
}
function resetInsights() {
  ++state.insightVersion;
  stopRequest('weather');
  stopRequest('reports');
  state.weather = null;
  state.reports = null;
  state.weatherLoading = false;
  state.reportsLoading = false;
  weatherLayer?.clearLayers();
  setHero({status: 'Ready when you are', title: 'A better journey starts here.', subtitle: 'Find your route to see when rain could cross your commute.', body: 'We’ll check the forecast along the way, with public traffic reports for extra context.'});
  $('journey-value').replaceChildren(document.createTextNode('— '), node('span', '', 'min'));
  $('journey-note').textContent = 'Choose a route first';
  $('rain-value').textContent = '—';
  $('rain-value').classList.remove('compact');
  $('rain-note').textContent = 'Awaiting forecast';
  $('forecast-coverage').textContent = 'Forecast checkpoints';
  $('forecast-note').textContent = 'Model estimates, not street-level observations. Timing depends on the forecast provider’s resolution.';
  emptyContent($('forecast-content'), 'Every part of the journey matters.', 'Rain can arrive at different times along your route. Pick a commute to see the forecast at each checkpoint.');
  emptyContent($('reports-content'), 'Local context for your commute.', 'Traffic police and local public reports will appear here after you choose a route.');
  $('reports-status').textContent = 'Not checked';
  $('reports-status').className = 'source-status';
  $('source-coverage').replaceChildren();
  $('last-updated').textContent = 'Check a route to get started';
}
function invalidateRoute() {
  ++state.routeVersion;
  stopRequest('routes');
  state.routes = [];
  state.selectedRoute = 0;
  state.routesLoading = false;
  resetInsights();
  routeLayer?.clearLayers();
  $('route-count').textContent = '—';
  $('route-options-list').replaceChildren(node('p', 'empty-copy', 'Choose your start and destination to compare the way ahead.'));
  $('map-route-meta').textContent = 'Bengaluru, Karnataka';
  updateButtons();
}
function renderField(field) {
  $(field + '-input').value = state[field]?.name || '';
  $(field + '-input').title = state[field]?.name || '';
}
function setActiveField(field) {
  state.activeField = field;
  document.querySelectorAll('[data-pick]').forEach(button => {
    button.classList.toggle('active', button.dataset.pick === field);
    button.setAttribute('aria-pressed', String(button.dataset.pick === field));
  });
  $('map-instruction').hidden = !field || !map || !$('map-fallback').hidden;
  if (field) $('map-instruction').textContent = `Click the map to set your ${field === 'origin' ? 'starting point' : 'destination'}`;
  if (map) map.getDiv().style.cursor = field ? 'crosshair' : '';
}
function closeSearch(field) {
  const search = searches[field];
  clearTimeout(search.timer);
  stopRequest(`search-${field}`);
  stopRequest(`details-${field}`);
  ++search.version;
  search.features = [];
  search.active = -1;
  $(field + '-results').hidden = true;
  $(field + '-input').setAttribute('aria-expanded', 'false');
  $(field + '-input').removeAttribute('aria-activedescendant');
}
function setLocation(field, location, {fetchRoute = true} = {}) {
  const clean = cleanLocation(location);
  if (!clean) return;
  searches[field].session = null;
  state[field] = clean;
  renderField(field);
  closeSearch(field);
  invalidateRoute();
  drawMarkers();
  setActiveField(state.origin && state.destination ? null : state.origin ? 'destination' : 'origin');
  if (fetchRoute && state.origin && state.destination) fetchRoutes();
  else if (map && fetchRoute) { map.setCenter({lat: clean.lat, lng: clean.lon}); map.setZoom(14); }
}
function clearLocation(field) {
  state.userEdited = true;
  state[field] = null;
  searches[field].session = null;
  closeSearch(field);
  renderField(field);
  invalidateRoute();
  drawMarkers();
  setActiveField(field);
  $(field + '-input').focus();
}
function displaySearchMessage(field, text) {
  $(field + '-results').replaceChildren(node('p', 'search-message', text));
  $(field + '-results').hidden = false;
  $(field + '-input').setAttribute('aria-expanded', 'true');
}
async function searchPlaces(field, query, version) {
  if (version !== searches[field].version || query.trim().length < 2) return;
  const controller = new AbortController();
  requests[`search-${field}`] = controller;
  displaySearchMessage(field, 'Searching Google Maps…');
  const search = searches[field];
  if (!search.session || Date.now() - search.started > 180000) {
    search.session = crypto.randomUUID();
    search.started = Date.now();
  }
  const params = new URLSearchParams({q: query, session: search.session});
  const nearby = state[field === 'origin' ? 'destination' : 'origin'];
  const center = map?.getCenter();
  if (center || nearby) {
    params.set('lat', center ? center.lat() : nearby.lat);
    params.set('lon', center ? center.lng() : nearby.lon);
  }
  try {
    const data = await api(`/api/search?${params}`, {signal: controller.signal, timeout: 20000});
    if (version !== searches[field].version || $(field + '-input').value !== query) return;
    const features = (data.features || []).filter(feature => typeof feature.place_id === 'string');
    searches[field].features = features;
    if (!features.length) {
      displaySearchMessage(field, data.error || 'No places found. Try a nearby landmark, or pick on the map.');
      return;
    }
    $(field + '-results').replaceChildren(...features.map((feature, index) => {
      const button = node('button', 'search-result');
      button.type = 'button';
      button.id = `${field}-option-${index}`;
      button.tabIndex = -1;
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', 'false');
      button.append(node('strong', '', feature.text || feature.place_name), node('span', '', feature.place_name || 'India'));
      button.addEventListener('click', event => {
        // Resolving a place replaces this button; don't let the document's
        // outside-click handler cancel the now-detached selection request.
        event.stopPropagation();
        chooseFeature(field, feature);
      });
      return button;
    }));
    const attribution = node('div', 'google-attribution', 'Google Maps');
    attribution.setAttribute('translate', 'no');
    $(field + '-results').append(attribution);
  } catch (error) {
    if (error.name !== 'AbortError' && version === searches[field].version) displaySearchMessage(field, message(error, 'Search is unavailable. Try picking a location on the map.'));
  }
}
async function chooseFeature(field, feature) {
  state.userEdited = true;
  const session = searches[field].session;
  closeSearch(field);
  const version = searches[field].version;
  // A Details request terminates this billing session; never reuse it afterward.
  searches[field].session = null;
  const controller = new AbortController();
  requests[`details-${field}`] = controller;
  displaySearchMessage(field, 'Locating this place…');
  try {
    const params = new URLSearchParams({place_id: feature.place_id, session});
    const data = await api(`/api/place?${params}`, {signal: controller.signal, timeout: 15000});
    if (version !== searches[field].version) return;
    const center = data.feature?.center;
    if (!Array.isArray(center) || center.length !== 2 || !center.every(finite)) throw new Error('This place has no usable map location. Try another result.');
    setLocation(field, {name: feature.text || data.feature.place_name, lat: center[1], lon: center[0]});
  } catch (error) {
    if (error.name !== 'AbortError' && version === searches[field].version) displaySearchMessage(field, message(error, 'Could not locate this place. Please search again.'));
  }
}
async function reverseGeocode(field, lat, lon) {
  state.userEdited = true;
  // The point itself is useful even if reverse geocoding is unavailable.
  setLocation(field, {lat, lon, name: `${lat.toFixed(4)}, ${lon.toFixed(4)}`});
  stopRequest(`reverse-${field}`);
  const controller = new AbortController();
  requests[`reverse-${field}`] = controller;
  try {
    const data = await api(`/api/reverse?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`, {signal: controller.signal, timeout: 15000});
    if (state[field]?.lat !== lat || state[field]?.lon !== lon) return;
    if (data.features?.length) {
      state[field].name = String(data.features[0].text || data.features[0].place_name || state[field].name);
      renderField(field);
      drawMarkers();
      updateButtons();
    }
  } catch (_) { /* Keep the selected coordinates when a place name cannot be resolved. */ }
}
function closestRouteIndex(preferred) {
  const saved = preferred?.geometry?.coordinates;
  if (!Array.isArray(saved) || saved.length < 2) {
    return Math.max(0, state.routes.findIndex(route => route.summary === preferred?.summary));
  }
  // Match the saved path against fresh alternatives so the displayed ETA is current.
  const sample = coordinates => coordinates.filter((_, index) => index % Math.max(1, Math.ceil(coordinates.length / 24)) === 0);
  const distance = (point, start, end) => {
    const scale = Math.cos(13 * Math.PI / 180);
    const x = (point[0] - start[0]) * scale, y = point[1] - start[1];
    const dx = (end[0] - start[0]) * scale, dy = end[1] - start[1];
    const t = Math.max(0, Math.min(1, (x * dx + y * dy) / (dx * dx + dy * dy || 1)));
    return Math.hypot(x - t * dx, y - t * dy);
  };
  const directed = (left, right) => {
    const sampled = sample(left);
    return sampled.reduce((sum, point) => sum + Math.min(...right.slice(1).map((end, index) => distance(point, right[index], end))), 0) / sampled.length;
  };
  const scores = state.routes.map(route => {
    const coordinates = route.geometry?.coordinates;
    return Array.isArray(coordinates) && coordinates.length > 1 ? directed(saved, coordinates) + directed(coordinates, saved) : Infinity;
  });
  return Math.max(0, scores.indexOf(Math.min(...scores)));
}
async function fetchRoutes({preserveSelection = false, preferredRoute = null} = {}) {
  if (!state.origin || !state.destination) return;
  const preferred = preferredRoute || (preserveSelection ? routeNow() : null);
  invalidateRoute();
  const version = state.routeVersion;
  const controller = new AbortController();
  requests.routes = controller;
  state.routesLoading = true;
  setNotice();
  updateButtons();
  loadingContent($('route-options-list'), 'Finding your route options…');
  setHero({status: 'Finding your route', title: 'Let’s see the way ahead.', subtitle: 'Comparing routes for your commute.', body: 'Your rain outlook and public traffic reports will follow once a route is selected.', tone: 'loading'});
  try {
    const data = await api('/api/routes', {body: {origin: state.origin, destination: state.destination, travel_mode: state.travelMode}, signal: controller.signal, timeout: 45000});
    if (version !== state.routeVersion) return;
    state.routes = Array.isArray(data.routes) ? data.routes.filter(route => finite(Number(route.duration_mins)) && route.duration_mins > 0) : [];
    if (!state.routes.length) throw new Error(data.error || 'No routes found for these locations. Try a nearby road or landmark.');
    state.selectedRoute = preferred ? closestRouteIndex(preferred) : 0;
    renderRoutes();
    drawRoutes();
    fitMap();
    fetchInsights();
  } catch (error) {
    if (error.name === 'AbortError' || version !== state.routeVersion) return;
    const reason = message(error, 'Could not find a route. Try again.');
    $('route-options-list').replaceChildren(node('p', 'error-copy', reason));
    setHero({status: 'Route unavailable', title: 'We couldn’t find the way.', subtitle: 'Your commute outlook is not ready yet.', body: reason, tone: 'error'});
  } finally {
    if (version === state.routeVersion) { state.routesLoading = false; updateButtons(); }
  }
}
function renderRoutes() {
  $('route-count').textContent = state.routes.length;
  const fastest = Math.min(...state.routes.map(route => Number(route.duration_mins)));
  $('route-options-list').replaceChildren(...state.routes.map((route, index) => {
    const button = node('button', `route-option${index === state.selectedRoute ? ' selected' : ''}`);
    button.type = 'button';
    button.setAttribute('aria-pressed', String(index === state.selectedRoute));
    const indicator = node('span', 'route-radio');
    indicator.setAttribute('aria-hidden', 'true');
    const info = node('span', 'route-option-info');
    const name = node('span', 'route-option-name', route.summary || `Route ${index + 1}`);
    name.title = name.textContent;
    const distance = finite(Number(route.distance_km)) ? `${Number(route.distance_km).toFixed(1)} km` : 'Distance unavailable';
    const fastestLabel = state.routes.length > 1 && Number(route.duration_mins) === fastest ? ' · Quickest' : '';
    info.append(name, node('span', 'route-option-meta', distance + fastestLabel));
    const duration = node('span', 'route-duration', Math.round(Number(route.duration_mins)));
    duration.append(node('small', '', ' min'));
    button.append(indicator, info, duration);
    button.addEventListener('click', () => {
      if (state.selectedRoute === index) return;
      state.selectedRoute = index;
      state.userEdited = true;
      renderRoutes();
      drawRoutes();
      fetchInsights();
    });
    return button;
  }));
}
function renderJourney() {
  const route = routeNow();
  if (!route) return;
  $('journey-value').replaceChildren(document.createTextNode(`${Math.round(Number(route.duration_mins))} `), node('span', '', 'min'));
  const distance = finite(Number(route.distance_km)) ? `${Number(route.distance_km).toFixed(1)} km · ` : '';
  $('journey-note').textContent = `${distance}${route.traffic_aware ? 'Traffic-aware estimate' : 'No live traffic estimate'}`;
  $('map-route-meta').textContent = `${distance}${route.provider || 'Route estimate'}`;
}
async function fetchInsights() {
  const route = routeNow();
  if (!route) return;
  resetInsights();
  const version = state.insightVersion;
  state.weatherLoading = true;
  state.reportsLoading = true;
  renderJourney();
  updateButtons();
  setHero({status: 'Checking the forecast', title: 'A closer look at your commute.', subtitle: 'Checking rain at points along your selected route.', body: 'Forecast timing is an estimate. Public traffic reports are checked separately below.', tone: 'loading'});
  loadingContent($('forecast-content'), 'Checking the forecast along your route…');
  loadingContent($('reports-content'), 'Checking public sources. This can take up to a minute…');
  $('reports-status').textContent = 'Checking';
  $('last-updated').textContent = 'Updating your outlook…';
  const weatherController = new AbortController();
  const reportsController = new AbortController();
  requests.weather = weatherController;
  requests.reports = reportsController;
  // A slower public-source check must never hold up the weather outlook.
  await Promise.allSettled([
    api('/api/weather', {body: {waypoints: route.waypoints || [], duration_mins: Number(route.duration_mins), origin_name: state.origin.name, destination_name: state.destination.name}, signal: weatherController.signal}).then(data => {
      if (version !== state.insightVersion) return;
      state.weather = data;
      renderWeather(data);
    }).catch(error => {
      if (error.name === 'AbortError' || version !== state.insightVersion) return;
      setHero({status: 'Forecast unavailable', title: 'The forecast is out of reach.', subtitle: 'We can’t estimate a departure window right now.', body: message(error, 'Please refresh and check local conditions before leaving.'), tone: 'error'});
      $('rain-value').textContent = 'Unknown';
      $('rain-value').classList.add('compact');
      $('rain-note').textContent = 'Forecast unavailable';
      emptyContent($('forecast-content'), 'No forecast to show yet.', 'Refresh to try again. Missing weather data is not a clear-weather signal.');
      $('forecast-coverage').textContent = 'Unavailable';
    }).finally(() => {
      if (version !== state.insightVersion) return;
      state.weatherLoading = false;
      renderUpdated();
      updateButtons();
    }),
    api('/api/btp', {body: {waypoints: route.waypoints || [], geometry: route.geometry}, signal: reportsController.signal, timeout: 90000}).then(data => {
      if (version !== state.insightVersion) return;
      state.reports = data;
      renderReports(data);
    }).catch(error => {
      if (error.name === 'AbortError' || version !== state.insightVersion) return;
      $('reports-status').textContent = 'Unavailable';
      $('reports-status').className = 'source-status warn';
      emptyContent($('reports-content'), 'Public reports are unavailable.', message(error, 'No public-source coverage is available for this check.'));
    }).finally(() => {
      if (version !== state.insightVersion) return;
      state.reportsLoading = false;
      renderUpdated();
      updateButtons();
    }),
  ]);
}
function renderUpdated() {
  const time = state.weather?.updated_at || state.reports?.updated_at;
  $('last-updated').textContent = time ? `Checked ${clockTime(time)}${state.reportsLoading ? ' · X checking' : ''}` : state.weatherLoading || state.reportsLoading ? 'Updating your outlook…' : 'Check incomplete · try refresh';
}
function renderWeather(data) {
  const advice = data.advice || {};
  const status = advice.state || data.status || 'UNKNOWN';
  const unknown = ['UNKNOWN', 'UNAVAILABLE', 'ERROR'].includes(String(status).toUpperCase());
  const clear = String(status).toUpperCase() === 'CLEAR';
  const leaveIn = finite(advice.leave_in_mins) ? advice.leave_in_mins : null;
  setHero({
    status: unknown ? 'Forecast incomplete' : clear ? 'Forecast checked' : 'Keep an eye on the sky',
    title: advice.title || data.status_label || 'Your route forecast',
    subtitle: advice.subtitle || (unknown ? 'Your departure window is uncertain.' : 'Forecast estimates for the selected route.'),
    body: advice.body || data.summary || 'Check local conditions before leaving.',
    tone: unknown ? 'error' : clear ? 'neutral' : 'warn',
    source: `${data.source || 'Weather model'}${leaveIn !== null ? ` · ${leaveIn} min window` : ''}`,
  });
  if (leaveIn !== null && !unknown) {
    $('window-value').textContent = leaveIn === 0 ? 'Now' : Math.round(leaveIn);
    $('window-unit').textContent = leaveIn === 0 ? 'Consider leaving soon' : leaveIn === 1 ? 'minute' : 'minutes';
    $('departure-window').hidden = false;
  }
  const rain = data.corridor_mins_to_rain;
  const partial = finite(data.coverage?.available) && finite(data.coverage?.total) && data.coverage.available < data.coverage.total;
  $('rain-value').classList.toggle('compact', !finite(rain) || rain >= 999 || rain === 0);
  if (!finite(rain)) {
    $('rain-value').textContent = 'Unknown';
    $('rain-note').textContent = 'Forecast unavailable';
  } else if (rain >= 999) {
    $('rain-value').textContent = partial ? 'Incomplete' : 'No signal';
    $('rain-note').textContent = partial ? 'Some checkpoints unavailable' : 'Within the forecast window';
  } else if (rain === 0) {
    $('rain-value').textContent = 'Now';
    $('rain-note').textContent = `Rain forecast${partial ? ' · partial coverage' : ' along the route'}`;
  } else {
    $('rain-value').replaceChildren(document.createTextNode(`~${Math.round(rain)} `), node('span', '', 'min'));
    $('rain-note').textContent = `Earliest model signal${partial ? ' · partial coverage' : ''}`;
  }
  const points = Array.isArray(data.waypoints) ? data.waypoints : [];
  const count = data.coverage?.available ?? points.filter(point => point.available !== false && finite(point.mins_to_rain)).length;
  $('forecast-coverage').textContent = `${count}/${data.coverage?.total ?? points.length} points checked`;
  $('forecast-note').textContent = `Amounts cover the 15-minute interval ending at each time. ${data.resolution_note || 'Model estimates, not street-level observations. Forecast rain timing and arrival times are approximate.'}`;
  renderForecast(points);
  drawWeather(points);
}
function forecastSample(point, timestamp) {
  return (point.forecast || []).find(sample => sample.time === timestamp);
}
function renderForecast(points) {
  const availableTimes = [...new Set(points.flatMap(point => (point.forecast || []).map(sample => sample.time)).filter(time => !Number.isNaN(new Date(time).getTime())))].sort((a, b) => new Date(a) - new Date(b));
  // Show actual provider timestamps, never invent an intermediate forecast.
  const upcoming = availableTimes.filter(time => new Date(time).getTime() >= Date.now() - 15 * 60000);
  const times = (upcoming.length ? upcoming : availableTimes).slice(0, 4);
  if (!points.length) {
    emptyContent($('forecast-content'), 'No checkpoints available.', 'The server could not return route weather. Refresh to try again.');
    return;
  }
  const table = node('table', 'forecast-table');
  const caption = node('caption', 'sr-only', 'Forecast precipitation by route checkpoint and time, in millimetres');
  caption.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)';
  table.append(caption);
  const head = node('thead');
  const header = node('tr');
  const first = node('th', '', 'CHECKPOINT');
  first.scope = 'col';
  header.append(first);
  if (times.length) times.forEach(time => { const cell = node('th', '', clockTime(time)); cell.scope = 'col'; header.append(cell); });
  else { const cell = node('th', '', 'FIRST RAIN SIGNAL'); cell.scope = 'col'; header.append(cell); }
  head.append(header);
  const body = node('tbody');
  points.forEach((point, index) => {
    const row = node('tr');
    const label = node('td');
    const fallback = index === 0 ? shortName(state.origin?.name) : index === points.length - 1 ? shortName(state.destination?.name) : `Checkpoint ${index + 1}`;
    const name = node('span', 'checkpoint-name', point.name || fallback);
    name.title = name.textContent;
    label.append(name, node('span', 'checkpoint-eta', finite(point.eta_mins) ? `${index === 0 ? 'Departure' : `~${Math.round(point.eta_mins)} min into trip`}` : `Point ${index + 1}`));
    row.append(label);
    if (times.length) times.forEach(time => {
      const sample = forecastSample(point, time);
      const value = sample?.precipitation_mm;
      const valid = finite(value) && point.available !== false;
      const cell = node('td');
      const content = node('span', `forecast-cell${!valid ? ' unknown' : value >= 2 ? ' heavy' : value > 0 ? ' wet' : ''}`);
      const bar = node('i', 'rain-bar');
      bar.setAttribute('aria-hidden', 'true');
      content.append(bar, document.createTextNode(valid ? `${value.toFixed(1)} mm` : '—'));
      if (!valid) content.setAttribute('aria-label', 'Forecast unavailable');
      cell.append(content);
      row.append(cell);
    });
    else {
      const rain = point.mins_to_rain;
      const text = point.available === false || !finite(rain) ? 'Unavailable' : rain >= 999 ? 'No signal in forecast' : rain === 0 ? 'Forecast now' : `In ~${Math.round(rain)} min`;
      row.append(node('td', 'forecast-cell', text));
    }
    body.append(row);
  });
  table.append(head, body);
  const scroller = node('div', 'forecast-scroller');
  scroller.append(table);
  $('forecast-content').replaceChildren(scroller);
  const susceptible = points.filter(point => point.waterlogged);
  if (susceptible.length) $('forecast-content').append(node('p', 'rain-proxy', 'Heavy recent rain suggests waterlogging susceptibility at some checkpoints. This is a forecast proxy, not a confirmed flood report.'));
}
function safeURL(value) {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch (_) { return null; }
}
function renderReports(data) {
  const status = data.status || 'unavailable';
  const sources = Array.isArray(data.sources) ? data.sources : [];
  const notConfigured = sources.length > 0 && sources.every(source => source.status === 'not_configured');
  const labels = {outside_coverage: 'Outside Bengaluru coverage', ok: 'Sources checked', partial: 'Partial coverage', unavailable: 'Unavailable', disabled: 'Not connected'};
  $('reports-status').textContent = notConfigured ? 'Not connected' : labels[status] || 'Unavailable';
  $('reports-status').className = `source-status ${status === 'ok' ? 'available' : 'warn'}`;
  const alerts = Array.isArray(data.alerts) ? data.alerts : [];
  if (!alerts.length) {
    const title = status === 'outside_coverage' ? 'Local reports cover Bengaluru only.' : status === 'ok' ? 'No matching reports returned.' : notConfigured || status === 'disabled' ? 'X reports are not connected.' : status === 'partial' ? 'Only some sources could be checked.' : 'Public reports are unavailable.';
    const detail = status === 'outside_coverage' ? 'This route is outside the Bengaluru source area, so those X accounts were not fetched. Route and weather checks still work.' : status === 'ok' ? 'No matching public reports were found in this check. This does not confirm clear roads.' : status === 'disabled' ? 'Public X checks are disabled in your local configuration.' : notConfigured ? 'Connect an existing X session or an X API credential in the local configuration to check public reports.' : status === 'partial' ? 'No matching reports were returned from available sources. Other sources could not be checked.' : 'No reliable public-source check is available right now. Review the source status below or refresh to try again.';
    emptyContent($('reports-content'), title, detail);
  } else {
    const wrapper = node('div', 'reports-scroll');
    alerts.forEach(alert => {
      const article = node('article', 'report');
      const top = node('div', 'report-top');
      top.append(node('strong', '', alert.handle ? `@${String(alert.handle).replace(/^@/, '')}` : 'Public report'));
      if (alert.scope || alert.area) top.append(node('span', 'report-scope', alert.area || alert.scope));
      if (alert.created_at && clockTime(alert.created_at)) {
        const time = node('time', '', new Date(alert.created_at).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit'}));
        time.dateTime = alert.created_at;
        top.append(time);
      }
      article.append(top, node('p', '', alert.text || 'Report text unavailable.'));
      const url = safeURL(alert.url);
      if (url) { const link = node('a', 'report-link', 'View original report ↗'); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; article.append(link); }
      wrapper.append(article);
    });
    $('reports-content').replaceChildren(wrapper);
  }
  $('source-coverage').replaceChildren();
  if (sources.length) {
    const details = node('details', 'coverage-details');
    const checked = sources.filter(source => ['ok', 'cached'].includes(source.status)).length;
    details.append(node('summary', '', `Source coverage · ${checked} of ${sources.length} checked`));
    sources.forEach(source => {
      const row = node('div', 'source-row');
      const content = node('div');
      content.append(node('strong', '', source.name || (source.handle ? `@${String(source.handle).replace(/^@/, '')}` : 'Public source')));
      content.append(node('p', '', [source.area || source.scope, source.message].filter(Boolean).join(' · ')));
      row.append(content, node('span', ['ok', 'cached'].includes(source.status) ? '' : 'unavailable', source.status || 'unknown'));
      details.append(row);
    });
    $('source-coverage').append(details);
  }
}
async function saveCommute() {
  if (!state.origin || !state.destination || state.saving) return;
  state.saving = true;
  const savedFingerprint = fingerprint();
  updateButtons();
  try {
    await api('/api/config', {body: {origin: state.origin, destination: state.destination, travel_mode: state.travelMode, ...(routeNow() ? {selected_route: routeNow()} : {})}, timeout: 15000});
    state.savedFingerprint = savedFingerprint;
    showToast('Commute saved. Background alerts run separately from this dashboard.');
  } catch (error) { showToast(message(error, 'Could not save your commute.'), true); }
  finally { state.saving = false; updateButtons(); }
}

// Google Places results are displayed on Google Maps. Search remains usable if
// the optional browser key, network or map script is unavailable.
function mapUnavailable(copy = 'The Google map could not load. You can still search locations and check your commute.') {
  $('map-fallback-title').textContent = 'Map unavailable';
  $('map-fallback-copy').textContent = copy;
  $('map-fallback').hidden = false;
  setActiveField(null);
  $('map').setAttribute('aria-label', 'Map unavailable. Use location search to plan your commute.');
  document.querySelectorAll('[data-pick]').forEach(button => { button.disabled = true; });
  $('fit-map-btn').disabled = true;
}
function overlayGroup() {
  const overlays = [];
  return {
    add(overlay) { overlays.push(overlay); return overlay; },
    clearLayers() { overlays.splice(0).forEach(overlay => { if (typeof overlay.setMap === 'function') overlay.setMap(null); else overlay.map = null; }); },
  };
}
let googleMapRequested = false;
let googleMapTimer;
function loadGoogleMap(key) {
  if (googleMapRequested) return;
  if (!key) {
    mapUnavailable('Add a Google Maps browser key in your local configuration to show the map. Place search, routes and forecasts still work.');
    return;
  }
  googleMapRequested = true;
  window.gm_authFailure = () => { clearTimeout(googleMapTimer); mapUnavailable('Google could not authorize the map. Check the browser key’s Maps JavaScript API and localhost restrictions. Search still works.'); };
  window.initializeDrySocksMap = initializeMap;
  const script = document.createElement('script');
  const params = new URLSearchParams({key, callback: 'initializeDrySocksMap', loading: 'async', libraries: 'marker', v: 'quarterly'});
  script.src = `https://maps.googleapis.com/maps/api/js?${params}`;
  script.async = true;
  script.onerror = () => { clearTimeout(googleMapTimer); mapUnavailable(); };
  googleMapTimer = setTimeout(() => { if (!map) mapUnavailable(); }, 15000);
  document.head.append(script);
}
function initializeMap() {
  if (map || !window.google?.maps) return;
  clearTimeout(googleMapTimer);
  try {
    map = new google.maps.Map($('map'), {center: {lat: 12.9716, lng: 77.6246}, zoom: 12,
      mapId: 'DEMO_MAP_ID', disableDefaultUI: true, zoomControl: true, gestureHandling: 'cooperative', clickableIcons: false});
    routeLayer = overlayGroup();
    weatherLayer = overlayGroup();
    markerLayer = overlayGroup();
    map.addListener('click', event => { if (state.activeField && event.latLng) reverseGeocode(state.activeField, event.latLng.lat(), event.latLng.lng()); });
    $('map-fallback').hidden = true;
    $('map').setAttribute('aria-label', 'Interactive Google commute map');
    document.querySelectorAll('[data-pick]').forEach(button => { button.disabled = false; });
    $('fit-map-btn').disabled = false;
    drawMarkers();
    drawRoutes();
    if (state.weather) drawWeather(state.weather.waypoints || []);
    setActiveField(state.activeField);
    fitMap();
  } catch (_) { mapUnavailable(); }
}
function drawMarkers() {
  if (!map || !markerLayer) return;
  markerLayer.clearLayers();
  fields.forEach(field => {
    const location = state[field];
    if (!location) return;
    const content = node('span', `route-marker ${field}`, field === 'origin' ? 'A' : 'B');
    const marker = markerLayer.add(new google.maps.marker.AdvancedMarkerElement({map,
      position: {lat: location.lat, lng: location.lon}, content, gmpDraggable: true, title: location.name, zIndex: 10}));
    marker.addListener('dragend', event => { if (event.latLng) reverseGeocode(field, event.latLng.lat(), event.latLng.lng()); });
  });
}
function drawRoutes() {
  if (!routeLayer) return;
  routeLayer.clearLayers();
  state.routes.forEach((route, index) => {
    if (!Array.isArray(route.geometry?.coordinates)) return;
    const selected = index === state.selectedRoute;
    const path = route.geometry.coordinates.filter(pair => Array.isArray(pair) && pair.length >= 2 && pair.slice(0, 2).every(finite)).map(pair => ({lat: pair[1], lng: pair[0]}));
    if (path.length < 2) return;
    if (selected) routeLayer.add(new google.maps.Polyline({map, path, strokeColor: '#fff', strokeWeight: 8, strokeOpacity: .85, clickable: false, zIndex: 2}));
    const line = routeLayer.add(new google.maps.Polyline({map, path, strokeColor: selected ? '#527544' : '#b5bdad', strokeWeight: selected ? 5 : 4, strokeOpacity: selected ? 1 : .75, zIndex: selected ? 3 : 1}));
    line.addListener('click', () => {
      if (index === state.selectedRoute) return;
      state.selectedRoute = index;
      state.userEdited = true;
      renderRoutes();
      drawRoutes();
      fetchInsights();
    });
  });
  renderJourney();
}
function drawWeather(points) {
  if (!weatherLayer) return;
  weatherLayer.clearLayers();
  points.forEach(point => {
    if (!finite(point.lat) || !finite(point.lon)) return;
    const unknown = point.available === false || !finite(point.mins_to_rain);
    const wet = !unknown && point.mins_to_rain < 999;
    const label = unknown ? 'Forecast unavailable' : wet ? `Model rain signal: ${point.mins_to_rain === 0 ? 'now' : `~${Math.round(point.mins_to_rain)} min`}` : 'No rain signal in forecast';
    const content = node('span', 'weather-map-dot');
    content.style.background = unknown ? '#abb0a4' : wet ? '#c29755' : '#72905b';
    weatherLayer.add(new google.maps.marker.AdvancedMarkerElement({map, position: {lat: point.lat, lng: point.lon},
      content, title: `${point.name || 'Route checkpoint'} · ${label}`, zIndex: 5}));
  });
}
function fitMap() {
  if (!map) return;
  const coordinates = routeNow()?.geometry?.coordinates;
  const points = Array.isArray(coordinates) && coordinates.length > 1
    ? coordinates.filter(pair => Array.isArray(pair) && pair.length >= 2 && pair.slice(0, 2).every(finite)).map(pair => ({lat: pair[1], lng: pair[0]}))
    : fields.map(field => state[field]).filter(Boolean).map(point => ({lat: point.lat, lng: point.lon}));
  if (points.length === 1) { map.setCenter(points[0]); map.setZoom(14); }
  else if (points.length > 1) {
    const bounds = new google.maps.LatLngBounds();
    points.forEach(point => bounds.extend(point));
    map.fitBounds(bounds, 40);
    google.maps.event.addListenerOnce(map, 'idle', () => { if (map.getZoom() > 15) map.setZoom(15); });
  }
}
async function loadConfig() {
  try {
    const config = await api('/api/config', {timeout: 15000});
    state.config = config;
    loadGoogleMap(config.google_maps_browser_key);
    if (state.userEdited) return;
    if (['DRIVE', 'TWO_WHEELER'].includes(config.route?.travel_mode)) state.travelMode = config.route.travel_mode;
    fields.forEach(field => { state[field] = cleanLocation(config.locations?.[field]); renderField(field); });
    renderMode();
    drawMarkers();
    updateButtons();
    fitMap();
    if (state.origin && state.destination) fetchRoutes({preferredRoute: config.route?.selected_route});
  } catch (error) {
    setNotice(message(error, 'Could not load your saved commute. Check that the local server is running.'));
  }
}
function renderMode() {
  document.querySelectorAll('[data-mode]').forEach(button => {
    const active = button.dataset.mode === state.travelMode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
}
function initializeTheme() {
  const button = $('theme-toggle');
  if (!button || !window.DrySocksTheme) return;
  window.DrySocksTheme.init({button});
  button.addEventListener('click', () => window.DrySocksTheme.toggle({button}));
}
fields.forEach(field => {
  const input = $(field + '-input');
  input.addEventListener('focus', () => {
    fields.filter(other => other !== field).forEach(closeSearch);
    setActiveField(field);
  });
  input.addEventListener('input', () => {
    state.userEdited = true;
    state[field] = null;
    closeSearch(field);
    invalidateRoute();
    drawMarkers();
    setActiveField(field);
    if (input.value.trim().length < 2) return;
    const version = searches[field].version;
    searches[field].timer = setTimeout(() => searchPlaces(field, input.value, version), 300);
  });
  input.addEventListener('keydown', event => {
    const search = searches[field];
    if (event.key === 'Escape') { closeSearch(field); setActiveField(null); return; }
    if (!search.features.length) return;
    if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
      event.preventDefault();
      search.active = (search.active + (event.key === 'ArrowDown' ? 1 : -1) + search.features.length) % search.features.length;
      $(field + '-results').querySelectorAll('.search-result').forEach((button, index) => {
        button.classList.toggle('active', index === search.active);
        button.setAttribute('aria-selected', String(index === search.active));
      });
      input.setAttribute('aria-activedescendant', `${field}-option-${search.active}`);
      $(`${field}-option-${search.active}`).scrollIntoView({block: 'nearest'});
    } else if (event.key === 'Enter') {
      event.preventDefault();
      chooseFeature(field, search.features[search.active < 0 ? 0 : search.active]);
    }
  });
});
document.querySelectorAll('[data-clear]').forEach(button => button.addEventListener('click', () => clearLocation(button.dataset.clear)));
document.querySelectorAll('[data-pick]').forEach(button => button.addEventListener('click', () => {
  fields.forEach(closeSearch);
  setActiveField(state.activeField === button.dataset.pick ? null : button.dataset.pick);
  if (state.activeField && window.innerWidth < 1150) $('map').scrollIntoView({behavior: 'smooth', block: 'center'});
}));
document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => {
  if (button.dataset.mode === state.travelMode) return;
  state.travelMode = button.dataset.mode;
  state.userEdited = true;
  renderMode();
  invalidateRoute();
  if (state.origin && state.destination) fetchRoutes();
}));
$('swap-btn').addEventListener('click', () => {
  state.userEdited = true;
  [state.origin, state.destination] = [state.destination, state.origin];
  fields.forEach(field => { closeSearch(field); renderField(field); });
  invalidateRoute();
  drawMarkers();
  setActiveField(null);
  if (state.origin && state.destination) fetchRoutes();
});
$('find-routes-btn').addEventListener('click', () => fetchRoutes());
$('refresh-btn').addEventListener('click', () => fetchRoutes({preserveSelection: true}));
$('save-btn').addEventListener('click', saveCommute);
$('fit-map-btn').addEventListener('click', fitMap);
document.addEventListener('click', event => {
  if (!event.target.closest('.location-group')) fields.forEach(closeSearch);
});

initializeTheme();
renderClock();
setInterval(renderClock, 30000);
loadConfig();
