/**
 * GridLock AI — Command Center App
 * Core application logic: data loading, zone map rendering,
 * tab switching, sidebar controls, and dispatch table.
 */

// ── State ────────────────────────────────────────────────────────────────
let APP = {
  zones: [],
  stats: null,
  dispatch: [],
  forecast: null,
  violations: null,
  hoveredZone: null,
  futureMinutes: 0,
  showHeatmap: true,
  showClusters: true,
  heatRadius: 12,
  canvasZones: [],   // { zone, x, y, r } for hit-testing
  sortCol: 'impact_score',
  sortAsc: false,
  filterSeverity: 'ALL',
  resolvingZones: new Set(),
  liveInterval: null,
};

// ── Zone label names (for top zones) ─────────────────────────────────────
const ZONE_LABELS = {
  'Z_68_85': 'Koramangala Hub',
  'Z_58_59': 'Jayanagar Central',
  'Z_61_60': 'BTM Layout',
  'Z_61_59': 'JP Nagar Main',
  'Z_62_59': 'Banashankari',
  'Z_62_62': 'Basavanagudi',
  'Z_57_60': 'Wilson Garden',
  'Z_55_62': 'Richmond Circle',
  'Z_59_59': 'Lalbagh Area',
  'Z_60_63': 'MG Road Junction',
  'Z_63_57': 'Vijayanagar',
  'Z_56_64': 'Shivajinagar',
  'Z_54_59': 'Cubbon Park',
  'Z_65_60': 'Padmanabhanagar',
  'Z_52_67': 'Ulsoor',
};

function getZoneLabel(zid) {
  return ZONE_LABELS[zid] || zid.replace('Z_', 'Zone ');
}

// ── Initialization ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateClock();
  setInterval(updateClock, 1000);
  initTabs();
  initSidebar();
  loadAllData();
});

// ── Clock ────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const t = now.toLocaleTimeString('en-IN', { hour12: false });
  document.getElementById('navClock').textContent = t;
  const mapTs = document.getElementById('mapTimestamp');
  if (mapTs) mapTs.textContent = t;
}

// ── Tab Switching ────────────────────────────────────────────────────────
function initTabs() {
  const btns = document.querySelectorAll('.tab-btn');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      const panel = document.getElementById('tab-' + btn.dataset.tab);
      if (panel) panel.classList.add('active');

      // Lazy-render charts when switching to their tab
      if (btn.dataset.tab === 'analytics') renderAnalyticsCharts();
      if (btn.dataset.tab === 'forecast') renderForecastCharts();
    });
  });
}

// ── Sidebar Controls ─────────────────────────────────────────────────────
function initSidebar() {
  // Toggle sidebar (mobile)
  const toggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');

  toggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('visible');
  });
  overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('visible');
  });

  // Theme Toggle
  const themeBtn = document.getElementById('themeToggleBtn');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      document.documentElement.classList.toggle('light-theme');
      const isLight = document.documentElement.classList.contains('light-theme');
      themeBtn.textContent = isLight ? '🌙' : '🌞';
      if (typeof updateChartTheme === 'function') updateChartTheme(isLight);
    });
  }

  // Heatmap toggle
  document.getElementById('toggleHeatmap').addEventListener('change', (e) => {
    APP.showHeatmap = e.target.checked;
    renderZoneMap();
  });

  // Clusters toggle
  document.getElementById('toggleClusters').addEventListener('change', (e) => {
    APP.showClusters = e.target.checked;
    renderZoneMap();
  });

  // Heat radius slider
  document.getElementById('heatRadius').addEventListener('input', (e) => {
    APP.heatRadius = parseInt(e.target.value);
    document.getElementById('heatRadiusVal').textContent = APP.heatRadius;
    renderZoneMap();
  });

  // Fast-forward slider
  document.getElementById('fastForward').addEventListener('input', (e) => {
    APP.futureMinutes = parseInt(e.target.value);
    const badge = document.getElementById('ffBadge');
    badge.textContent = APP.futureMinutes === 0 ? 'NOW' : `T+${APP.futureMinutes}`;
    badge.style.color = APP.futureMinutes > 0 ? '#ff9100' : '';
    badge.style.borderColor = APP.futureMinutes > 0 ? 'rgba(255,145,0,0.3)' : '';
    badge.style.background = APP.futureMinutes > 0 ? 'rgba(255,145,0,0.08)' : '';
    reloadWithSimulation();
  });

  // Severity filter (dispatch)
  document.getElementById('severityFilter').addEventListener('change', (e) => {
    APP.filterSeverity = e.target.value;
    renderDispatchTable();
  });

  // Download button
  document.getElementById('downloadBtn').addEventListener('click', downloadReport);

  // Dispatch table sort
  document.querySelectorAll('.dispatch-table th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (APP.sortCol === col) APP.sortAsc = !APP.sortAsc;
      else { APP.sortCol = col; APP.sortAsc = false; }
      renderDispatchTable();
    });
  });
}

