/**
 * GridLock AI — Chart.js Wrappers
 * All chart rendering functions for the Command Center dashboard.
 * Uses Chart.js v4 with custom dark-mode styling.
 */

// ── Chart.js Global Defaults ──────────────────────────────────────────────
Chart.defaults.font.family = "'JetBrains Mono', 'Inter', sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.color = '#8892a8';
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
Chart.defaults.plugins.legend.labels.padding = 16;
Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(13, 18, 33, 0.95)';
Chart.defaults.plugins.tooltip.borderColor = '#1a2340';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.cornerRadius = 8;
Chart.defaults.plugins.tooltip.padding = 12;
Chart.defaults.plugins.tooltip.titleFont = { family: "'JetBrains Mono'", weight: '600', size: 12 };
Chart.defaults.plugins.tooltip.bodyFont = { family: "'JetBrains Mono'", size: 11 };
Chart.defaults.scale.grid = { color: 'rgba(26, 35, 64, 0.6)', lineWidth: 1 };
Chart.defaults.scale.border = { color: '#1a2340' };

function updateChartTheme(isLight) {
  Chart.defaults.color = isLight ? '#475569' : '#8892a8';
  Chart.defaults.scale.grid.color = isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(26, 35, 64, 0.6)';
  Chart.defaults.scale.border.color = isLight ? '#cbd5e1' : '#1a2340';
  Chart.defaults.plugins.tooltip.backgroundColor = isLight ? 'rgba(255, 255, 255, 0.95)' : 'rgba(13, 18, 33, 0.95)';
  Chart.defaults.plugins.tooltip.borderColor = isLight ? '#cbd5e1' : '#1a2340';
  Chart.defaults.plugins.tooltip.titleColor = isLight ? '#0f172a' : '#fff';
  Chart.defaults.plugins.tooltip.bodyColor = isLight ? '#334155' : '#fff';
  
  const cardBg = isLight ? '#ffffff' : '#0d1221';

  for (let id in CHART_INSTANCES) {
    const chart = CHART_INSTANCES[id];
    // Update dataset borders if they match the old card background
    chart.data.datasets.forEach(ds => {
      if (ds.borderColor === '#0d1221' || ds.borderColor === '#ffffff') {
        ds.borderColor = cardBg;
      }
    });
    
    // Update scales
    if (chart.options.scales) {
      for (let axis in chart.options.scales) {
        if (chart.options.scales[axis].grid) {
          chart.options.scales[axis].grid.color = Chart.defaults.scale.grid.color;
        }
        if (chart.options.scales[axis].border) {
          chart.options.scales[axis].border.color = Chart.defaults.scale.border.color;
        }
        if (chart.options.scales[axis].ticks) {
          chart.options.scales[axis].ticks.color = Chart.defaults.color;
        }
      }
    }
    chart.update();
  }
}

const SEVERITY_COLORS = {
  CRITICAL: '#ff1744',
  HIGH: '#ff9100',
  MEDIUM: '#fbbf24',
  LOW: '#00e676',
};

const CHART_INSTANCES = {};

function destroyChart(id) {
  if (CHART_INSTANCES[id]) {
    CHART_INSTANCES[id].destroy();
    delete CHART_INSTANCES[id];
  }
}

// ── Severity Distribution Donut ──────────────────────────────────────────
function renderSeverityChart(zones) {
  destroyChart('severity');
  const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  zones.forEach(z => { if (counts[z.severity] !== undefined) counts[z.severity]++; });

  const ctx = document.getElementById('chartSeverity').getContext('2d');
  CHART_INSTANCES['severity'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: Object.keys(counts),
      datasets: [{
        data: Object.values(counts),
        backgroundColor: Object.keys(counts).map(k => SEVERITY_COLORS[k]),
        borderColor: '#0d1221',
        borderWidth: 3,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: { position: 'bottom' },
      },
      animation: {
        animateRotate: true,
        duration: 1000,
      },
    }
  });
}

// ── Congestion Reasons Donut ─────────────────────────────────────────────
function renderReasonsChart(reasonCounts) {
  destroyChart('reasons');
  const labels = Object.keys(reasonCounts);
  const data = Object.values(reasonCounts);
  const colors = ['#7c4dff', '#2979ff', '#00e5ff', '#00e676', '#fbbf24', '#ff9100'];

  const ctx = document.getElementById('chartReasons').getContext('2d');
  CHART_INSTANCES['reasons'] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors.slice(0, labels.length),
        borderColor: '#0d1221',
        borderWidth: 3,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: { position: 'bottom' },
      },
      animation: { duration: 1000 },
    }
  });
}

// ── Top 10 Critical Zones Bar ────────────────────────────────────────────
function renderTopZonesChart(zones) {
  destroyChart('topZones');
  const top10 = zones.slice(0, 10);
  const labels = top10.map(z => z.zone_id.replace('Z_', 'Z-'));
  const data = top10.map(z => z.impact_score);
  const bgColors = top10.map(z => SEVERITY_COLORS[z.severity] || '#8892a8');

  const ctx = document.getElementById('chartTopZones').getContext('2d');
  CHART_INSTANCES['topZones'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Impact Score',
        data,
        backgroundColor: bgColors.map(c => c + '80'),
        borderColor: bgColors,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.7,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          beginAtZero: true,
          max: 1,
          ticks: { callback: v => v.toFixed(1) },
        },
        y: {
          ticks: { font: { size: 10 } },
        },
      },
      animation: { duration: 800, easing: 'easeOutQuart' },
    }
  });
}

