"""
AI Analysis Module — Computes technical indicators, then uses
OpenRouter API (nvidia/nemotron-3-nano-30b-a3b:free) to generate
10 reasons to invest and 10 reasons NOT to invest.
Falls back to rule-based analysis if the API call fails.
"""

import os
import json
import requests
import pandas as pd
import numpy as np
import ta


OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"


def compute_indicators(daily_df: pd.DataFrame) -> dict:
    """Compute technical indicators on daily OHLCV data."""
    if daily_df.empty or len(daily_df) < 5:
        return {}

    close = daily_df["Close"]
    high = daily_df["High"]
    low = daily_df["Low"]
    volume = daily_df["Volume"]

    indicators = {}

    # --- Trend Indicators ---
    indicators["sma_20"] = ta.trend.sma_indicator(close, window=20).iloc[-1] if len(close) >= 20 else None
    indicators["sma_50"] = ta.trend.sma_indicator(close, window=50).iloc[-1] if len(close) >= 50 else None
    indicators["sma_200"] = ta.trend.sma_indicator(close, window=200).iloc[-1] if len(close) >= 200 else None
    indicators["ema_12"] = ta.trend.ema_indicator(close, window=12).iloc[-1] if len(close) >= 12 else None
    indicators["ema_26"] = ta.trend.ema_indicator(close, window=26).iloc[-1] if len(close) >= 26 else None

    # MACD
    if len(close) >= 26:
        macd_obj = ta.trend.MACD(close)
        indicators["macd"] = macd_obj.macd().iloc[-1]
        indicators["macd_signal"] = macd_obj.macd_signal().iloc[-1]
        indicators["macd_histogram"] = macd_obj.macd_diff().iloc[-1]
    else:
        indicators["macd"] = indicators["macd_signal"] = indicators["macd_histogram"] = None

    # ADX
    if len(close) >= 14:
        indicators["adx"] = ta.trend.adx(high, low, close, window=14).iloc[-1]
    else:
        indicators["adx"] = None

    # --- Momentum Indicators ---
    if len(close) >= 14:
        indicators["rsi"] = ta.momentum.rsi(close, window=14).iloc[-1]
    else:
        indicators["rsi"] = None

    if len(close) >= 14:
        stoch = ta.momentum.StochasticOscillator(high, low, close)
        indicators["stoch_k"] = stoch.stoch().iloc[-1]
        indicators["stoch_d"] = stoch.stoch_signal().iloc[-1]
    else:
        indicators["stoch_k"] = indicators["stoch_d"] = None

    # --- Volatility Indicators ---
    if len(close) >= 20:
        bb = ta.volatility.BollingerBands(close, window=20)
        indicators["bb_upper"] = bb.bollinger_hband().iloc[-1]
        indicators["bb_middle"] = bb.bollinger_mavg().iloc[-1]
        indicators["bb_lower"] = bb.bollinger_lband().iloc[-1]
        indicators["bb_width"] = (indicators["bb_upper"] - indicators["bb_lower"]) / indicators["bb_middle"] if indicators["bb_middle"] else None
    else:
        indicators["bb_upper"] = indicators["bb_middle"] = indicators["bb_lower"] = indicators["bb_width"] = None

    if len(close) >= 14:
        indicators["atr"] = ta.volatility.average_true_range(high, low, close, window=14).iloc[-1]
    else:
        indicators["atr"] = None

    # --- Volume Indicators ---
    if len(close) >= 20:
        indicators["volume_sma_20"] = volume.rolling(window=20).mean().iloc[-1]
    else:
        indicators["volume_sma_20"] = None
    indicators["current_volume"] = volume.iloc[-1]

    if len(close) >= 20:
        indicators["obv"] = ta.volume.on_balance_volume(close, volume).iloc[-1]
    else:
        indicators["obv"] = None

    # --- Price metrics ---
    indicators["current_price"] = close.iloc[-1]
    indicators["prev_close"] = close.iloc[-2] if len(close) >= 2 else close.iloc[-1]
    indicators["price_change_pct"] = ((indicators["current_price"] - indicators["prev_close"]) / indicators["prev_close"]) * 100

    if len(close) >= 6:
        indicators["return_5d"] = ((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6]) * 100
    else:
        indicators["return_5d"] = None

    if len(close) >= 21:
        indicators["return_20d"] = ((close.iloc[-1] - close.iloc[-21]) / close.iloc[-21]) * 100
    else:
        indicators["return_20d"] = None

    if len(close) >= 50:
        period_high = high.max()
        period_low = low.min()
        indicators["period_high"] = period_high
        indicators["period_low"] = period_low
        indicators["pct_from_high"] = ((close.iloc[-1] - period_high) / period_high) * 100
        indicators["pct_from_low"] = ((close.iloc[-1] - period_low) / period_low) * 100
    else:
        indicators["period_high"] = high.max()
        indicators["period_low"] = low.min()
        indicators["pct_from_high"] = 0
        indicators["pct_from_low"] = 0

    # Clean NaN values and convert numpy types to native Python
    for k, v in indicators.items():
        if v is None:
            continue
        # Convert numpy types to native Python types for JSON serialization
        if isinstance(v, (np.integer,)):
            indicators[k] = int(v)
        elif isinstance(v, (np.floating,)):
            if np.isnan(v) or np.isinf(v):
                indicators[k] = None
            else:
                indicators[k] = float(v)
        elif isinstance(v, (np.bool_,)):
            indicators[k] = bool(v)
        elif isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            indicators[k] = None

    return indicators


