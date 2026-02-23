"""
Data fetching module — uses yfinance to scrape Yahoo Finance data.
"""

import yfinance as yf
import pandas as pd


def fetch_minute_data(ticker: str) -> pd.DataFrame:
    """Fetch 1-day minute-level OHLCV data for the given ticker."""
    stock = yf.Ticker(ticker)
    df = stock.history(period="1d", interval="1m")
    return df


def fetch_daily_data(ticker: str, period: str = "3mo") -> pd.DataFrame:
    """Fetch daily OHLCV data over the given period for trend analysis."""
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval="1d")
    return df


def fetch_stock_info(ticker: str) -> dict:
    """Fetch basic stock information (name, sector, market cap, etc.)."""
    stock = yf.Ticker(ticker)
    try:
        info = stock.info
        return {
            "symbol": info.get("symbol", ticker.upper()),
            "shortName": info.get("shortName", ticker.upper()),
            "longName": info.get("longName", ""),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "marketCap": info.get("marketCap", 0),
            "currency": info.get("currency", "USD"),
            "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice", 0),
            "previousClose": info.get("previousClose", 0),
            "open": info.get("open") or info.get("regularMarketOpen", 0),
            "dayLow": info.get("dayLow") or info.get("regularMarketDayLow", 0),
            "dayHigh": info.get("dayHigh") or info.get("regularMarketDayHigh", 0),
            "volume": info.get("volume") or info.get("regularMarketVolume", 0),
            "averageVolume": info.get("averageVolume", 0),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow", 0),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh", 0),
            "trailingPE": info.get("trailingPE", 0),
            "forwardPE": info.get("forwardPE", 0),
            "dividendYield": info.get("dividendYield", 0),
            "beta": info.get("beta", 0),
            "fiftyDayAverage": info.get("fiftyDayAverage", 0),
            "twoHundredDayAverage": info.get("twoHundredDayAverage", 0),
        }
    except Exception:
        return {"symbol": ticker.upper(), "shortName": ticker.upper(), "error": "Info unavailable"}


def search_tickers(query: str) -> list[dict]:
    """
    Search for stock tickers matching the query.
    Uses yfinance's search functionality.
    """
    try:
        # Use yfinance search
        results = yf.Search(query)
        quotes = results.quotes if hasattr(results, 'quotes') else []

        matches = []
        for q in quotes[:10]:
            matches.append({
                "symbol": q.get("symbol", ""),
                "shortName": q.get("shortname", q.get("shortName", "")),
                "exchange": q.get("exchange", ""),
                "quoteType": q.get("quoteType", ""),
            })
        return matches
    except Exception:
        # Fallback: try to validate as a direct ticker
        try:
            stock = yf.Ticker(query.upper())
            info = stock.info
            if info and info.get("shortName"):
                return [{
                    "symbol": query.upper(),
                    "shortName": info.get("shortName", query.upper()),
                    "exchange": info.get("exchange", ""),
                    "quoteType": info.get("quoteType", "EQUITY"),
                }]
        except Exception:
            pass
        return []
