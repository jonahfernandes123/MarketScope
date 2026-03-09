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
  closeDrawer();
}

/* ── Price card state ──────────────────────────────────────────────────────── */
let instruments = [];

function renderCards(data) {
  instruments = data;
  const grid = document.getElementById('grid');

  if (grid.children.length === 0) {
    data.forEach(inst => {
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
      grid.appendChild(card);
    });
  }

  data.forEach(inst => {
    const pEl = document.getElementById('p-' + inst.key);
    const cEl = document.getElementById('c-' + inst.key);
    if (!pEl) return;

    if (!inst.price && inst.error) {
      pEl.className = 'card-price err';
      pEl.textContent = 'Unavailable';
      cEl.innerHTML = '<span class="neu" style="font-size:0.6rem">' + esc(inst.error.substring(0, 45)) + '</span>';
      return;
    }
    pEl.className = 'card-price';
    pEl.textContent = fmtPrice(inst);

    const chg = calcChg(inst);
    if (chg === null) {
      cEl.innerHTML = '<span class="neu">\u2014</span>';
    } else if (chg > 0) {
      cEl.innerHTML = '<span class="up">\u25b2</span><span class="up">+' + chg.toFixed(2) + '%</span>';
    } else {
      cEl.innerHTML = '<span class="down">\u25bc</span><span class="down">' + chg.toFixed(2) + '%</span>';
    }
  });

  if (_moversData) {
    _moversData = [...data].sort((a, b) => {
      const pa = a.price != null && a.prev_price ? Math.abs((a.price - a.prev_price) / a.prev_price) : -1;
      const pb = b.price != null && b.prev_price ? Math.abs((b.price - b.prev_price) / b.prev_price) : -1;
      return pb - pa;
    });
    renderMoversPreview();
  }
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

async function loadBriefingData() {
  const priceRes = await fetch('/api/prices').then(r => r.json()).catch(() => []);
  _moversData = [...priceRes].sort((a, b) => {
    const pa = a.price != null && a.prev_price ? Math.abs((a.price - a.prev_price) / a.prev_price) : -1;
    const pb = b.price != null && b.prev_price ? Math.abs((b.price - b.prev_price) / b.prev_price) : -1;
    return pb - pa;
  });
  renderMoversPreview();

  const [news, drivers] = await Promise.all([
    fetch('/api/home/news').then(r => r.json()).catch(() => []),
    fetch('/api/home/drivers').then(r => r.json()).catch(() => []),
  ]);
  _newsData    = news;
  _driversData = drivers;
  renderNewsPreview();
  renderDriversPreview();
}
loadBriefingData();

/* ── Briefing card preview renderers ──────────────────────────────────────── */
function renderMoversPreview() {
  const el = document.getElementById('preview-movers');
  if (!el || !_moversData) return;
  const top = _moversData.filter(r => r.price != null).slice(0, 3);
  if (!top.length) { el.innerHTML = '<span style="color:var(--dim)">No data yet</span>'; return; }
  el.innerHTML = '<div>' + top.map(r => {
    const pct = r.price != null && r.prev_price ? (r.price - r.prev_price) / r.prev_price * 100 : null;
    const { html } = fmtPct(pct);
    return `<div class="mover-row">
      <span class="mover-name">${esc(r.label)}</span>
      <span class="mover-pct">${html}</span>
    </div>`;
  }).join('') + '</div>';
}

function renderNewsPreview() {
  const el = document.getElementById('preview-news');
  const top = (_newsData || []).slice(0, 3);
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
    const pct = r.price != null && r.prev_price ? (r.price - r.prev_price) / r.prev_price * 100 : null;
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
  return '<ul class="news-list">' + _newsData.map(a => `
    <li>
      <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a>
      <div class="news-meta">
        ${esc(a.instrument || '')}
        ${a.publisher ? ' &middot; ' + esc(a.publisher) : ''}
        ${a.published ? ' &middot; ' + esc(a.published) : ''}
      </div>
    </li>`).join('') + '</ul>';
}

function buildDriversModal() {
  if (!_driversData || !_driversData.length) return '<p style="color:var(--muted)">No headlines available.</p>';
  return '<ul class="news-list">' + _driversData.map(d => `
    <li>
      <a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.title)}</a>
      <div class="news-meta">
        ${esc(d.source || '')}${d.published ? ' &middot; ' + esc(d.published) : ''}
      </div>
    </li>`).join('') + '</ul>';
}

/* ── Commodity detail modal ────────────────────────────────────────────────── */
let chart        = null;
let currentKey   = null;
let currentRange = '1mo';

async function openCommodityModal(key) {
  const inst = instruments.find(i => i.key === key);
  if (!inst) return;
  currentKey   = key;
  currentRange = '1mo';

  document.getElementById('modal').style.setProperty('--modal-accent', inst.accent);
  document.getElementById('modal').style.borderTopColor = inst.accent;
  document.getElementById('m-icon').innerHTML    = inst.icon;
  document.getElementById('m-name').textContent  = inst.label;
  document.getElementById('m-price').textContent = fmtPrice(inst);

  const chg = calcChg(inst);
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
    btn.classList.toggle('active', btn.dataset.range === '1mo');
  });
  resetChart();
  document.getElementById('articles-area').innerHTML =
    '<div class="placeholder"><span class="spin"></span>Loading articles\u2026</div>';
  document.getElementById('summary-area').innerHTML =
    '<div class="placeholder"><span class="spin"></span>Loading analysis\u2026</div>';

  document.getElementById('overlay').classList.add('open');
  document.body.style.overflow = 'hidden';

  const [histRes, summRes] = await Promise.all([
    fetch('/api/history/' + key + '?range=1mo'),
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
  if (e.key === 'Escape') { closeBriefingModal(); closeCommodityModal(); }
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
  ph.innerHTML = '<span style="color:var(--red);font-size:0.8rem">Chart data unavailable</span>';
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