// ── Data Loading ─────────────────────────────────────────────────────────
async function loadAllData() {
  try {
    const [statsRes, zonesRes, dispatchRes, forecastRes, violationsRes] = await Promise.all([
      fetch('/api/stats'),
      fetch('/api/zones'),
      fetch('/api/dispatch'),
      fetch('/api/forecast'),
      fetch('/api/violations'),
    ]);

    APP.stats = await statsRes.json();
    APP.zones = await zonesRes.json();
    APP.dispatch = await dispatchRes.json();
    APP.forecast = await forecastRes.json();
    APP.violations = await violationsRes.json();

    populateDashboard();

    // Start Live Simulation
    if (!APP.liveInterval) {
      APP.liveInterval = setInterval(simulateLiveFeed, 2500);
    }
  } catch (err) {
    console.error('Failed to load data:', err);
  }
}

async function reloadWithSimulation() {
  try {
    const [zonesRes, dispatchRes] = await Promise.all([
      fetch(`/api/zones?future_mins=${APP.futureMinutes}`),
      fetch(`/api/dispatch?future_mins=${APP.futureMinutes}`),
    ]);
    APP.zones = await zonesRes.json();
    APP.dispatch = await dispatchRes.json();

    renderZoneMap();
    renderDispatchTable();
    updateAlertBanner();
    updateSidebarCounts();
    updateStatCards();
  } catch (err) {
    console.error('Simulation reload failed:', err);
  }
}

// ── Live Simulation Engine ───────────────────────────────────────────────
function simulateLiveFeed() {
  // Pause simulation if user is fast-forwarding
  if (APP.zones.length === 0 || APP.futureMinutes > 0) return;

  let changed = false;

  APP.zones.forEach(z => {
    // Check if zone is currently resolving (units dispatched)
    if (APP.resolvingZones.has(z.zone_id)) {
      // Decrease impact and violations slowly so radar is visible for longer
      z.impact_score -= 0.05 + (Math.random() * 0.02);
      z.violation_count = Math.max(0, z.violation_count - Math.floor(Math.random() * 5 + 2));
      changed = true;

      // If resolved, remove from resolving set
      if (z.impact_score <= 0.4) {
        z.impact_score = Math.max(0.2, z.impact_score);
        APP.resolvingZones.delete(z.zone_id);
      }
    } else {
      // 30% chance to increase congestion
      if (Math.random() < 0.3) {
        z.impact_score += 0.02 + (Math.random() * 0.06);
        z.violation_count += Math.floor(Math.random() * 5 + 1);
        changed = true;
      } else {
        // slight jitter
        z.impact_score += (Math.random() - 0.5) * 0.01;
        z.impact_score = Math.max(0.1, z.impact_score);
        changed = true;
      }

      // If it hits CRITICAL, mark for resolution next tick (simulates dispatch)
      if (z.impact_score >= 0.80 && Math.random() < 0.6) {
        APP.resolvingZones.add(z.zone_id);
      }
    }

    // Keep impact bounded
    z.impact_score = Math.min(0.99, Math.max(0.01, z.impact_score));

    // Update Severity
    if (z.impact_score > 0.8) z.severity = "CRITICAL";
    else if (z.impact_score > 0.6) z.severity = "HIGH";
    else if (z.impact_score > 0.4) z.severity = "MEDIUM";
    else z.severity = "LOW";
  });

  if (changed) {
    // Sort zones by impact desc
    APP.zones.sort((a, b) => b.impact_score - a.impact_score);

    // Sync dispatch data
    APP.dispatch.forEach(d => {
      const z = APP.zones.find(zone => zone.zone_id === d.zone_id);
      if (z) {
        d.impact_score = z.impact_score;
        d.violation_count = z.violation_count;
        d.severity = z.severity;
        if (d.severity === "CRITICAL") d.action = "🚨 Dispatch Tow Truck ASAP";
        else if (d.severity === "HIGH") d.action = "🚓 Send Patrol Unit";
        else d.action = "🟢 Issue E-Challan";
      }
    });

    populateDashboard();
  }
}

