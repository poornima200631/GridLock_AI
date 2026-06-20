/**
 * GridLock AI — Command Center App
 * Core application logic: data loading, zone map rendering,
 * tab switching, sidebar controls, dispatch table, and Mappls APIs integration.
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

  // Interactive Map State (Mappls & Leaflet Fallback)
  map: null,
  mapMode: 'leaflet', // 'leaflet' or 'mappls'
  trafficEnabled: true,
  zoneMarkers: {}, // map of zone_id -> circle/marker layer
  poiMarkers: [],  // nearby POI layers
  routeLayer: null,
  snapRawLayer: null,
  snapCleanLayer: null,
  activeZoneId: null,
  chartHaeFlowInstance: null
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
  initNavbarDropdowns();
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
    if (APP.map) { renderMapZones(); } else { renderZoneMap(); }
  });

  // Clusters toggle
  document.getElementById('toggleClusters').addEventListener('change', (e) => {
    APP.showClusters = e.target.checked;
    if (APP.map) { renderMapZones(); } else { renderZoneMap(); }
  });

  // Heat radius slider
  document.getElementById('heatRadius').addEventListener('input', (e) => {
    APP.heatRadius = parseInt(e.target.value);
    document.getElementById('heatRadiusVal').textContent = APP.heatRadius;
    if (APP.map) { renderMapZones(); } else { renderZoneMap(); }
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

    // Initialize interactive map after dashboard data is populated
    initInteractiveMap();

    // Start Live Simulation
    if (!APP.liveInterval) {
      const savedInterval = parseInt(localStorage.getItem('gridlock_sim_interval'));
      const simInterval = (savedInterval !== null && !isNaN(savedInterval)) ? savedInterval : 2500;
      if (simInterval > 0) {
        APP.liveInterval = setInterval(simulateLiveFeed, simInterval);
      }
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

    const mapContainer = document.getElementById('mapContainer');
    if (APP.futureMinutes > 0) {
      if (mapContainer) mapContainer.classList.add('future-mode');
      showToast("Predictive Traffic", `Simulating conditions for T+${APP.futureMinutes} minutes.`, "warning");
    } else {
      if (mapContainer) mapContainer.classList.remove('future-mode');
    }
  } catch (err) {
    console.error('Simulation reload failed:', err);
  }
}

// ── Live Simulation Engine ───────────────────────────────────────────────
function simulateLiveFeed() {
  if (APP.zones.length === 0 || APP.futureMinutes > 0) return;

  let changed = false;

  APP.zones.forEach(z => {
    if (APP.resolvingZones.has(z.zone_id)) {
      z.impact_score -= 0.05 + (Math.random() * 0.02);
      z.violation_count = Math.max(0, z.violation_count - Math.floor(Math.random() * 5 + 2));
      changed = true;

      if (z.impact_score <= 0.4) {
        z.impact_score = Math.max(0.2, z.impact_score);
        APP.resolvingZones.delete(z.zone_id);
      }
    } else {
      if (Math.random() < 0.3) {
        z.impact_score += 0.04 + (Math.random() * 0.08);
        z.violation_count += Math.floor(Math.random() * 8 + 2);
        changed = true;
      } else {
        z.impact_score += (Math.random() - 0.5) * 0.02;
        z.impact_score = Math.max(0.1, z.impact_score);
        changed = true;
      }

      if (APP.dispatchMode !== 'manual' && z.impact_score >= 0.80 && Math.random() < 0.7) {
        if (!APP.resolvingZones.has(z.zone_id)) {
          APP.resolvingZones.add(z.zone_id);
        }
      }
    }

    z.impact_score = Math.min(0.99, Math.max(0.01, z.impact_score));

    if (z.impact_score > 0.8) z.severity = "CRITICAL";
    else if (z.impact_score > 0.6) z.severity = "HIGH";
    else if (z.impact_score > 0.4) z.severity = "MEDIUM";
    else z.severity = "LOW";
  });

  if (changed) {
    APP.zones.sort((a, b) => b.impact_score - a.impact_score);

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
  updateNotifications();
  
  const analyticsActive = document.getElementById('tab-analytics')?.classList.contains('active');
  if (analyticsActive) {
    analyticsRendered = false;
    renderAnalyticsCharts();
  }
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
  const top = APP.zones[0];
  const label = getZoneLabel(top.zone_id);
  const alertEl = document.getElementById('alertText');

  if (APP.futureMinutes > 0) {
    alertEl.innerHTML = `<strong>PREDICTIVE ALERT (T+${APP.futureMinutes}min):</strong> ${top.zone_id} — ${label} spillover expanding. Impact Score: ${top.impact_score.toFixed(4)}`;
  } else {
    alertEl.innerHTML = `<strong>ACTIVE ALERT:</strong> ${top.zone_id} — ${label} IS A CRITICAL ZONE REQUIRING IMMEDIATE ACTION. Impact Score: ${top.impact_score.toFixed(4)}`;
  }
}

// ══════════════════════════════════════════════════════════════════════════
// MAP DECORATOR / CONTROLLER (Canvas & Interactive Map Toggles)
// ══════════════════════════════════════════════════════════════════════════
let mapAnimStarted = false;

function renderZoneMap() {
  if (APP.map) {
    // If interactive map initialized, render zones there!
    renderMapZones();
    return;
  }
  if (!mapAnimStarted) {
    mapAnimStarted = true;
    requestAnimationFrame(drawMapFrame);
  }
}

// ── Helper: Draw Hexagon (H3 Style) ──────────────────────────────────────
function drawHexagon(ctx, x, y, size) {
  for (let i = 0; i < 6; i++) {
    const angle_deg = 60 * i - 30;
    const angle_rad = Math.PI / 180 * angle_deg;
    const hx = x + size * Math.cos(angle_rad);
    const hy = y + size * Math.sin(angle_rad);
    if (i === 0) ctx.moveTo(hx, hy);
    else ctx.lineTo(hx, hy);
  }
  ctx.closePath();
}

function drawMapFrame() {
  // If interactive map is running, terminate canvas loop to save performance
  if (APP.map) return;
  
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

  ctx.fillStyle = isLight ? '#e2e8f0' : '#080d19';
  ctx.fillRect(0, 0, W, H);

  drawGrid(ctx, W, H, isLight);

  if (APP.zones.length === 0) return;

  const lats = APP.zones.map(z => z.center_lat);
  const lngs = APP.zones.map(z => z.center_lng);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);

  const pad = 60;
  const mapW = W - pad * 2;
  const mapH = H - pad * 2;

  function project(lat, lng) {
    const x = pad + ((lng - minLng) / (maxLng - minLng || 1)) * mapW;
    const y = pad + ((maxLat - lat) / (maxLat - minLat || 1)) * mapH;
    return [x, y];
  }

  const displayZones = APP.zones.slice(0, 20);

  APP.canvasZones = displayZones.map(z => {
    const [x, y] = project(z.center_lat, z.center_lng);
    const maxV = Math.max(...displayZones.map(d => d.violation_count));
    const minR = 22, maxR = 65;
    const r = minR + ((z.violation_count / (maxV || 1)) * (maxR - minR));
    return { zone: z, x, y, r };
  });

  if (APP.showClusters) {
    drawConnections(ctx, time, isLight);
  }

  if (APP.showHeatmap) {
    ctx.globalCompositeOperation = isLight ? 'multiply' : 'screen'; 
    APP.canvasZones.forEach(cz => {
      let hR = cz.r * (APP.heatRadius / 8);
      if (cz.zone.severity === 'CRITICAL') {
        hR += Math.sin(time / 150) * 15;
      }
      const gradient = ctx.createRadialGradient(cz.x, cz.y, 0, cz.x, cz.y, Math.max(1, hR));
      const color = getSeverityColor(cz.zone.severity);
      gradient.addColorStop(0, color + (isLight ? '40' : '70')); 
      gradient.addColorStop(1, color + '00');
      ctx.fillStyle = gradient;
      ctx.fillRect(cz.x - hR * 2, cz.y - hR * 2, hR * 4, hR * 4);
    });
    ctx.globalCompositeOperation = 'source-over';
  }

  APP.canvasZones.forEach((cz, i) => {
    const color = getSeverityColor(cz.zone.severity);
    const isHovered = APP.hoveredZone === i;

    ctx.beginPath();
    let pulse = 0;
    if (cz.zone.severity === 'CRITICAL') {
      pulse = Math.sin(time / 150) * 8;
    }
    drawHexagon(ctx, cz.x, cz.y, Math.max(1, cz.r + 6 + pulse));
    ctx.strokeStyle = color + (isHovered ? '60' : '25');
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.stroke();
    ctx.setLineDash([]);

    if (APP.resolvingZones && APP.resolvingZones.has(cz.zone.zone_id)) {
       for (let p = 0; p < 3; p++) {
         const offset = p * 400;
         let progress = ((time + offset) % 1200) / 1200;
         const radarR = progress * (cz.r * 2.5);
         ctx.beginPath();
         drawHexagon(ctx, cz.x, cz.y, cz.r + radarR);
         ctx.strokeStyle = `rgba(0, 229, 255, ${1 - progress})`;
         ctx.lineWidth = 2;
         ctx.stroke();
       }
    }

    ctx.beginPath();
    drawHexagon(ctx, cz.x, cz.y, cz.r);
    const fillGrad = ctx.createRadialGradient(cz.x, cz.y, 0, cz.x, cz.y, cz.r);
    fillGrad.addColorStop(0, color + (isHovered ? '50' : '30'));
    fillGrad.addColorStop(1, color + (isHovered ? '20' : '10'));
    ctx.fillStyle = fillGrad;
    ctx.fill();

    ctx.beginPath();
    drawHexagon(ctx, cz.x, cz.y, cz.r);
    ctx.strokeStyle = color + (isHovered ? 'cc' : (isLight ? 'aa' : '80'));
    ctx.lineWidth = isHovered ? 2.5 : 1.5;
    ctx.stroke();

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
      if (dist < 200) {
        ctx.beginPath();
        ctx.moveTo(zones[i].x, zones[i].y);
        ctx.lineTo(zones[j].x, zones[j].y);
        ctx.strokeStyle = isLight ? 'rgba(0, 0, 0, 0.15)' : 'rgba(26, 35, 64, 0.5)';
        ctx.stroke();

        const speed = 0.0005 + ((i + j) % 5) * 0.0002;
        const progress = ((time * speed) + (i * 0.1) + (j * 0.2)) % 1;
        const dotX = zones[i].x - dx * progress;
        const dotY = zones[i].y - dy * progress;

        ctx.beginPath();
        ctx.arc(dotX, dotY, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = getSeverityColor(zones[i].zone.severity) + 'CC'; 
        ctx.fill();
        ctx.shadowBlur = 5;
        ctx.shadowColor = ctx.fillStyle;
        ctx.fill();
        ctx.shadowBlur = 0;
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
    LOW: '#00e676',
  }[severity] || '#8892a8';
}

// ── Canvas Mouse Interaction (Legacy Fallback) ───────────────────────────
(function initCanvasEvents() {
  document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('zoneCanvas');
    const tooltip = document.getElementById('mapTooltip');

    canvas.addEventListener('mousemove', (e) => {
      if (APP.map) return; // ignore legacy events if map is active
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

        const container = document.getElementById('mapContainer');
        const cr = container.getBoundingClientRect();
        let tx = e.clientX - cr.left + 16;
        let ty = e.clientY - cr.top - 10;
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
      if (APP.map) return;
      APP.hoveredZone = null;
      tooltip.classList.remove('visible');
      renderZoneMap();
    });

    window.addEventListener('resize', () => {
      if (APP.zones.length > 0) renderZoneMap();
    });
  });
})();

// ══════════════════════════════════════════════════════════════════════════
// MAPPLS INTEGRATION (Vector map and APIs handlers)
// ══════════════════════════════════════════════════════════════════════════

// ── Normalize zone radius in meters for map overlay ──────────────────────
function normalizeRadius(violationCount) {
  const minR = 300, maxR = 900;
  const maxV = APP.zones.length > 0 ? Math.max(...APP.zones.map(z => z.violation_count)) : 100;
  const baseRadius = minR + ((violationCount / (maxV || 1)) * (maxR - minR));
  const factor = APP.heatRadius ? (APP.heatRadius / 12) : 1;
  return baseRadius * factor;
}

// ── Dynamic Map Initialization ───────────────────────────────────────────
async function initInteractiveMap() {
  if (APP.map) return;

  let mapplsLoaded = false;
  try {
    const res = await fetch('/api/mappls/token');
    const data = await res.json();
    if (!data.is_mock) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = `https://sdk.mappls.com/map/sdk/web?v=3.0&access_token=${data.access_token}`;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
      });
      mapplsLoaded = true;
      APP.mapMode = 'mappls';
      console.log("[GridLock AI] Mappls Vector Map JS SDK loaded successfully.");
    }
  } catch (err) {
    console.warn("Mappls SDK failed to load. Falling back to Leaflet:", err);
  }

  if (!mapplsLoaded) {
    APP.mapMode = 'leaflet';
    const statusDot = document.getElementById('consoleStatus');
    statusDot.classList.remove('green');
    statusDot.classList.add('orange');
    statusDot.title = "Active (Leaflet Simulation Mode)";

    // Initialize Leaflet Map
    APP.map = L.map('map', {
      center: [12.9716, 77.5946],
      zoom: 12,
      zoomControl: true,
      zoomAnimation: true
    });

    // Dark Map Tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; CartoDB'
    }).addTo(APP.map);
  } else {
    // Initialize Mappls Vector Map
    APP.map = new mappls.Map('map', {
      center: {lat: 12.9716, lng: 77.5946},
      zoom: 12
    });
  }

  // Setup Event Listeners and Plot initial zones
  initMapplsConsole();
  renderMapZones();
}

// ── Render Hexagonal Zones on Interactive Map ────────────────────────────
function renderMapZones() {
  // Clear all existing layers
  for (let id in APP.zoneMarkers) {
    if (APP.mapMode === 'leaflet') {
      APP.map.removeLayer(APP.zoneMarkers[id]);
    } else {
      APP.zoneMarkers[id].remove();
    }
  }
  APP.zoneMarkers = {};

  if (APP.heatGlows) {
    APP.heatGlows.forEach(g => APP.map.removeLayer(g));
  }
  APP.heatGlows = [];

  if (APP.clusterLines) {
    APP.clusterLines.forEach(line => APP.map.removeLayer(line));
  }
  APP.clusterLines = [];

  const displayZones = APP.zones.slice(0, 30);

  displayZones.forEach(z => {
    const color = getSeverityColor(z.severity);
    const baseR = normalizeRadius(z.violation_count);
    const r = baseR * (APP.heatRadius / 12);
    const isResolving = APP.resolvingZones && APP.resolvingZones.has(z.zone_id);

    if (APP.mapMode === 'leaflet') {

      // ── Heatmap Glow Layer (thermal spectrum circles underneath hex) ──
      if (APP.showHeatmap) {
        const thermalGradients = {
          CRITICAL: { outer: '#ff9100', mid: '#ff3d00', inner: '#ff1744' },
          HIGH:     { outer: '#ffc400', mid: '#ff9100', inner: '#ff6d00' },
          MEDIUM:   { outer: '#ffee58', mid: '#fbc02d', inner: '#fbbf24' },
          LOW:      { outer: '#a7ffeb', mid: '#69f0ae', inner: '#00e676' }
        };
        const grad = thermalGradients[z.severity] || { outer: color, mid: color, inner: color };

        // Outer glow (faintest, largest)
        const glowOuter = L.circle([z.center_lat, z.center_lng], {
          radius: r * 2.2,
          color: 'transparent',
          fillColor: grad.outer,
          fillOpacity: 0.05,
          weight: 0,
          interactive: false
        }).addTo(APP.map);
        APP.heatGlows.push(glowOuter);

        // Mid glow
        const glowMid = L.circle([z.center_lat, z.center_lng], {
          radius: r * 1.5,
          color: 'transparent',
          fillColor: grad.mid,
          fillOpacity: 0.12,
          weight: 0,
          interactive: false
        }).addTo(APP.map);
        APP.heatGlows.push(glowMid);

        // Inner glow (most intense, smallest)
        const glowInner = L.circle([z.center_lat, z.center_lng], {
          radius: r * 0.9,
          color: 'transparent',
          fillColor: grad.inner,
          fillOpacity: 0.20,
          weight: 0,
          interactive: false
        }).addTo(APP.map);
        APP.heatGlows.push(glowInner);
      }

      // ── H3 Hexagon (main zone marker) ──
      const hexCoords = [];
      const latR = r / 111320;
      const lngR = r / (111320 * Math.cos(z.center_lat * (Math.PI / 180)));
      for (let i = 0; i < 6; i++) {
        const angle = (60 * i - 30) * (Math.PI / 180);
        hexCoords.push([z.center_lat + latR * Math.sin(angle), z.center_lng + lngR * Math.cos(angle)]);
      }

      const hexStyle = {
        color: isResolving ? '#00e5ff' : color,
        fillColor: color,
        fillOpacity: APP.showHeatmap ? 0.35 : 0.08,
        opacity: APP.showHeatmap ? 0.9 : 0.3,
        weight: isResolving ? 3 : (APP.showHeatmap ? 2 : 0.5),
        className: isResolving ? 'leaflet-radar-ripple' : ''
      };

      const circle = L.polygon(hexCoords, hexStyle).addTo(APP.map);

      // ── Hover Tooltip ──
      circle.on('mouseover', async (e) => {
        APP.hoveredZone = z.zone_id;
        let address = "Geocoding coordinates via API...";
        circle.setStyle({ fillOpacity: 0.55, weight: 3 });

        try {
          const geoRes = await fetch(`/api/mappls/rev_geocode?lat=${z.center_lat}&lng=${z.center_lng}`);
          const geoData = await geoRes.json();
          if (geoData.results && geoData.results[0]) {
            address = geoData.results[0].formatted_address;
          }
        } catch (err) {
          address = getZoneLabel(z.zone_id);
        }

        const tooltip = document.getElementById('mapTooltip');
        document.getElementById('tooltipTitle').textContent = `${z.zone_id} — ${address}`;
        document.getElementById('tooltipImpact').textContent = z.impact_score.toFixed(4);
        document.getElementById('tooltipRisk').textContent = z.risk_score.toFixed(6);
        document.getElementById('tooltipViolations').textContent = z.violation_count.toLocaleString();
        document.getElementById('tooltipPriority').textContent = `#${z.enforcement_priority}`;

        const container = document.getElementById('mapContainer');
        const cr = container.getBoundingClientRect();
        let tx = e.originalEvent.clientX - cr.left + 16;
        let ty = e.originalEvent.clientY - cr.top - 10;

        if (tx + 280 > container.clientWidth) tx = e.originalEvent.clientX - cr.left - 280;
        if (ty + 120 > container.clientHeight) ty = container.clientHeight - 130;

        tooltip.style.left = tx + 'px';
        tooltip.style.top = ty + 'px';
        tooltip.classList.add('visible');
      });

      circle.on('mouseout', () => {
        document.getElementById('mapTooltip').classList.remove('visible');
        circle.setStyle({
          fillOpacity: APP.showHeatmap ? 0.35 : 0.08,
          weight: APP.showHeatmap ? 2 : 0.5,
          opacity: APP.showHeatmap ? 0.9 : 0.3
        });
      });

      circle.on('click', () => {
        selectZoneForConsole(z.zone_id);
      });

      APP.zoneMarkers[z.zone_id] = circle;

    } else {
      // Mappls Vector Circle Overlay
      try {
        const mapCircle = new mappls.Circle({
          map: APP.map,
          center: {lat: z.center_lat, lng: z.center_lng},
          radius: r,
          fillColor: color,
          strokeColor: color,
          fillOpacity: APP.showHeatmap ? 0.2 : 0,
          strokeOpacity: APP.showHeatmap ? 0.8 : 0,
          strokeWeight: APP.showHeatmap ? 1.5 : 0
        });

        mapCircle.addListener('click', () => {
          selectZoneForConsole(z.zone_id);
        });

        APP.zoneMarkers[z.zone_id] = mapCircle;
      } catch (e) {
        console.error("Mappls circle rendering error:", e);
      }
    }
  });

  // ── Cluster Network Lines ──
  if (APP.mapMode === 'leaflet' && APP.showClusters) {
    const distThreshold = 0.06;
    for (let i = 0; i < displayZones.length; i++) {
      for (let j = i + 1; j < displayZones.length; j++) {
        const a = displayZones[i], b = displayZones[j];
        const dist = Math.sqrt(
          Math.pow(a.center_lat - b.center_lat, 2) +
          Math.pow(a.center_lng - b.center_lng, 2)
        );
        if (dist < distThreshold) {
          const avgImpact = (a.impact_score + b.impact_score) / 2;
          let lineColor = '#00e5ff';
          let lineWeight = 1.5;
          if (avgImpact > 0.7) { lineColor = '#ff1744'; lineWeight = 3; }
          else if (avgImpact > 0.5) { lineColor = '#ff9100'; lineWeight = 2.5; }
          else if (avgImpact > 0.3) { lineColor = '#fbbf24'; lineWeight = 2; }

          const line = L.polyline([
            [a.center_lat, a.center_lng],
            [b.center_lat, b.center_lng]
          ], {
            color: lineColor,
            weight: lineWeight,
            dashArray: '8, 6',
            opacity: 0.9,
            className: 'cluster-line-animated'
          }).addTo(APP.map);
          APP.clusterLines.push(line);

          // Midpoint dot for visual flair
          const dot = L.circleMarker([
            (a.center_lat + b.center_lat) / 2,
            (a.center_lng + b.center_lng) / 2
          ], {
            radius: 3,
            fillColor: lineColor,
            fillOpacity: 0.7,
            color: lineColor,
            weight: 1,
            interactive: false
          }).addTo(APP.map);
          APP.clusterLines.push(dot);
        }
      }
    }
  }

  MapManager.recenter(12.9716, 77.5946);
  MapManager.setTraffic(APP.trafficEnabled);
}


// ── Click zone handler to update Console ───────────────────────────────────
function selectZoneForConsole(zoneId) {
  APP.activeZoneId = zoneId;
  const z = APP.zones.find(zone => zone.zone_id === zoneId);
  const label = getZoneLabel(zoneId);

  const list = document.getElementById('nearbyList');
  list.innerHTML = `<li style="background: rgba(0, 229, 255, 0.05); border-color: var(--accent-cyan);">
    Selected Target: <strong>${label} (${zoneId})</strong>
  </li>`;

  if (!document.getElementById('predictiveFlowBox').classList.contains('hidden')) {
    showHaeFlowForZone(zoneId);
  }

  // Highlight Leaflet circle temporarily
  if (APP.mapMode === 'leaflet') {
    const circle = APP.zoneMarkers[zoneId];
    if (circle) {
      circle.setStyle({ fillOpacity: 0.6, weight: 3 });
      setTimeout(() => circle.setStyle({ fillOpacity: 0.2, weight: 1.5 }), 1200);
    }
  }
}

// ── MapManager Abstraction Layer for clean API calls ───────────────────────
const MapManager = {
  recenter(lat, lng) {
    if (APP.mapMode === 'leaflet') {
      APP.map.setView([lat, lng], 12);
    } else {
      try {
        APP.map.setCenter({lat: lat, lng: lng});
        APP.map.setZoom(12);
      } catch (e) {}
    }
  },

  setTraffic(enabled) {
    if (APP.mapMode === 'mappls') {
      try {
        APP.map.enableTraffic(enabled);
      } catch (err) {
        console.warn("Mappls traffic layer API error:", err);
      }
    } else {
      // Simulate real-time Traffic Flow vectors on Leaflet map
      if (enabled) {
        if (!APP.leafletTrafficLayers) {
          APP.leafletTrafficLayers = [];
          const mainRoads = [
            // Outer Ring Road (Green flow)
            { coords: [[12.9176, 77.6238], [12.9340, 77.6220], [12.9562, 77.6300], [12.9780, 77.6410]], color: '#00e676', speed: '52 km/h (Free Flow)' },
            // Hosur Road (Red flow)
            { coords: [[12.9010, 77.6110], [12.9176, 77.6238], [12.9300, 77.6350], [12.9420, 77.6420]], color: '#ff1744', speed: '14 km/h (Heavy Traffic)' },
            // Jayanagar 11th Main (Yellow flow)
            { coords: [[12.9250, 77.5900], [12.9300, 77.6000], [12.9340, 77.6100], [12.9340, 77.6220]], color: '#fbbf24', speed: '31 km/h (Moderate Traffic)' },
            // MG Road (Red flow)
            { coords: [[12.9740, 77.5900], [12.9750, 77.6000], [12.9750, 77.6100], [12.9755, 77.6250]], color: '#ff1744', speed: '9 km/h (Congested Gridlock)' }
          ];

          mainRoads.forEach(r => {
            const poly = L.polyline(r.coords, {
              color: r.color,
              weight: 4,
              opacity: 0.55,
              dashArray: '6, 8'
            }).addTo(APP.map);
            poly.bindTooltip(`Traffic Speed: ${r.speed}`, { sticky: true });
            APP.leafletTrafficLayers.push(poly);
          });
        } else {
          APP.leafletTrafficLayers.forEach(l => APP.map.addLayer(l));
        }
      } else {
        if (APP.leafletTrafficLayers) {
          APP.leafletTrafficLayers.forEach(l => APP.map.removeLayer(l));
        }
      }
    }
  },

  clearPois() {
    if (APP.mapMode === 'leaflet') {
      APP.poiMarkers.forEach(m => APP.map.removeLayer(m));
    } else {
      APP.poiMarkers.forEach(m => m.remove());
    }
    APP.poiMarkers = [];
  },

  drawPoiMarkers(pois) {
    this.clearPois();
    pois.forEach(poi => {
      const lat = poi.lat || (12.9716 + (Math.random() - 0.5) * 0.04);
      const lng = poi.lng || (77.5946 + (Math.random() - 0.5) * 0.04);
      const isPolice = poi.placeName.toLowerCase().includes("police");
      const iconText = isPolice ? "🚓" : "🔧";
      const color = isPolice ? "#2979ff" : "#ff9100";

      if (APP.mapMode === 'leaflet') {
        const markerIcon = L.divIcon({
          className: 'map-pulse-marker',
          html: `<div class="map-pulse-ring" style="--pulse-color:${color}"></div><div class="map-pulse-dot" style="background-color:${color}"></div><div style="font-size:16px; position:absolute; left:12px; top:-12px; filter:drop-shadow(0 0 4px rgba(0,0,0,0.5));">${iconText}</div>`,
          iconSize: [20, 20]
        });
        const marker = L.marker([lat, lng], { icon: markerIcon }).addTo(APP.map);
        marker.bindTooltip(poi.placeName, { direction: 'top' });
        marker.on('click', () => showPlaceDetail(poi.eLoc));
        APP.poiMarkers.push(marker);
      } else {
        try {
          const marker = new mappls.Marker({
            map: APP.map,
            position: {lat: lat, lng: lng},
            html: `<div style="font-size: 24px; cursor: pointer;">${iconText}</div>`,
            width: 32,
            height: 32
          });
          marker.addListener('click', () => showPlaceDetail(poi.eLoc));
          APP.poiMarkers.push(marker);
        } catch (e) {
          console.error("Mappls marker placement error:", e);
        }
      }
    });
  },

  clearRoutes() {
    if (APP.mapMode === 'leaflet') {
      if (APP.routeLayer) APP.map.removeLayer(APP.routeLayer);
      if (APP.snapRawLayer) APP.map.removeLayer(APP.snapRawLayer);
      if (APP.snapCleanLayer) APP.map.removeLayer(APP.snapCleanLayer);
    } else {
      if (APP.routeLayer) APP.routeLayer.remove();
      if (APP.snapRawLayer) APP.snapRawLayer.remove();
      if (APP.snapCleanLayer) APP.snapCleanLayer.remove();
    }
    APP.routeLayer = null;
    APP.snapRawLayer = null;
    APP.snapCleanLayer = null;
  },

  drawRoutePolyline(geom) {
    this.clearRoutes();
    if (APP.mapMode === 'leaflet') {
      APP.routeLayer = L.polyline(geom, {
        color: '#ff9100',
        weight: 5,
        opacity: 0.8,
        lineCap: 'round',
        lineJoin: 'round'
      }).addTo(APP.map);
      APP.map.fitBounds(APP.routeLayer.getBounds(), { padding: [40, 40] });
    } else {
      try {
        const paths = geom.map(p => ({lat: p[0], lng: p[1]}));
        APP.routeLayer = new mappls.Polyline({
          map: APP.map,
          paths: paths,
          strokeColor: '#ff9100',
          strokeWeight: 5,
          strokeOpacity: 0.8
        });
        APP.map.setCenter(paths[0]);
      } catch (e) {
        console.error("Mappls routing line error:", e);
      }
    }
  },

  drawSnapTrail(rawPts, snappedPts) {
    this.clearRoutes();
    if (APP.mapMode === 'leaflet') {
      APP.snapRawLayer = L.polyline(rawPts, {
        color: '#ff1744',
        weight: 3.5,
        dashArray: '4, 8',
        opacity: 0.7
      }).addTo(APP.map);

      APP.snapCleanLayer = L.polyline(snappedPts, {
        color: '#00e676',
        weight: 5,
        opacity: 0.85
      }).addTo(APP.map);

      APP.map.fitBounds(APP.snapCleanLayer.getBounds(), { padding: [30, 30] });
    } else {
      try {
        APP.snapRawLayer = new mappls.Polyline({
          map: APP.map,
          paths: rawPts.map(p => ({lat: p[0], lng: p[1]})),
          strokeColor: '#ff1744',
          strokeWeight: 3.5,
          strokeOpacity: 0.7
        });

        APP.snapCleanLayer = new mappls.Polyline({
          map: APP.map,
          paths: snappedPts.map(p => ({lat: p[0], lng: p[1]})),
          strokeColor: '#00e676',
          strokeWeight: 5,
          strokeOpacity: 0.85
        });
      } catch (e) {
        console.error("Mappls GPS snapping overlay error:", e);
      }
    }
  }
};

// ── Initialize console event controllers ──────────────────────────────────
function initMapplsConsole() {
  // Toggle traffic
  const btnToggleTraffic = document.getElementById('btnToggleTraffic');
  btnToggleTraffic.addEventListener('click', () => {
    APP.trafficEnabled = !APP.trafficEnabled;
    btnToggleTraffic.classList.toggle('active', APP.trafficEnabled);
    MapManager.setTraffic(APP.trafficEnabled);
  });

  // Recenter map
  document.getElementById('btnRecenter').addEventListener('click', () => {
    MapManager.recenter(12.9716, 77.5946);
  });

  // Calculate Route (Route ETA API Traffic & Road Details API)
  document.getElementById('btnCalculateRoute').addEventListener('click', async () => {
    if (APP.zones.length < 2) return;
    const z1 = APP.zones[0]; // Top critical zone
    const z2 = APP.zones[1]; // Second critical zone

    try {
      const res = await fetch(`/api/mappls/route?start_lat=${z1.center_lat}&start_lng=${z1.center_lng}&end_lat=${z2.center_lat}&end_lng=${z2.center_lng}`);
      const data = await res.json();
      
      if (data.routes && data.routes[0]) {
        const route = data.routes[0];
        MapManager.drawRoutePolyline(route.geometry);

        // Fetch Road Details
        const rDetailsRes = await fetch(`/api/mappls/road_details?lat=${z1.center_lat}&lng=${z1.center_lng}`);
        const rDetails = await rDetailsRes.json();

        // Reveal route metrics card
        const infoBox = document.getElementById('routeInfoBox');
        infoBox.classList.remove('hidden');

        document.getElementById('routePathText').textContent = `${z1.zone_id} ➔ ${z2.zone_id}`;
        document.getElementById('routeDistanceText').textContent = `${(route.distance / 1000).toFixed(2)} km`;
        document.getElementById('routeEtaText').textContent = `${Math.ceil(route.duration / 60)} mins`;
        
        const trafficTag = document.getElementById('routeTrafficText');
        const delayMins = Math.ceil(route.traffic_delay / 60);
        if (delayMins > 0) {
          trafficTag.className = "traffic-tag";
          trafficTag.textContent = `+${delayMins}m traffic delay`;
        } else {
          trafficTag.className = "traffic-tag green";
          trafficTag.textContent = "Free Flow";
        }

        document.getElementById('routeRoadTypeText').textContent = rDetails.road_type;
        document.getElementById('routeSpeedText').textContent = `${rDetails.speed_limit_kmh} km/h (Lanes: ${rDetails.lanes})`;
      }
    } catch (err) {
      console.error("Route calculation error:", err);
    }
  });

  // Snap to Road V2 API simulation
  document.getElementById('btnSnapRoad').addEventListener('click', async () => {
    if (APP.zones.length < 1) return;
    const z = APP.zones[0];
    const lat = z.center_lat;
    const lng = z.center_lng;

    // Simulate noisy raw GPS data trail
    const rawPts = [
      [lat - 0.006 + (Math.random() - 0.5) * 0.0008, lng - 0.006 + (Math.random() - 0.5) * 0.0008],
      [lat - 0.003 + (Math.random() - 0.5) * 0.0008, lng - 0.003 + (Math.random() - 0.5) * 0.0008],
      [lat + (Math.random() - 0.5) * 0.0012, lng + (Math.random() - 0.5) * 0.0012],
      [lat + 0.003 + (Math.random() - 0.5) * 0.0008, lng + 0.003 + (Math.random() - 0.5) * 0.0008],
      [lat + 0.006 + (Math.random() - 0.5) * 0.0008, lng + 0.006 + (Math.random() - 0.5) * 0.0008]
    ];

    const ptsQuery = rawPts.map(p => `${p[0]},${p[1]}`).join('|');

    try {
      const res = await fetch(`/api/mappls/snap_to_road?pts=${ptsQuery}`);
      const data = await res.json();
      
      if (data.snappedPoints) {
        const snappedPts = data.snappedPoints.map(p => [p.latitude, p.longitude]);
        MapManager.drawSnapTrail(rawPts, snappedPts);

        // Display results
        const infoBox = document.getElementById('routeInfoBox');
        infoBox.classList.remove('hidden');

        document.getElementById('routePathText').textContent = "Patrol Trail Snapping";
        document.getElementById('routeDistanceText').textContent = "Snapped via Road V2 API";
        document.getElementById('routeEtaText').textContent = "Red: Raw GPS | Green: Snapped Path";
        document.getElementById('routeTrafficText').className = "traffic-tag green";
        document.getElementById('routeTrafficText').textContent = "Aligned";
        document.getElementById('routeRoadTypeText').textContent = "Arterial Congestion Grid";
        document.getElementById('routeSpeedText').textContent = "Locked to Road Segments";
      }
    } catch (err) {
      console.error("GPS Snap API error:", err);
    }
  });

  // Nearby Responder Search
  document.getElementById('btnSearchNearby').addEventListener('click', async () => {
    const activeZone = APP.activeZoneId || (APP.zones.length > 0 ? APP.zones[0].zone_id : null);
    if (!activeZone) return;

    const z = APP.zones.find(zone => zone.zone_id === activeZone);
    const searchType = document.getElementById('nearbySearchType').value;

    try {
      const res = await fetch(`/api/mappls/nearby?lat=${z.center_lat}&lng=${z.center_lng}&keyword=${searchType}`);
      const data = await res.json();
      
      const list = document.getElementById('nearbyList');
      if (data.suggestedLocations && data.suggestedLocations.length > 0) {
        MapManager.drawPoiMarkers(data.suggestedLocations);

        list.innerHTML = data.suggestedLocations.map(poi => {
          return `<li onclick="showPlaceDetail('${poi.eLoc}')">
            <strong>${poi.placeName}</strong> (${poi.distance}m)
            <br/><span style="font-size:9px;color:var(--text-muted);">${poi.placeAddress}</span>
          </li>`;
        }).join('');
      } else {
        list.innerHTML = `<li class="placeholder">No active responders found within 2km.</li>`;
      }
    } catch (err) {
      console.error("Nearby responder lookup failed:", err);
    }
  });

  // Close Place details card
  document.getElementById('btnHidePlaceDetail').addEventListener('click', () => {
    document.getElementById('placeDetailCard').classList.add('hidden');
  });

  // Distance Matrix calculation
  document.getElementById('btnShowMatrix').addEventListener('click', async () => {
    const topZones = APP.zones.slice(0, 5);
    if (topZones.length === 0) return;

    const originsQuery = topZones.map(z => `${z.center_lat},${z.center_lng}`).join(';');
    const destinationsQuery = originsQuery; // Compute square matrix

    try {
      const res = await fetch(`/api/mappls/distance_matrix?origins=${originsQuery}&destinations=${destinationsQuery}`);
      const data = await res.json();
      
      const box = document.getElementById('matrixGridBox');
      box.classList.remove('hidden');
      const grid = document.getElementById('matrixGrid');

      // Build grid cells
      let html = '<div class="matrix-cell header">Loc</div>';
      topZones.forEach(z => {
        html += `<div class="matrix-cell header" title="${z.zone_id}">${z.zone_id.replace('Z_','')}</div>`;
      });

      for (let i = 0; i < topZones.length; i++) {
        html += `<div class="matrix-cell header" title="${topZones[i].zone_id}">${topZones[i].zone_id.replace('Z_','')}</div>`;
        for (let j = 0; j < topZones.length; j++) {
          if (i === j) {
            html += `<div class="matrix-cell" style="color:var(--text-muted);">--</div>`;
          } else {
            const distKm = (data.results.distances[i][j] / 1000).toFixed(1);
            const durMin = Math.ceil(data.results.durations[i][j] / 60);
            html += `<div class="matrix-cell" title="Distance: ${distKm}km">${durMin}m</div>`;
          }
        }
      }
      grid.innerHTML = html;
    } catch (err) {
      console.error("Distance matrix API calculation failed:", err);
    }
  });

  // HAE (Historical Average Speed) Predictive traffic flow
  document.getElementById('btnShowHae').addEventListener('click', () => {
    const activeZone = APP.activeZoneId || (APP.zones.length > 0 ? APP.zones[0].zone_id : "Z_68_85");
    const box = document.getElementById('predictiveFlowBox');
    box.classList.remove('hidden');
    showHaeFlowForZone(activeZone);
  });
}

// ── Show Place Detail (Place Detail API eLoc entity lookup) ────────────────
window.showPlaceDetail = async function(eloc) {
  try {
    const res = await fetch(`/api/mappls/place_detail?eloc=${eloc}`);
    const data = await res.json();
    
    const card = document.getElementById('placeDetailCard');
    card.classList.remove('hidden');

    document.getElementById('placeDetailName').textContent = data.placeName;
    document.getElementById('placeDetailType').textContent = data.type || "Responder Hub";
    document.getElementById('placeDetailAddr').textContent = data.address;
    document.getElementById('placeDetailPhone').textContent = data.phone;
    document.getElementById('placeDetailRating').textContent = `★ ${data.rating} / 5.0`;

    if (data.lat && data.lng) {
      MapManager.recenter(data.lat, data.lng);
    }
  } catch (err) {
    console.error("Place detail API entity lookup failed:", err);
  }
};

// ── Render HAE chart profile using Chart.js ────────────────────────────────
async function showHaeFlowForZone(zoneId) {
  try {
    const res = await fetch(`/api/mappls/predictive_flow?zone_id=${zoneId}`);
    const data = await res.json();
    
    const ctx = document.getElementById('chartHaeFlow').getContext('2d');
    if (APP.chartHaeFlowInstance) {
      APP.chartHaeFlowInstance.destroy();
    }

    APP.chartHaeFlowInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.hours.map(h => `${h}:00`),
        datasets: [{
          label: 'Avg Speed (km/h)',
          data: data.historical_avg_speeds_kmh,
          borderColor: '#ff9100',
          backgroundColor: 'rgba(255, 145, 0, 0.08)',
          borderWidth: 1.5,
          fill: true,
          tension: 0.35,
          pointRadius: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#8892a8', font: { size: 6.5 } }
          },
          y: {
            grid: { color: 'rgba(26, 35, 64, 0.2)' },
            ticks: { color: '#8892a8', font: { size: 6.5 } },
            min: 0,
            max: 50
          }
        }
      }
    });
  } catch (err) {
    console.error("Predictive HAE flow graph loading failed:", err);
  }
}

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

  document.getElementById('forecastPeak').textContent = summary.max_congestion;
  document.getElementById('forecastAvg').textContent = summary.avg_congestion;
  document.getElementById('forecastCritHours').textContent = summary.critical_hours;
  document.getElementById('forecastHighHours').textContent = summary.high_hours;

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

  renderForecastChart(forecast);
  renderViolationsChart(forecast);
}

// ══════════════════════════════════════════════════════════════════════════
// DISPATCH TABLE
// ══════════════════════════════════════════════════════════════════════════
function renderDispatchTable() {
  let data = [...APP.dispatch];

  if (APP.filterSeverity !== 'ALL') {
    const priorities = {
      'CRITICAL': ['CRITICAL'],
      'HIGH': ['CRITICAL', 'HIGH'],
      'MEDIUM': ['CRITICAL', 'HIGH', 'MEDIUM'],
    };
    const allowed = priorities[APP.filterSeverity] || [];
    data = data.filter(d => allowed.includes(d.severity));
  }

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
    
    let actionHtml = d.action;
    if (APP.dispatchMode === 'manual') {
      if (APP.resolvingZones.has(d.zone_id)) {
        actionHtml = `<span style="color:var(--accent-cyan); font-weight:bold; font-size:10px;">Approved & Dispatching</span>`;
      } else {
        actionHtml = `<button class="console-btn active approve-dispatch-btn" data-zone-id="${d.zone_id}" style="font-size:9px; padding:3px 6px; margin:0; line-height:1; min-width:90px;">Approve Action</button>`;
      }
    }

    return `
      <tr class="${rowClass}">
        <td>${d.zone_id}</td>
        <td><span class="severity-badge ${sevClass}">${d.severity}</span></td>
        <td>${d.risk_score.toFixed(4)}</td>
        <td>${d.impact_score.toFixed(4)}</td>
        <td>${d.violation_count.toLocaleString()}</td>
        <td>${actionHtml}</td>
      </tr>
    `;
  }).join('');

  // Attach event listeners for Manual Approve
  if (APP.dispatchMode === 'manual') {
    tbody.querySelectorAll('.approve-dispatch-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const zoneId = btn.dataset.zoneId;
        APP.resolvingZones.add(zoneId);
        renderDispatchTable();
        updateSidebarCounts();
        updateStatCards();
        showSystemNotification('Dispatch Approved', `Enforcement unit dispatched to ${getZoneLabel(zoneId)} (${zoneId}).`);
        showToast("Manual Dispatch", `Unit sent to ${getZoneLabel(zoneId)}`, 'success');
        sendTelegramAlert(`✅ *Manual Dispatch Approved*\n\n*Zone:* ${getZoneLabel(zoneId)} (${zoneId})\n*Action:* Unit Dispatched.`);
      });
    });
  }

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

// ── Navbar Dropdowns & Configurations ──────────────────────────────────────
function initNavbarDropdowns() {
  const notifBtn = document.getElementById('notifBtn');
  const notifDropdown = document.getElementById('notifDropdown');
  const settingsBtn = document.getElementById('settingsBtn');
  const settingsDropdown = document.getElementById('settingsDropdown');
  
  APP.dismissedZones = new Set();
  APP.dispatchMode = localStorage.getItem('gridlock_dispatch_mode') || 'auto';
  APP.simInterval = parseInt(localStorage.getItem('gridlock_sim_interval')) || 2500;
  
  const simSelect = document.getElementById('settingSimInterval');
  if (simSelect) {
    simSelect.value = APP.simInterval.toString();
  }
  
  const btnAuto = document.getElementById('btnSettingDispatchAuto');
  const btnManual = document.getElementById('btnSettingDispatchManual');
  if (btnAuto && btnManual) {
    if (APP.dispatchMode === 'manual') {
      btnAuto.classList.remove('active');
      btnManual.classList.add('active');
    } else {
      btnAuto.classList.add('active');
      btnManual.classList.remove('active');
    }
    
    btnAuto.addEventListener('click', () => {
      btnAuto.classList.add('active');
      btnManual.classList.remove('active');
      APP.dispatchMode = 'auto';
      localStorage.setItem('gridlock_dispatch_mode', 'auto');
      renderDispatchTable();
      showSystemNotification('Dispatch Mode Updated', 'Enforcement actions will now be auto-dispatched.');
    });
    
    btnManual.addEventListener('click', () => {
      btnManual.classList.add('active');
      btnAuto.classList.remove('active');
      APP.dispatchMode = 'manual';
      localStorage.setItem('gridlock_dispatch_mode', 'manual');
      renderDispatchTable();
      showSystemNotification('Dispatch Mode Updated', 'Enforcement actions now require manual approval.');
    });
  }

  loadSettings();

  if (notifBtn && notifDropdown) {
    notifBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      notifDropdown.classList.toggle('hidden');
      if (settingsDropdown) settingsDropdown.classList.add('hidden');
      updateNotifications();
    });
  }
  
  if (settingsBtn && settingsDropdown) {
    settingsBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      settingsDropdown.classList.toggle('hidden');
      if (notifDropdown) notifDropdown.classList.add('hidden');
    });
  }
  
  document.addEventListener('click', (e) => {
    if (notifDropdown && !notifDropdown.contains(e.target) && e.target !== notifBtn) {
      notifDropdown.classList.add('hidden');
    }
    if (settingsDropdown && !settingsDropdown.contains(e.target) && e.target !== settingsBtn) {
      settingsDropdown.classList.add('hidden');
    }
  });

  const dismissAllBtn = document.getElementById('btnDismissAllAlerts');
  if (dismissAllBtn) {
    dismissAllBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      APP.zones.forEach(z => {
        if (z.severity === 'CRITICAL' || z.severity === 'HIGH') {
          APP.dismissedZones.add(z.zone_id);
        }
      });
      updateNotifications();
      showSystemNotification('Alerts Dismissed', 'All active alerts have been cleared.');
    });
  }

  const saveBtn = document.getElementById('btnSaveSettings');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const clientId = document.getElementById('settingMapplsId').value.trim();
      const clientSecret = document.getElementById('settingMapplsSecret').value.trim();
      const intervalVal = parseInt(document.getElementById('settingSimInterval').value);
      const tgToken = document.getElementById('settingTelegramToken')?.value.trim();
      const tgChat = document.getElementById('settingTelegramChat')?.value.trim();
      
      APP.simInterval = intervalVal;
      localStorage.setItem('gridlock_sim_interval', intervalVal.toString());
      if (tgToken) localStorage.setItem('gridlock_tg_token', tgToken);
      if (tgChat) localStorage.setItem('gridlock_tg_chat', tgChat);
      
      try {
        saveBtn.textContent = 'Saving...';
        const res = await fetch('/api/mappls/save_keys', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ client_id: clientId, client_secret: clientSecret })
        });
        
        if (res.ok) {
          showSystemNotification('Settings Saved', 'System configurations updated successfully.');
          setTimeout(() => {
            location.reload();
          }, 1000);
        } else {
          showSystemNotification('Error Saving', 'Failed to save server credentials.');
          saveBtn.textContent = 'Save & Reload';
        }
      } catch (err) {
        console.error(err);
        showSystemNotification('Error Saving', 'Network error while saving credentials.');
        saveBtn.textContent = 'Save & Reload';
      }
    });
  }
}

function updateNotifications() {
  const notifList = document.getElementById('notifList');
  if (!notifList) return;
  
  if (!APP.dismissedZones) APP.dismissedZones = new Set();
  
  const activeAlerts = APP.zones.filter(z => 
    (z.severity === 'CRITICAL' || z.severity === 'HIGH') && 
    !APP.dismissedZones.has(z.zone_id)
  );
  
  const countBadge = document.getElementById('notifCount');
  if (countBadge) {
    countBadge.textContent = activeAlerts.length;
    if (activeAlerts.length > 0) {
      countBadge.style.display = 'inline-block';
    } else {
      countBadge.style.display = 'none';
    }
  }
  
  if (activeAlerts.length === 0) {
    notifList.innerHTML = '<li class="placeholder">No critical incidents reported</li>';
    return;
  }
  
  notifList.innerHTML = activeAlerts.map(z => {
    const isCritical = z.severity === 'CRITICAL';
    const label = getZoneLabel(z.zone_id);
    
    return `
      <li data-zone-id="${z.zone_id}" style="border-bottom: 1px solid var(--border-subtle); padding: 10px 12px; cursor: pointer;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
          <span style="display:flex; align-items:center; gap:6px; font-weight:bold; color:var(--text-primary);">
            <span class="zone-status-dot ${isCritical ? 'critical' : 'high'}" style="margin:0;"></span>
            ${isCritical ? '🔴 CRITICAL' : '🟠 HIGH RISK'}
          </span>
          <span style="font-family:var(--font-mono); font-size:10px; color:var(--accent-cyan); font-weight:bold;">
            ${z.impact_score.toFixed(4)}
          </span>
        </div>
        <div style="font-weight:600; color:var(--text-secondary); margin-bottom:2px;">
          ${label} (${z.zone_id})
        </div>
        <div style="font-size:10px; color:var(--text-muted);">
          ${z.violation_count} active violations. Click to focus map.
        </div>
        <div class="alert-time">Active now</div>
      </li>
    `;
  }).join('');
  
  notifList.querySelectorAll('li[data-zone-id]').forEach(li => {
    li.addEventListener('click', () => {
      const zoneId = li.dataset.zoneId;
      const z = APP.zones.find(zone => zone.zone_id === zoneId);
      if (z) {
        const mapTabBtn = document.querySelector('.tab-btn[data-tab="map"]');
        if (mapTabBtn) mapTabBtn.click();
        
        selectZoneForConsole(zoneId);
        
        if (z.center_lat && z.center_lng) {
          MapManager.recenter(z.center_lat, z.center_lng);
          if (APP.mapMode === 'leaflet') {
            const marker = APP.zoneMarkers[zoneId];
            if (marker) {
              marker.setStyle({ fillOpacity: 0.6, weight: 3 });
              setTimeout(() => marker.setStyle({ fillOpacity: 0.2, weight: 1.5 }), 1200);
            }
          }
        }
        
        const notifDropdown = document.getElementById('notifDropdown');
        if (notifDropdown) notifDropdown.classList.add('hidden');
      }
    });
  });
}

function showSystemNotification(title, message) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.position = 'fixed';
    container.style.bottom = '20px';
    container.style.right = '20px';
    container.style.zIndex = '9999';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    document.body.appendChild(container);
  }
  
  const toast = document.createElement('div');
  toast.className = 'toast-notification';
  toast.style.background = 'rgba(10, 15, 28, 0.95)';
  toast.style.borderLeft = '4px solid var(--accent-cyan)';
  toast.style.border = '1px solid var(--border-primary)';
  toast.style.borderRadius = '4px';
  toast.style.padding = '12px 16px';
  toast.style.minWidth = '250px';
  toast.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.5), var(--shadow-glow-cyan)';
  toast.style.color = 'var(--text-primary)';
  toast.style.fontFamily = 'var(--font-mono)';
  toast.style.fontSize = '11px';
  toast.style.transition = 'all 0.3s ease';
  toast.style.opacity = '0';
  toast.style.transform = 'translateY(20px)';
  
  toast.innerHTML = `
    <div style="font-weight: bold; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
      <span>⚡</span> <span>${title}</span>
    </div>
    <div style="color: var(--text-secondary);">${message}</div>
  `;
  
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  }, 10);
  
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-20px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

async function loadSettings() {
  try {
    const res = await fetch('/api/mappls/keys');
    if (res.ok) {
      const data = await res.json();
      if (data.client_id) document.getElementById('settingMapplsId').value = data.client_id;
      if (data.client_secret) document.getElementById('settingMapplsSecret').value = data.client_secret;
    }
  } catch (err) {
    console.error('Failed to load settings:', err);
  }

  const tgToken = localStorage.getItem('gridlock_tg_token');
  const tgChat = localStorage.getItem('gridlock_tg_chat');
  if (tgToken && document.getElementById('settingTelegramToken')) document.getElementById('settingTelegramToken').value = tgToken;
  if (tgChat && document.getElementById('settingTelegramChat')) document.getElementById('settingTelegramChat').value = tgChat;
}

/* ══════════════════════════════════════════════════════════════════════════
   TOAST NOTIFICATIONS
   ══════════════════════════════════════════════════════════════════════════ */
