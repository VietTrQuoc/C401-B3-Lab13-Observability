const state = {
  history: [],
  incidents: [],
  refreshMs: 15000,
  timerId: null,
  isGenerating: false,
  rangeMs: 60 * 60 * 1000,
};

const DEMO_MESSAGES = [
  "How do metrics, traces, and logs work together in observability?",
  "What should I inspect first for a tail latency incident?",
  "How should alerts map to user impact and mitigation?",
  "What is the policy for logging PII or sensitive data?",
  "Can I get a refund within 7 days with proof of purchase?",
  "Explain how monitoring helps localize root cause during incidents.",
];

const COLORS = {
  p50: "#5eead4",
  p95: "#ffb649",
  p99: "#ff6b6b",
  requests: "#59f0a0",
  success: "#78a6ff",
  error: "#ff6b6b",
  costAvg: "#5eead4",
  costTotal: "#ffb649",
  tokensIn: "#59f0a0",
  tokensOut: "#78a6ff",
  tokensTotal: "#ffb649",
  quality: "#59f0a0",
  slo: "#78a6ff",
};

const elements = {
  refreshSelect: document.getElementById("refreshSelect"),
  demoTrafficBtn: document.getElementById("demoTrafficBtn"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
  incidentList: document.getElementById("incidentList"),
  activeIncidentCount: document.getElementById("activeIncidentCount"),
  tracingStatus: document.getElementById("tracingStatus"),
  lastUpdated: document.getElementById("lastUpdated"),
  serviceHealth: document.getElementById("serviceHealth"),
  summaryRequests: document.getElementById("summaryRequests"),
  summaryErrorRate: document.getElementById("summaryErrorRate"),
  summaryLatency: document.getElementById("summaryLatency"),
  summaryQuality: document.getElementById("summaryQuality"),
  latencyPanel: document.getElementById("latencyPanel"),
  trafficPanel: document.getElementById("trafficPanel"),
  errorPanel: document.getElementById("errorPanel"),
  costPanel: document.getElementById("costPanel"),
  tokensPanel: document.getElementById("tokensPanel"),
  qualityPanel: document.getElementById("qualityPanel"),
};

document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  pollDashboard();
  startPolling();
});

function setupEventListeners() {
  elements.refreshSelect.addEventListener("change", (event) => {
    state.refreshMs = Number(event.target.value) || 15000;
    startPolling();
    renderPanels();
  });

  elements.clearHistoryBtn.addEventListener("click", () => {
    state.history = [];
    renderPanels();
  });

  elements.demoTrafficBtn.addEventListener("click", generateDemoTraffic);
}

function startPolling() {
  if (state.timerId) {
    clearInterval(state.timerId);
  }
  state.timerId = window.setInterval(pollDashboard, state.refreshMs);
}

async function pollDashboard() {
  try {
    const [metrics, health, incidentsPayload] = await Promise.all([
      fetchJson("/metrics"),
      fetchJson("/health"),
      fetchJson("/incidents"),
    ]);

    state.incidents = Array.isArray(incidentsPayload.items) ? incidentsPayload.items : [];
    pushSnapshot({
      ts: Date.now(),
      metrics,
      health,
    });
    renderHeader(health, metrics);
    renderIncidents();
    renderPanels();
  } catch (error) {
    elements.serviceHealth.textContent = "Unavailable";
    elements.lastUpdated.textContent = "Fetch failed";
    console.error(error);
  }
}

