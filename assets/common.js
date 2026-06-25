window.AlertAtlas = (() => {
  const ACCENT = "#d56554";
  const COLORS = ["#252d32", "#39464b", "#65504d", "#93534b", "#bd5d50", ACCENT];
  const CRIMEA_ADM1 = new Set(["UA01", "UA85"]);

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

  function isCrimeaFeature(feature) {
    const p = feature?.properties || {};
    return CRIMEA_ADM1.has(p.adm1_pcode) || CRIMEA_ADM1.has(p.adm2_pcode);
  }

  function crimeaTooltip(name) {
    return `<span class="tooltip-title">${name}</span>
      <span class="tooltip-grid tooltip-grid-note">
        <span>Статус карти</span><strong>Україна</strong>
        <span>Дані тривог</span><strong>немає у CSV</strong>
        <span>Пояснення</span><strong>територію позначено штрихуванням і не включено в розрахунки</strong>
      </span>`;
  }

  function ensureCrimeaHatchPattern(map) {
    const install = () => {
      const svg = map?.getPanes?.().overlayPane?.querySelector("svg");
      if (!svg || svg.querySelector("#crimea-hatch")) return;
      const ns = "http://www.w3.org/2000/svg";
      const defs = document.createElementNS(ns, "defs");
      const pattern = document.createElementNS(ns, "pattern");
      pattern.setAttribute("id", "crimea-hatch");
      pattern.setAttribute("patternUnits", "userSpaceOnUse");
      pattern.setAttribute("width", "8");
      pattern.setAttribute("height", "8");
      pattern.setAttribute("patternTransform", "rotate(45)");
      const background = document.createElementNS(ns, "rect");
      background.setAttribute("width", "8");
      background.setAttribute("height", "8");
      background.setAttribute("fill", "rgba(213,101,84,.08)");
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", "0");
      line.setAttribute("y1", "0");
      line.setAttribute("x2", "0");
      line.setAttribute("y2", "8");
      line.setAttribute("stroke", "rgba(231,232,230,.56)");
      line.setAttribute("stroke-width", "2");
      pattern.append(background, line);
      defs.append(pattern);
      svg.insertBefore(defs, svg.firstChild);
    };
    install();
    map?.once?.("layeradd", install);
  }

  function crimeaStyle(weight = 1) {
    return {
      color: "rgba(231,232,230,.58)",
      weight,
      dashArray: "4 4",
      fillColor: "url(#crimea-hatch)",
      fillOpacity: 0.82,
      className: "crimea-hatched",
    };
  }

  function createMap(elementId, options = {}) {
    const map = L.map(elementId, {
      zoomControl: false,
      attributionControl: true,
      minZoom: options.minZoom || 5,
      maxZoom: options.maxZoom || 9,
      zoomSnap: options.zoomSnap ?? 0.2,
      zoomDelta: options.zoomDelta ?? 0.5,
      wheelPxPerZoomLevel: options.wheelPxPerZoomLevel ?? 420,
      wheelDebounceTime: 130,
      scrollWheelZoom: options.scrollWheelZoom ?? "center",
      touchZoom: options.touchZoom ?? "center",
      doubleClickZoom: options.doubleClickZoom ?? "center",
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
    crimeaStyle,
    crimeaTooltip,
    ensureCrimeaHatchPattern,
    errorState,
    fetchJSON,
    formatDate,
    formatDateTime,
    formatNumber,
    isCrimeaFeature,
    scaleColor,
  };
})();