// ── Populate Dashboard ───────────────────────────────────────────────────
function populateDashboard() {
  updateStatCards();
  updateSidebarCounts();
  updateAlertBanner();
  renderZoneMap();
  renderDispatchTable();
}

// ── Stat Cards ───────────────────────────────────────────────────────────
function updateStatCards() {
  if (!APP.stats && APP.zones.length === 0) return;

  let critical = 0, high = 0, medium = 0, low = 0, totalViolations = 0;
  APP.zones.forEach(z => {
    if (z.severity === 'CRITICAL') critical++;
    else if (z.severity === 'HIGH') high++;
    else if (z.severity === 'MEDIUM') medium++;
    else low++;
    totalViolations += z.violation_count;
  });

  const avgImpact = APP.zones.length > 0
    ? (APP.zones.reduce((s, z) => s + z.impact_score, 0) / APP.zones.length).toFixed(4)
    : '0.0000';

  const units = critical + high;

  document.getElementById('statCritical').textContent = critical;
  document.getElementById('statViolations').textContent = totalViolations.toLocaleString();
  document.getElementById('statIncidents').textContent = `+${critical + high} active incidents`;
  document.getElementById('statImpact').textContent = avgImpact;
  document.getElementById('statImpactDelta').textContent = `↑ ${parseFloat(avgImpact).toFixed(4)}`;
  document.getElementById('statUnits').textContent = units;
  document.getElementById('statUnitsDetail').textContent = `${critical} tow trucks · ${high} patrols`;
  document.getElementById('notifCount').textContent = critical;
}

// ── Sidebar Counts ───────────────────────────────────────────────────────
function updateSidebarCounts() {
  let critical = 0, high = 0, medium = 0;
  APP.zones.forEach(z => {
    if (z.severity === 'CRITICAL') critical++;
    else if (z.severity === 'HIGH') high++;
    else if (z.severity === 'MEDIUM') medium++;
  });

  document.getElementById('sidebarCritical').textContent = critical;
  document.getElementById('sidebarHigh').textContent = high;
  document.getElementById('sidebarMedium').textContent = medium;
  document.getElementById('sidebarTotal').textContent = APP.zones.length;
  document.getElementById('zoneMonitored').textContent = APP.zones.length;
  document.getElementById('incidentCount').textContent = critical + high;
}