async function fetchJson(url, options) {
  const response = await fetch(url, {
    cache: "no-store",
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${url} -> ${response.status}`);
  }
  return response.json();
}

function pushSnapshot(entry) {
  state.history.push(entry);
  trimHistory();
}

function trimHistory() {
  const minTs = Date.now() - state.rangeMs;
  state.history = state.history.filter((item) => item.ts >= minTs);
}

function renderHeader(health, metrics) {
  elements.tracingStatus.textContent = health.tracing_enabled ? "Enabled" : "Off";
  elements.lastUpdated.textContent = new Date().toLocaleTimeString("vi-VN");
  elements.serviceHealth.textContent = health.ok ? "Healthy" : "Degraded";
  elements.summaryRequests.textContent = formatInteger(metrics.traffic.requests_total);
  elements.summaryErrorRate.textContent = formatPercent(metrics.traffic.error_rate);
  elements.summaryLatency.textContent = formatMs(metrics.latency_p95);
  elements.summaryQuality.textContent = formatScore(metrics.quality_avg);
}

function renderIncidents() {
  const activeCount = state.incidents.filter((item) => item.enabled).length;
  elements.activeIncidentCount.textContent = `${activeCount} active`;

  if (!state.incidents.length) {
    elements.incidentList.innerHTML = '<div class="empty-note">Không có incident metadata.</div>';
    return;
  }

  elements.incidentList.innerHTML = state.incidents
    .map((incident) => {
      const label = incident.name || incident.key;
      const buttonLabel = incident.enabled ? "Disable" : "Enable";
      const stateLabel = incident.enabled ? "Active" : "Idle";
      const stateClass = incident.enabled ? "active" : "idle";
      return `
        <article class="incident-card ${incident.enabled ? "active" : ""}">
          <div class="incident-topline">
            <strong>${escapeHtml(label)}</strong>
            <span class="incident-state ${stateClass}">${stateLabel}</span>
          </div>
          <p class="incident-copy">${escapeHtml(incident.description || "No description available.")}</p>
          <p class="incident-copy" style="margin-top: 8px;">Tác động: ${escapeHtml(incident.expected_effect || "Theo dõi trên dashboard.")}</p>
          <button class="incident-action" data-key="${incident.key}" data-next="${incident.enabled ? "disable" : "enable"}">${buttonLabel}</button>
        </article>
      `;
    })
    .join("");

  document.querySelectorAll(".incident-action").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.key;
      const next = button.dataset.next;
      button.disabled = true;
      try {
        await fetchJson(`/incidents/${key}/${next}`, { method: "POST" });
        await pollDashboard();
      } catch (error) {
        console.error(error);
        button.disabled = false;
      }
    });
  });
}

function renderPanels() {
  const latest = state.history[state.history.length - 1];
  const metrics = latest ? latest.metrics : emptyMetrics();
  const history = state.history;

  elements.latencyPanel.innerHTML = `
    ${panelHeader("Latency Trend", "p50 / p95 / p99", metricPill(formatMs(metrics.latency_p95), "p95"))}
    ${metricGrid([
      metricCard("p50", formatMs(metrics.latency_p50), "median"),
      metricCard("p95", formatMs(metrics.latency_p95), "tail latency"),
      metricCard("p99", formatMs(metrics.latency_p99), "worst-case"),
    ])}
    ${chartBlock(
      [
        { label: "p50", color: COLORS.p50, values: history.map((item) => item.metrics.latency_p50) },
        { label: "p95", color: COLORS.p95, values: history.map((item) => item.metrics.latency_p95) },
        { label: "p99", color: COLORS.p99, values: history.map((item) => item.metrics.latency_p99) },
      ],
      { unit: "ms", thresholds: [
        { value: 2000, color: COLORS.p95, label: "2000ms" },
        { value: 2500, color: COLORS.p99, label: "2500ms" },
      ] }
    )}
  `;

  elements.trafficPanel.innerHTML = `
    ${panelHeader("Traffic Summary", "requests / success / throughput", metricPill(formatRate(requestRatePerMinute(history)), "req/min"))}
    ${metricGrid([
      metricCard("Requests", formatInteger(metrics.traffic.requests_total), "total"),
      metricCard("Success", formatInteger(metrics.traffic.success_total), "2xx equivalent"),
      metricCard("Errors", formatInteger(metrics.traffic.errors_total), "failed"),
    ])}
    ${chartBlock(
      [
        { label: "requests_total", color: COLORS.requests, values: history.map((item) => item.metrics.traffic.requests_total) },
        { label: "success_total", color: COLORS.success, values: history.map((item) => item.metrics.traffic.success_total) },
      ],
      { unit: "count" }
    )}
  `;

  elements.errorPanel.innerHTML = `
    ${panelHeader("Error Rate & Breakdown", "ratio + current error types", metricPill(formatPercent(metrics.traffic.error_rate), "error rate"))}
    ${metricGrid([
      metricCard("Error rate", formatPercent(metrics.traffic.error_rate), "threshold 5%"),
      metricCard("Errors total", formatInteger(metrics.traffic.errors_total), "all failures"),
      metricCard("Active incidents", formatInteger(state.incidents.filter((item) => item.enabled).length), "control plane"),
    ])}
    ${chartBlock(
      [
        { label: "error_rate", color: COLORS.error, values: history.map((item) => item.metrics.traffic.error_rate) },
      ],
      { unit: "ratio", maxHint: 0.1, thresholds: [{ value: 0.05, color: COLORS.p95, label: "0.05" }] }
    )}
    ${renderErrorBreakdown(metrics.error_breakdown)}
  `;

  elements.costPanel.innerHTML = `
    ${panelHeader("Cost", "average and total USD", metricPill(formatUsd(metrics.total_cost_usd), "total"))}
    ${metricGrid([
      metricCard("Avg cost", formatUsd(metrics.avg_cost_usd), "threshold 0.0012"),
      metricCard("Total cost", formatUsd(metrics.total_cost_usd), "accumulated"),
    ], "two-col")}
    ${chartBlock(
      [
        { label: "avg_cost_usd", color: COLORS.costAvg, values: history.map((item) => item.metrics.avg_cost_usd) },
        { label: "total_cost_usd", color: COLORS.costTotal, values: history.map((item) => item.metrics.total_cost_usd) },
      ],
      { unit: "USD", thresholds: [{ value: 0.0012, color: COLORS.p95, label: "0.0012" }] }
    )}
  `;

  elements.tokensPanel.innerHTML = `
    ${panelHeader("Tokens", "input / output / total", metricPill(formatInteger(metrics.token.total), "tokens"))}
    ${metricGrid([
      metricCard("Input", formatInteger(metrics.tokens_in_total), "tokens_in_total"),
      metricCard("Output", formatInteger(metrics.tokens_out_total), "tokens_out_total"),
      metricCard("Total", formatInteger(metrics.token.total), "input + output"),
    ])}
    ${chartBlock(
      [
        { label: "tokens_in_total", color: COLORS.tokensIn, values: history.map((item) => item.metrics.tokens_in_total) },
        { label: "tokens_out_total", color: COLORS.tokensOut, values: history.map((item) => item.metrics.tokens_out_total) },
        { label: "token.total", color: COLORS.tokensTotal, values: history.map((item) => item.metrics.token.total) },
      ],
      { unit: "tokens" }
    )}
  `;

  elements.qualityPanel.innerHTML = `
    ${panelHeader("Quality Proxy", "quality_avg with SLO line", metricPill(formatScore(metrics.quality_avg), "score"))}
    ${metricGrid([
      metricCard("Quality avg", formatScore(metrics.quality_avg), "SLO 0.75"),
      metricCard("SLO gap", formatScore(metrics.quality_avg - 0.75), "current - target"),
    ], "two-col")}
    ${chartBlock(
      [
        { label: "quality_avg", color: COLORS.quality, values: history.map((item) => item.metrics.quality_avg) },
      ],
      { unit: "score", maxHint: 1, minHint: 0, thresholds: [{ value: 0.75, color: COLORS.slo, label: "0.75" }] }
    )}
  `;
}

function panelHeader(title, subtitle, pill) {
  return `
    <div class="panel-header">
      <div class="panel-title">
        <h3>${title}</h3>
        <p class="metric-subtitle">${subtitle}</p>
      </div>
      ${pill}
    </div>
  `;
}

function metricPill(value, label) {
  return `<div class="metric-pill"><strong>${value}</strong><span>${label}</span></div>`;
}

function metricGrid(items, extraClass = "") {
  return `<div class="metric-grid ${extraClass}">${items.join("")}</div>`;
}

function metricCard(label, value, subtitle) {
  return `
    <div class="metric">
      <span class="metric-label">${label}</span>
      <strong>${value}</strong>
      <span class="metric-subtitle">${subtitle}</span>
    </div>
  `;
}

function chartBlock(series, options) {
  return `
    <div class="chart-shell">${buildChartSvg(series, options)}</div>
    <div class="chart-caption">
      <div class="legend">${series.map((item) => legendItem(item.label, item.color)).join("")}</div>
      <span class="chart-note">time range 1h · refresh ${state.refreshMs / 1000}s · unit ${options.unit}</span>
    </div>
  `;
}

function legendItem(label, color) {
  return `<span class="legend-item"><span class="legend-dot" style="background:${color};"></span>${label}</span>`;
}

function buildChartSvg(series, options = {}) {
  const width = 720;
  const height = 220;
  const padding = { top: 12, right: 10, bottom: 26, left: 12 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const flatValues = series.flatMap((item) => item.values).filter((value) => Number.isFinite(value));

  if (!flatValues.length) {
    return `
      <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        <text x="${width / 2}" y="${height / 2}" text-anchor="middle" class="axis-label">Chưa có đủ dữ liệu để vẽ chart</text>
      </svg>
    `;
  }

  let minValue = options.minHint ?? Math.min(...flatValues);
  let maxValue = options.maxHint ?? Math.max(...flatValues);

  if (!Number.isFinite(minValue)) {
    minValue = 0;
  }
  if (!Number.isFinite(maxValue)) {
    maxValue = 1;
  }

  if (!options.minHint) {
    minValue = Math.min(minValue, 0);
  }
  if (Array.isArray(options.thresholds)) {
    for (const threshold of options.thresholds) {
      minValue = Math.min(minValue, threshold.value);
      maxValue = Math.max(maxValue, threshold.value);
    }
  }
  if (maxValue === minValue) {
    maxValue += maxValue === 0 ? 1 : Math.abs(maxValue) * 0.1;
  }

  const gridLines = [0.25, 0.5, 0.75]
    .map((ratio) => {
      const y = padding.top + chartHeight * ratio;
      return `<line class="grid-line" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}"></line>`;
    })
    .join("");

  const thresholdLines = (options.thresholds || [])
    .map((threshold) => {
      const y = toY(threshold.value, minValue, maxValue, padding.top, chartHeight);
      return `
        <line class="threshold-line" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="${threshold.color}"></line>
        <text class="axis-label" x="${width - padding.right}" y="${y - 5}" text-anchor="end">${threshold.label}</text>
      `;
    })
    .join("");

  const lines = series
    .map((item) => {
      const points = item.values.map((value, index) => {
        const x = toX(index, Math.max(item.values.length - 1, 1), padding.left, chartWidth);
        const y = toY(value, minValue, maxValue, padding.top, chartHeight);
        return { x, y };
      });

      const polyline = points.map((point) => `${point.x},${point.y}`).join(" ");
      const lastPoint = points[points.length - 1];
      return `
        <polyline class="series-line" points="${polyline}" stroke="${item.color}"></polyline>
        <circle class="series-point" cx="${lastPoint.x}" cy="${lastPoint.y}" r="4" stroke="${item.color}"></circle>
      `;
    })
    .join("");

  return `
    <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      ${gridLines}
      ${thresholdLines}
      ${lines}
      <text class="axis-label" x="${padding.left}" y="${height - 6}">-1h</text>
      <text class="axis-label" x="${width - padding.right}" y="${height - 6}" text-anchor="end">now</text>
      <text class="axis-label" x="${padding.left}" y="${padding.top + 10}">${formatAxis(maxValue, options.unit)}</text>
      <text class="axis-label" x="${padding.left}" y="${height - padding.bottom - 2}">${formatAxis(minValue, options.unit)}</text>
    </svg>
  `;
}

