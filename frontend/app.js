/* ========================================
   Global Stocks AI — Frontend Application
   ======================================== */

const API_BASE = '';
let currentTicker = null;
let refreshInterval = null;

// --- Initialize ---
document.addEventListener('DOMContentLoaded', () => {
    initParticles();
    initSearch();
    initSettings();
});

// --- Animated Background Particles ---
function initParticles() {
    const container = document.getElementById('particles');
    const colors = ['rgba(6,214,160,0.3)', 'rgba(124,58,237,0.3)', 'rgba(34,211,238,0.2)'];
    for (let i = 0; i < 30; i++) {
        const particle = document.createElement('div');
        particle.classList.add('particle');
        const size = Math.random() * 4 + 2;
        particle.style.width = size + 'px';
        particle.style.height = size + 'px';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.background = colors[Math.floor(Math.random() * colors.length)];
        particle.style.animationDuration = (Math.random() * 20 + 15) + 's';
        particle.style.animationDelay = (Math.random() * 20) + 's';
        container.appendChild(particle);
    }
}

// --- Settings Modal ---
function initSettings() {
    const settingsBtn = document.getElementById('settingsBtn');
    const modal = document.getElementById('settingsModal');
    const closeBtn = document.getElementById('modalClose');
    const saveBtn = document.getElementById('saveKeyBtn');

    settingsBtn.addEventListener('click', () => {
        modal.style.display = 'flex';
        document.getElementById('modalStatus').textContent = '';
        document.getElementById('modalStatus').className = 'modal-status';
    });

    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.style.display = 'none';
    });

    saveBtn.addEventListener('click', async () => {
        const key = document.getElementById('apiKeyInput').value.trim();
        const status = document.getElementById('modalStatus');

        if (!key) {
            status.textContent = 'Please enter an API key.';
            status.className = 'modal-status error';
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/api/set-key`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: key }),
            });
            const data = await res.json();

            if (res.ok) {
                status.textContent = '✅ API key saved! AI analysis is now enabled.';
                status.className = 'modal-status success';
                setTimeout(() => { modal.style.display = 'none'; }, 1500);
            } else {
                status.textContent = '❌ Failed to save key.';
                status.className = 'modal-status error';
            }
        } catch (err) {
            status.textContent = '❌ Connection error.';
            status.className = 'modal-status error';
        }
    });
}

// --- Search with Debounced Autocomplete ---
function initSearch() {
    const input = document.getElementById('searchInput');
    const dropdown = document.getElementById('searchDropdown');
    const spinner = document.getElementById('searchSpinner');
    let debounceTimer = null;

    input.addEventListener('input', () => {
        const query = input.value.trim();
        clearTimeout(debounceTimer);

        if (query.length < 1) {
            dropdown.classList.remove('active');
            spinner.classList.remove('active');
            return;
        }

        spinner.classList.add('active');
        debounceTimer = setTimeout(() => searchTickers(query), 400);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const query = input.value.trim();
            if (query.length > 0) {
                dropdown.classList.remove('active');
                loadStockAnalysis(query.toUpperCase());
            }
        }
    });

    // Close dropdown on click outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#searchContainer')) {
            dropdown.classList.remove('active');
        }
    });
}

async function searchTickers(query) {
    const dropdown = document.getElementById('searchDropdown');
    const spinner = document.getElementById('searchSpinner');

    try {
        const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}`);
        const data = await res.json();

        spinner.classList.remove('active');

        if (data.results && data.results.length > 0) {
            dropdown.innerHTML = data.results.map(item => `
                <div class="search-item" onclick="selectStock('${item.symbol}')">
                    <div class="search-item-left">
                        <span class="search-item-symbol">${item.symbol}</span>
                        <span class="search-item-name">${item.shortName || item.symbol}</span>
                    </div>
                    <span class="search-item-exchange">${item.exchange || ''}</span>
                </div>
            `).join('');
            dropdown.classList.add('active');
        } else {
            dropdown.innerHTML = '<div class="search-item"><span class="search-item-name" style="color:var(--text-muted)">No results found</span></div>';
            dropdown.classList.add('active');
        }
    } catch (err) {
        spinner.classList.remove('active');
        console.error('Search error:', err);
    }
}

function selectStock(ticker) {
    document.getElementById('searchDropdown').classList.remove('active');
    document.getElementById('searchInput').value = ticker;
    loadStockAnalysis(ticker);
}

