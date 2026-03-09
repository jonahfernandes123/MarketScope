/* ── Utilities ─────────────────────────────────────────────────────────────── */
function esc(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function fmtPct(pct) {
  if (pct === null || pct === undefined) return { html: '<span class="neu">&mdash;</span>', cls: 'neu' };
  const cls   = pct > 0 ? 'up' : pct < 0 ? 'down' : 'neu';
  const arrow = pct > 0 ? '&#9650;' : pct < 0 ? '&#9660;' : '';
  const sign  = pct > 0 ? '+' : '';
  return { html: `<span class="${cls}">${arrow} ${sign}${pct.toFixed(2)}%</span>`, cls };
}

function fmtPrice(inst) {
  if (inst.price == null) return inst.error ? 'Error' : 'Loading\u2026';
  const s = inst.thousands
    ? inst.price.toLocaleString('en-US', { minimumFractionDigits: inst.decimals, maximumFractionDigits: inst.decimals })
    : inst.price.toFixed(inst.decimals);
  return inst.prefix + s + inst.suffix;
}

function calcChg(inst) {
  if (inst.price == null || inst.prev_price == null || inst.prev_price === 0) return null;
  return (inst.price - inst.prev_price) / inst.prev_price * 100;
}

/* ── Clock & date ──────────────────────────────────────────────────────────── */
function tickClock() {
  document.getElementById('clock').textContent =
    new Date().toUTCString().replace(' GMT', '') + ' UTC';
}
setInterval(tickClock, 1000); tickClock();

document.getElementById('date-line').textContent =
  new Date().toLocaleDateString('en-US', { weekday:'long', year:'numeric', month:'long', day:'numeric' });

/* ── Refresh countdown ─────────────────────────────────────────────────────── */
let countdown = REFRESH;
setInterval(() => {
  countdown = Math.max(0, countdown - 1);
  document.getElementById('countdown').textContent = countdown;
  document.getElementById('progress-fill').style.width = (countdown / REFRESH * 100) + '%';
}, 1000);

/* ── Side drawer ───────────────────────────────────────────────────────────── */
function openDrawer() {
  document.getElementById('side-drawer').classList.add('open');
  document.getElementById('drawer-backdrop').classList.add('open');
}
function closeDrawer() {
  document.getElementById('side-drawer').classList.remove('open');
  document.getElementById('drawer-backdrop').classList.remove('open');
}
document.getElementById('drawer-backdrop').addEventListener('click', closeDrawer);

/* ── View switching ────────────────────────────────────────────────────────── */
function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById('view-' + name).classList.add('active');
  document.querySelectorAll('.drawer-link').forEach(l => l.classList.remove('active'));
  document.getElementById('nav-' + name).classList.add('active');
  document.querySelectorAll('.top-nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  closeDrawer();
}

/* ── Settings ──────────────────────────────────────────────────────────────── */
const SETTINGS_KEY = 'mkt_settings';
const SETTINGS_DEFAULTS = {
  chartRange:          '1mo',
  compactMode:         false,
  accentPreset:        'default',
  theme:               'dark',   // 'dark' | 'light' — dark is the default on first load
  hiddenInstruments:   [],       // only affects Markets page grid — not pulse/movers/home
};
let _settings = { ...SETTINGS_DEFAULTS };

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) _settings = { ...SETTINGS_DEFAULTS, ...JSON.parse(raw) };
  } catch(e) { /* ignore */ }
  applySettings();
}

function saveSettings() {
  try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(_settings)); } catch(e) {}
}

function applySettings() {
  const body = document.getElementById('app-body');
  if (!body) return;
  // Compact mode
  body.classList.toggle('compact', !!_settings.compactMode);
  // Light mode — only applied from saved settings; dark is the default
  body.classList.toggle('light-mode', _settings.theme === 'light');
  // Accent preset — remove all, then add current
  ['accent-amber','accent-teal','accent-rose','accent-slate'].forEach(c => body.classList.remove(c));
  if (_settings.accentPreset !== 'default') body.classList.add('accent-' + _settings.accentPreset);
}
loadSettings();

/* ── Collapsible section toggle ────────────────────────────────────────────── */
// Tracks which sections are open: { 'news:Energy': true, 'macro:0': true, ... }
const _sectionOpenState = {};

function toggleSection(headerEl) {
  const section = headerEl.closest('.collapsible');
  if (!section) return;
  const id = section.dataset.sid;
  const isNowOpen = !section.classList.contains('open');
  section.classList.toggle('open', isNowOpen);
  if (id) _sectionOpenState[id] = isNowOpen;
}

function _isSectionOpen(id, defaultOpen) {
  return _sectionOpenState.hasOwnProperty(id) ? _sectionOpenState[id] : defaultOpen;
}

/* ── Price card state & range mode ────────────────────────────────────────── */
let instruments = [];
const _cardElements = {};

// Active range for card % change display and movers ranking
let _marketsRangeMode = '1d';

// Return the change value for an instrument at the current range mode
function _instChg(inst, mode) {
  mode = mode || _marketsRangeMode;
  const v = inst['change_' + mode];
  return (v !== undefined && v !== null) ? v : null;
}

// Update the change label element for one instrument card
function updateCardChange(inst) {
  const cEl = document.getElementById('c-' + inst.key);
  if (!cEl) return;
  const chg = _instChg(inst);
  if (chg === null) {
    cEl.innerHTML = '<span class="neu">\u2014</span>';
  } else if (chg > 0) {
    cEl.innerHTML = '<span class="up">\u25b2</span><span class="up">+' + chg.toFixed(2) + '%</span>';
  } else {
    cEl.innerHTML = '<span class="down">\u25bc</span><span class="down">' + chg.toFixed(2) + '%</span>';
  }
}

// Change the active range and immediately refresh all change displays
function setMarketsRange(mode) {
  _marketsRangeMode = mode;
  document.querySelectorAll('.chg-tab').forEach(t => t.classList.remove('active'));
  const tab = document.getElementById('chg-tab-' + mode);
  if (tab) tab.classList.add('active');
  instruments.forEach(updateCardChange);
  _rebuildMovers();
}

const INSTRUMENT_GROUPS = [
  { label: 'Energy',  keys: ['brent', 'wti', 'henryhub', 'ttfgas', 'rbobgas', 'heatingoil'] },
  { label: 'Metals',  keys: ['gold', 'silver', 'copper', 'platinum', 'aluminium', 'palladium'] },
  { label: 'FX',      keys: ['eurusd', 'gbpusd', 'usdjpy', 'usdcnh'] },
  { label: 'Crypto',  keys: ['bitcoin', 'ethereum'] },
];
let pricesSortMode = 'grouped';

function renderCards(data) {
  instruments = data;

  // Create card elements once and cache them
  data.forEach(inst => {
    if (!_cardElements[inst.key]) {
      const card = document.createElement('div');
      card.className = 'card';
      card.id = 'card-' + inst.key;
      card.style.setProperty('--accent', inst.accent);
      card.addEventListener('click', () => openCommodityModal(inst.key));
      card.innerHTML =
        '<div class="card-accent"></div>' +
        '<div class="card-icon">'  + inst.icon  + '</div>' +
        '<div class="card-name">'  + inst.label + '</div>' +
        '<div class="card-price loading" id="p-' + inst.key + '">Loading\u2026</div>' +
        '<div class="card-change"  id="c-' + inst.key + '"></div>' +
        '<div class="card-hint">Click for details \u2192</div>';
      _cardElements[inst.key] = card;
    }
  });

  // Place cards in the grid (grouped or sorted)
  renderPricesGrid();

  // Update price and change labels on all cards
  data.forEach(inst => {
    const pEl = document.getElementById('p-' + inst.key);
    if (!pEl) return;

    if (!inst.price && inst.error) {
      pEl.className = 'card-price err';
      pEl.textContent = 'Unavailable';
      const cEl = document.getElementById('c-' + inst.key);
      if (cEl) cEl.innerHTML = '<span class="neu" style="font-size:0.6rem">' + esc(inst.error.substring(0, 45)) + '</span>';
      return;
    }
    pEl.className = 'card-price';
    pEl.textContent = fmtPrice(inst);
    updateCardChange(inst);
  });

  _rebuildMovers();
  renderPulse();
}

