/* ── Auth ───────────────────────────────────────────────────────────────────── */
// If any API call returns 401 (session expired / not logged in), redirect to
// the login page so the user is never stuck on a blank/broken dashboard.
async function apiFetch(url, opts) {
  const res = await fetch(url, opts);
  if (res.status === 401) { window.location.href = '/login'; return null; }
  return res;
}

/* ── Utilities ─────────────────────────────────────────────────────────────── */

// Trusted source badge
const _TRUSTED_SOURCES = new Set([
  'Reuters','Bloomberg','Financial Times','FT','The Wall Street Journal','WSJ',
  'The Economist','CNBC','BBC','Associated Press','AP','MarketWatch','Barron\'s',
  'S&P Global','Platts','Argus Media','Fastmarkets','ICE','CME Group',
]);

function _sourceBadge(source) {
  if (!source) return '';
  const trusted = _TRUSTED_SOURCES.has(source);
  return `<span class="source-badge${trusted ? ' source-badge-trusted' : ''}">${esc(source)}</span>`;
}

// Stable sort: trusted-source articles first, relative order within each group preserved.
function _sortByTrust(articles) {
  if (!articles || !articles.length) return articles;
  const trusted = articles.filter(a => _TRUSTED_SOURCES.has(a.source));
  const rest    = articles.filter(a => !_TRUSTED_SOURCES.has(a.source));
  return trusted.concat(rest);
}

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
  // Clear firms search bar value when switching to firms view so stale text doesn't persist
  if (name === 'firms') {
    const fsEl = document.getElementById('firms-search');
    if (fsEl && fsEl.value) { fsEl.value = ''; setFirmsSearch(''); }
  }
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
      const is429 = inst.error.toLowerCase().includes('429') || inst.error.toLowerCase().includes('too many');
      pEl.className = 'card-price err';
      pEl.textContent = is429 ? 'Updating\u2026' : 'Unavailable';
      const cEl = document.getElementById('c-' + inst.key);
      if (cEl) cEl.innerHTML = '<span class="neu" style="font-size:0.6rem">' + esc(is429 ? 'Rate limited \u2014 retrying\u2026' : inst.error.substring(0, 45)) + '</span>';
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
    const res = await apiFetch('/api/prices');
    if (!res) return;
    renderCards(await res.json());
    countdown = REFRESH;
  } catch(e) { console.error('Price fetch failed:', e); }
}
fetchPrices();
setInterval(fetchPrices, REFRESH * 1000);

/* ── Briefing card loaders ─────────────────────────────────────────────────── */
let _moversData       = null;
let _newsData         = null;
let _driversData      = null;
let _powerMarketsNews = null;  // null = not yet fetched; [] = fetched, empty
let _newsLastUpdated    = null;
let _macroLastUpdated   = null;

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

function _fetchPowerMarketsNews() {
  apiFetch('/api/news/search?q=' + encodeURIComponent(POWER_MARKETS_QUERY))
    .then(r => r && r.json())
    .then(articles => {
      if (!articles) return;
      if (!Array.isArray(articles)) { _powerMarketsNews = []; renderNewsPage(); return; }
      // Sort by recency descending
      const sorted = [...articles].sort((a, b) => {
        const ta = a.published ? new Date(a.published).getTime() : 0;
        const tb = b.published ? new Date(b.published).getTime() : 0;
        return tb - ta;
      });
      // Filter to within MAX_AGE_DAYS; fallback to all if too few remain
      const cutoff = Date.now() - POWER_MARKETS_MAX_AGE_DAYS * 86_400_000;
      const recent = sorted.filter(a => a.published && new Date(a.published).getTime() >= cutoff);
      const pool   = recent.length >= 3 ? recent : sorted;
      // Trust-elevate within the recency-sorted pool
      _powerMarketsNews = _sortByTrust(pool);
      renderNewsPage();
    })
    .catch(() => { _powerMarketsNews = []; });
}

async function loadBriefingData() {
  // Seed _moversData from prices if instruments not yet loaded
  if (!instruments.length) {
    const priceRes = await apiFetch('/api/prices').then(r => r ? r.json() : []).catch(() => []);
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
    apiFetch('/api/home/news').then(r => r ? r.json() : []).catch(() => []),
    apiFetch('/api/home/drivers').then(r => r ? r.json() : []).catch(() => []),
  ]);
  _newsData    = news;
  _driversData = drivers;
  _newsLastUpdated  = new Date();
  _macroLastUpdated = new Date();
  const _homeUpdEl = document.getElementById('home-updated-line');
  if (_homeUpdEl) _homeUpdEl.textContent = _fmtUpdated(_newsLastUpdated);
  renderNewsPreview();
  renderDriversPreview();
  renderNewsPage();
  _fetchPowerMarketsNews();
  renderMacroPage();
  renderSignalsBanner();
}
loadBriefingData();
// Refresh all briefing data (news, signals, macro drivers) every 5 minutes
setInterval(loadBriefingData, 5 * 60 * 1000);

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
  // Sort by recency first so we always pick the most current matching article
  const drivers = [...(_driversData || [])].sort((a, b) => {
    const ta = a.published ? new Date(a.published).getTime() : 0;
    const tb = b.published ? new Date(b.published).getTime() : 0;
    return tb - ta;
  });
  if (!drivers.length) return;

  const used = new Set();
  const signals = _SIGNAL_FILTERS.map(f => {
    const match = drivers.find(d => !used.has(d) && f.re.test(d.title || ''));
    if (match) used.add(match);
    return match || null;
  });

  // Fill empty slots with most recent unclaimed driver
  const fallbacks = drivers.filter(d => !used.has(d));
  signals.forEach((s, i) => {
    if (!s && fallbacks.length) signals[i] = fallbacks.shift();
  });

  el.innerHTML = signals.map((d, i) => {
    if (!d) return '';
    const f    = _SIGNAL_FILTERS[i];
    const meta = [d.source, d.published].filter(Boolean).join(' · ');
    // Use <a> so each signal is clickable and opens the source article
    return `<a class="signal-card" href="${esc(d.url || '#')}" target="_blank" rel="noopener" style="--signal-accent:${f.accent}">
      <div class="signal-theme">${f.label}</div>
      <div class="signal-headline">${esc(d.title)}</div>
      ${meta ? `<div class="signal-meta">${esc(meta)}</div>` : ''}
    </a>`;
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
// ── Power Markets news query — edit this string to tune which headlines appear ──
const POWER_MARKETS_QUERY = 'electricity grid power prices OR "power market" OR "energy prices" OR Ofgem OR "National Grid" OR "gas prices" OR renewables when:14d';
const POWER_MARKETS_MAX_AGE_DAYS = 28;

const _NEWS_SECTION_ORDER  = ['Energy', 'Metals', 'Crypto', 'FX', 'General'];
const _NEWS_SECTION_ACCENTS = {
  'Energy': '#10b981', 'Power': '#0ea5e9',
  'Metals': '#f59e0b', 'Crypto': '#8b5cf6', 'FX': '#3b82f6',
};

/* ── News column dashboard ─────────────────────────────────────────────────── */
// Column config — 'General' articles are merged into 'FX & Markets'
// Power Markets articles are fetched separately via _fetchPowerMarketsNews()
const _NEWS_COLS = [
  { key: 'Energy', label: 'Energy',           icon: '&#9679;' },
  { key: 'Power',  label: 'Power Markets',    icon: '&#9889;' },
  { key: 'Metals', label: 'Metals',           icon: '&#9671;' },
  { key: 'Crypto', label: 'Crypto',           icon: '&#x20BF;' },
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
  const _newsUpdLine = _newsLastUpdated
    ? `<div class="page-updated-line">${_fmtUpdated(_newsLastUpdated)}</div>` : '';

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
    const isPower   = col.key === 'Power';
    const isLoading = isPower && _powerMarketsNews === null;
    const rawList   = isPower ? (_powerMarketsNews || []) : (grouped[col.key] || []);
    const articles  = _sortByTrust(rawList.slice(0, 6));
    const accent    = _NEWS_SECTION_ACCENTS[col.key] || '#3b82f6';
    const isOpen    = _isNewsColOpen(col.key);
    const lead      = articles[0];
    const preview   = isLoading ? 'Loading\u2026' : lead ? esc(lead.title) : 'No articles';

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
    if (isLoading) {
      html += `<div class="news-col-body"><div class="placeholder"><span class="spin"></span>Loading&hellip;</div></div>`;
    } else if (articles.length) {
      html += `<div class="news-col-body">`;

      // Lead article
      const leadMeta = [lead.published].filter(Boolean).join(' · ');
      html += `<div class="news-lead-label">Featured</div>`;
      html += `<a class="lead-card" href="${esc(lead.url)}" target="_blank" rel="noopener">
        <div class="lead-card-headline">${esc(lead.title)}</div>
        ${lead.summary ? `<div class="lead-card-summary">${esc(lead.summary)}</div>` : ''}
        <div class="lead-card-meta">${lead.source ? _sourceBadge(lead.source) + ' ' : ''}${esc(leadMeta)}</div>
      </a>`;

      // Supporting headlines
      if (articles.length > 1) {
        html += `<div class="news-feed-label">More Headlines</div>`;
        html += `<div class="news-feed">`;
        articles.slice(1).forEach(a => {
          const meta = [a.published].filter(Boolean).join(' · ');
          html += `<a class="news-feed-row" href="${esc(a.url)}" target="_blank" rel="noopener">
            <div class="news-feed-headline">${esc(a.title)}</div>
            <div class="news-feed-meta">${a.source ? _sourceBadge(a.source) + ' ' : ''}${esc(meta)}</div>
          </a>`;
        });
        html += '</div>';
      }

      html += '</div>';  // .news-col-body
    }

    html += '</div>';  // .news-col
  });

  html += '</div>';  // .news-dashboard
  el.innerHTML = _newsUpdLine + html;
}

/* ── Macro page — always-visible briefing card grid ─────────────────────────── */
// Subtle SVG icons for each macro theme — monochrome paths, rendered at 18×18.
// Monetary: bank columns  |  Energy: lightning bolt  |  Geopolitics: globe  |  China/Demand: bar chart
const _MACRO_ICONS = [
  `<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M2 11h16v1.5a.5.5 0 01-.5.5h-15a.5.5 0 01-.5-.5V11zm1.5-1L10 4l6.5 6H3.5zM5 12.5h1.5v3H5v-3zm3.25 0h1.5v3h-1.5v-3zm3.25 0h1.5v3H11.5v-3zm3.25 0H16v3h-1.25v-3zM3 16h14v1H3v-1z"/>`,
  `<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M11.3 2.5a.75.75 0 00-1.3.43v5.57H5a.75.75 0 00-.6 1.2l5.7 7.8a.75.75 0 001.3-.43v-5.57H16a.75.75 0 00.6-1.2l-5.7-7.8 .4.43z" clip-rule="evenodd"/>`,
  `<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-3.536-2.05A6.5 6.5 0 013.5 10c0-.65.09-1.28.26-1.88l2.24 2.24v.64c0 .828.672 1.5 1.5 1.5h.5v1.5c0 .29.065.565.18.81zM10 3.5c.46 0 .91.05 1.34.14l-.84 1.68a1.5 1.5 0 00-.5-.07H9a1.5 1.5 0 00-1.5 1.5v.5H6a1.5 1.5 0 00-1.5 1.5 6.5 6.5 0 014.04-5.19A1.5 1.5 0 0010 3.5zm4.08 1.89A6.5 6.5 0 0116.5 10c0 1.55-.54 2.97-1.44 4.09V13.5a2 2 0 00-2-2H12v-1a1.5 1.5 0 00-1.5-1.5H10v-2h.5A1.5 1.5 0 0012 7.5V6h.5a2 2 0 001.58-3.11z" clip-rule="evenodd"/>`,
  `<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zm6-4a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zm6-3a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z"/>`,
];

const MACRO_THEMES = [
  {
    title: 'Monetary Policy &amp; Liquidity',
    accent: '#3b82f6',
    tagline: 'Fed · ECB · BoJ · Rates · Dollar strength',
    keywords: /fed|federal reserve|ecb|boj|central bank|\brate\b|interest rate|inflation|liquidity|hawkish|dovish|rate cut|rate hike|quantitative/i,
    text: 'Central bank rate cycles set the cost of capital globally. Tight policy strengthens the dollar and pressures USD-denominated commodity prices; easing cycles reduce carry costs and fuel demand for hard assets. Fed-ECB-BoJ divergence is the primary driver of currency-adjusted commodity returns.',
  },
  {
    title: 'Energy &amp; Physical Supply',
    accent: '#10b981',
    tagline: 'OPEC+ · LNG · Inventory · Refinery margins',
    keywords: /\boil\b|opec|crude|brent|wti|\bgas\b|lng|pipeline|supply|inventory|\benergy\b|fuel price|refinery|barrel|heating oil/i,
    text: 'Energy prices feed directly into inflation and industrial input costs. OPEC+ production decisions and infrastructure disruptions ripple across asset classes — from metals processing to the FX reserves of producer nations. Inventory levels and spare capacity are the key real-time signals.',
  },
  {
    title: 'Geopolitics &amp; Trade Flows',
    accent: '#f59e0b',
    tagline: 'Tariffs · Sanctions · Supply chains · Shipping',
    keywords: /tariff|trade war|sanction|ukraine|middle east|iran|israel|conflict|geopolit|nato|supply chain|export ban|import ban|embargo|shipping|strait/i,
    text: 'Trade restrictions and conflict reshape commodity routing, introduce supply shocks, and embed risk premiums into prices. Sanctions on energy exporters and tariff escalations create persistent pricing dislocations. Strategic chokepoint disruptions are a leading indicator of price spikes.',
  },
  {
    title: 'China &amp; Global Demand',
    accent: '#8b5cf6',
    tagline: 'PBoC · Property sector · PMI · Import volumes',
    keywords: /china|pboc|chinese|yuan|renminbi|\bcopper\b|\bsteel\b|iron ore|emerging market|india|brazil|\bdemand\b|stimulus|property sector|beijing|manufacturing pmi|factory output|infrastructure|global growth|commodity demand|import volumes|trade data|industrial output/i,
    text: 'China is the world\'s largest consumer of industrial metals, energy, and agricultural commodities. PBoC policy shifts, property sector health, and factory output data are the primary leading indicators for global commodity demand. Weakness in Chinese manufacturing directly moves copper, iron ore, and crude import volumes.',
  },
];