function toX(index, maxIndex, left, chartWidth) {
  return left + (chartWidth * index) / Math.max(maxIndex, 1);
}

function toY(value, minValue, maxValue, top, chartHeight) {
  const normalized = (value - minValue) / (maxValue - minValue);
  return top + chartHeight - normalized * chartHeight;
}

function renderErrorBreakdown(breakdown) {
  const entries = Object.entries(breakdown || {});
  if (!entries.length) {
    return '<div class="breakdown-list"><div class="empty-note">Chưa có lỗi nào được ghi nhận.</div></div>';
  }

  const maxValue = Math.max(...entries.map(([, value]) => value), 1);
  return `
    <div class="breakdown-list">
      ${entries
        .map(([name, value]) => `
          <div class="breakdown-item">
            <strong>${escapeHtml(name)}</strong>
            <small>${formatInteger(value)} hit</small>
            <div class="breakdown-bar"><span style="width:${(value / maxValue) * 100}%"></span></div>
          </div>
        `)
        .join("")}
    </div>
  `;
}

async function generateDemoTraffic() {
  if (state.isGenerating) {
    return;
  }

  state.isGenerating = true;
  elements.demoTrafficBtn.disabled = true;
  elements.demoTrafficBtn.textContent = "Đang tạo traffic...";

  try {
    const sessionId = `demo-${Date.now()}`;
    const jobs = DEMO_MESSAGES.map((message, index) =>
      fetch("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-request-id": `dashboard-${index + 1}-${Date.now()}`,
        },
        body: JSON.stringify({
          user_id: "u_dashboard_demo",
          session_id: `${sessionId}-${index + 1}`,
          feature: index % 2 === 0 ? "warranty" : "observability",
          message,
        }),
      })
    );
    await Promise.allSettled(jobs);
    await pollDashboard();
  } catch (error) {
    console.error(error);
  } finally {
    state.isGenerating = false;
    elements.demoTrafficBtn.disabled = false;
    elements.demoTrafficBtn.textContent = "Tạo demo traffic";
  }
}

