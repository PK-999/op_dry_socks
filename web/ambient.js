/**
 * Decorative scenery using Bengaluru time and the selected route's forecast.
 * Preview scenes are independent of the forecast and respect reduced motion.
 */
'use strict';

const Ambient = (() => {
  const ASSETS = {
    night: 'assets/bg_night.jpg',
    dusk: 'assets/bg_dusk.jpg',
    day: 'assets/bg_day.jpg',
    rain: 'assets/bg_rain.jpg',
  };

  const MODES = [null, 'rain', 'dusk', 'day', 'night'];
  let manualMode = null; // null (auto) | 'rain' | 'dusk' | 'day' | 'night'
  let activeLayer = 'a';
  let currentImage = '';
  let currentPeriod = '';
  let currentWeather = 'clear'; // 'clear' | 'rain' | 'heavy'
  let forecastWeather = 'clear';
  const motionQuery = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  let layerA = null;
  let layerB = null;
  let particleCanvas = null;
  let particleCtx = null;
  let particles = [];
  let animFrame = null;

  function getTimePeriod(hour) {
    if (hour >= 20 || hour < 5) return 'night';
    if (hour >= 5 && hour < 8) return 'dawn';
    if (hour >= 8 && hour < 17) return 'day';
    return 'dusk'; // 17:00 - 20:00
  }

  function periodAt(date = new Date()) {
    const hour = Number(new Intl.DateTimeFormat('en-GB', {timeZone: 'Asia/Kolkata', hour: 'numeric'}).format(date));
    return getTimePeriod(hour);
  }

  function getTargetImage() {
    if (manualMode) {
      if (manualMode === 'rain') return ASSETS.rain;
      if (manualMode === 'dusk') return ASSETS.dusk;
      if (manualMode === 'day') return ASSETS.day;
      return ASSETS.night;
    }
    if (currentWeather === 'rain' || currentWeather === 'heavy') {
      return ASSETS.rain;
    }
    const period = periodAt();
    currentPeriod = period;

    if (period === 'night') return ASSETS.night;
    if (period === 'dusk') return ASSETS.dusk;
    return ASSETS.day;
  }

  function initDOM() {
    let container = document.getElementById('ambient-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'ambient-container';
      container.className = 'ambient-container';
      container.setAttribute('aria-hidden', 'true');

      layerA = document.createElement('div');
      layerA.className = 'ambient-layer layer-a active';

      layerB = document.createElement('div');
      layerB.className = 'ambient-layer layer-b';

      const vignette = document.createElement('div');
      vignette.className = 'ambient-vignette';

      container.append(layerA, layerB, vignette);
      document.body.prepend(container);
    } else {
      layerA = container.querySelector('.layer-a');
      layerB = container.querySelector('.layer-b');
    }

    initParticles();
  }

  function updateBackground(targetImg) {
    if (!layerA || !layerB) return;
    if (!targetImg) targetImg = getTargetImage();
    if (targetImg === currentImage) return;

    currentImage = targetImg;

    // Preload image before fading
    const img = new Image();
    img.src = targetImg;
    img.onload = () => {
      if (activeLayer === 'a') {
        layerB.style.backgroundImage = `url("${targetImg}")`;
        layerB.classList.add('active');
        layerA.classList.remove('active');
        activeLayer = 'b';
      } else {
        layerA.style.backgroundImage = `url("${targetImg}")`;
        layerA.classList.add('active');
        layerB.classList.remove('active');
        activeLayer = 'a';
      }
      updateBadge();
    };
  }

  function updateBadge() {
    const badge = document.getElementById('ambient-badge');
    const label = document.getElementById('ambient-label');
    if (!badge || !label) return;

    if (manualMode) {
      const names = { rain: 'Live Rain', dusk: 'Dusk Sky', day: 'Day Sky', night: 'Night Sky' };
      label.textContent = `${names[manualMode] || manualMode} · Preview`;
      badge.setAttribute('data-state', manualMode === 'rain' ? 'rain' : 'preview');
      return;
    }

    const periodName = periodAt();
    const capitalizedPeriod = periodName.charAt(0).toUpperCase() + periodName.slice(1);

    if (currentWeather === 'rain' || currentWeather === 'heavy') {
      label.textContent = `${capitalizedPeriod} · Rain forecast`;
      badge.setAttribute('data-state', 'rain');
    } else {
      label.textContent = `${capitalizedPeriod} · Sky`;
      badge.setAttribute('data-state', 'clear');
    }
  }

  function cycleMode() {
    const idx = MODES.indexOf(manualMode);
    manualMode = MODES[(idx + 1) % MODES.length];

    if (manualMode === null) {
      setWeather(forecastWeather);
      updateBackground();
      if (typeof showToast === 'function') showToast('Ambient mode: Live Bengaluru time & forecast');
    } else if (manualMode === 'rain') {
      setWeather('rain');
      updateBackground(ASSETS.rain);
      if (typeof showToast === 'function') showToast('Preview mode: Bengaluru Rain with falling droplets');
    } else if (manualMode === 'dusk') {
      setWeather('clear');
      currentPeriod = 'dusk';
      updateBackground(ASSETS.dusk);
      if (typeof showToast === 'function') showToast('Preview mode: Bengaluru Dusk twilight');
    } else if (manualMode === 'day') {
      setWeather('clear');
      currentPeriod = 'day';
      updateBackground(ASSETS.day);
      if (typeof showToast === 'function') showToast('Preview mode: Bengaluru Daytime sunlight');
    } else if (manualMode === 'night') {
      setWeather('clear');
      currentPeriod = 'night';
      updateBackground(ASSETS.night);
      if (typeof showToast === 'function') showToast('Preview mode: Bengaluru Midnight starry sky');
    }
    updateBadge();
  }

  function initParticles() {
    if (particleCanvas) return;
    particleCanvas = document.createElement('canvas');
    particleCanvas.className = 'ambient-particles';
    particleCanvas.setAttribute('aria-hidden', 'true');
    document.body.prepend(particleCanvas);
    particleCtx = particleCanvas.getContext('2d');
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
  }

  function resizeCanvas() {
    if (!particleCanvas) return;
    particleCanvas.width = window.innerWidth;
    particleCanvas.height = window.innerHeight;
  }

  function spawnParticles(targetCount) {
    const w = particleCanvas ? particleCanvas.width : window.innerWidth;
    const h = particleCanvas ? particleCanvas.height : window.innerHeight;
    while (particles.length < targetCount) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h - h,
        speed: 7 + Math.random() * 8,
        length: 18 + Math.random() * 25,
        opacity: 0.18 + Math.random() * 0.25,
        drift: -1.2 + Math.random() * 0.6,
      });
    }
  }

  function renderParticles() {
    if (!particleCanvas || !particleCtx) return;
    const w = particleCanvas.width;
    const h = particleCanvas.height;

    particleCtx.clearRect(0, 0, w, h);

    if (currentWeather !== 'rain' && currentWeather !== 'heavy') {
      particles = [];
      if (animFrame) {
        cancelAnimationFrame(animFrame);
        animFrame = null;
      }
      return;
    }

    const count = currentWeather === 'heavy' ? 140 : 70;
    spawnParticles(count);

    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.y += p.speed;
      p.x += p.drift;

      if (p.y > h + p.length) {
        p.y = -p.length;
        p.x = Math.random() * w;
      }

      particleCtx.beginPath();
      particleCtx.moveTo(p.x, p.y);
      particleCtx.lineTo(p.x + p.drift * 3, p.y + p.length);
      particleCtx.strokeStyle = `rgba(200, 220, 255, ${p.opacity})`;
      particleCtx.lineWidth = 1.2;
      particleCtx.stroke();
    }

    animFrame = requestAnimationFrame(renderParticles);
  }

  function setWeather(condition) {
    currentWeather = condition;
    if (!motionQuery?.matches && (condition === 'rain' || condition === 'heavy')) {
      if (!animFrame) {
        animFrame = requestAnimationFrame(renderParticles);
      }
    } else {
      particles = [];
      if (animFrame) {
        cancelAnimationFrame(animFrame);
        animFrame = null;
      }
      if (particleCtx && particleCanvas) {
        particleCtx.clearRect(0, 0, particleCanvas.width, particleCanvas.height);
      }
    }
  }

  function fromWeatherData(data) {
    if (!data) {
      forecastWeather = 'clear';
      if (manualMode === null) { setWeather('clear'); updateBackground(); }
      return;
    }

    // Inspect weather for precipitation
    const hasRain = Boolean(
      data.rain_detected ||
      (typeof data.mins_to_rain === 'number' && data.mins_to_rain < 999) ||
      (Array.isArray(data.waypoints) && data.waypoints.some(w => typeof w.mins_to_rain === 'number' && w.mins_to_rain < 120)) ||
      (typeof data.max_intensity === 'number' && data.max_intensity > 0.1)
    );

    const isHeavy = Boolean(
      (typeof data.max_intensity === 'number' && data.max_intensity > 2.0) ||
      data.waterlogging_risk ||
      (data.status_category === 'rain_now')
    );

    forecastWeather = isHeavy ? 'heavy' : hasRain ? 'rain' : 'clear';
    if (manualMode !== null) return;
    setWeather(forecastWeather);
    updateBackground();
  }

  function init() {
    initDOM();
    updateBackground();
    updateBadge();
    motionQuery?.addEventListener?.('change', () => setWeather(currentWeather));

    const badge = document.getElementById('ambient-badge');
    if (badge) {
      badge.style.cursor = 'pointer';
      badge.setAttribute('role', 'button');
      badge.setAttribute('tabindex', '0');
      badge.title = 'Click to preview different Bengaluru skies and weather';
      badge.addEventListener('click', cycleMode);
      badge.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          cycleMode();
        }
      });
    }

    // Check every 2 minutes for time-of-day progression
    setInterval(() => {
      if (manualMode === null) updateBackground();
    }, 120000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  return {
    periodAt,
    setWeather,
    fromWeatherData,
    update: () => updateBackground(),
    cycle: cycleMode,
    getWeather: () => currentWeather,
    getPeriod: () => currentPeriod,
  };
})();