// ── Alert Banner ─────────────────────────────────────────────────────────
function updateAlertBanner() {
  if (APP.zones.length === 0) return;
  const top = APP.zones[0]; // already sorted by impact desc
  const label = getZoneLabel(top.zone_id);
  const alertEl = document.getElementById('alertText');

  if (APP.futureMinutes > 0) {
    alertEl.innerHTML = `<strong>PREDICTIVE ALERT (T+${APP.futureMinutes}min):</strong> ${top.zone_id} — ${label} spillover expanding. Impact Score: ${top.impact_score}`;
  } else {
    alertEl.innerHTML = `<strong>ACTIVE ALERT:</strong> ${top.zone_id} — ${label} IS A CRITICAL ZONE REQUIRING IMMEDIATE ACTION. Impact Score: ${top.impact_score}`;
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ZONE MAP (Canvas)
// ══════════════════════════════════════════════════════════════════════════
let mapAnimStarted = false;
function renderZoneMap() {
  if (!mapAnimStarted) {
    mapAnimStarted = true;
    requestAnimationFrame(drawMapFrame);
  }
}

function drawMapFrame() {
  requestAnimationFrame(drawMapFrame);
  const time = Date.now();

  const canvas = document.getElementById('zoneCanvas');
  const container = document.getElementById('mapContainer');
  const dpr = window.devicePixelRatio || 1;

  const w = container.clientWidth;
  const h = container.clientHeight;
  
  if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
  }

  const ctx = canvas.getContext('2d');
  ctx.save();
  ctx.scale(dpr, dpr);

  const W = w;
  const H = h;

  const isLight = document.documentElement.classList.contains('light-theme');

  // Clear
  ctx.fillStyle = isLight ? '#e2e8f0' : '#080d19';
  ctx.fillRect(0, 0, W, H);

  // Draw grid
  drawGrid(ctx, W, H, isLight);

  if (APP.zones.length === 0) return;

  // Get lat/lng bounds
  const lats = APP.zones.map(z => z.center_lat);
  const lngs = APP.zones.map(z => z.center_lng);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);

  const pad = 60;
  const mapW = W - pad * 2;
  const mapH = H - pad * 2;

  function project(lat, lng) {
    const x = pad + ((lng - minLng) / (maxLng - minLng || 1)) * mapW;
    const y = pad + ((maxLat - lat) / (maxLat - minLat || 1)) * mapH; // flip Y
    return [x, y];
  }

  // Select top zones to display (max 20 for clarity)
  const displayZones = APP.zones.slice(0, 20);

  // Compute positions
  APP.canvasZones = displayZones.map(z => {
    const [x, y] = project(z.center_lat, z.center_lng);
    // Radius based on violation count (normalized)
    const maxV = Math.max(...displayZones.map(d => d.violation_count));
    const minR = 22, maxR = 65;
    const r = minR + ((z.violation_count / (maxV || 1)) * (maxR - minR));
    return { zone: z, x, y, r };
  });

  // Draw connecting lines (dashed) and traffic dots
  if (APP.showClusters) {
    drawConnections(ctx, time, isLight);
  }

  // Draw heatmap glow
  if (APP.showHeatmap) {
    // For dark mode 'screen' is great, for light mode 'multiply' or 'source-over' is better
    ctx.globalCompositeOperation = isLight ? 'multiply' : 'screen'; 
    APP.canvasZones.forEach(cz => {
      // Pulse heatmap for CRITICAL
      let hR = cz.r * (APP.heatRadius / 8);
      if (cz.zone.severity === 'CRITICAL') {
        hR += Math.sin(time / 150) * 15;
      }

      const gradient = ctx.createRadialGradient(cz.x, cz.y, 0, cz.x, cz.y, Math.max(1, hR));
      const color = getSeverityColor(cz.zone.severity);
      // Use slightly softer opacity for light mode heatmap
      gradient.addColorStop(0, color + (isLight ? '40' : '70')); 
      gradient.addColorStop(1, 'transparent');
      ctx.fillStyle = gradient;
      ctx.fillRect(cz.x - hR * 2, cz.y - hR * 2, hR * 4, hR * 4);
    });
    ctx.globalCompositeOperation = 'source-over'; // Reset
  }

  // Draw zone circles
  APP.canvasZones.forEach((cz, i) => {
    const color = getSeverityColor(cz.zone.severity);
    const isHovered = APP.hoveredZone === i;

    // Outer glow ring
    ctx.beginPath();
    
    // Pulse animation for critical zones
    let pulse = 0;
    if (cz.zone.severity === 'CRITICAL') {
      pulse = Math.sin(time / 150) * 8;
    }
    
    ctx.arc(cz.x, cz.y, Math.max(1, cz.r + 6 + pulse), 0, Math.PI * 2);
    ctx.strokeStyle = color + (isHovered ? '60' : '25');
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw active dispatch radar if resolving
    if (APP.resolvingZones && APP.resolvingZones.has(cz.zone.zone_id)) {
       const radarR = (time % 800) / 800 * (cz.r * 2.5);
       ctx.beginPath();
       ctx.arc(cz.x, cz.y, cz.r + radarR, 0, Math.PI * 2);
       ctx.strokeStyle = `rgba(0, 229, 255, ${1 - (radarR / (cz.r * 2.5))})`;
       ctx.lineWidth = 2.5;
       ctx.stroke();
    }

    // Fill circle
    ctx.beginPath();
    ctx.arc(cz.x, cz.y, cz.r, 0, Math.PI * 2);
    const fillGrad = ctx.createRadialGradient(cz.x, cz.y, 0, cz.x, cz.y, cz.r);
    fillGrad.addColorStop(0, color + (isHovered ? '50' : '30'));
    fillGrad.addColorStop(1, color + (isHovered ? '20' : '10'));
    ctx.fillStyle = fillGrad;
    ctx.fill();

    // Border
    ctx.beginPath();
    ctx.arc(cz.x, cz.y, cz.r, 0, Math.PI * 2);
    ctx.strokeStyle = color + (isHovered ? 'cc' : (isLight ? 'aa' : '80'));
    ctx.lineWidth = isHovered ? 2.5 : 1.5;
    ctx.stroke();

    // Zone ID label
    const shortId = cz.zone.zone_id.replace('Z_', '');
    const parts = shortId.split('_');
    const label = parts.length >= 2 ? parts[0] : shortId;
    ctx.fillStyle = isLight ? '#0f172a' : color;
    ctx.font = `bold ${Math.max(12, cz.r * 0.4)}px 'JetBrains Mono', monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(label, cz.x, cz.y);
  });
  
  ctx.restore();
}

function drawGrid(ctx, W, H, isLight) {
  ctx.strokeStyle = isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(26, 35, 64, 0.3)';
  ctx.lineWidth = 0.5;
  const spacing = 40;
  for (let x = 0; x < W; x += spacing) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.stroke();
  }
  for (let y = 0; y < H; y += spacing) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(W, y);
    ctx.stroke();
  }
}

function drawConnections(ctx, time, isLight) {
  const zones = APP.canvasZones;
  ctx.setLineDash([5, 8]);
  ctx.lineWidth = 0.7;

  for (let i = 0; i < zones.length; i++) {
    for (let j = i + 1; j < zones.length; j++) {
      const dx = zones[i].x - zones[j].x;
      const dy = zones[i].y - zones[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      // Connect nearby zones
      if (dist < 200) {
        ctx.beginPath();
        ctx.moveTo(zones[i].x, zones[i].y);
        ctx.lineTo(zones[j].x, zones[j].y);
        ctx.strokeStyle = isLight ? 'rgba(0, 0, 0, 0.15)' : 'rgba(26, 35, 64, 0.5)';
        ctx.stroke();

        // Draw moving traffic particles along the connection
        const speed = 0.0005 + ((i + j) % 5) * 0.0002; // vary speeds slightly
        const progress = ((time * speed) + (i * 0.1) + (j * 0.2)) % 1;
        const dotX = zones[i].x - dx * progress;
        const dotY = zones[i].y - dy * progress;

        ctx.beginPath();
        ctx.arc(dotX, dotY, 2.5, 0, Math.PI * 2);
        // Color based on the target zone's severity
        ctx.fillStyle = getSeverityColor(zones[i].zone.severity) + 'CC'; 
        ctx.fill();
        
        // Add a slight glow to the particle
        ctx.shadowBlur = 5;
        ctx.shadowColor = ctx.fillStyle;
        ctx.fill();
        ctx.shadowBlur = 0; // reset
      }
    }
  }
  ctx.setLineDash([]);
}

function getSeverityColor(severity) {
  return {
    CRITICAL: '#ff1744',
    HIGH: '#ff9100',
    MEDIUM: '#fbbf24',
    LOW: '#00e5ff',
  }[severity] || '#8892a8';
}

// ── Canvas Mouse Interaction ─────────────────────────────────────────────
(function initCanvasEvents() {
  document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('zoneCanvas');
    const tooltip = document.getElementById('mapTooltip');

    canvas.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      let found = -1;
      for (let i = 0; i < APP.canvasZones.length; i++) {
        const cz = APP.canvasZones[i];
        const dx = mx - cz.x;
        const dy = my - cz.y;
        if (Math.sqrt(dx * dx + dy * dy) <= cz.r) {
          found = i;
          break;
        }
      }

      if (found !== APP.hoveredZone) {
        APP.hoveredZone = found;
        renderZoneMap();
      }

      if (found >= 0) {
        const cz = APP.canvasZones[found];
        const z = cz.zone;

        document.getElementById('tooltipTitle').textContent =
          `${z.zone_id} — ${getZoneLabel(z.zone_id)}`;
        document.getElementById('tooltipImpact').textContent = z.impact_score.toFixed(4);
        document.getElementById('tooltipRisk').textContent = z.risk_score.toFixed(6);
        document.getElementById('tooltipViolations').textContent = z.violation_count.toLocaleString();
        document.getElementById('tooltipPriority').textContent = `#${z.enforcement_priority}`;

        // Position tooltip
        const container = document.getElementById('mapContainer');
        const cr = container.getBoundingClientRect();
        let tx = e.clientX - cr.left + 16;
        let ty = e.clientY - cr.top - 10;
        // Keep tooltip in bounds
        if (tx + 220 > container.clientWidth) tx = e.clientX - cr.left - 220;
        if (ty + 120 > container.clientHeight) ty = container.clientHeight - 130;

        tooltip.style.left = tx + 'px';
        tooltip.style.top = ty + 'px';
        tooltip.classList.add('visible');
      } else {
        tooltip.classList.remove('visible');
      }
    });

    canvas.addEventListener('mouseleave', () => {
      APP.hoveredZone = null;
      tooltip.classList.remove('visible');
      renderZoneMap();
    });

    // Resize handler
    window.addEventListener('resize', () => {
      if (APP.zones.length > 0) renderZoneMap();
    });
  });
})();