def _safe(val, decimals=2):
    """Safely format a numeric value."""
    if val is None:
        return "N/A"
    return round(float(val), decimals)


def _build_ai_prompt(indicators: dict, stock_info: dict) -> str:
    """Build a detailed prompt for the AI model with all indicator data."""
    name = stock_info.get("shortName", stock_info.get("symbol", "the stock"))
    symbol = stock_info.get("symbol", "N/A")
    sector = stock_info.get("sector", "N/A")
    industry = stock_info.get("industry", "N/A")
    market_cap = stock_info.get("marketCap", 0)
    pe = stock_info.get("trailingPE", "N/A")
    div_yield = stock_info.get("dividendYield")
    beta = stock_info.get("beta", "N/A")

    div_str = f"{div_yield * 100:.2f}%" if div_yield else "N/A"
    mcap_str = f"${market_cap / 1e9:.1f}B" if market_cap and market_cap > 0 else "N/A"

    ind = {k: _safe(v, 2) for k, v in indicators.items()}

    prompt = f"""You are an expert stock analyst AI. Analyze the following stock data and provide exactly 10 reasons to invest and exactly 10 reasons NOT to invest.

## Stock: {name} ({symbol})
- Sector: {sector} | Industry: {industry}
- Market Cap: {mcap_str} | P/E Ratio: {pe} | Beta: {beta} | Dividend Yield: {div_str}

## Current Price Data:
- Current Price: ${ind.get('current_price', 'N/A')}
- Previous Close: ${ind.get('prev_close', 'N/A')}
- Daily Change: {ind.get('price_change_pct', 'N/A')}%
- 5-Day Return: {ind.get('return_5d', 'N/A')}%
- 20-Day Return: {ind.get('return_20d', 'N/A')}%
- Distance from Period High: {ind.get('pct_from_high', 'N/A')}%
- Distance from Period Low: {ind.get('pct_from_low', 'N/A')}%

## Technical Indicators:
- RSI (14): {ind.get('rsi', 'N/A')}
- MACD: {ind.get('macd', 'N/A')} | Signal: {ind.get('macd_signal', 'N/A')} | Histogram: {ind.get('macd_histogram', 'N/A')}
- SMA 20: {ind.get('sma_20', 'N/A')} | SMA 50: {ind.get('sma_50', 'N/A')} | SMA 200: {ind.get('sma_200', 'N/A')}
- EMA 12: {ind.get('ema_12', 'N/A')} | EMA 26: {ind.get('ema_26', 'N/A')}
- Bollinger Upper: {ind.get('bb_upper', 'N/A')} | Middle: {ind.get('bb_middle', 'N/A')} | Lower: {ind.get('bb_lower', 'N/A')} | Width: {ind.get('bb_width', 'N/A')}
- ADX: {ind.get('adx', 'N/A')}
- Stochastic %K: {ind.get('stoch_k', 'N/A')} | %D: {ind.get('stoch_d', 'N/A')}
- ATR: {ind.get('atr', 'N/A')}
- Current Volume: {ind.get('current_volume', 'N/A')} | 20-Day Avg Volume: {ind.get('volume_sma_20', 'N/A')}

## Instructions:
Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{{
  "reasons_to_invest": [
    {{"title": "Short title", "detail": "1-2 sentence explanation with specific numbers from the data above"}},
    ... (exactly 10 items)
  ],
  "reasons_not_to_invest": [
    {{"title": "Short title", "detail": "1-2 sentence explanation with specific numbers from the data above"}},
    ... (exactly 10 items)
  ]
}}

Base your analysis on the actual indicator values provided. Reference specific numbers. Be balanced and insightful."""
    return prompt