/* ── Prices page grid layout ───────────────────────────────────────────────── */
function renderPricesGrid() {
  const grid = document.getElementById('grid');
  if (!grid || !instruments.length) return;
  grid.innerHTML = '';

  if (pricesSortMode === 'grouped') {
    INSTRUMENT_GROUPS.forEach(group => {
      const cards = group.keys
        .filter(k => !_settings.hiddenInstruments.includes(k))
        .map(k => _cardElements[k]).filter(Boolean);
      if (!cards.length) return;
      const label = document.createElement('div');
      label.className = 'section-label grid-group-label';
      label.textContent = group.label;
      grid.appendChild(label);
      const sub = document.createElement('div');
      sub.className = 'grid-group';
      cards.forEach(c => sub.appendChild(c));
      grid.appendChild(sub);
    });
  } else {
    let sorted = [...instruments];
    if (pricesSortMode === 'gainers') {
      sorted.sort((a, b) => {
        const pa = _instChg(a) ?? -999;
        const pb = _instChg(b) ?? -999;
        return pb - pa;
      });
    } else if (pricesSortMode === 'losers') {
      sorted.sort((a, b) => {
        const pa = _instChg(a) ?? 999;
        const pb = _instChg(b) ?? 999;
        return pa - pb;
      });
    }
    sorted.forEach(inst => {
      if (!_settings.hiddenInstruments.includes(inst.key) && _cardElements[inst.key])
        grid.appendChild(_cardElements[inst.key]);
    });
  }
}

function setPricesSort(mode) {
  pricesSortMode = mode;
  document.querySelectorAll('.sort-tab').forEach(t => t.classList.remove('active'));
  const tab = document.getElementById('sort-tab-' + mode);
  if (tab) tab.classList.add('active');
  renderPricesGrid();
}

/* ── Market Pulse strip ────────────────────────────────────────────────────── */
function renderPulse() {
  const el = document.getElementById('pulse-strip');
  if (!el || !instruments.length) return;
  el.innerHTML = instruments.map(inst => {
    const price = fmtPrice(inst);
    const chg   = calcChg(inst);
    const { html: chgHtml } = fmtPct(chg);
    return `<div class="pulse-chip" style="--accent:${inst.accent}" onclick="openCommodityModal('${inst.key}')">
      <div class="pulse-name">${inst.icon}&ensp;${esc(inst.label)}</div>
      <div class="pulse-price">${esc(price)}</div>
      <div class="pulse-chg">${chgHtml}</div>
    </div>`;
  }).join('');
}

async function fetchPrices() {
  try {
    const res = await fetch('/api/prices');
    renderCards(await res.json());
    countdown = REFRESH;
  } catch(e) { console.error('Price fetch failed:', e); }
}
fetchPrices();
setInterval(fetchPrices, REFRESH * 1000);

/* ── Briefing card loaders ─────────────────────────────────────────────────── */
let _moversData  = null;
let _newsData    = null;
let _driversData = null;

// Sort instruments by absolute change for the current range mode and re-render movers
function _rebuildMovers() {
  if (!instruments.length) return;
  _moversData = [...instruments].sort((a, b) => {
    const pa = Math.abs(_instChg(a) ?? -1);
    const pb = Math.abs(_instChg(b) ?? -1);
    return pb - pa;
  });
  renderMoversPreview();
}

async function loadBriefingData() {
  // Seed _moversData from prices if instruments not yet loaded
  if (!instruments.length) {
    const priceRes = await fetch('/api/prices').then(r => r.json()).catch(() => []);
    _moversData = [...priceRes].sort((a, b) => {
      const pa = Math.abs(a.change_1d ?? -1);
      const pb = Math.abs(b.change_1d ?? -1);
      return pb - pa;
    });
    renderMoversPreview();
  } else {
    _rebuildMovers();
  }

  const [news, drivers] = await Promise.all([
    fetch('/api/home/news').then(r => r.json()).catch(() => []),
    fetch('/api/home/drivers').then(r => r.json()).catch(() => []),
  ]);
  _newsData    = news;
  _driversData = drivers;
  renderNewsPreview();
  renderDriversPreview();
  renderNewsPage();
  renderMacroPage();
  renderSignalsBanner();
}
loadBriefingData();

/* ── Briefing card preview renderers ──────────────────────────────────────── */
function renderMoversPreview() {
  const el = document.getElementById('preview-movers');
  if (!el || !_moversData) return;
  const top = _moversData.filter(r => r.price != null).slice(0, 5);
  if (!top.length) { el.innerHTML = '<span style="color:var(--dim)">No data yet</span>'; return; }
  el.innerHTML = '<div>' + top.map(r => {
    const pct = _instChg(r);
    const { html } = fmtPct(pct);
    return `<div class="mover-row">
      <span class="mover-name">${esc(r.label)}</span>
      <span class="mover-pct">${html}</span>
    </div>`;
  }).join('') + '</div>';
}

function renderNewsPreview() {
  const el = document.getElementById('preview-news');
  const top = (_newsData || []).slice(0, 4);
  if (!top.length) { el.innerHTML = '<span style="color:var(--dim)">No articles loaded</span>'; return; }
  el.innerHTML = '<ul class="bcard-preview-list">' +
    top.map(a => `<li title="${esc(a.title)}">${esc(a.title)}</li>`).join('') + '</ul>';
}

function renderDriversPreview() {
  const el = document.getElementById('preview-drivers');
  const top = (_driversData || []).slice(0, 3);
  if (!top.length) { el.innerHTML = '<span style="color:var(--dim)">No headlines loaded</span>'; return; }
  el.innerHTML = '<ul class="bcard-preview-list">' +
    top.map(d => `<li title="${esc(d.title)}">${esc(d.title)}</li>`).join('') + '</ul>';
}

/* ── Home page: Market Signals banner ─────────────────────────────────────── */
const _SIGNAL_FILTERS = [
  { label: 'Energy',          accent: '#10b981', re: /\boil\b|opec|brent|wti|crude|\bgas\b|lng|\benergy\b|fuel|refinery/i },
  { label: 'Monetary Policy', accent: '#3b82f6', re: /fed\b|federal reserve|ecb|boj|central bank|\brate\b|inflation|hawkish|dovish|liquidity/i },
  { label: 'China & Demand',  accent: '#8b5cf6', re: /china|pboc|yuan|copper|\bdemand\b|emerging market|india|manufacturing pmi/i },
];

function renderSignalsBanner() {
  const el = document.getElementById('signals-strip');
  if (!el) return;
  const drivers = _driversData || [];
  if (!drivers.length) return;

  const used = new Set();
  const signals = _SIGNAL_FILTERS.map(f => {
    const match = drivers.find(d => !used.has(d) && f.re.test(d.title || ''));
    if (match) used.add(match);
    return match || null;
  });

  // Fill empty slots with first unclaimed driver
  const fallbacks = drivers.filter(d => !used.has(d));
  signals.forEach((s, i) => {
    if (!s && fallbacks.length) signals[i] = fallbacks.shift();
  });

  el.innerHTML = signals.map((d, i) => {
    if (!d) return '';
    const f   = _SIGNAL_FILTERS[i];
    const meta = [d.source, d.published].filter(Boolean).join(' · ');
    return `<div class="signal-card" style="--signal-accent:${f.accent}">
      <div class="signal-theme">${f.label}</div>
      <div class="signal-headline">${esc(d.title)}</div>
      ${meta ? `<div class="signal-meta">${esc(meta)}</div>` : ''}
    </div>`;
  }).join('');
}

/* ── Full-page News renderer (sectioned by asset class) ────────────────────── */
const _NEWS_SECTION_MAP = {
  'Bitcoin':        'Crypto',  'Ethereum':       'Crypto',
  'Gold':           'Metals',  'Silver':         'Metals',
  'Copper':         'Metals',  'Platinum':       'Metals',
  'Aluminium':      'Metals',  'Palladium':      'Metals',
  'Brent Crude':    'Energy',  'WTI Crude':      'Energy',
  'Henry Hub Gas':  'Energy',  'TTF Gas':        'Energy',
  'RBOB Gasoline':  'Energy',  'Heating Oil':    'Energy',
  'EUR / USD':      'FX',      'GBP / USD':      'FX',
  'USD / JPY':      'FX',      'USD / CNH':      'FX',
};
const _NEWS_SECTION_ORDER  = ['Energy', 'Metals', 'Crypto', 'FX', 'General'];
const _NEWS_SECTION_ACCENTS = {
  'Energy': '#10b981', 'Metals': '#f59e0b',
  'Crypto': '#8b5cf6', 'FX':     '#3b82f6',
};

/* ── News column dashboard ─────────────────────────────────────────────────── */
// Column config — 'General' articles are merged into 'FX & Markets'
const _NEWS_COLS = [
  { key: 'Energy', label: 'Energy',        icon: '&#9679;' },
  { key: 'Metals', label: 'Metals',        icon: '&#9671;' },
  { key: 'Crypto', label: 'Crypto',        icon: '&#x20BF;' },
  { key: 'FX',     label: 'FX &amp; Markets', icon: '&#36;' },
];