// --- Load Full Stock Analysis ---
async function loadStockAnalysis(ticker) {
    currentTicker = ticker;
    showLoading(true);

    try {
        // Fetch stock data and analysis in parallel
        const [stockRes, analysisRes] = await Promise.all([
            fetch(`${API_BASE}/api/stock/${ticker}`),
            fetch(`${API_BASE}/api/analyze/${ticker}`)
        ]);

        if (!stockRes.ok || !analysisRes.ok) {
            throw new Error('Failed to fetch data. Please check the ticker symbol.');
        }

        const stockData = await stockRes.json();
        const analysisData = await analysisRes.json();

        renderStockOverview(stockData.info);
        renderIndicators(analysisData.analysis.indicators);
        renderAnalysis(analysisData.analysis);

        document.getElementById('mainContent').style.display = 'block';
        showLoading(false);

        // Scroll to results
        document.getElementById('mainContent').scrollIntoView({ behavior: 'smooth', block: 'start' });

        // Set up auto-refresh every 60 seconds
        if (refreshInterval) clearInterval(refreshInterval);
        refreshInterval = setInterval(() => refreshMinuteData(ticker), 60000);

    } catch (err) {
        showLoading(false);
        alert('Error: ' + err.message);
        console.error(err);
    }
}

async function refreshMinuteData(ticker) {
    try {
        const res = await fetch(`${API_BASE}/api/stock/${ticker}`);
        if (res.ok) {
            const data = await res.json();
            renderStockOverview(data.info);
        }
    } catch (err) {
        console.error('Refresh error:', err);
    }
}

// --- Render Stock Overview ---
function renderStockOverview(info) {
    document.getElementById('stockName').textContent = info.longName || info.shortName || info.symbol;
    document.getElementById('stockTicker').textContent = info.symbol;
    document.getElementById('stockExchange').textContent = info.sector || '';

    const price = info.currentPrice || 0;
    const prevClose = info.previousClose || 0;
    const change = price - prevClose;
    const changePct = prevClose ? ((change / prevClose) * 100) : 0;

    const currency = info.currency || 'USD';
    document.getElementById('currentPrice').textContent = `${formatCurrency(price, currency)}`;

    const changeEl = document.getElementById('priceChange');
    const sign = change >= 0 ? '+' : '';
    changeEl.textContent = `${sign}${change.toFixed(2)} (${sign}${changePct.toFixed(2)}%)`;
    changeEl.className = `price-change ${change >= 0 ? 'positive' : 'negative'}`;

    // Overview grid stats
    const stats = [
        { label: 'Open', value: formatNum(info.open) },
        { label: 'Day Low', value: formatNum(info.dayLow) },
        { label: 'Day High', value: formatNum(info.dayHigh) },
        { label: 'Volume', value: formatLargeNum(info.volume) },
        { label: 'Avg Volume', value: formatLargeNum(info.averageVolume) },
        { label: '52W Low', value: formatNum(info.fiftyTwoWeekLow) },
        { label: '52W High', value: formatNum(info.fiftyTwoWeekHigh) },
        { label: 'Market Cap', value: formatMarketCap(info.marketCap) },
        { label: 'P/E Ratio', value: info.trailingPE ? info.trailingPE.toFixed(2) : 'N/A' },
        { label: 'Beta', value: info.beta ? info.beta.toFixed(2) : 'N/A' },
        { label: 'Div Yield', value: info.dividendYield ? (info.dividendYield * 100).toFixed(2) + '%' : 'N/A' },
        { label: '50D Avg', value: formatNum(info.fiftyDayAverage) },
    ];

    document.getElementById('overviewGrid').innerHTML = stats.map(s => `
        <div class="overview-stat">
            <div class="label">${s.label}</div>
            <div class="value">${s.value}</div>
        </div>
    `).join('');
}

