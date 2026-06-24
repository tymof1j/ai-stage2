document.addEventListener("DOMContentLoaded", async () => {
  const A = window.AlertAtlas;
  const loading = document.getElementById("savings-loading");
  try {
    const [data, geo] = await Promise.all([
      A.fetchJSON("site-data/savings.json"),
      A.fetchJSON("site-data/ukraine_admin1.geojson"),
    ]);
    renderHeadline(data);
    renderMap(data, geo);
    renderChart(data.national_daily);
    renderRanking(data.totals);
    loading.hidden = true;
  } catch (error) {
    console.error(error);
    A.errorState(loading, error.message);
  }

  function renderHeadline(data) {
    const savedHours = data.national_saved_raion_minutes / 60;
    const share = 100 * data.national_saved_raion_minutes / data.national_counterfactual_raion_minutes;
    const last = data.national_daily.at(-1)?.d || data.start_date;
    document.getElementById("saved-hours").textContent = A.formatNumber(savedHours);
    document.getElementById("saved-percent").textContent = `${A.formatNumber(share, 1)}%`;
    document.getElementById("savings-period").textContent = `${A.formatDate(data.start_date, { year: undefined })} — ${A.formatDate(last)}`;
    document.getElementById("top-oblast").textContent = data.totals[0]?.name || "—";
  }

  function renderMap(data, geo) {
    const lookup = Object.fromEntries(data.totals.map((row) => [row.id, row]));
    const map = A.createMap("savings-map", { zoom: 6, minZoom: 5, maxZoom: 8 });
    const thresholds = [10, 20, 35, 50, 65];
    const layer = L.geoJSON(geo, {
      smoothFactor: 1.5,
      style: (feature) => {
        const row = lookup[feature.properties.adm1_pcode];
        return {
          color: row ? "rgba(231,232,230,.38)" : "rgba(231,232,230,.1)",
          weight: 1.1,
          fillColor: A.scaleColor(row?.saved_pct || 0, thresholds),
          fillOpacity: row ? .88 : .18,
        };
      },
      onEachFeature: (feature, polygon) => {
        const row = lookup[feature.properties.adm1_pcode];
        const name = feature.properties.adm1_name1;
        polygon.bindTooltip(
          `<span class="tooltip-title">${name}</span><span class="tooltip-grid">
            <span>Збережено</span><strong>${row ? A.formatNumber(row.saved / 60) : 0} район-год</strong>
            <span>Частка</span><strong>${row ? A.formatNumber(row.saved_pct, 1) : 0}%</strong>
            <span>Еквівалент</span><strong>${row ? A.formatNumber(row.equivalent_hours, 1) : 0} год</strong>
          </span>`,
          { sticky: true, direction: "top", opacity: 1 }
        );
        polygon.on({
          mouseover: () => polygon.setStyle({ weight: 2, color: "rgba(255,255,255,.76)", fillOpacity: .98 }),
          mouseout: () => layer.resetStyle(polygon),
        });
      },
    }).addTo(map);
    map.fitBounds(layer.getBounds(), { padding: [20, 20] });
  }

  function renderChart(rows) {
    const container = document.getElementById("savings-chart");
    const width = 1200;
    const height = 360;
    const margin = { top: 28, right: 24, bottom: 42, left: 76 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const max = Math.max(...rows.map((row) => row.cum / 60));
    const x = (index) => margin.left + index / Math.max(rows.length - 1, 1) * innerWidth;
    const y = (value) => margin.top + innerHeight - value / max * innerHeight;
    const points = rows.map((row, index) => `${x(index).toFixed(1)},${y(row.cum / 60).toFixed(1)}`).join(" ");
    const area = `${margin.left},${margin.top + innerHeight} ${points} ${margin.left + innerWidth},${margin.top + innerHeight}`;
    const yTicks = [0, .25, .5, .75, 1].map((fraction) => ({ value: max * fraction, y: y(max * fraction) }));
    const xTickIndices = [0, .25, .5, .75, 1].map((fraction) => Math.round((rows.length - 1) * fraction));

    container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Накопичені заощаджені район-години">
      ${yTicks.map((tick) => `<line class="chart-grid" x1="${margin.left}" y1="${tick.y}" x2="${width - margin.right}" y2="${tick.y}"/><text class="chart-axis" x="${margin.left - 12}" y="${tick.y + 4}" text-anchor="end">${A.formatNumber(tick.value)}</text>`).join("")}
      <polygon class="chart-area" points="${area}"/>
      <polyline class="chart-line" points="${points}"/>
      ${xTickIndices.map((index) => `<text class="chart-axis" x="${x(index)}" y="${height - 12}" text-anchor="middle">${new Intl.DateTimeFormat("uk-UA", { day:"2-digit", month:"short" }).format(new Date(`${rows[index].d}T12:00:00`))}</text>`).join("")}
    </svg>`;
  }

  function renderRanking(rows) {
    const container = document.getElementById("savings-ranking");
    const visible = rows.filter((row) => row.saved > 0).slice(0, 10);
    const max = Math.max(...visible.map((row) => row.saved));
    container.innerHTML = visible.map((row, index) => `<div class="ranking-row">
      <span>${String(index + 1).padStart(2, "0")}</span>
      <strong class="ranking-name">${row.name}</strong>
      <span class="rank-bar"><i style="width:${100 * row.saved / max}%"></i></span>
      <span class="ranking-value">${A.formatNumber(row.saved / 60)} район-год</span>
      <span class="ranking-percent">${A.formatNumber(row.saved_pct, 1)}%</span>
    </div>`).join("");
  }
});