// Persist open/closed state per column; default all open
const _newsColOpen = {};
function _isNewsColOpen(key) {
  return _newsColOpen[key] !== false;
}
function toggleNewsCol(key) {
  _newsColOpen[key] = !_isNewsColOpen(key);
  renderNewsPage();
}

function renderNewsPage() {
  const el = document.getElementById('news-page-body');
  if (!el) return;
  if (!_newsData || !_newsData.length) {
    el.innerHTML = '<p style="color:var(--muted);padding:24px 0">No articles available.</p>';
    return;
  }

  // Group articles by section
  const grouped = {};
  _NEWS_SECTION_ORDER.forEach(s => { grouped[s] = []; });
  _newsData.forEach(a => {
    const section = _NEWS_SECTION_MAP[a.instrument] || 'General';
    if (grouped[section]) grouped[section].push(a);
    else grouped['General'].push(a);
  });
  // Merge 'General' into FX column
  grouped['FX'] = [...(grouped['FX'] || []), ...(grouped['General'] || [])];

  let html = '<div class="news-dashboard">';

  _NEWS_COLS.forEach(col => {
    const articles = (grouped[col.key] || []).slice(0, 6);
    const accent   = _NEWS_SECTION_ACCENTS[col.key] || '#3b82f6';
    const isOpen   = _isNewsColOpen(col.key);
    const lead     = articles[0];
    const preview  = lead ? esc(lead.title) : 'No articles';

    html += `<div class="news-col${isOpen ? ' open' : ''}" style="--section-accent:${accent}">`;

    // ── Column header (always visible, clickable) ──
    html += `<div class="news-col-header" onclick="toggleNewsCol('${col.key}')">
      <div class="news-col-accent-bar"></div>
      <div class="news-col-header-row">
        <span class="news-col-title">${col.label}</span>
        <div class="news-col-header-right">
          ${articles.length ? `<span class="news-col-count">${articles.length}</span>` : ''}
          <span class="news-col-chevron">&#8250;</span>
        </div>
      </div>
      <div class="news-col-preview">${preview}</div>
    </div>`;

    // ── Column body (articles — shown when open) ──
    if (articles.length) {
      html += `<div class="news-col-body">`;

      // Lead article
      const leadMeta = [lead.publisher, lead.published].filter(Boolean).join(' · ');
      html += `<div class="news-lead-label">Featured</div>`;
      html += `<a class="lead-card" href="${esc(lead.url)}" target="_blank" rel="noopener">
        <div class="lead-card-headline">${esc(lead.title)}</div>
        ${lead.summary ? `<div class="lead-card-summary">${esc(lead.summary)}</div>` : ''}
        <div class="lead-card-meta">${esc(leadMeta)}</div>
      </a>`;

      // Supporting headlines
      if (articles.length > 1) {
        html += `<div class="news-feed-label">More Headlines</div>`;
        html += `<div class="news-feed">`;
        articles.slice(1).forEach(a => {
          const meta = [a.publisher, a.published].filter(Boolean).join(' · ');
          html += `<a class="news-feed-row" href="${esc(a.url)}" target="_blank" rel="noopener">
            <div class="news-feed-headline">${esc(a.title)}</div>
            <div class="news-feed-meta">${esc(meta)}</div>
          </a>`;
        });
        html += '</div>';
      }

      html += '</div>';  // .news-col-body
    }

    html += '</div>';  // .news-col
  });

  html += '</div>';  // .news-dashboard
  el.innerHTML = html;
}

/* ── Macro theme accordion ─────────────────────────────────────────────────── */
// Short tagline shown on the card face (below the title)
const MACRO_THEME_TAGLINES = [
  'Fed · ECB · BoJ rate cycles · Dollar strength · Commodity valuations',
  'OPEC+ · LNG flows · Inventory levels · Refinery margins',
  'Tariffs · Sanctions · Supply chain disruption · Shipping routes',
  'PBoC policy · Property sector · Manufacturing PMI · Import volumes',
];

let _activeMacroTheme = -1;  // -1 = all collapsed (default)

function openMacroTheme(i) {
  _activeMacroTheme = (_activeMacroTheme === i) ? -1 : i;  // toggle; -1 = all closed
  renderMacroPage();
}

/* ── Full-page Macro renderer (themed blocks + keyword-matched headlines) ───── */
const MACRO_THEMES = [
  {
    title: 'Monetary Policy &amp; Liquidity',
    accent: '#3b82f6',
    keywords: /fed|federal reserve|ecb|boj|central bank|\brate\b|interest rate|inflation|liquidity|hawkish|dovish|rate cut|rate hike|quantitative/i,
    text: 'Central bank rate cycles set the cost of capital globally. Tight policy strengthens the dollar and pressures commodity prices denominated in USD; easing cycles reduce carry costs and fuel demand for hard assets and risk-on positioning. Fed-ECB-BoJ divergence is the primary driver of currency-adjusted commodity returns.',
  },
  {
    title: 'Energy &amp; Physical Supply',
    accent: '#10b981',
    keywords: /\boil\b|opec|crude|brent|wti|\bgas\b|lng|pipeline|supply|inventory|\benergy\b|fuel price|refinery|barrel|heating oil/i,
    text: 'Energy prices feed directly into inflation, transportation costs, and industrial input costs globally. OPEC+ production decisions and infrastructure disruptions ripple across asset classes — from metals processing costs to FX reserves of producer nations. Inventory levels and spare capacity are the key real-time signals.',
  },
  {
    title: 'Geopolitics &amp; Trade Flows',
    accent: '#f59e0b',
    keywords: /tariff|trade war|sanction|ukraine|middle east|iran|israel|conflict|geopolit|nato|supply chain|export ban|import ban|embargo|shipping|strait/i,
    text: 'Trade restrictions and geopolitical conflict reshape commodity routing, introduce supply shocks, and embed risk premiums into prices. Sanctions on energy exporters and tariff escalations create persistent pricing dislocations. Shipping route disruptions — particularly through strategic chokepoints — are a leading indicator of commodity price spikes.',
  },
  {
    title: 'China &amp; Global Demand',
    accent: '#8b5cf6',
    keywords: /china|pboc|chinese|yuan|renminbi|copper demand|emerging market|india|brazil|\bdemand\b|stimulus|property sector|beijing|manufacturing pmi|factory output/i,
    text: 'China is the world\'s largest consumer of industrial metals, energy, and agricultural commodities. PBOC policy shifts, property sector health, and factory output data are the primary leading indicators for global commodity demand. Weakness in Chinese manufacturing directly moves copper, iron ore, and crude import volumes.',
  },
];

function renderMacroPage() {
  const el = document.getElementById('macro-page-body');
  if (!el) return;

  const drivers = _driversData || [];

  // Greedily assign each headline to at most one theme (first-match wins by theme order)
  const used = new Set();
  const themeMatches = MACRO_THEMES.map(theme => {
    const matched = [];
    for (const d of drivers) {
      if (!used.has(d) && theme.keywords.test(d.title || '')) {
        matched.push(d);
        used.add(d);
        if (matched.length === 3) break;
      }
    }
    return matched;
  });

  // Unclaimed articles as fallback pool
  const unclaimed = drivers.filter(d => !used.has(d));

  let html = '<div class="macro-theme-list">';

  MACRO_THEMES.forEach((theme, i) => {
    let headlines = themeMatches[i];
    if (!headlines.length && unclaimed.length) {
      headlines = unclaimed.splice(0, 2);
    }
    const isOpen = _activeMacroTheme === i;

    // ── Theme row (compact clickable header) ──
    html += `<div class="macro-theme-wrap" style="--theme-accent:${theme.accent}">`;
    html += `<div class="macro-row-header${isOpen ? ' active' : ''}" onclick="openMacroTheme(${i})">
      <div class="macro-row-stripe"></div>
      <div class="macro-row-info">
        <span class="macro-row-title">${theme.title}</span>
        <span class="macro-row-tagline">${MACRO_THEME_TAGLINES[i]}</span>
      </div>
      <span class="macro-row-chevron">&#8250;</span>
    </div>`;

    // ── Expanded body ──
    if (isOpen) {
      html += `<div class="macro-theme-body">`;
      html += `<div class="macro-editorial-label">Context</div>`;
      html += `<div class="macro-block-text">${theme.text}</div>`;

      if (headlines.length) {
        // Featured headline
        const featured = headlines[0];
        const featMeta = [featured.source, featured.published].filter(Boolean).join(' · ');
        html += `<div class="macro-key-dev-label">Key Development</div>`;
        html += `<a class="lead-card" href="${esc(featured.url)}" target="_blank" rel="noopener">
          <div class="lead-card-headline">${esc(featured.title)}</div>
          ${featMeta ? `<div class="lead-card-meta">${esc(featMeta)}</div>` : ''}
        </a>`;

        // Supporting headlines
        if (headlines.length > 1) {
          html += `<div class="macro-signals-label">Signals</div>`;
          headlines.slice(1).forEach(d => {
            const meta = [d.source, d.published].filter(Boolean).join(' · ');
            html += `<a class="macro-headline-row" href="${esc(d.url)}" target="_blank" rel="noopener">
              <span class="macro-headline-text">${esc(d.title)}</span>
              ${meta ? `<span class="macro-headline-meta">${esc(meta)}</span>` : ''}
            </a>`;
          });
        }
      } else {
        html += `<p class="macro-no-headlines">No matching headlines available.</p>`;
      }

      html += `</div>`;  // .macro-theme-body
    }

    html += `</div>`;  // .macro-theme-wrap
  });

  html += '</div>';  // .macro-theme-list
  el.innerHTML = html;
}

