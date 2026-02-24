/* ========================================
   Global Stocks AI — Frontend Application
   ======================================== */

const API_BASE = '';
let currentTicker = null;
let refreshInterval = null;

// Chart variables
let chart = null;
let candleSeries = null;
let currentRange = '1mo';

// --- Initialize ---
document.addEventListener('DOMContentLoaded', () => {
    initParticles();
    initSearch();
    initSettings();
    initChat();
    initFilters();
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
            if (res.ok) {
                status.textContent = '✅ API key saved! AI features enabled.';
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

// --- Historical Chart ---
function initChart() {
    const chartContainer = document.getElementById('priceChart');
    if (!chartContainer) return;

    // Clear previous chart if any
    chartContainer.innerHTML = '';

    chart = LightweightCharts.createChart(chartContainer, {
        layout: {
            background: { color: 'transparent' },
            textColor: '#8b949e',
            fontSize: 12,
        },
        grid: {
            vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
            horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
        },
        rightPriceScale: {
            borderColor: 'rgba(255, 255, 255, 0.1)',
            autoScale: true,
        },
        timeScale: {
            borderColor: 'rgba(255, 255, 255, 0.1)',
            timeVisible: true,
            secondsVisible: false,
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#06d6a0',
        downColor: '#f85149',
        borderVisible: false,
        wickUpColor: '#06d6a0',
        wickDownColor: '#f85149',
    });

    window.addEventListener('resize', () => {
        chart.resize(chartContainer.clientWidth, 400);
    });
}

async function loadHistoryData(ticker, range) {
    try {
        const res = await fetch(`${API_BASE}/api/history/${ticker}?range=${range}`);
        const data = await res.json();
        if (data.history && data.history.length > 0) {
            candleSeries.setData(data.history);
            chart.timeScale().fitContent();
        }
    } catch (err) {
        console.error('History fetch error:', err);
    }
}

function initFilters() {
    const filters = document.getElementById('chartFilters');
    if (!filters) return;

    filters.addEventListener('click', (e) => {
        if (e.target.classList.contains('filter-btn')) {
            const range = e.target.getAttribute('data-range');
            currentRange = range;

            // Update UI
            filters.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            e.target.classList.add('active');

            if (currentTicker) {
                loadHistoryData(currentTicker, range);
            }
        }
    });
}

// --- AI Chatbot ---
function initChat() {
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendChatBtn');
    const suggestions = document.querySelectorAll('.suggestion-btn');

    const handleSend = async (message) => {
        if (!message || !currentTicker) return;

        appendMessage('user', message);
        chatInput.value = '';

        try {
            const res = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker: currentTicker, message: message }),
            });
            const data = await res.json();
            appendMessage('bot', data.response);
        } catch (err) {
            appendMessage('bot', 'Sorry, I encountered an error. Please check your connection or API key.');
        }
    };

    sendBtn.addEventListener('click', () => handleSend(chatInput.value.trim()));
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleSend(chatInput.value.trim());
    });

    suggestions.forEach(btn => {
        btn.addEventListener('click', () => handleSend(btn.innerText));
    });
}

function appendMessage(role, text) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.classList.add('message', `${role}-message`);
    div.innerText = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// --- Search ---
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

    document.addEventListener('click', (e) => {
        if (!e.target.closest('#searchContainer')) dropdown.classList.remove('active');
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
    }
}

function selectStock(ticker) {
    document.getElementById('searchDropdown').classList.remove('active');
    document.getElementById('searchInput').value = ticker;
    loadStockAnalysis(ticker);
}

// --- Load Analysis ---
async function loadStockAnalysis(ticker) {
    currentTicker = ticker;
    showLoading(true);

    try {
        const [stockRes, analysisRes] = await Promise.all([
            fetch(`${API_BASE}/api/stock/${ticker}`),
            fetch(`${API_BASE}/api/analyze/${ticker}`)
        ]);

        if (!stockRes.ok || !analysisRes.ok) throw new Error('Data unavailable for this ticker.');

        const stockData = await stockRes.json();
        const analysisData = await analysisRes.json();

        // Clear chat
        document.getElementById('chatMessages').innerHTML = '<div class="message bot-message">Hello! I\'m your info assistant for ' + ticker + '. Ask me anything!</div>';

        renderStockOverview(stockData.info);
        renderIndicators(analysisData.analysis.indicators);
        renderAnalysis(analysisData.analysis);

        // Chart
        if (!chart) initChart();
        loadHistoryData(ticker, currentRange);

        document.getElementById('mainContent').style.display = 'block';
        showLoading(false);
        document.getElementById('mainContent').scrollIntoView({ behavior: 'smooth', block: 'start' });

        if (refreshInterval) clearInterval(refreshInterval);
        refreshInterval = setInterval(() => refreshMinuteData(ticker), 60000);
    } catch (err) {
        showLoading(false);
        alert('Error: ' + err.message);
    }
}