function renderMacroPage() {
  const el = document.getElementById('macro-page-body');
  if (!el) return;

  const drivers = _driversData || [];

  // Greedily assign each headline to at most one theme (first-match wins by theme order).
  // Collect up to 4 per theme so _sortByTrust can elevate the best lead.
  const used = new Set();
  const themeMatches = MACRO_THEMES.map(theme => {
    const matched = [];
    for (const d of drivers) {
      if (!used.has(d) && theme.keywords.test(d.title || '')) {
        matched.push(d);
        used.add(d);
        if (matched.length === 4) break;
      }
    }
    return _sortByTrust(matched).slice(0, 3);
  });

  // Unclaimed articles as fallback pool — fill themes with fewest matches first
  const unclaimed = [..._sortByTrust(drivers.filter(d => !used.has(d)))];

  // Priority order: theme with fewest keyword matches gets first pick from unclaimed pool
  [0, 1, 2, 3]
    .sort((a, b) => themeMatches[a].length - themeMatches[b].length)
    .forEach(idx => {
      const needed = 3 - themeMatches[idx].length;
      if (needed > 0 && unclaimed.length) {
        const supplement = unclaimed.splice(0, needed);
        themeMatches[idx] = _sortByTrust([...themeMatches[idx], ...supplement]).slice(0, 3);
      }
    });

  const _macroUpdLine = _macroLastUpdated
    ? `<div class="page-updated-line">${_fmtUpdated(_macroLastUpdated)}</div>` : '';
  let html = '<div class="macro-card-grid">';

  MACRO_THEMES.forEach((theme, i) => {
    let headlines = themeMatches[i];
    // Ensure every theme has at least 2 items (featured + 1 signal) if any drivers remain
    if (headlines.length < 2 && unclaimed.length) {
      const needed = 2 - headlines.length;
      headlines = _sortByTrust([...headlines, ...unclaimed.splice(0, needed)]);
    }
    // Last resort: if still empty but any drivers exist, use best available regardless of prior use
    if (!headlines.length && drivers.length) {
      headlines = _sortByTrust(drivers).slice(0, 2);
    }
    const featured  = headlines[0] || null;
    const signals   = headlines.slice(1);

    html += `<div class="macro-card" style="--theme-accent:${theme.accent}">`;

    // ── Card header ──
    html += `<div class="macro-card-header">
      <div class="macro-card-icon">${_MACRO_ICONS[i]}</svg></div>
      <div class="macro-card-header-body">
        <div class="macro-card-title">${theme.title}</div>
        <div class="macro-card-tagline">${theme.tagline}</div>
      </div>
    </div>`;

    // ── Context paragraph ──
    html += `<p class="macro-card-context">${theme.text}</p>`;

    if (featured) {
      // ── Featured development ──
      html += `<div class="macro-card-divider"><span class="macro-card-section-label">Featured Development</span></div>`;
      html += `<a class="macro-featured" href="${esc(featured.url)}" target="_blank" rel="noopener">
        <div class="macro-featured-headline">${esc(featured.title)}</div>
        <div class="macro-featured-meta">${featured.source ? _sourceBadge(featured.source) + ' ' : ''}${featured.published ? esc(featured.published) : ''}</div>
      </a>`;

      // ── Signals ──
      if (signals.length) {
        html += `<div class="macro-card-divider"><span class="macro-card-section-label">Signals</span></div>`;
        html += `<div class="macro-signals-list">`;
        signals.forEach(d => {
          html += `<a class="macro-signal-row" href="${esc(d.url)}" target="_blank" rel="noopener">
            <span class="macro-signal-dot" style="background:${theme.accent}"></span>
            <span class="macro-signal-body">
              <span class="macro-signal-headline">${esc(d.title)}</span>
              ${d.source ? `<span class="macro-signal-meta">${_sourceBadge(d.source)}${d.published ? ' ' + esc(d.published) : ''}</span>` : ''}
            </span>
          </a>`;
        });
        html += `</div>`;
      }
    } else {
      html += `<p class="macro-no-headlines">No matching headlines available.</p>`;
    }

    html += `</div>`;  // .macro-card
  });

  html += '</div>';  // .macro-card-grid
  el.innerHTML = _macroUpdLine + html;
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
  const sorted = _sortByTrust(_newsData);
  const lead = sorted[0];
  const leadMeta = [lead.instrument, lead.published].filter(Boolean).join(' · ');
  let html = `<a class="lead-card" href="${esc(lead.url)}" target="_blank" rel="noopener">
    <div class="lead-card-headline">${esc(lead.title)}</div>
    <div class="lead-card-meta">${lead.source ? _sourceBadge(lead.source) + ' ' : ''}${esc(leadMeta)}</div>
  </a>`;
  if (sorted.length > 1) {
    html += '<ul class="news-list" style="margin-top:8px">' + sorted.slice(1).map(a => `
      <li>
        <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a>
        <div class="news-meta">
          ${esc(a.instrument || '')}${a.source ? ' ' + _sourceBadge(a.source) : ''}${a.published ? ' &middot; ' + esc(a.published) : ''}
        </div>
      </li>`).join('') + '</ul>';
  }
  return html;
}