/* ── Briefing modal ────────────────────────────────────────────────────────── */
const BRIEFING_CONFIG = {
  movers:  { title: 'Biggest Movers',        subtitle: 'All instruments ranked by 24h % change', accent: '#f59e0b' },
  news:    { title: 'Key Market News',        subtitle: 'Latest articles aggregated across all instruments', accent: '#10b981' },
  drivers: { title: "Today\u2019s Market Drivers", subtitle: 'Top macro & market headlines from Google News', accent: '#8b5cf6' },
};

function openBriefingModal(key) {
  const cfg = BRIEFING_CONFIG[key];
  if (!cfg) return;
  const modal = document.getElementById('briefing-modal');
  modal.style.setProperty('--modal-accent', cfg.accent);
  modal.style.borderTopColor = cfg.accent;
  document.getElementById('bm-title').textContent    = cfg.title;
  document.getElementById('bm-subtitle').textContent = cfg.subtitle;
  const body = document.getElementById('briefing-modal-body');
  if      (key === 'movers')  body.innerHTML = buildMoversModal();
  else if (key === 'news')    body.innerHTML = buildNewsModal();
  else if (key === 'drivers') body.innerHTML = buildDriversModal();
  document.getElementById('briefing-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeBriefingModal() {
  document.getElementById('briefing-overlay').classList.remove('open');
  document.body.style.overflow = '';
}
document.getElementById('briefing-close-btn').addEventListener('click', closeBriefingModal);
document.getElementById('briefing-overlay').addEventListener('click', e => {
  if (e.target.id === 'briefing-overlay') closeBriefingModal();
});

function buildMoversModal() {
  if (!_moversData || !_moversData.length) return '<p style="color:var(--muted)">No data available.</p>';
  const rows = _moversData.map((r, i) => {
    const pct = _instChg(r);
    const { html, cls } = fmtPct(pct);
    return `<tr>
      <td class="col-rank">${i + 1}</td>
      <td class="col-name">${esc(r.label)}</td>
      <td class="col-price">${esc(fmtPrice(r))}</td>
      <td class="col-pct ${cls}">${html}</td>
    </tr>`;
  }).join('');
  return `<table class="movers-table"><tbody>${rows}</tbody></table>`;
}

function buildNewsModal() {
  if (!_newsData || !_newsData.length) return '<p style="color:var(--muted)">No articles available.</p>';
  const lead = _newsData[0];
  const leadMeta = [lead.instrument, lead.publisher, lead.published].filter(Boolean).join(' · ');
  let html = `<a class="lead-card" href="${esc(lead.url)}" target="_blank" rel="noopener">
    <div class="lead-card-headline">${esc(lead.title)}</div>
    <div class="lead-card-meta">${esc(leadMeta)}</div>
  </a>`;
  if (_newsData.length > 1) {
    html += '<ul class="news-list" style="margin-top:8px">' + _newsData.slice(1).map(a => `
      <li>
        <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a>
        <div class="news-meta">
          ${esc(a.instrument || '')}${a.publisher ? ' &middot; ' + esc(a.publisher) : ''}${a.published ? ' &middot; ' + esc(a.published) : ''}
        </div>
      </li>`).join('') + '</ul>';
  }
  return html;
}

function buildDriversModal() {
  if (!_driversData || !_driversData.length) return '<p style="color:var(--muted)">No headlines available.</p>';
  const lead = _driversData[0];
  const leadMeta = [lead.source, lead.published].filter(Boolean).join(' · ');
  let html = `<a class="lead-card" href="${esc(lead.url)}" target="_blank" rel="noopener">
    <div class="lead-card-headline">${esc(lead.title)}</div>
    ${leadMeta ? `<div class="lead-card-meta">${esc(leadMeta)}</div>` : ''}
  </a>`;
  if (_driversData.length > 1) {
    html += '<ul class="news-list" style="margin-top:8px">' + _driversData.slice(1).map(d => `
      <li>
        <a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
        <div class="news-meta">
          ${esc(d.source || '')}${d.published ? ' &middot; ' + esc(d.published) : ''}
        </div>
      </li>`).join('') + '</ul>';
  }
  return html;
}

/* ── Commodity detail modal ────────────────────────────────────────────────── */
let chart        = null;
let currentKey   = null;
let currentRange = '1mo';

async function openCommodityModal(key) {
  const inst = instruments.find(i => i.key === key);
  if (!inst) return;
  currentKey   = key;
  currentRange = _settings.chartRange;

  document.getElementById('modal').style.setProperty('--modal-accent', inst.accent);
  document.getElementById('modal').style.borderTopColor = inst.accent;
  document.getElementById('m-icon').innerHTML    = inst.icon;
  document.getElementById('m-name').textContent  = inst.label;
  document.getElementById('m-price').textContent = fmtPrice(inst);

  const chg = _instChg(inst, currentRange);
  const chgEl = document.getElementById('m-chg');
  if (chg === null) {
    chgEl.textContent = ''; chgEl.className = 'modal-chg';
  } else if (chg > 0) {
    chgEl.textContent = '\u25b2 +' + chg.toFixed(2) + '%';
    chgEl.className = 'modal-chg up';
  } else {
    chgEl.textContent = '\u25bc ' + chg.toFixed(2) + '%';
    chgEl.className = 'modal-chg down';
  }

  document.querySelectorAll('.range-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.range === currentRange);
  });
  resetChart();
  document.getElementById('articles-area').innerHTML =
    '<div class="placeholder"><span class="spin"></span>Loading articles\u2026</div>';
  document.getElementById('summary-area').innerHTML =
    '<div class="placeholder"><span class="spin"></span>Loading analysis\u2026</div>';

  document.getElementById('overlay').classList.add('open');
  document.body.style.overflow = 'hidden';

  const [histRes, summRes] = await Promise.all([
    fetch('/api/history/' + key + '?range=' + currentRange),
    fetch('/api/summary/' + key),
  ]);
  if (histRes.ok) renderChart(await histRes.json());
  else showChartError();
  if (summRes.ok) {
    const data = await summRes.json();
    renderArticles(data.articles, inst.accent);
    renderSummary(data);
  } else {
    document.getElementById('articles-area').innerHTML = '<p class="no-articles">Could not load articles.</p>';
    document.getElementById('summary-area').innerHTML  = '<p class="no-articles">Could not load analysis.</p>';
  }
}

async function changeRange(range) {
  if (range === currentRange || !currentKey) return;
  currentRange = range;
  document.querySelectorAll('.range-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.range === range);
  });

  // Update modal header change % to match selected range
  const inst = instruments.find(i => i.key === currentKey);
  if (inst) {
    const chg   = _instChg(inst, range);
    const chgEl = document.getElementById('m-chg');
    if (chg === null) {
      chgEl.textContent = ''; chgEl.className = 'modal-chg';
    } else if (chg > 0) {
      chgEl.textContent = '\u25b2 +' + chg.toFixed(2) + '%'; chgEl.className = 'modal-chg up';
    } else {
      chgEl.textContent = '\u25bc ' + chg.toFixed(2) + '%'; chgEl.className = 'modal-chg down';
    }
  }

  resetChart();
  try {
    const res = await fetch('/api/history/' + currentKey + '?range=' + range);
    if (res.ok) renderChart(await res.json());
    else showChartError();
  } catch(e) { showChartError(); }
}

function closeCommodityModal() {
  document.getElementById('overlay').classList.remove('open');
  document.body.style.overflow = '';
  if (chart) { chart.destroy(); chart = null; }
  currentKey = null;
}
document.getElementById('close-btn').addEventListener('click', closeCommodityModal);
document.getElementById('overlay').addEventListener('click', e => {
  if (e.target.id === 'overlay') closeCommodityModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeBriefingModal(); closeCommodityModal(); closeFirmModal(); }
});