function requestRatePerMinute(history) {
  if (history.length < 2) {
    return 0;
  }
  const latest = history[history.length - 1];
  const previous = history[history.length - 2];
  const requestDelta = latest.metrics.traffic.requests_total - previous.metrics.traffic.requests_total;
  const timeDeltaMs = latest.ts - previous.ts;

  if (requestDelta <= 0 || timeDeltaMs <= 0) {
    return 0;
  }
  return (requestDelta / timeDeltaMs) * 60000;
}

function emptyMetrics() {
  return {
    traffic: {
      requests_total: 0,
      errors_total: 0,
      success_total: 0,
      error_rate: 0,
    },
    latency_p50: 0,
    latency_p95: 0,
    latency_p99: 0,
    error_breakdown: {},
    token: {
      total: 0,
    },
    avg_cost_usd: 0,
    total_cost_usd: 0,
    tokens_in_total: 0,
    tokens_out_total: 0,
    quality_avg: 0,
  };
}

function formatAxis(value, unit) {
  if (unit === "ms") {
    return formatMs(value);
  }
  if (unit === "ratio") {
    return value.toFixed(2);
  }
  if (unit === "USD") {
    return formatUsd(value);
  }
  if (unit === "tokens" || unit === "count") {
    return formatInteger(value);
  }
  return formatScore(value);
}

function formatInteger(value) {
  return Number(value || 0).toLocaleString("en-US");
}

function formatMs(value) {
  return `${Math.round(Number(value || 0))} ms`;
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(2)}%`;
}

function formatUsd(value) {
  return `$${Number(value || 0).toFixed(4)}`;
}

function formatScore(value) {
  return Number(value || 0).toFixed(2);
}

function formatRate(value) {
  return `${Number(value || 0).toFixed(2)}`;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