function showToast(title, message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let icon = 'ℹ️';
  if (type === 'error') icon = '🚨';
  if (type === 'success') icon = '✅';
  if (type === 'warning') icon = '⚠️';

  toast.innerHTML = `
    <div class="toast-icon">${icon}</div>
    <div class="toast-content">
      <div class="toast-title">${title}</div>
      <div class="toast-message">${message}</div>
    </div>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'toast-exit 0.3s forwards';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/* ══════════════════════════════════════════════════════════════════════════
   TELEGRAM INTEGRATION
   ══════════════════════════════════════════════════════════════════════════ */
async function sendTelegramAlert(message) {
  const token = document.getElementById('settingTelegramToken')?.value;
  const chatId = document.getElementById('settingTelegramChat')?.value;
  
  if (!token || !chatId) {
    console.log("[Mock Telegram] No credentials. Would send:", message);
    return;
  }

  try {
    const url = `https://api.telegram.org/bot${token}/sendMessage`;
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, text: message, parse_mode: 'Markdown' })
    });
  } catch (err) {
    console.error("Telegram API Error:", err);
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   ANPR CAMERA SIMULATOR LOOP
   ══════════════════════════════════════════════════════════════════════════ */
const anprCanvas = document.getElementById('anprCanvas');
const anprCtx = anprCanvas ? anprCanvas.getContext('2d') : null;
let anprCars = [];

function generatePlate() {
  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const num1 = Math.floor(Math.random() * 90 + 10);
  const l1 = letters[Math.floor(Math.random() * 26)] + letters[Math.floor(Math.random() * 26)];
  const num2 = Math.floor(Math.random() * 9000 + 1000);
  return `KA-${num1}-${l1}-${num2}`;
}

function logAnpr(msg, isViolation = false) {
  const logContainer = document.getElementById('anprLog');
  if (!logContainer) return;
  const item = document.createElement('div');
  item.className = `anpr-log-item ${isViolation ? 'violation' : ''}`;
  item.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  logContainer.prepend(item);
  if (logContainer.children.length > 5) {
    logContainer.removeChild(logContainer.lastChild);
  }
}

function anprLoop() {
  if (!anprCtx) return;
  requestAnimationFrame(anprLoop);
  
  const w = anprCanvas.width;
  const h = anprCanvas.height;
  
  // Draw Road Background
  anprCtx.fillStyle = '#111';
  anprCtx.fillRect(0, 0, w, h);
  
  // Draw Lane Dividers
  anprCtx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
  anprCtx.lineWidth = 2;
  anprCtx.setLineDash([10, 10]);
  anprCtx.beginPath();
  anprCtx.moveTo(0, h/2);
  anprCtx.lineTo(w, h/2);
  anprCtx.stroke();
  anprCtx.setLineDash([]);
  
  // Manage Cars
  if (Math.random() < 0.02) {
    anprCars.push({
      x: -40,
      y: Math.random() > 0.5 ? h/4 : (h/4)*3,
      speed: 2 + Math.random() * 3,
      plate: generatePlate(),
      color: `hsl(${Math.random() * 360}, 70%, 50%)`,
      scanned: false,
      violation: Math.random() < 0.15
    });
  }
  
  for (let i = anprCars.length - 1; i >= 0; i--) {
    let car = anprCars[i];
    car.x += car.speed;
    
    // Draw Car
    anprCtx.fillStyle = car.color;
    anprCtx.fillRect(car.x, car.y - 10, 30, 16);
    
    // Tracking Bounding Box
    if (car.x > 30 && car.x < w - 30) {
      anprCtx.strokeStyle = car.violation && car.scanned ? '#ff4b2b' : '#00e5ff';
      anprCtx.lineWidth = 1.5;
      anprCtx.strokeRect(car.x - 4, car.y - 14, 38, 24);
      
      // OCR Text
      if (car.x > w/2 - 20 && !car.scanned) {
        car.scanned = true;
        if (car.violation) {
          logAnpr(`VIOLATION: ${car.plate} (No Parking)`, true);
          showToast("ANPR Alert", `Illegal Parking Detected: ${car.plate}`, 'error');
          sendTelegramAlert(`🚨 *GridLock AI Alert*\n\n*Violation:* No Parking\n*Vehicle:* \`${car.plate}\`\n*Location:* CAM-442 (MG Road)\n*Action:* Tow Truck Dispatched automatically.`);
        } else {
          logAnpr(`SCAN: ${car.plate} - CLEAR`);
        }
      }
      
      if (car.scanned) {
        anprCtx.fillStyle = '#fff';
        anprCtx.font = '10px monospace';
        anprCtx.fillText(car.plate, car.x - 5, car.y - 18);
      }
    }
    
    if (car.x > w) {
      anprCars.splice(i, 1);
    }
  }
}

// Start ANPR Simulator
if (anprCanvas) {
  anprLoop();
}