/* ── Chart ─────────────────────────────────────────────────────────────────── */
function resetChart() {
  const ph = document.getElementById('chart-ph');
  const cv = document.getElementById('price-chart');
  ph.style.display = 'flex';
  ph.innerHTML = '<span class="spin"></span>&nbsp;Loading chart\u2026';
  cv.style.display = 'none';
  if (chart) { chart.destroy(); chart = null; }
}

function showChartError() {
  const ph = document.getElementById('chart-ph');
  ph.style.display = 'flex';
  const inst = currentKey ? instruments.find(i => i.key === currentKey) : null;
  const label = inst ? inst.label : '';
  ph.innerHTML =
    `<span style="color:var(--red);font-size:0.8rem">Chart unavailable${label ? ' \u2014 ' + esc(label) : ''}</span>` +
    `&ensp;<button class="chart-retry-btn" onclick="changeRange(currentRange)">Retry</button>`;
}

function renderChart(hist) {
  const ph = document.getElementById('chart-ph');
  const cv = document.getElementById('price-chart');
  ph.style.display = 'none';
  cv.style.display = 'block';

  const prices  = hist.prices;
  const isUp    = prices.length > 1 && prices[prices.length - 1] >= prices[0];
  const lineCol = isUp ? '#22c55e' : '#ef4444';

  const ctx  = cv.getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 210);
  grad.addColorStop(0, isUp ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');

  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: hist.labels,
      datasets: [{
        data: prices, borderColor: lineCol, borderWidth: 1.8,
        backgroundColor: grad, fill: true, tension: 0.3,
        pointRadius: 0, pointHoverRadius: 5,
        pointHoverBackgroundColor: lineCol,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#131e30',
          borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1,
          titleColor: '#6b7f9e', titleFont: { size: 11 },
          bodyColor: '#dde8f8',  bodyFont: { size: 12, weight: '600' },
          padding: 10, displayColors: false,
          callbacks: {
            label: ctx => {
              const v = ctx.parsed.y;
              if (hist.thousands) {
                return hist.prefix + v.toLocaleString('en-US', {
                  minimumFractionDigits: hist.decimals,
                  maximumFractionDigits: hist.decimals,
                }) + hist.suffix;
              }
              return hist.prefix + v.toFixed(hist.decimals) + hist.suffix;
            }
          }
        }
      },
      scales: {
        x: {
          grid:   { color: 'rgba(255,255,255,0.04)' },
          border: { color: 'rgba(255,255,255,0.06)' },
          ticks:  { color: '#374d68', font: { size: 10 }, maxTicksLimit: 8, maxRotation: 0 }
        },
        y: {
          position: 'right',
          grid:   { color: 'rgba(255,255,255,0.04)' },
          border: { color: 'rgba(255,255,255,0.06)' },
          ticks: {
            color: '#374d68', font: { size: 10 },
            callback: v => {
              if (hist.thousands)
                return hist.prefix + v.toLocaleString('en-US', { maximumFractionDigits: 0 });
              return hist.prefix + v.toFixed(Math.min(hist.decimals, 3));
            }
          }
        }
      }
    }
  });
}

/* ── Articles ───────────────────────────────────────────────────────────────── */
function renderArticles(articles, accent) {
  const area = document.getElementById('articles-area');
  if (!articles || articles.length === 0) {
    area.innerHTML = '<p class="no-articles">No articles available at this time.</p>';
    return;
  }
  const cards = articles.map(a => `
    <a class="article-card" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">
      <div class="article-publisher">${esc(a.publisher || 'News')}</div>
      <div class="article-title">${esc(a.title)}</div>
      ${a.summary ? `<div class="article-snippet">${esc(a.summary)}</div>` : ''}
      <div class="article-footer">
        <span class="article-date">${esc(a.published)}</span>
        <span class="article-cta">Read more &rarr;</span>
      </div>
    </a>
  `).join('');
  area.innerHTML = `<div class="articles-grid">${cards}</div>`;
}