async function refreshMinuteData(ticker) {
    try {
        const res = await fetch(`${API_BASE}/api/stock/${ticker}`);
        if (res.ok) {
            const data = await res.json();
            renderStockOverview(data.info);
        }
    } catch (err) { }
}

// --- Renderers ---
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
    document.getElementById('overviewGrid').innerHTML = stats.map(s => `<div class="overview-stat"><div class="label">${s.label}</div><div class="value">${s.value}</div></div>`).join('');
}

function renderIndicators(indicators) {
    if (!indicators) return;
    const cards = [
        { label: 'RSI (14)', value: indicators.rsi, signal: rsiSignal(indicators.rsi) },
        { label: 'MACD', value: indicators.macd, signal: macdSignal(indicators.macd, indicators.macd_signal) },
        { label: 'MACD Hist', value: indicators.macd_histogram, signal: indicators.macd_histogram > 0 ? 'bullish' : 'bearish' },
        { label: 'SMA 20', value: indicators.sma_20, signal: priceVsSma(indicators.current_price, indicators.sma_20) },
        { label: 'SMA 50', value: indicators.sma_50, signal: priceVsSma(indicators.current_price, indicators.sma_50) },
        { label: 'EMA 12', value: indicators.ema_12, signal: null },
        { label: 'EMA 26', value: indicators.ema_26, signal: null },
        { label: 'ADX', value: indicators.adx, signal: adxSignal(indicators.adx) },
        { label: 'ATR', value: indicators.atr, signal: null },
        { label: 'Stoch %K', value: indicators.stoch_k, signal: stochSignal(indicators.stoch_k) },
        { label: 'BB Width', value: indicators.bb_width, signal: null },
        { label: '5D Return', value: indicators.return_5d + '%', signal: indicators.return_5d > 0 ? 'bullish' : 'bearish', raw: true },
        { label: '20D Return', value: indicators.return_20d + '%', signal: indicators.return_20d > 0 ? 'bullish' : 'bearish', raw: true },
        { label: 'Pct High', value: indicators.pct_from_high + '%', signal: null, raw: true },
    ];

    const generateHtml = (c) => {
        const val = c.raw ? c.value : (c.value != null ? parseFloat(c.value).toFixed(2) : 'N/A');
        const sig = c.signal ? `<span class="ind-signal ${c.signal}">${c.signal}</span>` : '';
        return `<div class="indicator-card"><div class="ind-label">${c.label}</div><div class="ind-value">${val}</div>${sig}</div>`;
    };

    // Split indicators 50/50
    const half = Math.ceil(cards.length / 2);
    document.getElementById('leftIndicators').innerHTML = cards.slice(0, half).map(generateHtml).join('');
    document.getElementById('rightIndicators').innerHTML = cards.slice(half).map(generateHtml).join('');
}

function rsiSignal(r) { r = parseFloat(r); if (r < 30) return 'bullish'; if (r > 70) return 'bearish'; return 'neutral'; }
function macdSignal(m, s) { return parseFloat(m) > parseFloat(s) ? 'bullish' : 'bearish'; }
function priceVsSma(p, s) { return parseFloat(p) > parseFloat(s) ? 'bullish' : 'bearish'; }
function adxSignal(a) { return parseFloat(a) > 25 ? 'bullish' : 'neutral'; }
function stochSignal(k) { k = parseFloat(k); if (k < 20) return 'bullish'; if (k > 80) return 'bearish'; return 'neutral'; }

function renderAnalysis(analysis) {
    const pros = document.getElementById('reasonsToInvest');
    const cons = document.getElementById('reasonsNotToInvest');
    document.getElementById('aiBadge').style.display = analysis.ai_powered ? 'inline-block' : 'none';
    const mapFn = (r, i) => `<div class="reason-card"><div class="reason-header"><span class="reason-number">${i + 1}</span><span class="reason-title">${r.title}</span></div><p class="reason-detail">${r.detail}</p></div>`;
    pros.innerHTML = analysis.reasons_to_invest.map(mapFn).join('');
    cons.innerHTML = analysis.reasons_not_to_invest.map(mapFn).join('');
}

function showLoading(show) { document.getElementById('loadingOverlay').style.display = show ? 'flex' : 'none'; }
function formatNum(n) { return n != null ? parseFloat(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'N/A'; }
function formatCurrency(n, c) { try { return new Intl.NumberFormat('en-US', { style: 'currency', currency: c }).format(n); } catch { return '$' + parseFloat(n).toFixed(2); } }
function formatLargeNum(n) { if (!n) return 'N/A'; if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B'; if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M'; return n.toLocaleString(); }
function formatMarketCap(n) { if (!n) return 'N/A'; if (n >= 1e12) return '$' + (n / 1e12).toFixed(2) + 'T'; if (n >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B'; return '$' + n.toLocaleString(); }