function buildDriversModal() {
  if (!_driversData || !_driversData.length) return '<p style="color:var(--muted)">No headlines available.</p>';
  const sortedDrivers = _sortByTrust(_driversData);
  const lead = sortedDrivers[0];
  let html = `<a class="lead-card" href="${esc(lead.url)}" target="_blank" rel="noopener">
    <div class="lead-card-headline">${esc(lead.title)}</div>
    <div class="lead-card-meta">${lead.source ? _sourceBadge(lead.source) + ' ' : ''}${esc(lead.published || '')}</div>
  </a>`;
  if (sortedDrivers.length > 1) {
    html += '<ul class="news-list" style="margin-top:8px">' + sortedDrivers.slice(1).map(d => `
      <li>
        <a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
        <div class="news-meta">
          ${d.source ? _sourceBadge(d.source) : ''}${d.published ? ' &middot; ' + esc(d.published) : ''}
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
    apiFetch('/api/history/' + key + '?range=' + currentRange),
    apiFetch('/api/summary/' + key),
  ]);
  if (histRes && histRes.ok) renderChart(await histRes.json());
  else showChartError();
  if (summRes && summRes.ok) {
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
  // Clear header while chart loads; renderChart will set correct values from chart series.
  const chgEl = document.getElementById('m-chg');
  if (chgEl) { chgEl.textContent = '\u2026'; chgEl.className = 'modal-chg'; }

  resetChart();
  try {
    const res = await apiFetch('/api/history/' + currentKey + '?range=' + range);
    if (res && res.ok) renderChart(await res.json());
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

  // Sync modal header to chart series: price = latest point, change = first→last
  if (prices.length >= 1) {
    const latest = prices[prices.length - 1];
    const prEl = document.getElementById('m-price');
    if (prEl) {
      prEl.textContent = hist.thousands
        ? hist.prefix + latest.toLocaleString('en-US', { minimumFractionDigits: hist.decimals, maximumFractionDigits: hist.decimals }) + hist.suffix
        : hist.prefix + latest.toFixed(hist.decimals) + hist.suffix;
    }
    const chgEl = document.getElementById('m-chg');
    if (chgEl) {
      if (prices.length >= 2 && prices[0] !== 0) {
        const pct = (latest - prices[0]) / prices[0] * 100;
        if (pct > 0)      { chgEl.textContent = '\u25b2 +' + pct.toFixed(2) + '%'; chgEl.className = 'modal-chg up'; }
        else if (pct < 0) { chgEl.textContent = '\u25bc '  + pct.toFixed(2) + '%'; chgEl.className = 'modal-chg down'; }
        else              { chgEl.textContent = '0.00%';                            chgEl.className = 'modal-chg neu'; }
      } else {
        chgEl.textContent = ''; chgEl.className = 'modal-chg';
      }
    }
  }
}

/* ── Articles ───────────────────────────────────────────────────────────────── */
function renderArticles(articles, accent) {
  const area = document.getElementById('articles-area');
  if (!articles || articles.length === 0) {
    area.innerHTML = '<p class="no-articles">No articles available at this time.</p>';
    return;
  }
  articles = _sortByTrust(articles);
  const cards = articles.map(a => `
    <a class="article-card" href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">
      <div class="article-publisher">${_sourceBadge(a.source || 'News')}</div>
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
const FEATURED_FIRMS = [
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
    key: 'man', name: 'Man Group', fullName: 'Man Group plc',
    category: 'Hedge Fund', region: 'Europe', hq: 'London',
    initials: 'MN', color: '#1b5e20', website: 'man.com',
    tagline: "Listed alternative manager with leading systematic AHL platform",
    overview: "Man Group is one of the world's largest publicly listed alternative investment managers, with roots dating to 1783. Its primary systematic engine — Man AHL — is one of the longest-established CTAs globally, with significant commodity futures exposure through trend-following and diversified systematic strategies. Man Group also operates discretionary macro and credit strategies through Man GLG and Man FRM.",
    markets: ['Systematic / CTA', 'Commodity Futures', 'Global Macro', 'Credit', 'Multi-Strategy'],
    offices: ['London', 'New York', 'Hong Kong', 'Singapore', 'Sydney', 'Denver'],
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
    key: 'aqr', name: 'AQR Capital Management', fullName: 'AQR Capital Management LLC',
    category: 'Hedge Fund', region: 'US', hq: 'Greenwich, CT',
    initials: 'AQ', color: '#00838f', website: 'aqr.com',
    tagline: "Quantitative factor-based manager across global asset classes",
    overview: "AQR Capital Management is one of the world's largest quantitative investment managers, founded in 1998 by Cliff Asness and colleagues from Goldman Sachs. AQR applies systematic, factor-based strategies across equities, fixed income, currencies, and commodities in both hedge fund and long-only formats. Commodity exposure is primarily through trend-following, carry, and value factor strategies in futures markets.",
    markets: ['Quantitative / Factor', 'Commodity Futures', 'Trend-Following', 'Fixed Income', 'Equities'],
    offices: ['Greenwich', 'New York', 'London', 'Hong Kong', 'Sydney'],
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
    key: 'deshaw', name: 'D.E. Shaw', fullName: 'D. E. Shaw & Co., L.P.',
    category: 'Hedge Fund', region: 'US', hq: 'New York',
    initials: 'DE', color: '#0d47a1', website: 'deshaw.com',
    tagline: "Quantitative and computational investment manager across global markets",
    overview: "D. E. Shaw & Co. is a global investment and technology development firm founded by David E. Shaw in 1988. Widely regarded as one of the most influential quantitative funds, the firm applies computational methods across equities, fixed income, commodities, and alternative strategies. Its systematic trading operations span a significant fraction of daily US equity volume and include substantial commodity and macro futures exposure.",
    markets: ['Quantitative / Systematic', 'Commodity Futures', 'Equities', 'Fixed Income', 'Global Macro'],
    offices: ['New York', 'London', 'Hyderabad', 'Hong Kong', 'Boston', 'San Francisco'],
  },
  {
    key: 'twosigma', name: 'Two Sigma', fullName: 'Two Sigma Investments, LP',
    category: 'Hedge Fund', region: 'US', hq: 'New York',
    initials: 'TS', color: '#00838f', website: 'twosigma.com',
    tagline: "Technology-driven systematic manager using data science and ML",
    overview: "Two Sigma is a quantitative investment firm founded in 2001 by John Overdeck and David Siegel. The firm uses machine learning, distributed computing, and large-scale data analysis to develop systematic trading strategies across equities, futures, FX, and commodities. Two Sigma manages over $60 billion in assets and has become one of the largest systematic hedge funds globally.",
    markets: ['Systematic / ML', 'Commodity Futures', 'Equities', 'FX', 'Fixed Income'],
    offices: ['New York', 'Houston', 'London', 'Hong Kong', 'Tokyo', 'Singapore'],
  },
  {
    key: 'freepoint', name: 'Freepoint Commodities', fullName: 'Freepoint Commodities LLC',
    category: 'Trading House', region: 'US', hq: 'Stamford, CT',
    initials: 'FP', color: '#1565c0', website: 'freepointcommodities.com',
    tagline: "Independent commodity merchant in energy, metals, and concentrates",
    overview: "Freepoint Commodities is a global commodity merchant founded in 2011 by former Louis Dreyfus executives. The firm trades crude oil, petroleum products, natural gas, power, metals, and concentrates across global markets. Freepoint operates with a principal trading model and has invested in logistics and processing infrastructure to support physical commodity flows.",
    markets: ['Crude Oil & Products', 'Natural Gas & Power', 'Metals & Concentrates', 'LNG', 'Biofuels'],
    offices: ['Stamford', 'Houston', 'Geneva', 'Singapore', 'Shanghai', 'London'],
  },
  {
    key: 'adm', name: 'ADM', fullName: 'Archer-Daniels-Midland Company',
    category: 'Trading House', region: 'US', hq: 'Chicago, IL',
    initials: 'AD', color: '#4e342e', website: 'adm.com',
    tagline: "Global agricultural processor and commodity trader",
    overview: "Archer-Daniels-Midland (ADM) is one of the world's largest agricultural processors and commodity trading companies, founded in 1902. ADM processes corn, oilseeds, wheat, and cocoa into food, animal feed, and industrial ingredients. Its trading division spans grains, oilseeds, sugar, cotton, ethanol, and energy commodities globally, supported by an extensive network of grain elevators, processing plants, and river terminals.",
    markets: ['Grains & Oilseeds', 'Sugar & Sweeteners', 'Ethanol & Biofuels', 'Cotton', 'Animal Nutrition'],
    offices: ['Chicago', 'Geneva', 'Hamburg', 'São Paulo', 'Singapore', 'Shanghai'],
  },
];

// ── Extended directory — not shown by default, searchable ────────────────────
const _EXTRA_FIRMS = [
  // ── Market Makers / Prop Trading ──────────────────────────────────────────
  {
    key: 'drw', name: 'DRW', fullName: 'DRW Holdings, LLC',
    category: 'Market Maker', region: 'US', hq: 'Chicago, IL',
    initials: 'DRW', color: '#1e3a5f', website: 'drw.com',
    tagline: "Principal trading firm across futures, crypto, and fixed income",
    overview: "DRW is a diversified principal trading firm founded by Don Wilson in 1992 in Chicago. The firm trades its own capital across interest rate futures, fixed income, equities, energy, metals, and cryptocurrencies. DRW is also the parent of Cumberland, a leading crypto OTC desk, and has invested in financial technology and real estate through associated ventures.",
    markets: ['Interest Rate Futures', 'Energy & Commodities', 'Equities', 'Cryptocurrency', 'Fixed Income'],
    offices: ['Chicago', 'New York', 'London', 'Austin', 'Singapore'],
  },
  {
    key: 'janestreet', name: 'Jane Street', fullName: 'Jane Street Capital, LLC',
    category: 'Market Maker', region: 'US', hq: 'New York',
    initials: 'JS', color: '#2d6a4f', website: 'janestreet.com',
    tagline: "Global quantitative trading firm and liquidity provider",
    overview: "Jane Street is a global quantitative trading firm and liquidity provider, founded in 2000 in New York. The firm trades equities, fixed income, commodities, cryptocurrencies, and ETFs across global markets, providing liquidity and making markets as a principal. Jane Street is known for its heavy investment in technology, functional programming (OCaml), and research-driven trading strategies.",
    markets: ['ETFs', 'Equities', 'Fixed Income', 'Commodities', 'Cryptocurrency'],
    offices: ['New York', 'London', 'Hong Kong', 'Amsterdam', 'Singapore'],
  },
  {
    key: 'optiver', name: 'Optiver', fullName: 'Optiver Holding B.V.',
    category: 'Market Maker', region: 'Europe', hq: 'Amsterdam',
    initials: 'OP', color: '#e63946', website: 'optiver.com',
    tagline: "Market maker in derivatives, equities, and commodities globally",
    overview: "Optiver is a global electronic market maker founded in Amsterdam in 1986. The firm provides liquidity across options, futures, equities, bonds, and currencies on over 70 exchanges worldwide. Optiver is fully proprietary — trading its own capital — and is known for its rigorous quantitative approach to options pricing and risk management, as well as its significant exposure to commodity derivatives markets.",
    markets: ['Options & Derivatives', 'Commodity Futures', 'Equities', 'Fixed Income', 'FX'],
    offices: ['Amsterdam', 'Chicago', 'Sydney', 'Shanghai', 'Taipei', 'London', 'Singapore'],
  },
  {
    key: 'imc', name: 'IMC', fullName: 'IMC Trading B.V.',
    category: 'Market Maker', region: 'Europe', hq: 'Amsterdam',
    initials: 'IMC', color: '#457b9d', website: 'imc.com',
    tagline: "Technology-driven market maker in derivatives and cash markets",
    overview: "IMC is a global market-making firm founded in Amsterdam in 1989. It provides liquidity in options, equities, ETFs, fixed income, and commodity derivatives across major exchanges worldwide. IMC operates as a principal trading firm using proprietary algorithms and technology infrastructure, with particular depth in index and commodity options markets.",
    markets: ['Options', 'ETFs', 'Commodity Derivatives', 'Equities', 'Fixed Income'],
    offices: ['Amsterdam', 'Chicago', 'Sydney', 'Bratislava', 'Mumbai', 'Singapore'],
  },
  {
    key: 'flowtraders', name: 'Flow Traders', fullName: 'Flow Traders N.V.',
    category: 'Market Maker', region: 'Europe', hq: 'Amsterdam',
    initials: 'FT', color: '#f4a261', website: 'flowtraders.com',
    tagline: "Listed ETP market maker across equities, fixed income, and commodities",
    overview: "Flow Traders is a global technology-enabled liquidity provider specialising in exchange-traded products (ETPs), founded in Amsterdam in 2004. Listed on Euronext Amsterdam, the firm makes markets in equity, fixed income, commodity, and currency ETPs across global exchanges. Flow Traders is one of the largest ETP market makers in Europe and a significant player in commodity ETP liquidity.",
    markets: ['ETP / ETF Market Making', 'Commodity ETPs', 'Fixed Income ETPs', 'Equity ETPs', 'Crypto ETPs'],
    offices: ['Amsterdam', 'New York', 'Singapore', 'Cluj-Napoca'],
  },
  {
    key: 'jumptrading', name: 'Jump Trading', fullName: 'Jump Trading, LLC',
    category: 'Market Maker', region: 'US', hq: 'Chicago, IL',
    initials: 'JT', color: '#6a0572', website: 'jumptrading.com',
    tagline: "High-frequency prop trader in futures, equities, and crypto",
    overview: "Jump Trading is a research-driven proprietary trading firm founded in Chicago in 1999. The firm trades futures, equities, fixed income, FX, and cryptocurrency across global markets using quantitative and algorithmic strategies. Jump is particularly active in commodity futures markets and is a major participant in crypto market infrastructure through its Jump Crypto division.",
    markets: ['Futures & Derivatives', 'Commodity Futures', 'Equities', 'Fixed Income', 'Cryptocurrency'],
    offices: ['Chicago', 'New York', 'London', 'Singapore', 'Shanghai', 'Bristol'],
  },
  // ── Additional Hedge Funds ─────────────────────────────────────────────────
  {
    key: 'schonfeld', name: 'Schonfeld', fullName: 'Schonfeld Strategic Advisors',
    category: 'Hedge Fund', region: 'US', hq: 'New York',
    initials: 'SC', color: '#2b4590', website: 'schonfeld.com',
    tagline: "Multi-strategy platform with equity, macro, and quant pods",
    overview: "Schonfeld Strategic Advisors is a global multi-strategy hedge fund that evolved from the Schonfeld family office, which has traded equities since 1988. The firm operates a pod-based platform across systematic trading, equity long/short, macro, and quantitative strategies. Schonfeld has expanded its macro and commodities capabilities significantly as part of its multi-strategy build-out.",
    markets: ['Equities L/S', 'Global Macro', 'Systematic / Quant', 'Commodities', 'Fixed Income'],
    offices: ['New York', 'London', 'Hong Kong', 'Miami', 'Houston', 'Dubai'],
  },
  {
    key: 'squarepoint', name: 'Squarepoint Capital', fullName: 'Squarepoint Capital LLP',
    category: 'Hedge Fund', region: 'Europe', hq: 'London',
    initials: 'SQ', color: '#2c7873', website: 'squarepoint-capital.com',
    tagline: "Quantitative hedge fund trading systematic strategies globally",
    overview: "Squarepoint Capital is a global quantitative hedge fund founded in 2014, with roots in the systematic trading group formerly at BlueCrest. The firm applies statistical and machine learning models to trade equities, futures, and derivatives systematically across global markets, including significant commodity futures exposure through trend and mean-reversion strategies.",
    markets: ['Systematic / Quant', 'Equity Futures', 'Commodity Futures', 'Fixed Income Futures', 'FX'],
    offices: ['London', 'New York', 'Singapore', 'Montreal'],
  },
  {
    key: 'tudor', name: 'Tudor Investment Corp', fullName: 'Tudor Investment Corp',
    category: 'Hedge Fund', region: 'US', hq: 'Stamford, CT',
    initials: 'TU', color: '#8b1a1a', website: 'tudor.com',
    tagline: "Macro and multi-strategy fund, pioneer of trend following",
    overview: "Tudor Investment Corp is one of the oldest and most respected macro hedge funds, founded by Paul Tudor Jones in 1980. The firm built its reputation through discretionary global macro and trend-following strategies across commodities, equities, fixed income, and currencies. Tudor remains a significant force in commodity futures markets and has expanded into systematic and data-driven approaches alongside its core discretionary franchise.",
    markets: ['Global Macro', 'Commodity Futures', 'Trend Following', 'Equities', 'Fixed Income'],
    offices: ['Stamford', 'New York', 'London', 'Sydney', 'Singapore'],
  },
];

// ── Featured Banks (8 — shown on default Firms page) ─────────────────────────
const FEATURED_BANKS = [
  {
    key: 'goldmansachs', name: 'Goldman Sachs', fullName: 'The Goldman Sachs Group, Inc.',
    category: 'Bank', region: 'US', hq: 'New York',
    initials: 'GS', color: '#1a1a2e',
    tagline: 'Global investment bank, securities, and investment management',
    overview: "Goldman Sachs is one of the world's premier investment banks, founded in 1869. Known for its dominance in M&A advisory, securities underwriting, and FICC trading, Goldman built one of the largest commodity trading franchises on Wall Street before scaling it back post-2008 regulation. Its Global Markets division remains a major force in commodity derivatives, energy, and metals. The firm manages over $2.5 trillion in assets and is a defining institution of global finance.",
    markets: ['Investment Banking', 'FICC & Commodities', 'Equities', 'Asset Management', 'Transaction Banking'],
    offices: ['New York', 'London', 'Hong Kong', 'Tokyo', 'Singapore', 'Frankfurt', 'Dubai'],
  },
  {
    key: 'jpmorgan', name: 'JPMorgan', fullName: 'JPMorgan Chase & Co.',
    category: 'Bank', region: 'US', hq: 'New York',
    initials: 'JP', color: '#003087',
    tagline: "America's largest bank by assets with a global markets powerhouse",
    overview: "JPMorgan Chase is the largest US bank by assets and one of the most systemically important financial institutions in the world. Its investment banking arm, J.P. Morgan, is consistently ranked No. 1 globally in investment banking fees. JPMorgan maintains a major presence in commodity markets — energy financing, metals, agricultural commodities — through both its Markets division and extensive corporate banking relationships with commodity producers and traders.",
    markets: ['Investment Banking', 'Markets (FICC + Equities)', 'Commercial Banking', 'Asset & Wealth Management', 'Treasury Services'],
    offices: ['New York', 'London', 'Hong Kong', 'Singapore', 'São Paulo', 'Mumbai', 'Dubai'],
  },
  {
    key: 'morganstanley', name: 'Morgan Stanley', fullName: 'Morgan Stanley',
    category: 'Bank', region: 'US', hq: 'New York',
    initials: 'MS', color: '#003087',
    tagline: 'Global investment bank with leading wealth and institutional securities businesses',
    overview: "Morgan Stanley is a global financial services firm with major positions in institutional securities, wealth management, and investment management. Its Commodities division — historically among the largest on Wall Street — covers energy, metals, and agricultural derivatives. Morgan Stanley serves commodity producers, traders, and end-users through structured financing, derivatives, and risk management solutions alongside its core investment banking and markets franchise.",
    markets: ['Institutional Securities', 'Commodities & FICC', 'Wealth Management', 'Investment Management', 'Equities'],
    offices: ['New York', 'London', 'Tokyo', 'Hong Kong', 'Sydney', 'Frankfurt', 'Dubai'],
  },
  {
    key: 'citi', name: 'Citi', fullName: 'Citigroup Inc.',
    category: 'Bank', region: 'US', hq: 'New York',
    initials: 'CI', color: '#003f88',
    tagline: 'Global bank with one of the widest geographic and commodities footprints',
    overview: "Citi is one of the most globally connected banks in the world, operating in 160+ countries. Its Institutional Clients Group (ICG) provides investment banking, capital markets, and trade finance services to corporations, governments, and institutional investors. Citi's commodities business spans energy, metals, and agricultural derivatives, with particular strength in trade finance and structured commodity solutions for producers and sovereign exporters.",
    markets: ['Markets & Securities Services', 'Commodity Trade Finance', 'Banking Capital Markets & Advisory', 'FICC', 'Treasury & Trade Solutions'],
    offices: ['New York', 'London', 'Hong Kong', 'Singapore', 'Dubai', 'Mexico City', 'Mumbai'],
  },
  {
    key: 'bofa', name: 'Bank of America', fullName: 'Bank of America Corporation',
    category: 'Bank', region: 'US', hq: 'Charlotte, NC',
    initials: 'BA', color: '#e31837',
    tagline: 'Major US bank with a large global markets and natural resources franchise',
    overview: "Bank of America is one of the largest US banks by assets and deposits, with a major investment banking operation under its BofA Securities brand. The bank has significant exposure to commodity markets through its Global Markets division, particularly energy and natural resources lending and derivatives. BofA provides financing, hedging, and advisory services to oil companies, utilities, mining firms, and agricultural businesses globally.",
    markets: ['Global Markets (FICC)', 'Investment Banking', 'Natural Resources Financing', 'Equities', 'Wealth Management'],
    offices: ['Charlotte', 'New York', 'London', 'Hong Kong', 'Tokyo', 'Singapore', 'Sydney'],
  },
  {
    key: 'barclays', name: 'Barclays', fullName: 'Barclays PLC',
    category: 'Bank', region: 'Europe', hq: 'London',
    initials: 'BA', color: '#00aeef',
    tagline: 'British bank with a major global investment banking and commodity derivatives operation',
    overview: "Barclays is a major British universal bank with a significant global investment banking division (Barclays Investment Bank). Its commodity franchise is particularly strong in energy derivatives, metals, and structured commodity finance, with deep roots in the power markets and a major presence in EMEA commodity trade flows. Barclays also provides commodity index products and structured solutions to institutional investors and corporates globally.",
    markets: ['Investment Banking', 'FICC & Commodities', 'Energy & Power Derivatives', 'Equities', 'Private & Corporate Banking'],
    offices: ['London', 'New York', 'Hong Kong', 'Singapore', 'Frankfurt', 'Dubai', 'Tokyo'],
  },
  {
    key: 'bnpparibas', name: 'BNP Paribas', fullName: 'BNP Paribas S.A.',
    category: 'Bank', region: 'Europe', hq: 'Paris',
    initials: 'BN', color: '#00965e',
    tagline: "Europe's largest bank by assets with a leading commodity trade finance business",
    overview: "BNP Paribas is the largest European bank by assets and a dominant force in commodity trade finance. Its Corporate & Institutional Banking (CIB) division serves commodity traders, producers, and processors globally — with particular strength in financing oil, gas, metals, and agricultural commodity flows. BNP Paribas is consistently ranked among the top global banks for commodity trade finance and has a significant presence in structured energy and metals derivatives.",
    markets: ['Commodity Trade Finance', 'Energy & Natural Resources', 'FICC', 'Investment Banking', 'Corporate Banking'],
    offices: ['Paris', 'London', 'New York', 'Hong Kong', 'Singapore', 'Geneva', 'Dubai'],
  },
  {
    key: 'socgen', name: 'Société Générale', fullName: 'Société Générale S.A.',
    category: 'Bank', region: 'Europe', hq: 'Paris',
    initials: 'SG', color: '#e4032d',
    tagline: 'French bank renowned for commodity derivatives, structured products, and energy financing',
    overview: "Société Générale (SocGen) is a major French bank with a globally recognised derivatives franchise. SocGen's Global Markets division is particularly strong in commodity structured products, energy derivatives, and metals — historically ranking among the most innovative banks in this space. Its Natural Resources & Energy team provides financing, hedging, and advisory services to commodity producers and trading houses globally, and SocGen is a major provider of commodity index and structured note products.",
    markets: ['Commodity Derivatives', 'Energy & Natural Resources', 'FICC', 'Structured Products', 'Investment Banking'],
    offices: ['Paris', 'London', 'New York', 'Hong Kong', 'Singapore', 'Geneva', 'Moscow'],
  },
];

// ── Extended bank database (searchable, not featured by default) ───────────────
const _EXTRA_BANKS = [
  {
    key: 'deutschebank', name: 'Deutsche Bank', fullName: 'Deutsche Bank AG',
    category: 'Bank', region: 'Europe', hq: 'Frankfurt',
    initials: 'DB', color: '#0074c8',
    tagline: 'German universal bank with a significant global markets and commodities operation',
    overview: "Deutsche Bank is Germany's largest bank and a major player in global fixed income, currencies, and commodities (FICC) markets. Despite significant restructuring since 2019, Deutsche Bank maintains a meaningful commodity derivatives and trade finance operation, particularly in energy, metals, and agricultural finance in EMEA and Asia. Its Corporate Bank provides structured trade finance solutions to commodity producers and traders.",
    markets: ['FICC & Commodities', 'Investment Banking', 'Corporate Banking', 'Trade Finance', 'Equities'],
    offices: ['Frankfurt', 'London', 'New York', 'Singapore', 'Hong Kong', 'Dubai'],
  },
  {
    key: 'hsbc', name: 'HSBC', fullName: 'HSBC Holdings plc',
    category: 'Bank', region: 'Europe', hq: 'London',
    initials: 'HS', color: '#db0011',
    tagline: "World's largest trade finance bank with unmatched Asia-Pacific reach",
    overview: "HSBC is one of the world's largest banks by assets, with its roots in the Hong Kong and Shanghai Banking Corporation. It is consistently ranked as the No. 1 global trade finance bank and a dominant force in commodity trade finance — particularly for Asian commodities flows (metals, energy, agricultural products). HSBC's Global Banking and Markets division provides significant commodity-linked financing, derivatives, and advisory services with particular depth in China, Southeast Asia, and the Middle East.",
    markets: ['Trade Finance & Commodities', 'FICC', 'Investment Banking', 'Wealth & Personal Banking', 'Global Payments'],
    offices: ['London', 'Hong Kong', 'Singapore', 'Dubai', 'New York', 'Paris', 'Shanghai'],
  },
  {
    key: 'ubs', name: 'UBS', fullName: 'UBS Group AG',
    category: 'Bank', region: 'Europe', hq: 'Zurich',
    initials: 'UB', color: '#e00101',
    tagline: 'Swiss bank and wealth management giant with global investment banking capabilities',
    overview: "UBS is the world's largest wealth manager and a leading Swiss universal bank. Following the emergency acquisition of Credit Suisse in 2023, UBS significantly expanded its investment banking and markets capabilities. UBS provides commodity-linked structured products, financing, and derivatives to institutional clients and ultra-high-net-worth individuals. Its Investment Bank division covers FICC (including commodities), equities, and advisory, while the expanded platform includes Credit Suisse's commodity trade finance book.",
    markets: ['Wealth Management', 'Investment Banking', 'FICC & Commodities', 'Equities', 'Asset Management'],
    offices: ['Zurich', 'London', 'New York', 'Hong Kong', 'Singapore', 'Tokyo', 'Geneva'],
  },
  {
    key: 'stanchart', name: 'Standard Chartered', fullName: 'Standard Chartered PLC',
    category: 'Bank', region: 'Europe', hq: 'London',
    initials: 'SC', color: '#1d8348',
    tagline: 'Emerging markets bank with strong commodity trade finance and Asian metals flows',
    overview: "Standard Chartered is a British international bank with its primary operations across Asia, Africa, and the Middle East. Its Financial Markets and Corporate Finance divisions are major providers of commodity trade finance — particularly for metals, energy, and soft commodities in high-growth Asian and African markets. Standard Chartered is a key financier of commodity flows in corridors underserved by US and European banks, with particular strength in precious metals, base metals, and agricultural commodity finance.",
    markets: ['Commodity Trade Finance', 'Financial Markets', 'Transaction Banking', 'Corporate Finance', 'Metals & Mining Finance'],
    offices: ['London', 'Singapore', 'Hong Kong', 'Dubai', 'Mumbai', 'Shanghai', 'Nairobi'],
  },
  {
    key: 'macquarie', name: 'Macquarie', fullName: 'Macquarie Group Limited',
    category: 'Bank', region: 'Asia-Pacific', hq: 'Sydney',
    initials: 'MQ', color: '#006633',
    tagline: 'Australian bank and one of the world\'s largest commodity trading and financing groups',
    overview: "Macquarie Group is an Australian-origin global financial services group that has built one of the world's largest commodity trading and financing businesses outside the traditional Wall Street and European banking giants. Its Commodities and Global Markets (CGM) division spans physical commodity trading, risk management, and financing across energy, metals, and agricultural markets. Macquarie is a major principal in commodity markets — particularly gas, power, and LNG — and provides sophisticated hedging and financing solutions to producers, traders, and consumers globally.",
    markets: ['Commodity Trading & Risk Management', 'Energy & Power', 'Metals & Mining Finance', 'Agricultural Finance', 'Infrastructure'],
    offices: ['Sydney', 'London', 'New York', 'Houston', 'Singapore', 'Hong Kong', 'Tokyo'],
  },
  {
    key: 'wellsfargo', name: 'Wells Fargo', fullName: 'Wells Fargo & Company',
    category: 'Bank', region: 'US', hq: 'San Francisco, CA',
    initials: 'WF', color: '#d71e28',
    tagline: 'Major US bank with significant energy lending and commodity trade finance capabilities',
    overview: "Wells Fargo is one of the largest US banks by deposits and a major provider of commercial banking, lending, and capital markets services. Its Corporate & Investment Banking division provides energy lending, commodity trade finance, and structured products to oil, gas, mining, and agricultural companies. Wells Fargo has particular depth in US energy sector financing — from upstream exploration to midstream infrastructure — and provides commodity risk management solutions to US producers and end-users.",
    markets: ['Energy Lending', 'Commercial Banking', 'Capital Markets', 'Commodity Trade Finance', 'FICC'],
    offices: ['San Francisco', 'New York', 'Houston', 'Charlotte', 'London', 'Hong Kong'],
  },
  {
    key: 'rbc', name: 'RBC Capital Markets', fullName: 'RBC Capital Markets',
    category: 'Bank', region: 'Americas', hq: 'Toronto',
    initials: 'RB', color: '#002d72',
    tagline: "Canada's leading investment bank with major energy and mining capabilities",
    overview: "RBC Capital Markets is the investment banking arm of Royal Bank of Canada, consistently ranked as one of the top investment banks in North America. It has particular depth in energy, mining, and natural resources — reflecting Canada's position as a major commodity producer. RBC advises on and finances oil & gas, mining, and infrastructure projects globally, and provides commodity derivatives and structured solutions to producers, royalty companies, and commodity-linked corporates.",
    markets: ['Energy & Natural Resources', 'Mining & Metals', 'Investment Banking', 'FICC', 'Equities'],
    offices: ['Toronto', 'New York', 'London', 'Sydney', 'Hong Kong', 'Singapore', 'Calgary'],
  },
  {
    key: 'natixis', name: 'Natixis', fullName: 'Natixis S.A.',
    category: 'Bank', region: 'Europe', hq: 'Paris',
    initials: 'NA', color: '#8b0000',
    tagline: 'French bank with a strong commodity trade finance and structured energy franchise',
    overview: "Natixis is the corporate and investment banking arm of Groupe BPCE, France's second-largest banking group. Its Global markets division has a notable presence in commodity structured products and energy derivatives, while its Commodity Finance team is an active provider of trade finance for oil, metals, and soft commodities. Natixis is particularly active in structured commodity transactions, reserve-based lending for energy producers, and commodity-linked structured notes.",
    markets: ['Commodity Trade Finance', 'Energy & Natural Resources', 'FICC', 'Structured Products', 'Investment Banking'],
    offices: ['Paris', 'London', 'New York', 'Hong Kong', 'Singapore', 'Dubai'],
  },
  {
    key: 'mufg', name: 'MUFG', fullName: 'Mitsubishi UFJ Financial Group',
    category: 'Bank', region: 'Asia-Pacific', hq: 'Tokyo',
    initials: 'MU', color: '#e20012',
    tagline: "Japan's largest bank with global energy, metals, and trade finance capabilities",
    overview: "MUFG (Mitsubishi UFJ Financial Group) is Japan's largest and the world's second-largest bank by assets. Its Global Corporate & Investment Banking division provides energy project finance, metals financing, and commodity trade finance globally, with particular strength in LNG financing (Japan being the world's largest LNG importer), mining project finance, and trade finance for Asian commodity flows. MUFG's global network spans over 50 countries, making it a critical financing partner for commodity supply chains connecting Asia with producing regions.",
    markets: ['Energy Project Finance', 'Trade Finance', 'Metals & Mining', 'Investment Banking', 'FICC'],
    offices: ['Tokyo', 'New York', 'London', 'Hong Kong', 'Singapore', 'Sydney', 'Dubai'],
  },
  {
    key: 'nomura', name: 'Nomura', fullName: 'Nomura Holdings, Inc.',
    category: 'Bank', region: 'Asia-Pacific', hq: 'Tokyo',
    initials: 'NO', color: '#1a1a6e',
    tagline: "Japan's leading investment bank with global markets and commodities operations",
    overview: "Nomura is Japan's largest investment bank and one of the most significant Asia-headquartered financial institutions globally. Its Wholesale division provides institutional investors with fixed income, equities, and commodity-linked products. Nomura has a notable presence in commodity derivatives — particularly precious metals, energy, and agricultural products — through its Global Markets division, and provides structured commodity solutions to Japanese and international institutional clients and corporates.",
    markets: ['Fixed Income & Commodities', 'Equities', 'Investment Banking', 'Asset Management', 'Structured Products'],
    offices: ['Tokyo', 'New York', 'London', 'Hong Kong', 'Singapore', 'Mumbai', 'Dubai'],
  },
  {
    key: 'ing', name: 'ING', fullName: 'ING Group N.V.',
    category: 'Bank', region: 'Europe', hq: 'Amsterdam',
    initials: 'IN', color: '#ff6600',
    tagline: 'Dutch bank and one of Europe\'s largest commodity trade finance providers',
    overview: "ING is a Dutch multinational bank and a major provider of commodity trade finance in Europe and globally. Its Commodity Trade Finance division finances agricultural, energy, and metals commodity flows for traders, producers, and processors. ING is particularly strong in soft commodities (grains, oilseeds, sugar), energy trade finance, and structured commodity transactions. The bank is consistently ranked among the top European banks for commodity trade finance by notional volume.",
    markets: ['Commodity Trade Finance', 'Agricultural Finance', 'Energy Finance', 'Structured Finance', 'Corporate Lending'],
    offices: ['Amsterdam', 'London', 'Singapore', 'Geneva', 'New York', 'Hong Kong', 'Dubai'],
  },
  {
    key: 'abnamro', name: 'ABN AMRO', fullName: 'ABN AMRO Bank N.V.',
    category: 'Bank', region: 'Europe', hq: 'Amsterdam',
    initials: 'AA', color: '#009286',
    tagline: 'Dutch bank with specialist expertise in commodity trade finance and energy transition',
    overview: "ABN AMRO is a leading Dutch bank with longstanding expertise in commodity trade finance, particularly for metals, soft commodities, and energy products. Its Trade & Commodity Finance team has strong relationships with major commodity trading houses in Geneva, Singapore, and Houston. ABN AMRO is also positioning as a financing partner for the energy transition — providing green commodity finance, carbon finance, and sustainability-linked trade finance solutions.",
    markets: ['Commodity Trade Finance', 'Metals & Soft Commodities', 'Energy Transition Finance', 'Corporate Banking', 'Global Markets'],
    offices: ['Amsterdam', 'London', 'Singapore', 'Geneva', 'Dubai', 'New York', 'Hong Kong'],
  },
];

const ALL_FIRMS = [...FEATURED_FIRMS, ..._EXTRA_FIRMS, ...FEATURED_BANKS, ..._EXTRA_BANKS];

const _FIRMS_MAP = Object.fromEntries(ALL_FIRMS.map(f => [f.key, f]));

let _firmsSearchQuery = '';
let _firmsCategoryFilter = null; // null = default featured view; string = focused category
const _contactsIndex = {}; // firmKey → contacts array
let _contactViewCache = []; // rebuilt each renderFirmsPage search render; [{firmKey,contactIdx},…]

// ── Contact view state ────────────────────────────────────────────────────────
let _cvKey         = null;   // firmKey of the open contact view
let _cvIdx         = null;   // contact index within _cvData.contacts
let _cvData        = null;   // { notes, contacts } workspace data for this firm
let _cvEditing     = false;  // true = showing edit form for contact fields
let _cvEditingNote = null;   // { ni } or null — note being edited inline
let _cvAddingNote  = false;  // true = add-note textarea visible

// After any firm-modal contact save: sync _contactsIndex and the open contact view
function _afterFwContactsSave() {
  _contactsIndex[_fwKey] = _fwData.contacts;
  if (_cvKey === _fwKey && _cvData) {
    _cvData.contacts = _fwData.contacts;
    _renderContactView();
  }
}

function setFirmsSearch(val) {
  _firmsSearchQuery = val;
  renderFirmsPage();
}

function toggleFirmCategoryFilter(cat) {
  _firmsCategoryFilter = (_firmsCategoryFilter === cat) ? null : cat;
  _updateFilterPills();
  renderFirmsPage();
}

function _updateFilterPills() {
  ['Trading House', 'Hedge Fund', 'Bank'].forEach(cat => {
    const btn = document.getElementById('fpill-' + cat);
    if (btn) btn.classList.toggle('active', _firmsCategoryFilter === cat);
  });
}

// Pre-load all saved contacts into the index so search works immediately
async function _loadAllContactsIndex() {
  const res = await apiFetch('/api/workspace/all');
  if (!res) return;
  const data = await res.json().catch(() => null);
  if (!data || typeof data !== 'object') return;
  Object.entries(data).forEach(([firmKey, fw]) => {
    if (_FIRMS_MAP[firmKey] && Array.isArray(fw.contacts) && fw.contacts.length) {
      _contactsIndex[firmKey] = fw.contacts;
    }
  });
  if (_firmsSearchQuery.trim()) renderFirmsPage();
}
_loadAllContactsIndex();

/* ── Favorites ─────────────────────────────────────────────────────────────── */
let _favoriteFirms = [];  // array of firm keys, per-user, loaded from server

async function loadFavorites() {
  const res = await apiFetch('/api/favorites');
  if (!res) return;
  const data = await res.json();
  _favoriteFirms = Array.isArray(data) ? data : [];
  renderFirmsPage();
}
loadFavorites();

function isFavorite(key) { return _favoriteFirms.includes(key); }

function toggleFavorite(key) {
  const idx = _favoriteFirms.indexOf(key);
  if (idx >= 0) _favoriteFirms.splice(idx, 1);
  else _favoriteFirms.push(key);
  apiFetch('/api/favorites', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keys: _favoriteFirms }),
  });
  renderFirmsPage();
  _refreshModalFavBtn(key);
}