/* ── Firms page ────────────────────────────────────────────────────────────── */
const FIRMS_DATA = [
  // ── Commodity Trading Houses ──────────────────────────────────────────────
  {
    key: 'vitol', name: 'Vitol', fullName: 'Vitol Group',
    category: 'Trading House', region: 'Europe', hq: 'Rotterdam',
    initials: 'VI', color: '#e65c00', website: 'vitol.com',
    tagline: "World's largest independent energy trader",
    overview: "Vitol is the world's largest independent energy trading company, handling over 7 million barrels of oil equivalent per day. Founded in Rotterdam in 1966, it operates across the full energy supply chain — crude oil, petroleum products, LNG, power, and carbon — across 40+ countries through a network of trading, refining, and storage assets.",
    markets: ['Crude Oil', 'Petroleum Products', 'LNG / Natural Gas', 'Power & Renewables', 'Carbon'],
    offices: ['Rotterdam', 'Geneva', 'Houston', 'Singapore', 'Dubai', 'London'],
  },
  {
    key: 'trafigura', name: 'Trafigura', fullName: 'Trafigura Group',
    category: 'Trading House', region: 'Europe', hq: 'Geneva',
    initials: 'TF', color: '#c62828', website: 'trafigura.com',
    tagline: "Global commodity merchant spanning oil, metals, and minerals",
    overview: "Trafigura is one of the world's largest commodity trading companies, active in crude oil, refined products, metals, and minerals across 150+ countries. Founded in 1993, it has significant investments in logistics infrastructure including ports, terminals, and warehouses. Trafigura is privately held by its management and employees.",
    markets: ['Crude Oil', 'Refined Products', 'Metals & Minerals', 'LNG', 'Bulk Commodities'],
    offices: ['Geneva', 'Singapore', 'Houston', 'Mumbai', 'Shanghai', 'London'],
  },
  {
    key: 'glencore', name: 'Glencore', fullName: 'Glencore plc',
    category: 'Trading House', region: 'Europe', hq: 'Baar, Switzerland',
    initials: 'GL', color: '#1565c0', website: 'glencore.com',
    tagline: "Diversified natural resource trader, producer, and recycler",
    overview: "Glencore is one of the world's largest diversified natural resource companies, combining a major commodity trading operation with a global portfolio of mining and processing assets. Publicly listed since 2011, Glencore produces and trades coal, copper, cobalt, nickel, zinc, oil, and agricultural products. Its physical asset base provides a structural competitive advantage in trading flows.",
    markets: ['Copper & Cobalt', 'Coal', 'Oil & LNG', 'Nickel & Zinc', 'Agricultural Products'],
    offices: ['Baar', 'London', 'Singapore', 'Johannesburg', 'Astana', 'Toronto'],
  },
  {
    key: 'mercuria', name: 'Mercuria', fullName: 'Mercuria Energy Group',
    category: 'Trading House', region: 'Europe', hq: 'Geneva',
    initials: 'ME', color: '#6a1b9a', website: 'mercuria.com',
    tagline: "Independent energy and commodity trader with global reach",
    overview: "Mercuria is one of the world's largest independent energy and commodity trading groups. Founded in 2004, it has grown rapidly through diversification beyond crude oil into natural gas, LNG, metals, carbon, and power. Mercuria operates in 50+ countries and has made significant investments in physical assets including storage terminals, refineries, and renewables infrastructure.",
    markets: ['Crude Oil', 'Natural Gas & LNG', 'Metals', 'Carbon & Power', 'Biofuels'],
    offices: ['Geneva', 'Houston', 'Singapore', 'Beijing', 'London', 'Moscow'],
  },
  {
    key: 'gunvor', name: 'Gunvor', fullName: 'Gunvor Group',
    category: 'Trading House', region: 'Europe', hq: 'Geneva',
    initials: 'GU', color: '#2e7d32', website: 'gunvorgroup.com',
    tagline: "Energy trader specialising in crude oil, LNG, and refined products",
    overview: "Gunvor is a major global commodities trading group focused on energy. Founded in 2000, it handles crude oil, refined petroleum products, LNG, and power across global markets. Gunvor has built a network of refining and terminal infrastructure in Europe and is active across the full energy value chain from production logistics to downstream distribution.",
    markets: ['Crude Oil', 'LNG', 'Petroleum Products', 'Power', 'Petrochemicals'],
    offices: ['Geneva', 'Singapore', 'Houston', 'Antwerp', 'Dubai', 'London'],
  },
  {
    key: 'cargill', name: 'Cargill', fullName: 'Cargill, Incorporated',
    category: 'Trading House', region: 'US', hq: 'Minnetonka, MN',
    initials: 'CA', color: '#f57f17', website: 'cargill.com',
    tagline: "Agricultural and commodity giant with energy and financial arms",
    overview: "Cargill is one of the largest privately held corporations in the world, founded in 1865. Its core businesses span agriculture — grains, oilseeds, cotton, sugar, cocoa — but Cargill also has significant energy trading, metals, and financial risk management operations. With 160,000+ employees across 70+ countries, Cargill is a dominant force in global food and commodity supply chains.",
    markets: ['Grains & Oilseeds', 'Sugar & Cocoa', 'Cotton', 'Energy', 'Financial Risk Management'],
    offices: ['Minneapolis', 'Geneva', 'Singapore', 'São Paulo', 'Tokyo', 'Amsterdam'],
  },
  {
    key: 'koch', name: 'Koch Supply & Trading', fullName: 'Koch Supply & Trading, LP',
    category: 'Trading House', region: 'US', hq: 'Houston, TX',
    initials: 'KS', color: '#37474f', website: 'kochind.com',
    tagline: "Commodity trader and risk manager within the Koch Industries group",
    overview: "Koch Supply & Trading is the commodity trading arm of Koch Industries, one of the largest privately held companies in the United States. It trades crude oil, petroleum products, natural gas, petrochemicals, and commodities, leveraging the broader Koch group's refining, chemical manufacturing, and distribution assets to support trading activities and risk management functions.",
    markets: ['Crude Oil', 'Refined Products', 'Natural Gas', 'Petrochemicals', 'Commodities'],
    offices: ['Houston', 'Rotterdam', 'Singapore', 'London', 'Calgary'],
  },
  {
    key: 'ldcom', name: 'Louis Dreyfus', fullName: 'Louis Dreyfus Company',
    category: 'Trading House', region: 'Europe', hq: 'Rotterdam',
    initials: 'LD', color: '#00695c', website: 'ldcom.com',
    tagline: "Agricultural commodity merchant and processor across global supply chains",
    overview: "Louis Dreyfus Company (LDC) is a global merchant and processor of agricultural goods, operating across the food and feed value chain since 1851. LDC trades and processes grains, oilseeds, sugar, coffee, cotton, rice, and juice through a global network of processing facilities, port terminals, and logistics infrastructure. It is privately held by the Louis-Dreyfus family.",
    markets: ['Grains & Oilseeds', 'Sugar', 'Cotton', 'Coffee & Cocoa', 'Rice & Juice'],
    offices: ['Rotterdam', 'Geneva', 'São Paulo', 'Singapore', 'Dubai', 'Buenos Aires'],
  },
  {
    key: 'castleton', name: 'Castleton Commodities', fullName: 'Castleton Commodities International',
    category: 'Trading House', region: 'US', hq: 'Stamford, CT',
    initials: 'CC', color: '#0277bd', website: 'castletoncommodities.com',
    tagline: "Multi-commodity merchant with energy, metals, and shipping focus",
    overview: "Castleton Commodities International (CCI) is a global merchant trading firm founded in 2012 by former Goldman Sachs commodity traders. CCI has rapidly built physical trading and asset positions across natural gas, LNG, crude oil, petroleum products, metals, and dry bulk shipping, operating with a principal trading model that emphasises physical asset control.",
    markets: ['Natural Gas & LNG', 'Crude Oil & Products', 'Metals', 'Shipping', 'Power'],
    offices: ['Stamford', 'Houston', 'Geneva', 'Singapore', 'London'],
  },
  {
    key: 'hartree', name: 'Hartree Partners', fullName: 'Hartree Partners, LP',
    category: 'Trading House', region: 'US', hq: 'New York',
    initials: 'HP', color: '#7b1fa2', website: 'hartreepartners.com',
    tagline: "Energy and commodity merchant with global physical trading operations",
    overview: "Hartree Partners is a global energy and commodity merchant founded in 2001 by former Shell traders. It operates across natural gas, LNG, crude oil, petroleum products, metals, power, and dry bulk shipping. Hartree is a principal trading firm that has invested significantly in physical infrastructure assets to support its trading activities across the commodity complex.",
    markets: ['Natural Gas & LNG', 'Crude Oil & Products', 'Power', 'Metals', 'Shipping'],
    offices: ['New York', 'Houston', 'London', 'Singapore', 'Geneva'],
  },
  // ── Hedge Funds ───────────────────────────────────────────────────────────
  {
    key: 'citadel', name: 'Citadel', fullName: 'Citadel LLC',
    category: 'Hedge Fund', region: 'US', hq: 'Miami, FL',
    initials: 'CI', color: '#b71c1c', website: 'citadel.com',
    tagline: "Multi-strategy hedge fund and global market maker",
    overview: "Citadel is one of the world's largest and most successful alternative investment management firms, founded by Ken Griffin in 1990. It operates two distinct businesses: Citadel (hedge fund) and Citadel Securities (market maker). Commodity and macro strategies are core engines alongside equities and fixed income, with Citadel consistently ranking among the most profitable funds globally.",
    markets: ['Commodities', 'Global Macro', 'Equities L/S', 'Fixed Income & Credit', 'Quantitative Strategies'],
    offices: ['Miami', 'Chicago', 'New York', 'London', 'Hong Kong', 'Dubai'],
  },
  {
    key: 'millennium', name: 'Millennium', fullName: 'Millennium Management LLC',
    category: 'Hedge Fund', region: 'US', hq: 'New York',
    initials: 'MM', color: '#e64a19', website: 'mlp.com',
    tagline: "Multi-strategy platform with 300+ independent investment teams",
    overview: "Millennium Management is one of the world's largest multi-strategy hedge funds, founded by Izzy Englander in 1989. Operating through a platform of 300+ independent trading teams, Millennium's strategies span equities, fixed income, commodities, and macro. Its commodity trading operations include energy, metals, and agricultural markets across physical and derivatives instruments.",
    markets: ['Commodities', 'Equities L/S', 'Fixed Income', 'Global Macro', 'Statistical Arbitrage'],
    offices: ['New York', 'London', 'Hong Kong', 'Singapore', 'Miami', 'Dublin'],
  },
  {
    key: 'point72', name: 'Point72', fullName: 'Point72 Asset Management',
    category: 'Hedge Fund', region: 'US', hq: 'Stamford, CT',
    initials: 'P7', color: '#1565c0', website: 'point72.com',
    tagline: "Global discretionary and quantitative multi-strategy fund",
    overview: "Point72 Asset Management was founded by Steve Cohen in 2014 as the successor to SAC Capital. It manages capital through discretionary long/short equity, global macro, commodities, and systematic quantitative strategies. Point72 has significantly expanded its macro and commodities trading capabilities alongside its core equities franchise.",
    markets: ['Equities L/S', 'Global Macro', 'Commodities', 'Quantitative Strategies', 'Venture'],
    offices: ['Stamford', 'New York', 'London', 'Hong Kong', 'Singapore', 'Tokyo'],
  },
  {
    key: 'balyasny', name: 'Balyasny', fullName: 'Balyasny Asset Management',
    category: 'Hedge Fund', region: 'US', hq: 'Chicago',
    initials: 'BA', color: '#4527a0', website: 'balyasny.com',
    tagline: "Multi-strategy manager with systematic and discretionary capabilities",
    overview: "Balyasny Asset Management is a global multi-strategy hedge fund founded by Dmitry Balyasny in 2001. The firm operates across long/short equity, global macro, and commodities strategies using both discretionary and systematic approaches. Balyasny has expanded significantly from its equity roots to build dedicated macro and commodity trading teams.",
    markets: ['Equities L/S', 'Global Macro', 'Commodities', 'Quantitative Strategies'],
    offices: ['Chicago', 'New York', 'London', 'Hong Kong', 'Dubai'],
  },
  {
    key: 'brevan', name: 'Brevan Howard', fullName: 'Brevan Howard Asset Management',
    category: 'Hedge Fund', region: 'Europe', hq: 'Jersey / Abu Dhabi',
    initials: 'BH', color: '#283593', website: 'brevanhoward.com',
    tagline: "Global macro hedge fund with rates, FX, and commodity focus",
    overview: "Brevan Howard is one of Europe's largest hedge funds, founded in 2002 by Alan Howard and colleagues from Credit Suisse. Primarily known as a global macro fund with deep expertise in interest rates, FX, and commodity derivatives, Brevan Howard has significantly expanded its systematic trading capabilities alongside its core discretionary macro operations.",
    markets: ['Global Macro', 'Interest Rates', 'FX', 'Commodities', 'Systematic Strategies'],
    offices: ['Jersey', 'Abu Dhabi', 'London', 'Geneva', 'New York', 'Hong Kong'],
  },
  {
    key: 'caxton', name: 'Caxton Associates', fullName: 'Caxton Associates LP',
    category: 'Hedge Fund', region: 'US', hq: 'Princeton, NJ',
    initials: 'CX', color: '#00695c', website: 'caxton.com',
    tagline: "Discretionary global macro manager with a 40-year track record",
    overview: "Caxton Associates is one of the oldest and most respected global macro hedge funds, founded by Bruce Kovner in 1983. The firm specialises in discretionary macro trading across FX, commodities, rates, and equities. Caxton is known for its rigorous fundamental research approach and has consistently operated as a principal-led, research-driven trading organisation.",
    markets: ['Global Macro', 'FX', 'Commodities', 'Interest Rates', 'Equities'],
    offices: ['Princeton', 'London'],
  },
  {
    key: 'bluecrest', name: 'BlueCrest Capital', fullName: 'BlueCrest Capital Management',
    category: 'Hedge Fund', region: 'Europe', hq: 'Geneva',
    initials: 'BC', color: '#0277bd', website: 'bluecrest.com',
    tagline: "Macro and systematic manager, now trading only proprietary capital",
    overview: "BlueCrest Capital Management returned all outside investor capital in 2015 to trade solely as a proprietary firm. Founded by Michael Platt in 2000, BlueCrest built its reputation through global macro, systematic CTA (BlueTrend), and credit strategies. It continues to operate as a major principal trading firm in global macro and systematic markets.",
    markets: ['Global Macro', 'Systematic / CTA', 'Credit', 'Rates', 'FX & Commodities'],
    offices: ['Geneva', 'London', 'New York'],
  },
  {
    key: 'aqr', name: 'AQR Capital Management', fullName: 'AQR Capital Management LLC',
    category: 'Hedge Fund', region: 'US', hq: 'Greenwich, CT',
    initials: 'AQ', color: '#00838f', website: 'aqr.com',
    tagline: "Quantitative factor-based manager across global asset classes",
    overview: "AQR Capital Management is one of the world's largest quantitative investment managers, founded in 1998 by Cliff Asness and colleagues from Goldman Sachs. AQR applies systematic, factor-based strategies across equities, fixed income, currencies, and commodities in both hedge fund and long-only formats. Commodity exposure is primarily through trend-following, carry, and value factor strategies in futures markets.",
    markets: ['Quantitative / Factor', 'Commodity Futures', 'Trend-Following', 'Fixed Income', 'Equities'],
    offices: ['Greenwich', 'New York', 'London', 'Hong Kong', 'Sydney'],
  },
  {
    key: 'winton', name: 'Winton Group', fullName: 'Winton Group Ltd',
    category: 'Hedge Fund', region: 'Europe', hq: 'London',
    initials: 'WG', color: '#37474f', website: 'winton.com',
    tagline: "Research-driven systematic CTA with commodity futures expertise",
    overview: "Winton Group is a leading systematic investment manager founded by David Harding in 1997. Winton applies scientific research and statistical methods to trading systems across global futures markets, including commodities. It is one of the largest commodity trading advisors (CTAs) globally, with significant exposure to energy, metals, and agricultural futures through trend-following and diversified systematic strategies.",
    markets: ['Systematic / CTA', 'Commodity Futures', 'Equity Futures', 'Fixed Income Futures', 'FX'],
    offices: ['London', 'Hong Kong', 'New York'],
  },
  {
    key: 'man', name: 'Man Group', fullName: 'Man Group plc',
    category: 'Hedge Fund', region: 'Europe', hq: 'London',
    initials: 'MN', color: '#1b5e20', website: 'man.com',
    tagline: "Listed alternative manager with leading systematic AHL platform",
    overview: "Man Group is one of the world's largest publicly listed alternative investment managers, with roots dating to 1783. Its primary systematic engine — Man AHL — is one of the longest-established CTAs globally, with significant commodity futures exposure through trend-following and diversified systematic strategies. Man Group also operates discretionary macro and credit strategies through Man GLG and Man FRM.",
    markets: ['Systematic / CTA', 'Commodity Futures', 'Global Macro', 'Credit', 'Multi-Strategy'],
    offices: ['London', 'New York', 'Hong Kong', 'Singapore', 'Sydney', 'Denver'],
  },
];

