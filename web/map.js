/* Map lifecycle and overlays. Live Google content stays on Google Maps.
 * The offline demo uses local Leaflet with no external tiles. */
(() => {
  'use strict';

  function create({getState, onPick, onSelect, onReady}) {
    const element = document.getElementById('map');
    const $ = id => document.getElementById(id);
    let native = null;
    let provider = null;
    let requested = false;
    let failed = false;
    let timer;
    const layers = {routes: [], markers: [], weather: []};

    function clear(group) {
      layers[group].splice(0).forEach(layer => {
        if (provider === 'demo') native.removeLayer(layer);
        else if (typeof layer.setMap === 'function') layer.setMap(null);
        else layer.map = null;
      });
    }

    function unavailable(copy) {
      clearTimeout(timer);
      failed = true;
      Object.keys(layers).forEach(clear);
      native = null;
      provider = null;
      element.replaceChildren();
      element.dataset.provider = 'unavailable';
      element.setAttribute('aria-label', 'Map unavailable. Use location search to plan your commute.');
      $('map-fallback-title').textContent = 'Map unavailable';
      $('map-fallback-copy').textContent = copy || 'The map could not load. You can still search locations and check your commute.';
      $('map-fallback').hidden = false;
      $('map-instruction').hidden = true;
      document.querySelectorAll('[data-pick]').forEach(button => { button.disabled = true; });
      $('fit-map-btn').disabled = true;
    }

    function ready(kind) {
      provider = kind;
      element.dataset.provider = kind;
      element.setAttribute('aria-label', kind === 'demo' ? 'Synthetic demo commute map, without road tiles' : 'Interactive Google commute map');
      $('map-fallback').hidden = true;
      document.querySelectorAll('[data-pick]').forEach(button => { button.disabled = false; });
      $('fit-map-btn').disabled = false;
      drawMarkers();
      drawRoutes();
      drawWeather(getState().weather?.waypoints || []);
      fit();
      onReady();
    }

    function initializeGoogle() {
      if (failed || native || !window.google?.maps) return;
      clearTimeout(timer);
      try {
        native = new google.maps.Map(element, {
          center: {lat: 12.9716, lng: 77.6246}, zoom: 12, mapId: 'DEMO_MAP_ID',
          disableDefaultUI: true, zoomControl: true, gestureHandling: 'cooperative', clickableIcons: false,
        });
        native.addListener('click', event => {
          const field = getState().activeField;
          if (field && event.latLng) onPick(field, event.latLng.lat(), event.latLng.lng());
        });
        ready('google');
      } catch (_) {
        unavailable();
      }
    }

    function initializeDemo() {
      if (!window.L) { unavailable('The bundled demo map could not load. Route and forecast checks still work.'); return; }
      try {
        native = L.map(element, {center: [12.9716, 77.6246], zoom: 12, zoomControl: false, attributionControl: false});
        L.control.zoom({position: 'bottomright'}).addTo(native);
        L.control.attribution({prefix: 'Leaflet · synthetic corridors, no road map'}).addTo(native);
        native.on('click', event => {
          const field = getState().activeField;
          if (field) onPick(field, event.latlng.lat, event.latlng.lng);
        });
        ready('demo');
      } catch (_) { unavailable(); }
    }

    function load(key, {demo = false} = {}) {
      if (requested) return;
      requested = true;
      if (demo) { initializeDemo(); return; }
      if (!key) { unavailable('Add a dedicated Google Maps browser key to enable the map. Location search and forecasts still work.'); return; }
      window.gm_authFailure = () => unavailable('Google Maps could not authorize your browser key. Check its API and website restrictions.');
      window.initializeDrySocksMap = initializeGoogle;
      const script = document.createElement('script');
      const params = new URLSearchParams({key, callback: 'initializeDrySocksMap', loading: 'async', libraries: 'marker', v: 'quarterly'});
      script.src = `https://maps.googleapis.com/maps/api/js?${params}`;
      script.async = true;
      script.onerror = () => unavailable();
      timer = setTimeout(() => unavailable('Google Maps took too long to load. Reload to retry; search and forecasts still work.'), 10000);
      document.head.append(script);
    }

    function span(className, text) {
      const content = document.createElement('span');
      content.className = className;
      if (text) content.textContent = text;
      return content;
    }

    function drawMarkers() {
      if (!native) return;
      clear('markers');
      const state = getState();
      ['origin', 'destination'].forEach(field => {
        const point = state[field];
        if (!point) return;
        const content = span(`route-marker ${field}`, field === 'origin' ? 'A' : 'B');
        let marker;
        if (provider === 'google') {
          marker = new google.maps.marker.AdvancedMarkerElement({map: native,
            position: {lat: point.lat, lng: point.lon}, content, gmpDraggable: true, title: point.name, zIndex: 10});
          marker.addListener('dragend', event => {
            if (event.latLng) onPick(field, event.latLng.lat(), event.latLng.lng());
          });
        } else {
          const icon = L.divIcon({className: 'custom-route-marker', html: content, iconSize: [28, 28], iconAnchor: [14, 14]});
          marker = L.marker([point.lat, point.lon], {icon, draggable: true, title: point.name}).addTo(native);
          marker.on('dragend', event => {
            const position = event.target.getLatLng();
            onPick(field, position.lat, position.lng);
          });
        }
        layers.markers.push(marker);
      });
    }

    function coordinates(route) {
      return (route?.geometry?.coordinates || []).filter(pair => Array.isArray(pair) && pair.length >= 2 && pair.slice(0, 2).every(Number.isFinite));
    }

    function drawRoutes() {
      if (!native) return;
      clear('routes');
      const state = getState();
      state.routes.forEach((route, index) => {
        const coords = coordinates(route);
        if (coords.length < 2) return;
        const selected = index === state.selectedRoute;
        let line;
        if (provider === 'google') {
          const path = coords.map(pair => ({lat: pair[1], lng: pair[0]}));
          if (selected) layers.routes.push(new google.maps.Polyline({map: native, path, strokeColor: '#fff', strokeWeight: 8, strokeOpacity: .85, clickable: false, zIndex: 2}));
          line = new google.maps.Polyline({map: native, path, strokeColor: selected ? '#c5a04e' : '#6b7280', strokeWeight: selected ? 5 : 4, zIndex: selected ? 3 : 1});
          line.addListener('click', () => onSelect(index));
        } else {
          const path = coords.map(pair => [pair[1], pair[0]]);
          if (selected) layers.routes.push(L.polyline(path, {color: '#fff', weight: 8, opacity: .85, interactive: false}).addTo(native));
          line = L.polyline(path, {color: selected ? '#c5a04e' : '#6b7280', weight: selected ? 5 : 4}).addTo(native);
          line.on('click', () => onSelect(index));
        }
        layers.routes.push(line);
      });
    }

    function drawWeather(points) {
      if (!native) return;
      clear('weather');
      points.forEach(point => {
        if (!Number.isFinite(point.lat) || !Number.isFinite(point.lon)) return;
        const unknown = point.available === false || !Number.isFinite(point.mins_to_rain);
        const wet = !unknown && point.mins_to_rain < 999;
        const label = unknown ? 'Forecast unavailable' : wet ? `Model rain signal: ~${Math.round(point.mins_to_rain)} min` : 'No rain signal in forecast';
        const content = span('weather-map-dot');
        content.style.background = unknown ? '#abb0a4' : wet ? '#c29755' : '#72905b';
        const title = `${point.name || 'Route checkpoint'} · ${label}`;
        const marker = provider === 'google'
          ? new google.maps.marker.AdvancedMarkerElement({map: native, position: {lat: point.lat, lng: point.lon}, content, title, zIndex: 5})
          : L.marker([point.lat, point.lon], {icon: L.divIcon({className: 'custom-weather-dot', html: content, iconSize: [12, 12], iconAnchor: [6, 6]}), title}).addTo(native);
        layers.weather.push(marker);
      });
    }

    function fit() {
      if (!native) return;
      const state = getState();
      const coords = coordinates(state.routes[state.selectedRoute]);
      const points = coords.length > 1 ? coords.map(pair => ({lat: pair[1], lng: pair[0]}))
        : [state.origin, state.destination].filter(Boolean).map(point => ({lat: point.lat, lng: point.lon}));
      if (points.length === 1) focusLocation({lat: points[0].lat, lon: points[0].lng});
      else if (points.length > 1 && provider === 'google') {
        const bounds = new google.maps.LatLngBounds();
        points.forEach(point => bounds.extend(point));
        native.fitBounds(bounds, 40);
        const fittedMap = native;
        google.maps.event.addListenerOnce(fittedMap, 'idle', () => {
          if (native === fittedMap && fittedMap.getZoom() > 15) fittedMap.setZoom(15);
        });
      } else if (points.length > 1) native.fitBounds(points.map(point => [point.lat, point.lng]), {padding: [40, 40], maxZoom: 15});
    }

    function focusLocation(point) {
      if (provider === 'google') { native.setCenter({lat: point.lat, lng: point.lon}); native.setZoom(14); }
      else if (native) native.setView([point.lat, point.lon], 14);
    }

    function center() {
      if (!native) return null;
      const point = native.getCenter();
      return provider === 'google' ? {lat: point.lat(), lon: point.lng()} : {lat: point.lat, lon: point.lng};
    }

    return {
      load, drawMarkers, drawRoutes, drawWeather, fit, center, focusLocation,
      available: () => native !== null,
      clearRoutes: () => clear('routes'), clearWeather: () => clear('weather'),
      setPicking: field => { element.style.cursor = field && native ? 'crosshair' : ''; },
    };
  }

  window.DrySocksMap = {create};
})();