const _STAR_FILLED = `<svg viewBox="0 0 20 20" fill="currentColor" width="15" height="15"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.286 3.957a1 1 0 00.95.69h4.162c.969 0 1.371 1.24.588 1.81l-3.368 2.448a1 1 0 00-.364 1.118l1.287 3.957c.3.921-.755 1.688-1.54 1.118l-3.368-2.448a1 1 0 00-1.175 0l-3.368 2.448c-.784.57-1.838-.197-1.539-1.118l1.287-3.957a1 1 0 00-.364-1.118L2.065 9.384c-.783-.57-.38-1.81.588-1.81h4.162a1 1 0 00.95-.69L9.049 2.927z"/></svg>`;
const _STAR_EMPTY  = `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" width="15" height="15"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.286 3.957a1 1 0 00.95.69h4.162c.969 0 1.371 1.24.588 1.81l-3.368 2.448a1 1 0 00-.364 1.118l1.287 3.957c.3.921-.755 1.688-1.54 1.118l-3.368-2.448a1 1 0 00-1.175 0l-3.368 2.448c-.784.57-1.838-.197-1.539-1.118l1.287-3.957a1 1 0 00-.364-1.118L2.065 9.384c-.783-.57-.38-1.81.588-1.81h4.162a1 1 0 00.95-.69L9.049 2.927z" stroke-linejoin="round"/></svg>`;
const _STAR_FILLED_LG = `<svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.286 3.957a1 1 0 00.95.69h4.162c.969 0 1.371 1.24.588 1.81l-3.368 2.448a1 1 0 00-.364 1.118l1.287 3.957c.3.921-.755 1.688-1.54 1.118l-3.368-2.448a1 1 0 00-1.175 0l-3.368 2.448c-.784.57-1.838-.197-1.539-1.118l1.287-3.957a1 1 0 00-.364-1.118L2.065 9.384c-.783-.57-.38-1.81.588-1.81h4.162a1 1 0 00.95-.69L9.049 2.927z"/></svg>`;
const _STAR_EMPTY_LG  = `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" width="18" height="18"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.286 3.957a1 1 0 00.95.69h4.162c.969 0 1.371 1.24.588 1.81l-3.368 2.448a1 1 0 00-.364 1.118l1.287 3.957c.3.921-.755 1.688-1.54 1.118l-3.368-2.448a1 1 0 00-1.175 0l-3.368 2.448c-.784.57-1.838-.197-1.539-1.118l1.287-3.957a1 1 0 00-.364-1.118L2.065 9.384c-.783-.57-.38-1.81.588-1.81h4.162a1 1 0 00.95-.69L9.049 2.927z" stroke-linejoin="round"/></svg>`;

