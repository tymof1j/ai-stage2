window.AlertAtlas = (() => {
  const ACCENT = "#d56554";
  const COLORS = ["#252d32", "#39464b", "#65504d", "#93534b", "#bd5d50", ACCENT];

  async function fetchJSON(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Не вдалося завантажити ${path}: ${response.status}`);
    return response.json();
  }

  function formatNumber(value, digits = 0) {
    return new Intl.NumberFormat("uk-UA", {
      maximumFractionDigits: digits,
      minimumFractionDigits: digits,
    }).format(value);
  }

  function formatDate(iso, options = {}) {
    const date = new Date(`${iso}T12:00:00`);
    return new Intl.DateTimeFormat("uk-UA", {
      day: "numeric",
      month: "long",
      year: "numeric",
      ...options,
    }).format(date);
  }

  function formatDateTime(iso) {
    return new Intl.DateTimeFormat("uk-UA", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Europe/Kyiv",
    }).format(new Date(iso));
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function scaleColor(value, thresholds) {
    if (!Number.isFinite(value) || value <= 0) return COLORS[0];
    const index = thresholds.findIndex((threshold) => value <= threshold);
    return COLORS[index === -1 ? COLORS.length - 1 : Math.min(index + 1, COLORS.length - 1)];
  }

  function createMap(elementId, options = {}) {
    const map = L.map(elementId, {
      zoomControl: false,
      attributionControl: true,
      minZoom: options.minZoom || 5,
      maxZoom: options.maxZoom || 9,
      zoomSnap: options.zoomSnap ?? 0.25,
      zoomDelta: options.zoomDelta ?? 0.5,
      wheelPxPerZoomLevel: options.wheelPxPerZoomLevel ?? 180,
      wheelDebounceTime: 80,
      scrollWheelZoom: options.scrollWheelZoom ?? false,
      touchZoom: options.touchZoom ?? "center",
      doubleClickZoom: options.doubleClickZoom ?? false,
      boxZoom: false,
      bounceAtZoomLimits: false,
      preferCanvas: true,
      ...options,
    }).setView(options.center || [48.75, 31.4], options.zoom || 6);

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 20,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; CARTO',
    }).addTo(map);
    L.control.zoom({ position: "bottomright" }).addTo(map);
    return map;
  }

  function errorState(container, message) {
    if (!container) return;
    container.innerHTML = `<div class="inline-error"><strong>Дані не завантажилися</strong><span>${message}</span></div>`;
    container.hidden = false;
  }

  return {
    ACCENT,
    COLORS,
    clamp,
    createMap,
    errorState,
    fetchJSON,
    formatDate,
    formatDateTime,
    formatNumber,
    scaleColor,
  };
})();