const _FIRMS_MAP = Object.fromEntries(FIRMS_DATA.map(f => [f.key, f]));

function renderFirmsPage() {
  const el = document.getElementById('firms-page-body');
  if (!el) return;
  const categories = [
    { key: 'Trading House', label: 'Commodity Trading Houses' },
    { key: 'Hedge Fund',    label: 'Hedge Funds' },
  ];
  let html = '';
  categories.forEach(cat => {
    const firms = FIRMS_DATA.filter(f => f.category === cat.key);
    html += `<div class="page-section-heading">${cat.label}</div>`;
    html += '<div class="firm-grid">';
    firms.forEach(f => {
      html += `<div class="firm-card" onclick="openFirmModal('${f.key}')">
        <div class="firm-card-header">
          <div class="firm-logo" style="background:${f.color}">${esc(f.initials)}</div>
          <div class="firm-card-meta">
            <div class="firm-card-name">${esc(f.name)}</div>
            <div class="firm-card-tags">
              <span class="firm-tag firm-tag-region">${esc(f.region)}</span>
              <span class="firm-tag">${esc(f.category)}</span>
            </div>
          </div>
        </div>
        <div class="firm-card-tagline">${esc(f.tagline)}</div>
        <div class="firm-card-hint">View details &rarr;</div>
      </div>`;
    });
    html += '</div>';
  });
  el.innerHTML = html;
}
renderFirmsPage();