// ── Shared SVG icon constants (reused across workspace cards and contact view) ─
const _SVG_LINKEDIN = `<svg class="li-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M20.45 20.45h-3.554v-5.57c0-1.328-.024-3.037-1.85-3.037-1.851 0-2.134 1.446-2.134 2.94v5.667H9.358V9h3.414v1.561h.047c.475-.9 1.636-1.85 3.368-1.85 3.6 0 4.267 2.369 4.267 5.455v6.284zM5.337 7.433a2.062 2.062 0 1 1 0-4.124 2.062 2.062 0 0 1 0 4.124zM6.968 20.45H3.706V9h3.262v11.45zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>`;
const _SVG_EMAIL    = `<svg class="email-icon" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"/><path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"/></svg>`;
const _SVG_PENCIL   = `<svg class="fw-pencil-icon" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" fill="currentColor"><path d="M13.586 3.586a2 2 0 1 1 2.828 2.828l-.793.793-2.828-2.828.793-.793zm-2.207 2.207L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/></svg>`;
const _SVG_TRASH    = `<svg class="fw-trash-icon" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>`;

function _refreshModalFavBtn(key) {
  const btn = document.getElementById('firm-modal-fav-btn');
  if (!btn) return;
  const fav = isFavorite(key);
  btn.className  = 'firm-modal-fav-btn' + (fav ? ' active' : '');
  btn.title      = fav ? 'Remove from favorites' : 'Add to favorites';
  btn.innerHTML  = fav ? _STAR_FILLED_LG : _STAR_EMPTY_LG;
}

function _contactResultHtml(contact, firm) {
  const contacts   = _contactsIndex[firm.key] || [];
  const contactIdx = contacts.indexOf(contact);
  const cacheIdx   = _contactViewCache.push({ firmKey: firm.key, contactIdx }) - 1;
  const logo = `<span class="firm-logo contact-result-logo" style="background:${firm.color}">${esc(firm.initials)}</span>`;
  const titlePart = contact.title ? `<span class="contact-result-sep">&middot;</span><span class="contact-result-title">${esc(contact.title)}</span>` : '';
  const locPart   = contact.location ? `<span class="contact-result-sep">&middot;</span><span class="contact-result-loc">${esc(contact.location)}</span>` : '';
  return `<div class="contact-result-card" onclick="openContactView(${cacheIdx})">
    <div class="contact-result-name">${esc(contact.name)}</div>
    <div class="contact-result-meta">${logo}<span class="contact-result-firm">${esc(firm.name)}</span>${titlePart}${locPart}</div>
  </div>`;
}

function _firmCardHtml(f) {
  const fav = isFavorite(f.key);
  return `<div class="firm-card" onclick="openFirmModal('${f.key}')">
    <div class="firm-card-header">
      <div class="firm-logo" style="background:${f.color}">${esc(f.initials)}</div>
      <div class="firm-card-meta">
        <div class="firm-card-name">${esc(f.name)}</div>
        <div class="firm-card-tags">
          <span class="firm-tag firm-tag-region">${esc(f.region)}</span>
          <span class="firm-tag">${esc(f.category)}</span>
        </div>
      </div>
      <button class="firm-card-fav-btn${fav ? ' active' : ''}" onclick="event.stopPropagation();toggleFavorite('${f.key}')" title="${fav ? 'Remove from favorites' : 'Add to favorites'}">${fav ? _STAR_FILLED : _STAR_EMPTY}</button>
    </div>
    <div class="firm-card-tagline">${esc(f.tagline)}</div>
    <div class="firm-card-hint">View details &rarr;</div>
  </div>`;
}

function renderFirmsPage() {
  const el = document.getElementById('firms-page-body');
  if (!el) return;

  const q      = _firmsSearchQuery.toLowerCase().trim();
  const inCat  = f => !_firmsCategoryFilter || f.category === _firmsCategoryFilter;

  if (!q) {
    let html = '';

    if (_firmsCategoryFilter) {
      // Focused category view — show ALL firms of that category (no favorites section)
      const catLabels = {
        'Trading House': 'All Commodity Trading Houses',
        'Hedge Fund':    'All Hedge Funds',
        'Bank':          'All Banks',
      };
      const firms = ALL_FIRMS.filter(f => f.category === _firmsCategoryFilter);
      html += `<div class="page-section-heading">${catLabels[_firmsCategoryFilter] || _firmsCategoryFilter}</div>`;
      html += '<div class="firm-grid">';
      firms.forEach(f => { html += _firmCardHtml(f); });
      html += '</div>';
    } else {
      // Default featured grouped view
      const favFirms = _favoriteFirms.map(k => _FIRMS_MAP[k]).filter(Boolean);
      if (favFirms.length) {
        html += `<div class="page-section-heading">Your Favorites</div>`;
        html += '<div class="firm-grid">';
        favFirms.forEach(f => { html += _firmCardHtml(f); });
        html += '</div>';
      }
      const categories = [
        { key: 'Trading House', label: 'Featured Commodity Trading Houses', src: FEATURED_FIRMS },
        { key: 'Hedge Fund',    label: 'Featured Hedge Funds',              src: FEATURED_FIRMS },
        { key: 'Bank',          label: 'Featured Banks',                    src: FEATURED_BANKS },
      ];
      categories.forEach(cat => {
        const firms = cat.src.filter(f => f.category === cat.key).slice(0, 8);
        if (!firms.length) return;
        html += `<div class="page-section-heading">${cat.label}</div>`;
        html += '<div class="firm-grid">';
        firms.forEach(f => { html += _firmCardHtml(f); });
        html += '</div>';
      });
    }

    el.innerHTML = html;
    return;
  }

  // ── Search mode ─────────────────────────────────────────────────────────────
  _contactViewCache = []; // reset before building contact results for this render
  const filteredFirms = ALL_FIRMS.filter(f =>
    inCat(f) && (
      f.name.toLowerCase().includes(q)
      || (f.fullName || '').toLowerCase().includes(q)
      || (f.category || '').toLowerCase().includes(q)
      || (f.region || '').toLowerCase().includes(q)
      || (f.hq || '').toLowerCase().includes(q)
    )
  );

  // Search contacts index
  const filteredContacts = [];
  Object.entries(_contactsIndex).forEach(([firmKey, contacts]) => {
    const firm = _FIRMS_MAP[firmKey];
    if (!firm || !inCat(firm)) return;
    contacts.forEach(c => {
      if (!c.name) return;
      const noteTexts = [
        c.notes || c.description || '',
        ...(Array.isArray(c.note_history) ? c.note_history.map(n => n.text || '') : []),
      ].join(' ');
      if (
        c.name.toLowerCase().includes(q)
        || (c.title    || '').toLowerCase().includes(q)
        || (c.location || '').toLowerCase().includes(q)
        || noteTexts.toLowerCase().includes(q)
      ) filteredContacts.push({ contact: c, firm });
    });
  });

  if (!filteredFirms.length && !filteredContacts.length) {
    el.innerHTML = `<div class="firms-empty-state">No firms or contacts match &ldquo;${esc(q)}&rdquo;</div>`;
    return;
  }

  let html = '';
  if (filteredFirms.length) {
    html += `<div class="page-section-heading">Firms</div>`;
    html += '<div class="firm-grid">';
    filteredFirms.forEach(f => { html += _firmCardHtml(f); });
    html += '</div>';
  }
  if (filteredContacts.length) {
    html += `<div class="page-section-heading">Contacts</div>`;
    html += '<div class="contact-results-list">';
    filteredContacts.forEach(({ contact, firm }) => { html += _contactResultHtml(contact, firm); });
    html += '</div>';
  }
  el.innerHTML = html;
}
renderFirmsPage();

// ── Firm activity auto-refresh ────────────────────────────────────────────────
let _firmActivityTimer = null;

function _loadFirmActivity(key) {
  const f = _FIRMS_MAP[key];
  if (!f) return;
  const keyword = f.category === 'Trading House' ? 'commodity trading'
                : f.category === 'Bank'          ? 'investment bank'
                :                                  'hedge fund';
  const q = encodeURIComponent(f.name + ' ' + keyword);
  fetch('/api/news/search?q=' + q)
    .then(r => r.json())
    .then(articles => {
      const byDate = Array.isArray(articles)
        ? [...articles].sort((a, b) => {
            const ta = a.published ? new Date(a.published).getTime() : 0;
            const tb = b.published ? new Date(b.published).getTime() : 0;
            return tb - ta;
          })
        : [];
      const area = document.getElementById('firm-activity-body');
      if (!area) return;
      const _actTs = `<div class="page-updated-line" style="margin-top:10px;margin-bottom:0">${_fmtUpdated(new Date())}</div>`;
      if (!byDate.length) {
        area.innerHTML = '<p class="firm-activity-none">No recent news found for ' + esc(f.name) + '.</p>' + _actTs;
        return;
      }
      area.innerHTML = '<div class="firm-timeline">' +
        byDate.map(a => {
          const dateLabel = _relativeDate(a.published);
          return `<div class="firm-timeline-entry">
            <div class="firm-timeline-date">${dateLabel}</div>
            <div class="firm-timeline-content">
              <a class="firm-timeline-headline" href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a>
              ${a.source ? `<div class="firm-timeline-meta">${esc(a.source)}</div>` : ''}
            </div>
          </div>`;
        }).join('') + '</div>' + _actTs;
    })
    .catch(() => {
      const area = document.getElementById('firm-activity-body');
      if (area) area.innerHTML = '<p class="firm-activity-none">Could not load recent activity.</p>';
    });
}

