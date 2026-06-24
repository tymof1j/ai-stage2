document.addEventListener("DOMContentLoaded", async () => {
  const A = window.AlertAtlas;
  const loading = document.getElementById("forecast-loading");
  try {
    const data = await A.fetchJSON("site-data/forecast.json");
    renderSnapshot(data);
    renderMetrics(data);
    renderChart(data);
    renderEvaluation(data.evaluations);
    loading.hidden = true;
  } catch (error) {
    console.error(error);
    A.errorState(loading, error.message);
  }

  function renderSnapshot(data) {
    const origin = A.formatDateTime(data.origin);
    const last = A.formatDateTime(data.diagnostics.last_finished_at);
    document.getElementById("snapshot-copy").textContent = `Останній запис CSV: ${last}; остання повна година моделі: ${origin}. Live API token очікує окремого схвалення.`;
  }

  function renderMetrics(data) {
    const predictions = data.predictions;
    const level = document.getElementById("forecast-level");
    level.textContent = data.outlook.label;
    level.dataset.level = data.outlook.level;
    document.getElementById("forecast-level-detail").textContent = `середнє ${A.formatNumber(data.outlook.mean_load * 100, 1)}% моніторених районів`;
    for (const horizon of [3, 6]) {
      const row = predictions.find((item) => item.horizon === horizon);
      document.getElementById(`forecast-${horizon}h`).textContent = `${A.formatNumber(row.point * 100, 1)}%`;
      document.getElementById(`forecast-${horizon}h-range`).textContent = `інтервал ${A.formatNumber(row.lower * 100, 1)}–${A.formatNumber(row.upper * 100, 1)}%`;
    }
  }

  function renderChart(data) {
    const container = document.getElementById("forecast-chart");
    const history = data.history.slice(-48).map((row) => ({ time: new Date(row.timestamp), value: row.load }));
    const originTime = new Date(data.origin);
    const forecast = [{ time: originTime, value: data.current_load, lower: data.current_load, upper: data.current_load }]
      .concat(data.predictions.map((row) => ({ time: new Date(row.timestamp), value: row.point, lower: row.lower, upper: row.upper })));
    const all = history.concat(forecast);
    const minTime = Math.min(...all.map((row) => row.time));
    const maxTime = Math.max(...all.map((row) => row.time));
    const maxValue = Math.max(.1, ...all.map((row) => row.upper ?? row.value)) * 1.12;
    const width = 1200;
    const height = 400;
    const margin = { top: 26, right: 24, bottom: 50, left: 68 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const x = (time) => margin.left + (time - minTime) / (maxTime - minTime) * innerWidth;
    const y = (value) => margin.top + innerHeight - value / maxValue * innerHeight;
    const historyPoints = history.map((row) => `${x(row.time).toFixed(1)},${y(row.value).toFixed(1)}`).join(" ");
    const forecastPoints = forecast.map((row) => `${x(row.time).toFixed(1)},${y(row.value).toFixed(1)}`).join(" ");
    const upper = forecast.map((row) => `${x(row.time).toFixed(1)},${y(row.upper).toFixed(1)}`);
    const lower = [...forecast].reverse().map((row) => `${x(row.time).toFixed(1)},${y(row.lower).toFixed(1)}`);
    const interval = upper.concat(lower).join(" ");
    const yTicks = [0, .25, .5, .75, 1].map((fraction) => ({ value: maxValue * fraction, y: y(maxValue * fraction) }));
    const tickTimes = [0, .25, .5, .75, 1].map((fraction) => new Date(minTime + (maxTime - minTime) * fraction));

    container.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Історичне і прогнозоване навантаження">
      ${yTicks.map((tick) => `<line class="chart-grid" x1="${margin.left}" y1="${tick.y}" x2="${width-margin.right}" y2="${tick.y}"/><text class="chart-axis" x="${margin.left-12}" y="${tick.y+4}" text-anchor="end">${A.formatNumber(tick.value*100)}%</text>`).join("")}
      <polygon class="chart-interval" points="${interval}"/>
      <polyline class="chart-history" points="${historyPoints}"/>
      <polyline class="chart-forecast" points="${forecastPoints}"/>
      <line class="chart-snapshot" x1="${x(originTime)}" y1="${margin.top}" x2="${x(originTime)}" y2="${margin.top+innerHeight}"/>
      <text class="chart-axis" x="${x(originTime)+8}" y="${margin.top+14}">snapshot</text>
      ${tickTimes.map((time) => `<text class="chart-axis" x="${x(time)}" y="${height-14}" text-anchor="middle">${new Intl.DateTimeFormat("uk-UA", { day:"2-digit", month:"short", hour:"2-digit", timeZone:"Europe/Kyiv" }).format(time)}</text>`).join("")}
    </svg>`;
  }

  function renderEvaluation(rows) {
    const container = document.getElementById("forecast-evaluation");
    container.innerHTML = rows.map((row) => `<div class="evaluation-row">
      <strong>+${row.horizon} год</strong>
      <span>MAE моделі <strong>${A.formatNumber(row.model_mae * 100, 2)} п.п.</strong></span>
      <span>baseline <strong>${A.formatNumber(Math.min(row.persistence_mae, row.seasonal_mae) * 100, 2)} п.п.</strong></span>
      <strong class="${row.skill_vs_best_baseline > 0 ? "skill-positive" : ""}">${row.skill_vs_best_baseline > 0 ? "+" : ""}${A.formatNumber(row.skill_vs_best_baseline * 100, 1)}% skill</strong>
    </div>`).join("");
  }
});