// --- Render Technical Indicators ---
function renderIndicators(indicators) {
    if (!indicators) return;

    const cards = [
        { label: 'RSI (14)', value: indicators.rsi, signal: rsiSignal(indicators.rsi) },
        { label: 'MACD', value: indicators.macd, signal: macdSignal(indicators.macd, indicators.macd_signal) },
        { label: 'MACD Signal', value: indicators.macd_signal, signal: null },
        { label: 'MACD Histogram', value: indicators.macd_histogram, signal: indicators.macd_histogram > 0 ? 'bullish' : 'bearish' },
        { label: 'SMA 20', value: indicators.sma_20, signal: priceVsSma(indicators.current_price, indicators.sma_20) },
        { label: 'SMA 50', value: indicators.sma_50, signal: priceVsSma(indicators.current_price, indicators.sma_50) },
        { label: 'EMA 12', value: indicators.ema_12, signal: null },
        { label: 'EMA 26', value: indicators.ema_26, signal: null },
        { label: 'Bollinger Upper', value: indicators.bb_upper, signal: null },
        { label: 'Bollinger Lower', value: indicators.bb_lower, signal: null },
        { label: 'ADX', value: indicators.adx, signal: adxSignal(indicators.adx) },
        { label: 'ATR', value: indicators.atr, signal: null },
        { label: 'Stochastic %K', value: indicators.stoch_k, signal: stochSignal(indicators.stoch_k) },
        { label: 'Stochastic %D', value: indicators.stoch_d, signal: null },
        { label: '5-Day Return', value: indicators.return_5d != null ? indicators.return_5d + '%' : 'N/A', signal: indicators.return_5d > 0 ? 'bullish' : indicators.return_5d < 0 ? 'bearish' : 'neutral', raw: true },
        { label: '20-Day Return', value: indicators.return_20d != null ? indicators.return_20d + '%' : 'N/A', signal: indicators.return_20d > 0 ? 'bullish' : indicators.return_20d < 0 ? 'bearish' : 'neutral', raw: true },
    ];

    document.getElementById('indicatorsGrid').innerHTML = cards.map(c => {
        const displayVal = c.raw ? c.value : (c.value != null && c.value !== 'N/A' ? parseFloat(c.value).toFixed(2) : 'N/A');
        const signalHtml = c.signal ? `<span class="ind-signal ${c.signal}">${c.signal}</span>` : '';
        return `
            <div class="indicator-card">
                <div class="ind-label">${c.label}</div>
                <div class="ind-value">${displayVal}</div>
                ${signalHtml}
            </div>
        `;
    }).join('');
}

function rsiSignal(rsi) {
    if (rsi == null || rsi === 'N/A') return 'neutral';
    rsi = parseFloat(rsi);
    if (rsi < 30) return 'bullish';
    if (rsi > 70) return 'bearish';
    return 'neutral';
}

function macdSignal(macd, signal) {
    if (macd == null || signal == null) return 'neutral';
    return parseFloat(macd) > parseFloat(signal) ? 'bullish' : 'bearish';
}

function priceVsSma(price, sma) {
    if (price == null || sma == null) return 'neutral';
    return parseFloat(price) > parseFloat(sma) ? 'bullish' : 'bearish';
}

function adxSignal(adx) {
    if (adx == null) return 'neutral';
    return parseFloat(adx) > 25 ? 'bullish' : 'neutral';
}

function stochSignal(k) {
    if (k == null) return 'neutral';
    k = parseFloat(k);
    if (k < 20) return 'bullish';
    if (k > 80) return 'bearish';
    return 'neutral';
}

// --- Render AI Analysis ---
function renderAnalysis(analysis) {
    const prosContainer = document.getElementById('reasonsToInvest');
    const consContainer = document.getElementById('reasonsNotToInvest');

    // Show/hide AI badge
    const aiBadge = document.getElementById('aiBadge');
    if (analysis.ai_powered) {
        aiBadge.style.display = 'inline-block';
    } else {
        aiBadge.style.display = 'none';
    }

    prosContainer.innerHTML = analysis.reasons_to_invest.map((r, i) => `
        <div class="reason-card">
            <div class="reason-header">
                <span class="reason-number">${i + 1}</span>
                <span class="reason-title">${r.title}</span>
            </div>
            <p class="reason-detail">${r.detail}</p>
        </div>
    `).join('');

    consContainer.innerHTML = analysis.reasons_not_to_invest.map((r, i) => `
        <div class="reason-card">
            <div class="reason-header">
                <span class="reason-number">${i + 1}</span>
                <span class="reason-title">${r.title}</span>
            </div>
            <p class="reason-detail">${r.detail}</p>
        </div>
    `).join('');
}

// --- Loading Overlay ---
function showLoading(show) {
    document.getElementById('loadingOverlay').style.display = show ? 'flex' : 'none';
}

// --- Formatting Helpers ---
function formatNum(n) {
    if (!n && n !== 0) return 'N/A';
    return parseFloat(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCurrency(n, currency) {
    if (!n && n !== 0) return 'N/A';
    try {
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency }).format(n);
    } catch {
        return '$' + parseFloat(n).toFixed(2);
    }
}

function formatLargeNum(n) {
    if (!n) return 'N/A';
    if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n.toLocaleString();
}

function formatMarketCap(n) {
    if (!n) return 'N/A';
    if (n >= 1e12) return '$' + (n / 1e12).toFixed(2) + 'T';
    if (n >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
    if (n >= 1e6) return '$' + (n / 1e6).toFixed(0) + 'M';
    return '$' + n.toLocaleString();
}