// ── Firm workspace state (one modal open at a time) ─────────────────────────
let _fwKey           = null;
let _fwData          = { notes: '', contacts: [] };
let _fwAddingContact = false;
let _fwEditingIdx    = null;   // null = not editing; integer = index in _fwData.contacts
let _fwAddingNoteIdx = null;   // null = not adding note; integer = contact index receiving new note
let _fwEditingNote   = null;   // null or { ci: contactIdx, ni: noteIdx } for inline note edit
let _fwContactSort   = 'name';
let _fwSearchQuery   = '';

function openFirmModal(key) {
  const f = _FIRMS_MAP[key];
  if (!f) return;

  // Reset workspace state for this opening
  _fwKey           = key;
  _fwData          = { notes: '', contacts: [] };
  _fwAddingContact = false;
  _fwEditingIdx    = null;
  _fwAddingNoteIdx = null;
  _fwEditingNote   = null;
  _fwContactSort   = 'name';
  _fwSearchQuery   = '';

  const modal = document.getElementById('firm-modal');
  modal.style.setProperty('--modal-accent', f.color);
  modal.style.borderTopColor = f.color;
  const _modalFav = isFavorite(key);
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
      <button class="firm-modal-fav-btn${_modalFav ? ' active' : ''}" id="firm-modal-fav-btn" onclick="toggleFavorite('${f.key}')" title="${_modalFav ? 'Remove from favorites' : 'Add to favorites'}">${_modalFav ? _STAR_FILLED_LG : _STAR_EMPTY_LG}</button>
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
    <div class="modal-divider"></div>
    <div class="section-label" style="margin-bottom:14px">Private Workspace</div>
    <div id="firm-workspace-body">
      <div class="placeholder"><span class="spin"></span>Loading&hellip;</div>
    </div>
  `;
  document.getElementById('firm-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';

  _loadFirmActivity(key);

  // Auto-refresh firm activity every 3 minutes while this modal is open
  if (_firmActivityTimer) clearInterval(_firmActivityTimer);
  _firmActivityTimer = setInterval(() => { if (_fwKey === key) _loadFirmActivity(key); }, 3 * 60 * 1000);

  // Load private workspace data for this user + firm
  apiFetch('/api/workspace/' + key)
    .then(r => r && r.json())
    .then(data => {
      if (!data) return;
      _fwData = { notes: data.notes || '', contacts: Array.isArray(data.contacts) ? data.contacts : [] };
      _contactsIndex[key] = _fwData.contacts;
      _renderFirmWorkspace();
    })
    .catch(() => {
      const el = document.getElementById('firm-workspace-body');
      if (el) el.innerHTML = '<p class="firm-activity-none">Could not load workspace.</p>';
    });
}

function closeFirmModal() {
  if (_firmActivityTimer) { clearInterval(_firmActivityTimer); _firmActivityTimer = null; }
  document.getElementById('firm-overlay').classList.remove('open');
  document.body.style.overflow = '';
}
document.getElementById('firm-close-btn').addEventListener('click', closeFirmModal);
document.getElementById('firm-overlay').addEventListener('click', e => {
  if (e.target.id === 'firm-overlay') closeFirmModal();
});

// ── Contact view modal ────────────────────────────────────────────────────────

function openContactView(cacheIdx) {
  const item = _contactViewCache[cacheIdx];
  if (!item) return;
  _cvKey         = item.firmKey;
  _cvIdx         = item.contactIdx;
  _cvData        = null;
  _cvEditing     = false;
  _cvEditingNote = null;
  _cvAddingNote  = false;
  document.getElementById('contact-view-body').innerHTML =
    '<div class="placeholder"><span class="spin"></span>Loading\u2026</div>';
  document.getElementById('contact-view-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  apiFetch('/api/workspace/' + _cvKey)
    .then(r => r && r.json())
    .then(data => {
      if (!data) return;
      _cvData = { notes: data.notes || '', contacts: Array.isArray(data.contacts) ? data.contacts : [] };
      _contactsIndex[_cvKey] = _cvData.contacts;
      _renderContactView();
    })
    .catch(() => {
      const el = document.getElementById('contact-view-body');
      if (el) el.innerHTML = '<p style="color:var(--muted);padding:16px 0">Could not load contact.</p>';
    });
}

function closeContactView() {
  _cvKey = null; _cvIdx = null; _cvData = null;
  _cvEditing = false; _cvEditingNote = null; _cvAddingNote = false;
  document.getElementById('contact-view-overlay').classList.remove('open');
  document.body.style.overflow = '';
}
document.getElementById('contact-view-close-btn').addEventListener('click', closeContactView);
document.getElementById('contact-view-overlay').addEventListener('click', e => {
  if (e.target.id === 'contact-view-overlay') closeContactView();
});

function _renderContactView() {
  const el = document.getElementById('contact-view-body');
  if (!el || !_cvData) return;
  const c    = _cvData.contacts[_cvIdx];
  const firm = _FIRMS_MAP[_cvKey];
  if (!c || !firm) {
    el.innerHTML = '<p style="color:var(--muted);padding:16px 0">Contact not found.</p>';
    return;
  }
  const expLabel  = c.years_experience ? `<span class="workspace-contact-exp">${esc(String(c.years_experience))} yrs exp</span>` : '';
  const liLink    = c.linkedin_url ? `<a class="workspace-contact-linkedin" href="${esc(c.linkedin_url)}" target="_blank" rel="noopener" title="LinkedIn">${_SVG_LINKEDIN}</a>` : '';
  const emailLink = c.email ? `<a class="workspace-contact-email" href="mailto:${esc(c.email)}" title="${esc(c.email)}">${_SVG_EMAIL}</a>` : '';

  let html = `<div class="contact-view-firm-row" onclick="closeContactView();openFirmModal('${firm.key}')" title="Open firm workspace">
    <span class="firm-logo contact-view-firm-logo" style="background:${firm.color}">${esc(firm.initials)}</span>
    <span class="contact-view-firm-name">${esc(firm.name)}</span>
    <span class="contact-view-firm-arrow">&rsaquo;</span>
  </div>`;

  if (_cvEditing) {
    html += `<div class="workspace-contact-form">
      <div class="workspace-form-title">Edit Contact</div>
      <div class="workspace-form-field"><label class="workspace-form-label">Name <span class="workspace-form-req">*</span></label>
        <input class="workspace-input" id="cv-cf-name" type="text" value="${esc(c.name || '')}"></div>
      <div class="workspace-form-field"><label class="workspace-form-label">Job Title</label>
        <input class="workspace-input" id="cv-cf-title" type="text" value="${esc(c.title || '')}"></div>
      <div class="workspace-form-field"><label class="workspace-form-label">Location</label>
        <input class="workspace-input" id="cv-cf-location" type="text" value="${esc(c.location || '')}"></div>
      <div class="workspace-form-field"><label class="workspace-form-label">Phone</label>
        <input class="workspace-input" id="cv-cf-phone" type="tel" value="${esc(c.phone || '')}"></div>
      <div class="workspace-form-field"><label class="workspace-form-label">Email</label>
        <input class="workspace-input" id="cv-cf-email" type="email" value="${esc(c.email || '')}"></div>
      <div class="workspace-form-field"><label class="workspace-form-label">Years of Experience</label>
        <input class="workspace-input" id="cv-cf-exp" type="number" min="0" max="60" value="${esc(c.years_experience != null ? String(c.years_experience) : '')}"></div>
      <div class="workspace-form-field"><label class="workspace-form-label">LinkedIn URL</label>
        <input class="workspace-input" id="cv-cf-linkedin" type="url" value="${esc(c.linkedin_url || '')}"></div>
      <div class="workspace-form-actions">
        <button class="workspace-btn-primary" onclick="cvSaveEdit()">Save</button>
        <button class="workspace-btn-ghost"   onclick="cvCancelEdit()">Cancel</button>
      </div>
    </div>`;
  } else {
    html += `<div class="contact-view-name">${esc(c.name)}${liLink}${emailLink}</div>`;
    if (c.title || expLabel) html += `<div class="workspace-contact-title">${c.title ? esc(c.title) : ''}${expLabel ? `&ensp;${expLabel}` : ''}</div>`;
    if (c.location) html += `<div class="workspace-contact-location">${esc(c.location)}</div>`;
    if (c.phone)    html += `<div class="workspace-contact-phone">${esc(c.phone)}</div>`;
    if (c.email)    html += `<div class="contact-view-email-text">${esc(c.email)}</div>`;
    html += `<button class="workspace-btn-secondary" style="margin-top:8px" onclick="cvStartEdit()">Edit contact</button>`;
  }

  // Note history
  html += '<div class="modal-divider" style="margin-top:8px"></div>';
  html += '<div class="section-label" style="margin-bottom:10px">Notes</div>';
  const noteHistory = Array.isArray(c.note_history) ? c.note_history : [];
  const legacyNote  = (c.notes || c.description || '').trim();
  // Merge legacy note into note_history as a deletable entry if no structured history exists
  const allNotes = noteHistory.length
    ? noteHistory
    : (legacyNote ? [{ text: legacyNote, ts: null }] : []);
  if (allNotes.length) {
    html += '<div class="contact-note-history">';
    allNotes.map((entry, ni) => ({ entry, ni })).reverse().forEach(({ entry, ni }) => {
      const ts = entry.ts ? _fmtNoteDate(entry.ts) : '';
      const isEditingThis = _cvEditingNote && _cvEditingNote.ni === ni;
      if (isEditingThis) {
        html += `<div class="contact-note-entry contact-note-editing">
          ${ts ? `<div class="contact-note-entry-header"><span class="contact-note-ts">${esc(ts)}</span></div>` : ''}
          <textarea class="workspace-input contact-addnote-textarea" id="cv-editnote-${ni}" rows="3">${esc(entry.text || '')}</textarea>
          <div class="contact-addnote-actions">
            <button class="workspace-btn-primary" onclick="cvSaveEditedNote(${ni})">Save</button>
            <button class="workspace-btn-ghost"   onclick="cvCancelEditNote()">Cancel</button>
          </div>
        </div>`;
      } else {
        html += `<div class="contact-note-entry">
          <div class="contact-note-entry-header">
            ${ts ? `<span class="contact-note-ts">${esc(ts)}</span>` : ''}
            <button class="contact-note-edit-btn"   onclick="cvStartEditNote(${ni})"  title="Edit note">${_SVG_PENCIL}</button>
            <button class="contact-note-delete-btn" onclick="cvDeleteNote(${ni})"     title="Delete note">${_SVG_TRASH}</button>
          </div>
          <span class="contact-note-text">${esc(entry.text || '')}</span>
        </div>`;
      }
    });
    html += '</div>';
  }

  if (_cvAddingNote) {
    html += `<div class="contact-addnote-form">
      <textarea class="workspace-input contact-addnote-textarea" id="cv-addnote" placeholder="Add a note\u2026" rows="3"></textarea>
      <div class="contact-addnote-actions">
        <button class="workspace-btn-primary" onclick="cvSaveNote()">Save note</button>
        <button class="workspace-btn-ghost"   onclick="cvCancelAddNote()">Cancel</button>
      </div>
    </div>`;
  } else {
    html += `<button class="workspace-btn-addnote" onclick="cvStartAddNote()">+ Add note</button>`;
  }

  el.innerHTML = html;
}

// ── Contact view editing functions ───────────────────────────────────────────

function _cvSaveToServer() {
  _contactsIndex[_cvKey] = _cvData.contacts;
  if (_fwKey === _cvKey && _fwData) {
    _fwData.contacts = _cvData.contacts;
    _renderFirmWorkspace();
  }
  apiFetch('/api/workspace/' + _cvKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_cvData),
  }).then(() => _renderContactView());
}

function cvStartEdit() { _cvEditing = true; _cvAddingNote = false; _cvEditingNote = null; _renderContactView(); }
function cvCancelEdit() { _cvEditing = false; _renderContactView(); }

function cvSaveEdit() {
  const name         = (document.getElementById('cv-cf-name')?.value     || '').trim();
  const title        = (document.getElementById('cv-cf-title')?.value    || '').trim();
  const location     = (document.getElementById('cv-cf-location')?.value || '').trim();
  const phone        = (document.getElementById('cv-cf-phone')?.value    || '').trim();
  const email        = (document.getElementById('cv-cf-email')?.value    || '').trim();
  const linkedin_url = (document.getElementById('cv-cf-linkedin')?.value || '').trim();
  const expRaw       = (document.getElementById('cv-cf-exp')?.value      || '').trim();
  const years_experience = expRaw !== '' ? parseInt(expRaw, 10) || null : null;
  if (!name) { const el = document.getElementById('cv-cf-name'); if (el) { el.focus(); el.classList.add('workspace-input-err'); } return; }
  const existing = _cvData.contacts[_cvIdx];
  _cvData.contacts[_cvIdx] = { name, title, location, phone, email, years_experience, linkedin_url, notes: existing.notes || '', note_history: existing.note_history || [] };
  _cvEditing = false;
  _cvSaveToServer();
}

function cvStartAddNote() {
  _cvAddingNote = true; _cvEditingNote = null; _cvEditing = false;
  _renderContactView();
  setTimeout(() => { const ta = document.getElementById('cv-addnote'); if (ta) ta.focus(); }, 30);
}
function cvCancelAddNote() { _cvAddingNote = false; _renderContactView(); }

function cvSaveNote() {
  const ta = document.getElementById('cv-addnote');
  const text = (ta?.value || '').trim();
  if (!text) { if (ta) ta.focus(); return; }
  const contact = _cvData.contacts[_cvIdx];
  if (!Array.isArray(contact.note_history)) contact.note_history = [];
  contact.note_history.push({ text, ts: new Date().toISOString() });
  _cvAddingNote = false;
  _cvSaveToServer();
}

function cvStartEditNote(ni) {
  _cvEditingNote = { ni }; _cvAddingNote = false; _cvEditing = false;
  _renderContactView();
  setTimeout(() => { const ta = document.getElementById(`cv-editnote-${ni}`); if (ta) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); } }, 30);
}
function cvCancelEditNote() { _cvEditingNote = null; _renderContactView(); }

function cvSaveEditedNote(ni) {
  const ta = document.getElementById(`cv-editnote-${ni}`);
  const text = (ta?.value || '').trim();
  if (!text) { if (ta) ta.focus(); return; }
  const contact = _cvData.contacts[_cvIdx];
  // Handle legacy-note-only case: save back to notes field and promote to history
  if (!Array.isArray(contact.note_history) || !contact.note_history.length) {
    contact.notes = text; _cvEditingNote = null; _cvSaveToServer(); return;
  }
  if (!contact.note_history[ni]) return;
  contact.note_history[ni] = { ...contact.note_history[ni], text };
  _cvEditingNote = null;
  _cvSaveToServer();
}

function cvDeleteNote(ni) {
  if (!confirm('Delete this note entry? This cannot be undone.')) return;
  const contact = _cvData.contacts[_cvIdx];
  // Handle legacy-note-only case: clear the notes field instead
  if (!Array.isArray(contact.note_history) || !contact.note_history.length) {
    contact.notes = ''; contact.description = '';
    if (_cvEditingNote) _cvEditingNote = null;
    _cvSaveToServer(); return;
  }
  contact.note_history.splice(ni, 1);
  if (_cvEditingNote && _cvEditingNote.ni === ni) _cvEditingNote = null;
  _cvSaveToServer();
}

/* ── Date helpers ────────────────────────────────────────────────────────────── */
function _relativeDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  const diffMs = Date.now() - d.getTime();
  const diffH  = Math.floor(diffMs / 3_600_000);
  const diffD  = Math.floor(diffMs / 86_400_000);
  if (diffH < 1)  return 'just now';
  if (diffH < 24) return diffH + 'h ago';
  if (diffD < 7)  return diffD + 'd ago';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Absolute date/time format for stored note timestamps — e.g. "11 Mar 2026, 14:32"
function _fmtNoteDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  if (isNaN(d)) return String(isoStr);
  const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${h}:${m}`;
}

