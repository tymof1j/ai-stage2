document.addEventListener("DOMContentLoaded", async () => {
  const A = window.AlertAtlas;
  const loading = document.getElementById("history-loading");
  const dateInput = document.getElementById("history-date");
  const metricButtons = [...document.querySelectorAll("[data-metric]")];
  const levelButtons = [...document.querySelectorAll("[data-level]")];
  const config = {
    minutes: { index: 1, label: "Хвилини під тривогою", range: "0–720+", thresholds: [15, 60, 180, 360, 720], suffix: " хв" },
    count: { index: 0, label: "Кількість епізодів", range: "0–12+", thresholds: [1, 2, 4, 8, 12], suffix: "" },
    night: { index: 3, label: "Нічні хвилини", range: "0–360+", thresholds: [15, 45, 90, 180, 360], suffix: " хв" },
  };

  let history;
  let geo = {};
  let map;
  let layer;
  let metric = "minutes";
  let level = "oblast";
  let fitted = false;

  try {
    [history, geo.oblast, geo.raion] = await Promise.all([
      A.fetchJSON("site-data/history.json"),
      A.fetchJSON("site-data/ukraine_admin1.geojson"),
      A.fetchJSON("site-data/ukraine_admin2.geojson"),
    ]);
    map = A.createMap("history-map", { zoom: 5.25, minZoom: 4, maxZoom: 8 });
    dateInput.min = history.first_date;
    dateInput.max = history.last_date;
    dateInput.value = history.last_date;
    update();
    loading.hidden = true;
    setupResizeHandling();
  } catch (error) {
    console.error(error);
    A.errorState(loading, error.message);
  }

  function currentDateData() {
    return (history[level] && history[level][dateInput.value]) || {};
  }

  function featureMeta(feature) {
    const p = feature.properties;
    return level === "oblast"
      ? { id: p.adm1_pcode, name: p.adm1_name1 }
      : { id: p.adm2_pcode, name: p.adm2_name1 };
  }

  function styleFeature(feature) {
    if (A.isCrimeaFeature(feature)) {
      return A.crimeaStyle(level === "oblast" ? 1.15 : 0.7);
    }
    const { id } = featureMeta(feature);
    const values = currentDateData()[id];
    const value = values ? values[config[metric].index] : 0;
    const hasData = Boolean(values);
    return {
      color: hasData ? "rgba(231,232,230,.38)" : "rgba(231,232,230,.12)",
      weight: level === "oblast" ? 1.15 : 0.7,
      fillColor: A.scaleColor(value, config[metric].thresholds),
      fillOpacity: hasData ? 0.84 : 0.24,
    };
  }

  function tooltip(feature) {
    const { id, name } = featureMeta(feature);
    if (A.isCrimeaFeature(feature)) return A.crimeaTooltip(name);
    const values = currentDateData()[id] || [0, 0, 0, 0];
    return `<span class="tooltip-title">${name}</span>
      <span class="tooltip-grid">
        <span>Епізоди</span><strong>${A.formatNumber(values[0])}</strong>
        <span>Унікальний час</span><strong>${A.formatNumber(values[1])} хв</strong>
        <span>Найдовший</span><strong>${A.formatNumber(values[2])} хв</strong>
        <span>Вночі</span><strong>${A.formatNumber(values[3])} хв</strong>
      </span>`;
  }

  function onEachFeature(feature, polygon) {
    polygon.bindTooltip(() => tooltip(feature), { sticky: true, direction: "top", opacity: 1 });
    polygon.on({
      mouseover: () => polygon.setStyle({ weight: 2, color: "rgba(255,255,255,.75)", fillOpacity: 0.96 }),
      mouseout: () => polygon.setStyle(styleFeature(feature)),
    });
  }

  function updateLayer() {
    if (layer) layer.remove();
    A.ensureCrimeaHatchPattern(map);
    layer = L.geoJSON(geo[level], {
      renderer: L.svg({ padding: 0.5 }),
      style: styleFeature,
      onEachFeature,
      smoothFactor: 1.5,
    }).addTo(map);
    A.ensureCrimeaHatchPattern(map);
    if (!fitted) fitToLayer();
  }

  function fitToLayer() {
    if (!layer || !map) return;
    map.invalidateSize({ pan: false });
    const mobile = window.matchMedia("(max-width: 767px)").matches;
    map.fitBounds(layer.getBounds(), mobile
      ? { paddingTopLeft: [14, 154], paddingBottomRight: [14, 286], maxZoom: 4.65 }
      : { paddingTopLeft: [410, 42], paddingBottomRight: [124, 42], maxZoom: 5.15 });
    fitted = true;
  }

  function setupResizeHandling() {
    if (!map) return;
    const observer = new ResizeObserver(() => {
      map.invalidateSize({ pan: false });
      if (!fitted) fitToLayer();
    });
    observer.observe(document.querySelector(".map-page"));
    window.addEventListener("resize", () => {
      fitted = false;
      fitToLayer();
    });
  }

  function updateSummary() {
    const dayData = currentDateData();
    const entries = Object.entries(dayData);
    const index = config[metric].index;
    const active = entries.filter(([, values]) => values[index] > 0);
    const featureCollection = geo[level].features;
    const names = Object.fromEntries(featureCollection.map((feature) => {
      const meta = featureMeta(feature);
      return [meta.id, meta.name];
    }));
    const leading = active.sort((a, b) => b[1][index] - a[1][index])[0];
    const total = active.reduce((sum, [, values]) => sum + values[index], 0);
    document.getElementById("summary-date").textContent = A.formatDate(dateInput.value);
    document.getElementById("active-regions").textContent = `${active.length}`;
    document.getElementById("leading-region").textContent = leading ? names[leading[0]] : "Немає записів";
    document.getElementById("metric-total").textContent = `${A.formatNumber(total)}${config[metric].suffix}`;
    document.getElementById("summary-metric-label").textContent = metric === "count" ? "Сума епізодів" : "Сума регіон-хвилин";
  }

  function updateControls() {
    const raionAvailable = dateInput.value >= history.raion_first_date;
    const raionButton = levelButtons.find((button) => button.dataset.level === "raion");
    raionButton.disabled = !raionAvailable;
    document.getElementById("raion-hint").textContent = raionAvailable
      ? "Районні записи агрегують hromada alerts до батьківського району."
      : "Районний режим доступний з 1 грудня 2025 року.";
    if (!raionAvailable && level === "raion") level = "oblast";
    metricButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.metric === metric));
    levelButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.level === level));
    document.getElementById("legend-title").textContent = config[metric].label;
    document.getElementById("legend-range").textContent = config[metric].range;
  }

  function update() {
    updateControls();
    updateLayer();
    updateSummary();
  }

  function shiftDate(days) {
    const current = new Date(`${dateInput.value}T12:00:00Z`);
    current.setUTCDate(current.getUTCDate() + days);
    const next = current.toISOString().slice(0, 10);
    if (next >= history.first_date && next <= history.last_date) {
      dateInput.value = next;
      update();
    }
  }

  dateInput.addEventListener("change", update);
  document.getElementById("date-prev").addEventListener("click", () => shiftDate(-1));
  document.getElementById("date-next").addEventListener("click", () => shiftDate(1));
  document.getElementById("map-reset").addEventListener("click", () => { fitted = false; fitToLayer(); });
  metricButtons.forEach((button) => button.addEventListener("click", () => { metric = button.dataset.metric; update(); }));
  levelButtons.forEach((button) => button.addEventListener("click", () => {
    if (!button.disabled) { level = button.dataset.level; fitted = false; update(); }
  }));
  window.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") shiftDate(-1);
    if (event.key === "ArrowRight") shiftDate(1);
  });
});