def _call_openrouter(prompt: str) -> dict | None:
    """Call OpenRouter API and parse the JSON response."""
    if not OPENROUTER_API_KEY:
        print("[AI] No OPENROUTER_API_KEY set — falling back to rule-based analysis.")
        return None

    try:
        response = requests.post(
            url=OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "You are an expert stock market analyst. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 3000,
            },
            timeout=60,
        )

        if response.status_code != 200:
            print(f"[AI] OpenRouter API error {response.status_code}: {response.text[:200]}")
            return None

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Try to parse JSON from the response
        # Sometimes the model wraps it in markdown code blocks
        content = content.strip()
        if content.startswith("```"):
            # Remove markdown code fences
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)

        result = json.loads(content)

        # Validate structure
        if ("reasons_to_invest" in result and "reasons_not_to_invest" in result
                and len(result["reasons_to_invest"]) >= 1
                and len(result["reasons_not_to_invest"]) >= 1):
            return result

        print("[AI] Invalid response structure from model.")
        return None

    except json.JSONDecodeError as e:
        print(f"[AI] Failed to parse model JSON response: {e}")
        return None
    except Exception as e:
        print(f"[AI] OpenRouter call failed: {e}")
        return None


def generate_analysis(indicators: dict, stock_info: dict) -> dict:
    """
    Generate AI analysis: tries OpenRouter API first, falls back to rule-based.
    Always returns exactly 10 reasons to invest and 10 reasons NOT to invest.
    """
    # Try AI-powered analysis
    prompt = _build_ai_prompt(indicators, stock_info)
    ai_result = _call_openrouter(prompt)

    if ai_result:
        pros = ai_result.get("reasons_to_invest", [])[:10]
        cons = ai_result.get("reasons_not_to_invest", [])[:10]

        # Pad if AI returned fewer than 10
        _pad_reasons(pros, cons, indicators, stock_info)

        return {
            "reasons_to_invest": pros[:10],
            "reasons_not_to_invest": cons[:10],
            "indicators": {k: _safe(v, 4) if isinstance(v, float) else v for k, v in indicators.items()},
            "ai_powered": True,
        }

    # Fallback: rule-based analysis
    return _generate_rule_based(indicators, stock_info)