function _fmtUpdated(d) {
  if (!d) return '';
  const h = String(d.getUTCHours()).padStart(2, '0');
  const m = String(d.getUTCMinutes()).padStart(2, '0');
  return `Last updated ${h}:${m} UTC`;
}

/* ── Firm workspace ──────────────────────────────────────────────────────────── */

function _syncFwNotes() {
  // Preserve any unsaved text in the textarea before a re-render
  const el = document.getElementById('fw-notes');
  if (el) _fwData.notes = el.value;
}

function _renderFirmWorkspace() {
  const el = document.getElementById('firm-workspace-body');
  if (!el) return;

  // Notes block
  const _hasNotes = _fwData.notes.trim().length > 0;
  let html = `<div class="workspace-block">
    <div class="workspace-block-label">Notes</div>
    <textarea class="workspace-notes-area" id="fw-notes"
              placeholder="Your private notes for this firm\u2026"
              onblur="autoSaveFirmNotes()">${esc(_fwData.notes)}</textarea>
    <div class="workspace-row-actions">
      <button class="workspace-btn-primary" onclick="saveFirmNotes()">Save</button>
      ${_hasNotes ? '<button class="workspace-btn-notes-clear" onclick="clearFirmNotes()">Clear</button>' : ''}
      <span class="workspace-save-status" id="fw-notes-status"></span>
    </div>
  </div>`;

  // Contacts block
  html += '<div class="workspace-block">';
  const _cCount = _fwData.contacts.length;
  html += `<div class="workspace-block-label">Contacts${_cCount ? ` <span class="workspace-count">(${_cCount})</span>` : ''}</div>`;

  if (_fwData.contacts.length) {
    // Search bar
    html += `<div class="workspace-search-wrap">
      <input class="workspace-search-input" type="text" placeholder="Search contacts\u2026"
             value="${esc(_fwSearchQuery)}" oninput="setFwSearch(this.value)">
    </div>`;

    // Sort pills
    const sortFields = [['name','Name'],['title','Title'],['location','Location']];
    html += '<div class="workspace-sort-pills">';
    sortFields.forEach(([field, label]) => {
      html += `<button class="workspace-sort-pill${_fwContactSort === field ? ' active' : ''}" onclick="setFwSort('${field}')">${label}</button>`;
    });
    html += '</div>';

    // Build filtered indexed list — preserve original array indices for edit/delete targeting
    const _searchQ = _fwSearchQuery.toLowerCase();
    const allIdx   = _fwData.contacts.map((c, idx) => ({ c, idx }));
    const filtered = _searchQ
      ? allIdx.filter(({ c }) => {
          const notes = [
            c.notes || c.description || '',
            ...(Array.isArray(c.note_history) ? c.note_history.map(n => n.text || '') : []),
          ].join(' ');
          return (c.name     || '').toLowerCase().includes(_searchQ)
              || (c.title    || '').toLowerCase().includes(_searchQ)
              || (c.location || '').toLowerCase().includes(_searchQ)
              || (c.email    || '').toLowerCase().includes(_searchQ)
              || (c.phone    || '').toLowerCase().includes(_searchQ)
              || notes.toLowerCase().includes(_searchQ);
        })
      : allIdx;

    // Shared SVG assets
    const _liSvg     = `<svg class="li-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M20.45 20.45h-3.554v-5.57c0-1.328-.024-3.037-1.85-3.037-1.851 0-2.134 1.446-2.134 2.94v5.667H9.358V9h3.414v1.561h.047c.475-.9 1.636-1.85 3.368-1.85 3.6 0 4.267 2.369 4.267 5.455v6.284zM5.337 7.433a2.062 2.062 0 1 1 0-4.124 2.062 2.062 0 0 1 0 4.124zM6.968 20.45H3.706V9h3.262v11.45zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>`;
    const _emailSvg  = `<svg class="email-icon" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"/><path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"/></svg>`;
    const _pencilSvg = `<svg class="fw-pencil-icon" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" fill="currentColor"><path d="M13.586 3.586a2 2 0 1 1 2.828 2.828l-.793.793-2.828-2.828.793-.793zm-2.207 2.207L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/></svg>`;
    const _trashSvg  = `<svg class="fw-trash-icon" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>`;

    // Contact card builder — idx is the original array index (for edit/delete targeting)
    const _cardHtml = (c, idx, showLocation = true) => {
      const liLink   = c.linkedin_url
        ? `<a class="workspace-contact-linkedin" href="${esc(c.linkedin_url)}" target="_blank" rel="noopener" title="LinkedIn profile">${_liSvg}</a>`
        : '';
      const emailLink = c.email
        ? `<a class="workspace-contact-email" href="mailto:${esc(c.email)}" title="${esc(c.email)}">${_emailSvg}</a>`
        : '';
      const editBtn   = `<button class="fw-edit-btn"   onclick="editFirmContact(${idx})"   title="Edit contact">${_pencilSvg}</button>`;
      const deleteBtn = `<button class="fw-delete-btn" onclick="deleteFirmContact(${idx})" title="Delete contact">${_trashSvg}</button>`;
      const expLabel  = c.years_experience ? `<span class="workspace-contact-exp">${esc(String(c.years_experience))} yrs exp</span>` : '';

      // Note history — new entries + backward-compat legacy notes field
      const noteHistory  = Array.isArray(c.note_history) ? c.note_history : [];
      const legacyNote   = (c.notes || c.description || '').trim();
      // Merge legacy note as a deletable entry when no structured history exists
      const allNotesFw   = noteHistory.length ? noteHistory : (legacyNote ? [{ text: legacyNote, ts: null }] : []);
      let noteHistoryHtml = '';
      if (allNotesFw.length) {
        noteHistoryHtml += '<div class="contact-note-history">';
        // Render newest-first; preserve original index (ni) for edit targeting
        allNotesFw.map((entry, ni) => ({ entry, ni })).reverse().forEach(({ entry, ni }) => {
          const ts = entry.ts ? _fmtNoteDate(entry.ts) : '';
          const isEditingThis = _fwEditingNote && _fwEditingNote.ci === idx && _fwEditingNote.ni === ni;
          if (isEditingThis) {
            noteHistoryHtml += `<div class="contact-note-entry contact-note-editing">
              ${ts ? `<div class="contact-note-entry-header"><span class="contact-note-ts">${esc(ts)}</span></div>` : ''}
              <textarea class="workspace-input contact-addnote-textarea" id="fw-editnote-${idx}-${ni}" rows="3">${esc(entry.text || '')}</textarea>
              <div class="contact-addnote-actions">
                <button class="workspace-btn-primary" onclick="saveEditedNote(${idx},${ni})">Save</button>
                <button class="workspace-btn-ghost"   onclick="cancelEditNote()">Cancel</button>
              </div>
            </div>`;
          } else {
            noteHistoryHtml += `<div class="contact-note-entry">
              <div class="contact-note-entry-header">
                ${ts ? `<span class="contact-note-ts">${esc(ts)}</span>` : ''}
                <button class="contact-note-edit-btn" onclick="startEditNote(${idx},${ni})" title="Edit note">${_pencilSvg}</button>
                <button class="contact-note-delete-btn" onclick="deleteContactNote(${idx},${ni})" title="Delete note">${_trashSvg}</button>
              </div>
              <span class="contact-note-text">${esc(entry.text || '')}</span>
            </div>`;
          }
        });
        noteHistoryHtml += '</div>';
      }

      // Inline add-note form or button
      const addNoteSection = _fwAddingNoteIdx === idx
        ? `<div class="contact-addnote-form">
            <textarea class="workspace-input contact-addnote-textarea" id="fw-addnote-${idx}" placeholder="Add a note\u2026" rows="3"></textarea>
            <div class="contact-addnote-actions">
              <button class="workspace-btn-primary" onclick="saveContactNote(${idx})">Save note</button>
              <button class="workspace-btn-ghost"   onclick="cancelAddNote()">Cancel</button>
            </div>
          </div>`
        : `<button class="workspace-btn-addnote" onclick="startAddNote(${idx})">+ Add note</button>`;

      return `<div class="workspace-contact-card">
        <div class="fw-card-actions">${editBtn}${deleteBtn}</div>
        <div class="workspace-contact-name">${esc(c.name)}${liLink}${emailLink}</div>
        ${c.title ? `<div class="workspace-contact-title">${esc(c.title)}${expLabel ? `&ensp;${expLabel}` : ''}</div>` : (expLabel ? `<div class="workspace-contact-title">${expLabel}</div>` : '')}
        ${c.phone  ? `<div class="workspace-contact-phone">${esc(c.phone)}</div>` : ''}
        ${showLocation && c.location ? `<div class="workspace-contact-location">${esc(c.location)}</div>` : ''}
        ${noteHistoryHtml}
        ${addNoteSection}
      </div>`;
    };

    if (!filtered.length) {
      html += '<p class="workspace-empty">No contacts match your search.</p>';
    } else if (_fwContactSort === 'location') {
      // Group by location — keyed by trimmed location (case-preserved from first occurrence)
      const groupMap = new Map();
      const noLocContacts = [];
      filtered.forEach(({ c, idx }) => {
        const loc = (c.location || '').trim();
        if (!loc) { noLocContacts.push({ c, idx }); return; }
        const key = loc.toLowerCase();
        if (!groupMap.has(key)) groupMap.set(key, { label: loc, items: [] });
        groupMap.get(key).items.push({ c, idx });
      });
      const groups = [...groupMap.entries()].sort((a, b) => a[0] < b[0] ? -1 : 1).map(([, v]) => v);
      if (noLocContacts.length) groups.push({ label: 'No location', items: noLocContacts });

      html += '<div class="workspace-location-groups">';
      groups.forEach(g => {
        const isNoloc = g.label === 'No location';
        html += `<div class="workspace-location-group${isNoloc ? ' workspace-location-group-noloc' : ''}">`;
        html += `<div class="workspace-location-header">${esc(g.label)}<span class="workspace-location-count"> (${g.items.length})</span></div>`;
        html += `<div class="workspace-contacts-list">`;
        g.items.forEach(({ c, idx }) => { html += _cardHtml(c, idx, false); });
        html += `</div></div>`;
      });
      html += '</div>';
    } else {
      // Stable alphabetical sort — track original indices for edit/delete targeting
      const sorted = [...filtered];
      sorted.sort((a, b) => {
        const av = (a.c[_fwContactSort] || '').toLowerCase();
        const bv = (b.c[_fwContactSort] || '').toLowerCase();
        return av < bv ? -1 : av > bv ? 1 : 0;
      });
      html += '<div class="workspace-contacts-list">';
      sorted.forEach(({ c, idx }) => { html += _cardHtml(c, idx); });
      html += '</div>';
    }
  } else {
    html += '<p class="workspace-empty">No contacts saved yet.</p>';
  }

  // ── Contact form panel (Add or Edit) ──────────────────────────────────────
  const isEditing = _fwEditingIdx !== null;
  const isAdding  = _fwAddingContact;

  if (!isAdding && !isEditing) {
    html += `<button class="workspace-btn-secondary" onclick="showFirmContactForm()">+ Add Contact</button>`;
  } else {
    const pre = isEditing ? _fwData.contacts[_fwEditingIdx] : {};
    const formTitle = isEditing ? 'Edit Contact' : 'New Contact';
    const saveCall  = isEditing ? 'saveEditedContact()' : 'saveFirmContact()';
    const cancelCall = isEditing ? 'cancelEditContact()' : 'hideFirmContactForm()';
    html += `<div class="workspace-contact-form">
      <div class="workspace-form-title">${formTitle}</div>
      <div class="workspace-form-field">
        <label class="workspace-form-label">Name <span class="workspace-form-req">*</span></label>
        <input class="workspace-input" id="fw-cf-name" type="text" placeholder="Full name" value="${esc(pre.name || '')}">
      </div>
      <div class="workspace-form-field">
        <label class="workspace-form-label">Job Title</label>
        <input class="workspace-input" id="fw-cf-title" type="text" placeholder="e.g. Head of Trading" value="${esc(pre.title || '')}">
      </div>
      ${!isEditing ? `<div class="workspace-form-field">
        <label class="workspace-form-label">Initial note <span class="workspace-form-opt">(optional)</span></label>
        <input class="workspace-input" id="fw-cf-desc" type="text" placeholder="Context, relationship, how you met\u2026">
      </div>` : ''}
      <div class="workspace-form-field">
        <label class="workspace-form-label">Location</label>
        <input class="workspace-input" id="fw-cf-location" type="text" placeholder="City or office" value="${esc(pre.location || '')}">
      </div>
      <div class="workspace-form-field">
        <label class="workspace-form-label">Phone</label>
        <input class="workspace-input" id="fw-cf-phone" type="tel" placeholder="+44 7700 900000" value="${esc(pre.phone || '')}">
      </div>
      <div class="workspace-form-field">
        <label class="workspace-form-label">Email</label>
        <input class="workspace-input" id="fw-cf-email" type="email" placeholder="name@firm.com" value="${esc(pre.email || '')}">
      </div>
      <div class="workspace-form-field">
        <label class="workspace-form-label">Years of Experience</label>
        <input class="workspace-input" id="fw-cf-exp" type="number" min="0" max="60" placeholder="e.g. 12" value="${esc(pre.years_experience != null ? String(pre.years_experience) : '')}">
      </div>
      <div class="workspace-form-field">
        <label class="workspace-form-label">LinkedIn URL</label>
        <input class="workspace-input" id="fw-cf-linkedin" type="url" placeholder="https://linkedin.com/in/\u2026" value="${esc(pre.linkedin_url || '')}">
      </div>
      <div class="workspace-form-actions">
        <button class="workspace-btn-primary" onclick="${saveCall}">Save</button>
        <button class="workspace-btn-ghost"   onclick="${cancelCall}">Cancel</button>
      </div>
    </div>`;
  }

  html += '</div>'; // .workspace-block (contacts)
  el.innerHTML = html;
}