function openFirmModal(key) {
  const f = _FIRMS_MAP[key];
  if (!f) return;
  const modal = document.getElementById('firm-modal');
  modal.style.setProperty('--modal-accent', f.color);
  modal.style.borderTopColor = f.color;
  document.getElementById('firm-modal-body').innerHTML = `
    <div class="firm-modal-header">
      <div class="firm-modal-logo" style="background:${f.color}">${esc(f.initials)}</div>
      <div class="firm-modal-header-text">
        <div class="firm-modal-name">${esc(f.fullName)}</div>
        <div class="firm-modal-tags">
          <span class="firm-tag firm-tag-region">${esc(f.region)}</span>
          <span class="firm-tag">${esc(f.category)}</span>
          <span class="firm-tag">${esc(f.hq)}</span>
        </div>
        <div class="firm-modal-tagline">${esc(f.tagline)}</div>
      </div>
    </div>
    <div class="modal-divider"></div>
    <p class="summary-overview">${esc(f.overview)}</p>
    <div class="firm-detail-cols">
      <div>
        <div class="firm-detail-col-title">Focus &amp; Markets</div>
        <ul class="firm-detail-list">${f.markets.map(m => `<li>${esc(m)}</li>`).join('')}</ul>
      </div>
      <div>
        <div class="firm-detail-col-title">Offices</div>
        <ul class="firm-detail-list">${f.offices.map(o => `<li>${esc(o)}</li>`).join('')}</ul>
      </div>
    </div>
    <div class="modal-divider"></div>
    <div class="section-label" style="margin-bottom:14px">Recent Activity</div>
    <div id="firm-activity-body">
      <div class="placeholder"><span class="spin"></span>Loading&hellip;</div>
    </div>
  `;
  document.getElementById('firm-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';

  // Fetch live recent activity for this firm
  const keyword = f.category === 'Trading House' ? 'commodity trading' : 'hedge fund';
  const q = encodeURIComponent(f.name + ' ' + keyword);
  fetch('/api/news/search?q=' + q)
    .then(r => r.json())
    .then(articles => {
      const area = document.getElementById('firm-activity-body');
      if (!area) return;
      if (!articles || !articles.length) {
        area.innerHTML = '<p class="firm-activity-none">No recent news found for ' + esc(f.name) + '.</p>';
        return;
      }
      area.innerHTML = '<div class="firm-activity-feed">' +
        articles.map(a => {
          const meta = [a.source, a.published].filter(Boolean).join(' · ');
          return `<a class="firm-activity-row" href="${esc(a.url)}" target="_blank" rel="noopener">
            <div class="firm-activity-headline">${esc(a.title)}</div>
            ${meta ? `<div class="firm-activity-meta">${esc(meta)}</div>` : ''}
          </a>`;
        }).join('') + '</div>';
    })
    .catch(() => {
      const area = document.getElementById('firm-activity-body');
      if (area) area.innerHTML = '<p class="firm-activity-none">Could not load recent activity.</p>';
    });
}

function closeFirmModal() {
  document.getElementById('firm-overlay').classList.remove('open');
  document.body.style.overflow = '';
}
document.getElementById('firm-close-btn').addEventListener('click', closeFirmModal);
document.getElementById('firm-overlay').addEventListener('click', e => {
  if (e.target.id === 'firm-overlay') closeFirmModal();
});

/* ── Summary (macro / geopolitical / outlook) ──────────────────────────────── */
function renderSummary(data) {
  let html = '';
  html += `<p class="summary-overview">${esc(data.overview)}</p>`;

  const hasContext = data.context && data.context.length > 0;
  const half = hasContext ? Math.ceil(data.context.length / 2) : 0;
  const colA = hasContext ? data.context.slice(0, half) : null;
  const colB = hasContext ? data.context.slice(half)    : null;

  html += '<div class="summary-cols">';

  html += '<div class="summary-col">';
  html += '<div class="summary-col-heading">' + (hasContext ? 'Current Macro Context' : 'Macro Factors') + '</div>';
  if (hasContext && colA.length) {
    html += '<ul class="context-list">' + colA.map(item =>
      `<li>
        <a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a>
        <div class="context-meta">${esc(item.source)}${item.published ? ' &middot; ' + esc(item.published) : ''}</div>
      </li>`
    ).join('') + '</ul>';
  } else {
    html += '<ul>' + data.macro.map(x => `<li>${esc(x)}</li>`).join('') + '</ul>';
  }
  html += '</div>';

  html += '<div class="summary-col">';
  html += '<div class="summary-col-heading">' + (hasContext ? 'Market &amp; Geopolitical News' : 'Geopolitical Drivers') + '</div>';
  if (hasContext && colB.length) {
    html += '<ul class="context-list">' + colB.map(item =>
      `<li>
        <a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a>
        <div class="context-meta">${esc(item.source)}${item.published ? ' &middot; ' + esc(item.published) : ''}</div>
      </li>`
    ).join('') + '</ul>';
  } else {
    html += '<ul>' + data.geopolitical.map(x => `<li>${esc(x)}</li>`).join('') + '</ul>';
  }
  html += '</div>';

  html += '</div>';
  html += `
    <div class="outlook-box">
      <div class="outlook-label">Outlook</div>
      ${esc(data.outlook)}
    </div>`;

  document.getElementById('summary-area').innerHTML = html;
}

/* ── Settings page ─────────────────────────────────────────────────────────── */
const _ACCENT_PRESETS = [
  { id: 'default', label: 'Default',  color: '#3b82f6' },
  { id: 'amber',   label: 'Amber',    color: '#f59e0b' },
  { id: 'teal',    label: 'Teal',     color: '#14b8a6' },
  { id: 'rose',    label: 'Rose',     color: '#f43f5e' },
  { id: 'slate',   label: 'Slate',    color: '#64748b' },
];

function renderSettingsPage() {
  const el = document.getElementById('settings-page-body');
  if (!el) return;

  const rangeOptions = [
    { v: '1d', l: '24H' }, { v: '1w', l: '1W' },
    { v: '1mo', l: '1M' }, { v: '1y', l: '1Y' },
  ];

  let html = '<div class="settings-sections">';

  // ── Display ──────────────────────────────────────────────────
  html += '<div class="settings-section">';
  html += '<div class="settings-section-title">Display</div>';

  // Compact mode
  const compactChecked = _settings.compactMode ? 'checked' : '';
  html += `<div class="settings-row">
    <div>
      <div class="settings-row-label">Compact Mode</div>
      <div class="settings-row-desc">Tighter padding and smaller cards</div>
    </div>
    <label class="settings-toggle">
      <input type="checkbox" ${compactChecked} onchange="setCompact(this.checked)">
      <div class="settings-toggle-track"></div>
      <div class="settings-toggle-thumb"></div>
    </label>
  </div>`;

  // Theme toggle
  html += `<div class="settings-row">
    <div>
      <div class="settings-row-label">Colour Scheme</div>
      <div class="settings-row-desc">Dark is the default on first load</div>
    </div>
    <div class="settings-pills">
      <button class="settings-pill${_settings.theme !== 'light' ? ' active' : ''}" onclick="setTheme('dark')">Dark</button>
      <button class="settings-pill${_settings.theme === 'light' ? ' active' : ''}" onclick="setTheme('light')">Light</button>
    </div>
  </div>`;

  // Accent colour
  const swatches = _ACCENT_PRESETS.map(p =>
    `<div class="settings-accent-swatch${_settings.accentPreset === p.id ? ' active' : ''}"
         style="background:${p.color}" title="${p.label}"
         onclick="setAccentPreset('${p.id}')"></div>`
  ).join('');
  html += `<div class="settings-row">
    <div>
      <div class="settings-row-label">Accent Colour</div>
      <div class="settings-row-desc">UI chrome and navigation highlights</div>
    </div>
    <div class="settings-accents">${swatches}</div>
  </div>`;

  html += '</div>'; // .settings-section

  // ── Market Preferences ───────────────────────────────────────
  html += '<div class="settings-section">';
  html += '<div class="settings-section-title">Market Preferences</div>';

  // Default chart range
  const rangePills = rangeOptions.map(o =>
    `<button class="settings-pill${_settings.chartRange === o.v ? ' active' : ''}"
             onclick="setChartRange('${o.v}')">${o.l}</button>`
  ).join('');
  html += `<div class="settings-row">
    <div>
      <div class="settings-row-label">Default Chart Range</div>
      <div class="settings-row-desc">Applied when opening instrument details</div>
    </div>
    <div class="settings-pills">${rangePills}</div>
  </div>`;

  html += '<div class="settings-note">Data refresh interval (${REFRESH}s) is configured server-side.</div>';
  html += '</div>'; // .settings-section

  // ── Market Visibility ────────────────────────────────────────
  html += '<div class="settings-section">';
  html += '<div class="settings-section-title">Market Visibility</div>';

  html += '<div style="font-size:0.78rem;color:var(--muted);margin-bottom:16px;line-height:1.6">' +
    'Choose which instruments appear on the <b>Markets page</b>. Hidden instruments are still tracked and appear in Home, pulse strip, and movers.' +
    '</div>';

  INSTRUMENT_GROUPS.forEach(group => {
    html += `<div class="settings-inst-group">`;
    html += `<div class="settings-inst-group-label">${esc(group.label)}</div>`;
    html += '<div class="settings-inst-chips">';
    group.keys.forEach(key => {
      const inst = instruments.find(i => i.key === key);
      const label = inst ? inst.label : key;
      const visible = !_settings.hiddenInstruments.includes(key);
      html += `<div class="settings-inst-chip${visible ? ' visible' : ''}" onclick="toggleInstrumentVisibility('${key}')">
        <div class="settings-inst-chip-dot"></div>
        <span>${esc(label)}</span>
      </div>`;
    });
    html += '</div></div>';
  });

  html += '</div>'; // .settings-section (Market Visibility)

  // ── Account ──────────────────────────────────────────────────
  html += '<div class="settings-section">';
  html += '<div class="settings-section-title">Account</div>';
  html += `<div class="settings-row">
    <div>
      <div class="settings-row-label">Sign In or Create Account</div>
      <div class="settings-row-desc">Save preferences and access personalised features</div>
    </div>
    <div class="settings-pills">
      <button class="settings-pill" disabled style="opacity:0.45;cursor:default">Sign In</button>
      <button class="settings-pill" disabled style="opacity:0.45;cursor:default">Create Account</button>
    </div>
  </div>`;
  html += '<div class="settings-note">Account system coming soon.</div>';
  html += '</div>'; // .settings-section (Account)

  html += '</div>'; // .settings-sections
  el.innerHTML = html;
}

function setCompact(on) {
  _settings.compactMode = on;
  saveSettings(); applySettings();
  // re-render settings to keep toggle in sync
  renderSettingsPage();
}

function setAccentPreset(id) {
  _settings.accentPreset = id;
  saveSettings(); applySettings();
  renderSettingsPage();
}

function setChartRange(range) {
  _settings.chartRange = range;
  saveSettings();
  renderSettingsPage();
}

function setTheme(t) {
  _settings.theme = t;
  saveSettings(); applySettings();
  renderSettingsPage();
}

function toggleInstrumentVisibility(key) {
  const hidden = _settings.hiddenInstruments;
  const idx = hidden.indexOf(key);
  if (idx === -1) hidden.push(key);
  else hidden.splice(idx, 1);
  saveSettings();
  renderPricesGrid();   // update Markets grid immediately
  renderSettingsPage(); // re-render to reflect new state
}

renderSettingsPage();