// ── Impact vs Violations Scatter ─────────────────────────────────────────
function renderScatterChart(zones) {
  destroyChart('scatter');
  const datasets = {};
  zones.forEach(z => {
    if (!datasets[z.severity]) {
      datasets[z.severity] = {
        label: z.severity,
        data: [],
        backgroundColor: SEVERITY_COLORS[z.severity] + '90',
        borderColor: SEVERITY_COLORS[z.severity],
        borderWidth: 1,
        pointRadius: 5,
        pointHoverRadius: 8,
      };
    }
    datasets[z.severity].data.push({ x: z.violation_count, y: z.impact_score });
  });

  const ctx = document.getElementById('chartScatter').getContext('2d');
  CHART_INSTANCES['scatter'] = new Chart(ctx, {
    type: 'scatter',
    data: { datasets: Object.values(datasets) },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' },
        tooltip: {
          callbacks: {
            label: (ctx) => `Violations: ${ctx.raw.x}, Impact: ${ctx.raw.y.toFixed(4)}`,
          }
        }
      },
      scales: {
        x: { title: { display: true, text: 'Violation Count', color: '#8892a8' } },
        y: { title: { display: true, text: 'Impact Score', color: '#8892a8' }, beginAtZero: true },
      },
      animation: { duration: 800 },
    }
  });
}

// ── Dispatch Summary Horizontal Bar ──────────────────────────────────────
function renderDispatchChart(dispatchData) {
  destroyChart('dispatch');
  const actionCounts = {};
  dispatchData.forEach(d => {
    actionCounts[d.action] = (actionCounts[d.action] || 0) + 1;
  });

  const labels = Object.keys(actionCounts);
  const data = Object.values(actionCounts);
  const colors = labels.map(l => {
    if (l.includes('Tow')) return '#ff174480';
    if (l.includes('Patrol')) return '#ff910080';
    return '#00e67680';
  });
  const borderColors = labels.map(l => {
    if (l.includes('Tow')) return '#ff1744';
    if (l.includes('Patrol')) return '#ff9100';
    return '#00e676';
  });

  const ctx = document.getElementById('chartDispatch').getContext('2d');
  CHART_INSTANCES['dispatch'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Count',
        data,
        backgroundColor: colors,
        borderColor: borderColors,
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { stepSize: 50 } },
        y: { ticks: { font: { size: 10 } } },
      },
      animation: { duration: 800 },
    }
  });
}

// ── 24H Forecast Line Chart ──────────────────────────────────────────────
function renderForecastChart(forecast) {
  destroyChart('forecast');
  const labels = forecast.map(f => f.hour_label);
  const data = forecast.map(f => f.congestion_index);
  const upper = forecast.map(f => f.confidence_upper);
  const lower = forecast.map(f => f.confidence_lower);
  const pointColors = forecast.map(f => SEVERITY_COLORS[f.risk_level] || '#8892a8');

  const ctx = document.getElementById('chartForecast').getContext('2d');
  CHART_INSTANCES['forecast'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Upper Band',
          data: upper,
          borderColor: 'transparent',
          backgroundColor: 'rgba(99, 110, 250, 0.08)',
          fill: '+1',
          pointRadius: 0,
          tension: 0.4,
        },
        {
          label: 'Predicted Congestion',
          data,
          borderColor: '#636EFA',
          borderWidth: 3,
          backgroundColor: 'rgba(99, 110, 250, 0.05)',
          pointBackgroundColor: pointColors,
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointRadius: 6,
          pointHoverRadius: 9,
          fill: false,
          tension: 0.4,
        },
        {
          label: 'Lower Band',
          data: lower,
          borderColor: 'transparent',
          backgroundColor: 'transparent',
          fill: false,
          pointRadius: 0,
          tension: 0.4,
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: {
            filter: (item) => item.text === 'Predicted Congestion',
          }
        },
        annotation: undefined,
      },
      scales: {
        y: {
          min: 0,
          max: 105,
          title: { display: true, text: 'Congestion Index', color: '#8892a8' },
        },
        x: {
          title: { display: true, text: 'Time', color: '#8892a8' },
          ticks: { maxRotation: 45 },
        }
      },
      animation: { duration: 1200, easing: 'easeOutQuart' },
    }
  });
}

// ── Violations Per Hour Bar ──────────────────────────────────────────────
function renderViolationsChart(forecast) {
  destroyChart('violations');
  const labels = forecast.map(f => f.hour_label);
  const data = forecast.map(f => f.violations_predicted);
  const bgColors = forecast.map(f => (SEVERITY_COLORS[f.risk_level] || '#8892a8') + '70');
  const borderColors = forecast.map(f => SEVERITY_COLORS[f.risk_level] || '#8892a8');

  const ctx = document.getElementById('chartViolations').getContext('2d');
  CHART_INSTANCES['violations'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Predicted Violations',
        data,
        backgroundColor: bgColors,
        borderColor: borderColors,
        borderWidth: 1,
        borderRadius: 3,
        barPercentage: 0.75,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Predicted Violations', color: '#8892a8' },
        },
        x: {
          title: { display: true, text: 'Time', color: '#8892a8' },
          ticks: { maxRotation: 45 },
        }
      },
      animation: { duration: 800 },
    }
  });
}