function saveFirmNotes() {
  const textarea = document.getElementById('fw-notes');
  const status   = document.getElementById('fw-notes-status');
  if (!textarea || !status) return;
  _fwData.notes = textarea.value;
  status.className = 'workspace-save-status';
  status.textContent = 'Saving\u2026';
  apiFetch('/api/workspace/' + _fwKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_fwData),
  }).then(r => {
    if (!r) return;
    status.textContent = r.ok ? 'Saved.' : 'Failed to save.';
    status.classList.add(r.ok ? 'ok' : 'err');
    setTimeout(() => { if (status) { status.textContent = ''; status.className = 'workspace-save-status'; } }, 2500);
  });
}

function autoSaveFirmNotes() {
  const textarea = document.getElementById('fw-notes');
  if (!textarea) return;
  const newVal = textarea.value;
  if (newVal === _fwData.notes) return;  // nothing changed
  _fwData.notes = newVal;
  const status = document.getElementById('fw-notes-status');
  apiFetch('/api/workspace/' + _fwKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_fwData),
  }).then(r => {
    if (!r || !status) return;
    if (r.ok) {
      status.className = 'workspace-save-status ok';
      status.textContent = 'Saved';
      setTimeout(() => { if (status) { status.textContent = ''; status.className = 'workspace-save-status'; } }, 1800);
    }
  });
}

function clearFirmNotes() {
  if (!confirm('Clear all notes for this firm? This cannot be undone.')) return;
  _fwData.notes = '';
  apiFetch('/api/workspace/' + _fwKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_fwData),
  }).then(() => _renderFirmWorkspace());
}

function showFirmContactForm() {
  _syncFwNotes();
  _fwAddingContact = true;
  _fwEditingIdx    = null;
  _fwAddingNoteIdx = null;
  _fwEditingNote   = null;
  _renderFirmWorkspace();
}

function hideFirmContactForm() {
  _syncFwNotes();
  _fwAddingContact = false;
  _renderFirmWorkspace();
}

function editFirmContact(idx) {
  _syncFwNotes();
  _fwAddingContact = false;
  _fwAddingNoteIdx = null;
  _fwEditingNote   = null;
  _fwEditingIdx    = idx;
  _renderFirmWorkspace();
}

function cancelEditContact() {
  _syncFwNotes();
  _fwEditingIdx    = null;
  _fwAddingNoteIdx = null;
  _fwEditingNote   = null;
  _renderFirmWorkspace();
}

function deleteFirmContact(idx) {
  if (!confirm('Delete this contact? This cannot be undone.')) return;
  _syncFwNotes();
  _fwData.contacts.splice(idx, 1);
  if (_fwEditingIdx === idx) _fwEditingIdx = null;
  else if (_fwEditingIdx !== null && _fwEditingIdx > idx) _fwEditingIdx--;
  if (_fwAddingNoteIdx === idx) _fwAddingNoteIdx = null;
  else if (_fwAddingNoteIdx !== null && _fwAddingNoteIdx > idx) _fwAddingNoteIdx--;
  if (_fwEditingNote && _fwEditingNote.ci === idx) _fwEditingNote = null;
  else if (_fwEditingNote && _fwEditingNote.ci > idx) _fwEditingNote = { ..._fwEditingNote, ci: _fwEditingNote.ci - 1 };
  _afterFwContactsSave();
  apiFetch('/api/workspace/' + _fwKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_fwData),
  }).then(() => _renderFirmWorkspace());
}

function saveEditedContact() {
  const name             = (document.getElementById('fw-cf-name')?.value     || '').trim();
  const title            = (document.getElementById('fw-cf-title')?.value    || '').trim();
  const desc             = (document.getElementById('fw-cf-desc')?.value     || '').trim();
  const location         = (document.getElementById('fw-cf-location')?.value || '').trim();
  const phone            = (document.getElementById('fw-cf-phone')?.value    || '').trim();
  const email            = (document.getElementById('fw-cf-email')?.value    || '').trim();
  const linkedin_url     = (document.getElementById('fw-cf-linkedin')?.value || '').trim();
  const _expRaw          = (document.getElementById('fw-cf-exp')?.value      || '').trim();
  const years_experience = _expRaw !== '' ? parseInt(_expRaw, 10) || null : null;
  if (!name) {
    const el = document.getElementById('fw-cf-name');
    if (el) { el.focus(); el.classList.add('workspace-input-err'); }
    return;
  }
  const existing = _fwData.contacts[_fwEditingIdx];
  _fwData.contacts[_fwEditingIdx] = {
    name, title, location, phone, email, years_experience, linkedin_url,
    notes:        existing.notes || '',
    note_history: existing.note_history || [],
  };
  _fwEditingIdx = null;
  _afterFwContactsSave();
  apiFetch('/api/workspace/' + _fwKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_fwData),
  }).then(() => _renderFirmWorkspace());
}

function saveFirmContact() {
  const name             = (document.getElementById('fw-cf-name')?.value     || '').trim();
  const title            = (document.getElementById('fw-cf-title')?.value    || '').trim();
  const desc             = (document.getElementById('fw-cf-desc')?.value     || '').trim();
  const location         = (document.getElementById('fw-cf-location')?.value || '').trim();
  const phone            = (document.getElementById('fw-cf-phone')?.value    || '').trim();
  const email            = (document.getElementById('fw-cf-email')?.value    || '').trim();
  const linkedin_url     = (document.getElementById('fw-cf-linkedin')?.value || '').trim();
  const _expRaw          = (document.getElementById('fw-cf-exp')?.value      || '').trim();
  const years_experience = _expRaw !== '' ? parseInt(_expRaw, 10) || null : null;
  if (!name) {
    const el = document.getElementById('fw-cf-name');
    if (el) { el.focus(); el.classList.add('workspace-input-err'); }
    return;
  }
  const note_history = desc ? [{ text: desc, ts: new Date().toISOString() }] : [];
  _fwData.contacts.push({ name, title, notes: '', note_history, location, phone, email, years_experience, linkedin_url });
  _fwAddingContact = false;
  _afterFwContactsSave();
  apiFetch('/api/workspace/' + _fwKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_fwData),
  }).then(() => _renderFirmWorkspace());
}

function setFwSort(field) {
  _syncFwNotes();
  _fwContactSort = field;
  _renderFirmWorkspace();
}

function setFwSearch(val) {
  _fwSearchQuery = val;
  _renderFirmWorkspace();
}

function startAddNote(idx) {
  _syncFwNotes();
  _fwAddingNoteIdx = idx;
  _fwEditingNote   = null;
  _renderFirmWorkspace();
  setTimeout(() => {
    const ta = document.getElementById('fw-addnote-' + idx);
    if (ta) ta.focus();
  }, 30);
}

function cancelAddNote() {
  _fwAddingNoteIdx = null;
  _renderFirmWorkspace();
}

function startEditNote(ci, ni) {
  _syncFwNotes();
  _fwEditingNote   = { ci, ni };
  _fwAddingNoteIdx = null;
  _renderFirmWorkspace();
  setTimeout(() => {
    const ta = document.getElementById(`fw-editnote-${ci}-${ni}`);
    if (ta) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
  }, 30);
}

function cancelEditNote() {
  _fwEditingNote = null;
  _renderFirmWorkspace();
}

function saveEditedNote(ci, ni) {
  const ta = document.getElementById(`fw-editnote-${ci}-${ni}`);
  const text = (ta?.value || '').trim();
  if (!text) { if (ta) ta.focus(); return; }
  _syncFwNotes();
  const contact = _fwData.contacts[ci];
  if (!Array.isArray(contact.note_history) || !contact.note_history[ni]) return;
  contact.note_history[ni] = { ...contact.note_history[ni], text };
  _fwEditingNote = null;
  _afterFwContactsSave();
  apiFetch('/api/workspace/' + _fwKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_fwData),
  }).then(() => _renderFirmWorkspace());
}

function deleteContactNote(ci, ni) {
  if (!confirm('Delete this note entry? This cannot be undone.')) return;
  _syncFwNotes();
  const contact = _fwData.contacts[ci];
  // Handle legacy-note-only case: clear notes field
  if (!Array.isArray(contact.note_history) || !contact.note_history.length) {
    contact.notes = ''; contact.description = '';
    if (_fwEditingNote && _fwEditingNote.ci === ci) _fwEditingNote = null;
    _afterFwContactsSave();
    apiFetch('/api/workspace/' + _fwKey, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(_fwData),
    }).then(() => _renderFirmWorkspace()); return;
  }
  contact.note_history.splice(ni, 1);
  if (_fwEditingNote && _fwEditingNote.ci === ci && _fwEditingNote.ni === ni) _fwEditingNote = null;
  _afterFwContactsSave();
  apiFetch('/api/workspace/' + _fwKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_fwData),
  }).then(() => _renderFirmWorkspace());
}

function saveContactNote(idx) {
  const textarea = document.getElementById('fw-addnote-' + idx);
  const text = (textarea?.value || '').trim();
  if (!text) { if (textarea) textarea.focus(); return; }
  _syncFwNotes();
  const contact = _fwData.contacts[idx];
  if (!Array.isArray(contact.note_history)) contact.note_history = [];
  contact.note_history.push({ text, ts: new Date().toISOString() });
  _fwAddingNoteIdx = null;
  _afterFwContactsSave();
  apiFetch('/api/workspace/' + _fwKey, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(_fwData),
  }).then(() => _renderFirmWorkspace());
}

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
        <div class="context-meta">${_sourceBadge(item.source)}${item.published ? ' &middot; ' + esc(item.published) : ''}</div>
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
        <div class="context-meta">${_sourceBadge(item.source)}${item.published ? ' &middot; ' + esc(item.published) : ''}</div>
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
      <div class="settings-row-label">Signed in as ${esc(CURRENT_USER)}</div>
    </div>
    <div class="settings-pills">
      <button class="settings-pill" onclick="openPwModal()">Change Password</button>
      <a class="settings-pill settings-pill-link" href="/logout">Sign Out</a>
      <a class="settings-pill settings-pill-link" href="/logout">Switch Account</a>
    </div>
  </div>`;
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

/* ── Change Password modal ────────────────────────────────────────────────── */
function openPwModal() {
  const overlay = document.getElementById('pw-change-overlay');
  if (!overlay) return;
  // Clear previous state
  ['pw-current', 'pw-new', 'pw-confirm'].forEach(id => {
    const el = document.getElementById(id); if (el) el.value = '';
  });
  const msg = document.getElementById('pw-modal-msg');
  if (msg) { msg.textContent = ''; msg.className = 'pw-modal-msg'; }
  overlay.classList.add('open');
}

function togglePwVis(inputId, btn) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  const show = inp.type === 'password';
  inp.type = show ? 'text' : 'password';
  btn.innerHTML = show
    ? `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16" aria-hidden="true"><path d="M3 3l14 14"/><path d="M10.584 10.587a2 2 0 01-2.828-2.83"/><path d="M9.363 5.365A7.96 7.96 0 0110 5.25c4.418 0 8 4.75 8 4.75a13.93 13.93 0 01-2.29 2.79M6.228 6.228A10.45 10.45 0 002 10s3.582 4.75 8 4.75c1.33 0 2.6-.32 3.72-.88"/></svg>`
    : `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16" aria-hidden="true"><path d="M2 10s3.582-4.75 8-4.75S18 10 18 10s-3.582 4.75-8 4.75S2 10 2 10z"/><circle cx="10" cy="10" r="2.25"/></svg>`;
}

function closePwModal() {
  const overlay = document.getElementById('pw-change-overlay');
  if (overlay) overlay.classList.remove('open');
}

// Close on backdrop click
document.getElementById('pw-change-overlay').addEventListener('click', function(e) {
  if (e.target === this) closePwModal();
});

async function submitChangePassword() {
  const current = document.getElementById('pw-current');
  const newPw   = document.getElementById('pw-new');
  const confirm = document.getElementById('pw-confirm');
  const msg     = document.getElementById('pw-modal-msg');
  if (!current || !newPw || !confirm || !msg) return;

  msg.textContent = '';
  msg.className = 'pw-modal-msg';

  const res = await apiFetch('/api/account/password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      current_password: current.value,
      new_password:     newPw.value,
      confirm_password: confirm.value,
    }),
  });
  if (!res) return; // redirected to login by apiFetch

  const data = await res.json();
  if (res.ok) {
    msg.classList.add('pw-modal-msg-ok');
    msg.textContent = 'Password updated successfully.';
    current.value = ''; newPw.value = ''; confirm.value = '';
    setTimeout(closePwModal, 1400);
  } else {
    msg.classList.add('pw-modal-msg-err');
    msg.textContent = data.error || 'Something went wrong.';
  }
}