def _generate_rule_based(indicators: dict, stock_info: dict) -> dict:
    """Rule-based fallback analysis when AI API is unavailable."""
    reasons_to_invest = []
    reasons_not_to_invest = []

    price = indicators.get("current_price", 0)

    # 1. RSI
    rsi = indicators.get("rsi")
    if rsi is not None:
        if rsi < 30:
            reasons_to_invest.append({"title": "RSI Indicates Oversold", "detail": f"RSI is at {_safe(rsi)}, below 30, suggesting the stock is oversold and may be due for a price rebound."})
        elif rsi < 50:
            reasons_to_invest.append({"title": "RSI in Moderate Zone", "detail": f"RSI at {_safe(rsi)} is below 50, indicating the stock still has room for upward movement."})
        if rsi > 70:
            reasons_not_to_invest.append({"title": "RSI Signals Overbought", "detail": f"RSI is at {_safe(rsi)}, above 70, indicating the stock may be overbought and could face a pullback."})
        elif rsi > 50:
            reasons_not_to_invest.append({"title": "RSI Approaching Caution Zone", "detail": f"RSI at {_safe(rsi)} is above 50, suggesting momentum risk increases as it approaches overbought territory."})

    # 2. MACD
    macd = indicators.get("macd")
    macd_signal = indicators.get("macd_signal")
    macd_hist = indicators.get("macd_histogram")
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            reasons_to_invest.append({"title": "MACD Bullish Crossover", "detail": f"MACD ({_safe(macd)}) is above the signal line ({_safe(macd_signal)}), indicating bullish momentum."})
        else:
            reasons_not_to_invest.append({"title": "MACD Bearish Signal", "detail": f"MACD ({_safe(macd)}) is below the signal line ({_safe(macd_signal)}), suggesting bearish momentum."})
        if macd_hist is not None and macd_hist > 0:
            reasons_to_invest.append({"title": "Positive MACD Histogram", "detail": f"MACD histogram is positive ({_safe(macd_hist)}), showing increasing bullish momentum."})
        elif macd_hist is not None:
            reasons_not_to_invest.append({"title": "Negative MACD Histogram", "detail": f"MACD histogram is negative ({_safe(macd_hist)}), indicating weakening momentum."})

    # 3. SMA
    sma_20 = indicators.get("sma_20")
    sma_50 = indicators.get("sma_50")
    if sma_20 is not None and price:
        if price > sma_20:
            reasons_to_invest.append({"title": "Trading Above 20-Day SMA", "detail": f"Stock at ${_safe(price)} is above its 20-day SMA (${_safe(sma_20)}), confirming a short-term uptrend."})
        else:
            reasons_not_to_invest.append({"title": "Below 20-Day SMA", "detail": f"Stock at ${_safe(price)} is below its 20-day SMA (${_safe(sma_20)}), signaling short-term weakness."})
    if sma_50 is not None and price:
        if price > sma_50:
            reasons_to_invest.append({"title": "Above 50-Day Moving Average", "detail": f"Price is above the 50-day SMA (${_safe(sma_50)}), indicating healthy medium-term trend."})
        else:
            reasons_not_to_invest.append({"title": "Below 50-Day Moving Average", "detail": f"Stock is below its 50-day SMA (${_safe(sma_50)}), indicating a medium-term downtrend."})

    # 4. Golden/Death Cross
    if sma_20 is not None and sma_50 is not None:
        if sma_20 > sma_50:
            reasons_to_invest.append({"title": "Golden Cross Pattern", "detail": f"20-day SMA (${_safe(sma_20)}) is above 50-day SMA (${_safe(sma_50)}) — a classic bullish signal."})
        else:
            reasons_not_to_invest.append({"title": "Death Cross Warning", "detail": f"20-day SMA (${_safe(sma_20)}) has crossed below 50-day SMA (${_safe(sma_50)}) — a bearish signal."})

    # 5. Bollinger Bands
    bb_upper = indicators.get("bb_upper")
    bb_lower = indicators.get("bb_lower")
    if bb_lower is not None and bb_upper is not None and price:
        if price <= bb_lower * 1.02:
            reasons_to_invest.append({"title": "Near Lower Bollinger Band", "detail": f"Price near lower band (${_safe(bb_lower)}), stock may be undervalued."})
        if price >= bb_upper * 0.98:
            reasons_not_to_invest.append({"title": "At Upper Bollinger Band", "detail": f"Price near upper band (${_safe(bb_upper)}), stock may be overextended."})

    # 6. Volume
    vol_sma = indicators.get("volume_sma_20")
    cur_vol = indicators.get("current_volume")
    if vol_sma is not None and cur_vol is not None and vol_sma > 0:
        vol_ratio = cur_vol / vol_sma
        if vol_ratio > 1.5:
            reasons_to_invest.append({"title": "Elevated Trading Volume", "detail": f"Volume ({cur_vol:,.0f}) is {_safe(vol_ratio)}x the 20-day average, indicating strong interest."})
        elif vol_ratio < 0.5:
            reasons_not_to_invest.append({"title": "Low Volume", "detail": f"Volume is only {_safe(vol_ratio)}x of average, suggesting lack of conviction."})

    # 7. ADX
    adx = indicators.get("adx")
    if adx is not None:
        if adx > 25:
            reasons_to_invest.append({"title": "Strong Trend (ADX)", "detail": f"ADX at {_safe(adx)} confirms a strong trending move."})
        else:
            reasons_not_to_invest.append({"title": "Weak Trend Strength", "detail": f"ADX at {_safe(adx)} indicates no clear directional trend."})

    # 8. Stochastic
    stoch_k = indicators.get("stoch_k")
    if stoch_k is not None:
        if stoch_k < 20:
            reasons_to_invest.append({"title": "Stochastic Oversold", "detail": f"Stochastic %K at {_safe(stoch_k)}, deep in oversold territory."})
        if stoch_k > 80:
            reasons_not_to_invest.append({"title": "Stochastic Overbought", "detail": f"Stochastic %K at {_safe(stoch_k)}, in overbought territory."})

    # 9. Returns
    ret_5d = indicators.get("return_5d")
    if ret_5d is not None:
        if ret_5d > 3:
            reasons_to_invest.append({"title": "Strong 5-Day Momentum", "detail": f"Stock gained {_safe(ret_5d)}% over 5 days, solid short-term momentum."})
        elif ret_5d < -3:
            reasons_not_to_invest.append({"title": "Weak 5-Day Performance", "detail": f"Stock declined {_safe(abs(ret_5d))}% over 5 days."})

    ret_20d = indicators.get("return_20d")
    if ret_20d is not None:
        if ret_20d > 10:
            reasons_to_invest.append({"title": "Impressive Monthly Returns", "detail": f"{_safe(ret_20d)}% gain over 20 trading days."})
        elif ret_20d < -10:
            reasons_not_to_invest.append({"title": "Poor Monthly Performance", "detail": f"{_safe(abs(ret_20d))}% decline over 20 days."})

    # 10. EMA
    ema_12 = indicators.get("ema_12")
    ema_26 = indicators.get("ema_26")
    if ema_12 is not None and ema_26 is not None:
        if ema_12 > ema_26:
            reasons_to_invest.append({"title": "EMA Bullish Alignment", "detail": f"12-day EMA (${_safe(ema_12)}) above 26-day EMA (${_safe(ema_26)})."})
        else:
            reasons_not_to_invest.append({"title": "EMA Bearish Alignment", "detail": f"12-day EMA (${_safe(ema_12)}) below 26-day EMA (${_safe(ema_26)})."})

    # Fundamentals
    pe = stock_info.get("trailingPE")
    if pe and pe > 0:
        if pe < 20:
            reasons_to_invest.append({"title": "Attractive P/E Ratio", "detail": f"Trailing P/E of {_safe(pe)} suggests potential undervaluation."})
        elif pe > 40:
            reasons_not_to_invest.append({"title": "Elevated P/E Ratio", "detail": f"Trailing P/E of {_safe(pe)} indicates premium pricing."})

    div_yield = stock_info.get("dividendYield")
    if div_yield and div_yield > 0:
        reasons_to_invest.append({"title": "Dividend Income", "detail": f"{_safe(div_yield * 100)}% dividend yield provides passive income."})
    else:
        reasons_not_to_invest.append({"title": "No Dividend Income", "detail": "No dividend — returns depend entirely on price appreciation."})

    _pad_reasons(reasons_to_invest, reasons_not_to_invest, indicators, stock_info)

    return {
        "reasons_to_invest": reasons_to_invest[:10],
        "reasons_not_to_invest": reasons_not_to_invest[:10],
        "indicators": {k: _safe(v, 4) if isinstance(v, float) else v for k, v in indicators.items()},
        "ai_powered": False,
    }