// ══════════════════════════════════════════════════════════════════════════
// ANALYTICS CHARTS
// ══════════════════════════════════════════════════════════════════════════
let analyticsRendered = false;
function renderAnalyticsCharts() {
  if (analyticsRendered && APP.futureMinutes === 0) return;
  analyticsRendered = true;

  if (APP.zones.length > 0) {
    renderSeverityChart(APP.zones);
    renderTopZonesChart(APP.zones);
    renderScatterChart(APP.zones);
  }
  if (APP.violations) {
    renderReasonsChart(APP.violations.reason_counts);
  }
}

// ══════════════════════════════════════════════════════════════════════════
// FORECAST
// ══════════════════════════════════════════════════════════════════════════
let forecastRendered = false;
function renderForecastCharts() {
  if (forecastRendered || !APP.forecast) return;
  forecastRendered = true;

  const { forecast, summary, peaks } = APP.forecast;

  // Metrics
  document.getElementById('forecastPeak').textContent = summary.max_congestion;
  document.getElementById('forecastAvg').textContent = summary.avg_congestion;
  document.getElementById('forecastCritHours').textContent = summary.critical_hours;
  document.getElementById('forecastHighHours').textContent = summary.high_hours;

  // Peak alerts
  const peakContainer = document.getElementById('peakAlerts');
  peakContainer.innerHTML = peaks.map(p => {
    const emoji = { CRITICAL: '🔴', HIGH: '🟠', MEDIUM: '🟡', LOW: '🟢' }[p.risk_level] || '⚪';
    return `
      <div class="peak-alert">
        <div class="peak-alert-left">${emoji} ${p.hour_label} — Congestion Index: <strong>${p.congestion_index.toFixed(1)}</strong></div>
        <div class="peak-alert-right">Risk: ${p.risk_level}</div>
      </div>
    `;
  }).join('');

  // Charts
  renderForecastChart(forecast);
  renderViolationsChart(forecast);
}

// ══════════════════════════════════════════════════════════════════════════
// DISPATCH TABLE
// ══════════════════════════════════════════════════════════════════════════
function renderDispatchTable() {
  let data = [...APP.dispatch];

  // Filter
  if (APP.filterSeverity !== 'ALL') {
    const priorities = {
      'CRITICAL': ['CRITICAL'],
      'HIGH': ['CRITICAL', 'HIGH'],
      'MEDIUM': ['CRITICAL', 'HIGH', 'MEDIUM'],
    };
    const allowed = priorities[APP.filterSeverity] || [];
    data = data.filter(d => allowed.includes(d.severity));
  }

  // Sort
  data.sort((a, b) => {
    let va = a[APP.sortCol], vb = b[APP.sortCol];
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return APP.sortAsc ? -1 : 1;
    if (va > vb) return APP.sortAsc ? 1 : -1;
    return 0;
  });

  const tbody = document.getElementById('dispatchBody');
  if (data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#4a5568;padding:30px;">No zones match the current filter.</td></tr>';
    return;
  }

  tbody.innerHTML = data.map(d => {
    const sevClass = d.severity.toLowerCase();
    const rowClass = d.severity === 'CRITICAL' ? 'critical-row' : '';
    return `
      <tr class="${rowClass}">
        <td>${d.zone_id}</td>
        <td><span class="severity-badge ${sevClass}">${d.severity}</span></td>
        <td>${d.risk_score.toFixed(4)}</td>
        <td>${d.impact_score.toFixed(4)}</td>
        <td>${d.violation_count.toLocaleString()}</td>
        <td>${d.action}</td>
      </tr>
    `;
  }).join('');

  // Update dispatch chart if the function is available
  if (typeof renderDispatchChart === 'function') {
    renderDispatchChart(APP.dispatch);
  }
}

// ── Download Report ──────────────────────────────────────────────────────
function downloadReport() {
  let data = APP.dispatch;
  const headers = ['Zone ID', 'Severity', 'Risk Score', 'Impact Score', 'Violations', 'Recommended Action'];
  const rows = data.map(d => [d.zone_id, d.severity, d.risk_score, d.impact_score, d.violation_count, d.action]);

  let csv = headers.join(',') + '\n';
  rows.forEach(r => {
    csv += r.map(v => `"${v}"`).join(',') + '\n';
  });

  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'gridlock_dispatch_report.csv';
  a.click();
  URL.revokeObjectURL(url);
}