def _pad_reasons(pros: list, cons: list, indicators: dict, info: dict):
    """Ensure we always have at least 10 of each."""
    generic_pros = [
        {"title": "Diversified Market Exposure", "detail": "Adding this stock can provide diversification and reduce concentration risk."},
        {"title": "Liquidity Advantage", "detail": "Actively traded on major exchanges with minimal slippage."},
        {"title": "Historical Resilience", "detail": "Established public companies have historically recovered from downturns."},
        {"title": "Transparent Financials", "detail": "Regular SEC filings and earnings reports provide transparency."},
        {"title": "Potential for Capital Appreciation", "detail": "Equity investments offer uncapped upside potential."},
        {"title": "Institutional Coverage", "detail": "Covered by multiple analysts with regular research updates."},
        {"title": "Dollar-Cost Averaging Friendly", "detail": "Liquidity makes it ideal for systematic investment plans."},
        {"title": "Portfolio Growth Catalyst", "detail": "Even moderate allocation can serve as a growth catalyst."},
        {"title": "Real-Time Data Availability", "detail": "Comprehensive data and indicators available for informed trading."},
        {"title": "Accessible to All Investors", "detail": "Available on all major brokerages with no access restrictions."},
    ]

    generic_cons = [
        {"title": "Market Risk Exposure", "detail": "Subject to broader market risk from economic downturns and geopolitical events."},
        {"title": "No Guaranteed Returns", "detail": "Past performance does not guarantee future results — capital at risk."},
        {"title": "Opportunity Cost", "detail": "Capital could potentially earn better returns in alternative investments."},
        {"title": "Sector-Specific Risks", "detail": "Exposed to regulatory changes, competition, and disruption in its sector."},
        {"title": "Short-Term Volatility", "detail": "Day-to-day fluctuations can be significant for short-term investors."},
        {"title": "Interest Rate Sensitivity", "detail": "Rising rates can reduce valuations as investors shift to fixed income."},
        {"title": "Inflation Erosion", "detail": "High inflation can erode real returns and squeeze margins."},
        {"title": "External Event Risk", "detail": "Unforeseen events can materially impact stock prices."},
        {"title": "Currency Risk", "detail": "For international investors, currency fluctuations impact returns."},
        {"title": "Timing Risk", "detail": "Entering after a significant run-up can result in poor short-term returns."},
    ]

    existing_pro_titles = {r["title"] for r in pros}
    existing_con_titles = {r["title"] for r in cons}

    for g in generic_pros:
        if len(pros) >= 10:
            break
        if g["title"] not in existing_pro_titles:
            pros.append(g)

    for g in generic_cons:
        if len(cons) >= 10:
            break
        if g["title"] not in existing_con_titles:
            cons.append(g)
