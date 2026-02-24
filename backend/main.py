"""
FastAPI application — serves API endpoints and the frontend.
"""

import os
import json
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_fetcher import fetch_minute_data, fetch_daily_data, fetch_stock_info, search_tickers, fetch_historical_chart_data
from analysis import compute_indicators, generate_analysis, OPENROUTER_API_KEY
import analysis as analysis_module

app = FastAPI(title="Global Stocks AI", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class ApiKeyRequest(BaseModel):
    api_key: str


class ChatRequest(BaseModel):
    ticker: str
    message: str


@app.get("/")
async def serve_frontend():
    """Serve the main HTML page."""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.post("/api/set-key")
async def set_api_key(req: ApiKeyRequest):
    """Set the OpenRouter API key at runtime."""
    analysis_module.OPENROUTER_API_KEY = req.api_key
    return JSONResponse(content={"status": "ok", "message": "API key set successfully"})


@app.get("/api/key-status")
async def key_status():
    """Check if an API key is configured."""
    has_key = bool(analysis_module.OPENROUTER_API_KEY)
    return JSONResponse(content={"hasKey": has_key})


@app.get("/api/search")
async def api_search(q: str = Query(..., min_length=1, description="Search query")):
    """Search for stock tickers matching the query."""
    try:
        results = search_tickers(q)
        return JSONResponse(content={"results": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{ticker}")
async def api_stock_data(ticker: str):
    """Fetch minute-level data and stock info for the given ticker."""
    try:
        info = fetch_stock_info(ticker)
        minute_df = fetch_minute_data(ticker)

        minute_data = []
        if not minute_df.empty:
            for idx, row in minute_df.iterrows():
                minute_data.append({
                    "timestamp": idx.isoformat(),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })

        return JSONResponse(content={
            "info": info,
            "minuteData": minute_data,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analyze/{ticker}")
async def api_analyze(ticker: str):
    """Perform full AI analysis on the given ticker."""
    try:
        info = fetch_stock_info(ticker)
        daily_df = fetch_daily_data(ticker, period="3mo")

        if daily_df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for ticker '{ticker}'")

        indicators = compute_indicators(daily_df)
        analysis = generate_analysis(indicators, info)

        return JSONResponse(content={
            "ticker": ticker.upper(),
            "info": info,
            "analysis": analysis,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/{ticker}")
async def api_stock_history(ticker: str, range: str = Query("1mo")):
    """Fetch historical data for charting."""
    try:
        df = fetch_historical_chart_data(ticker, range)

        history_data = []
        if not df.empty:
            for idx, row in df.iterrows():
                history_data.append({
                    "time": int(idx.timestamp()),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                })

        return JSONResponse(content={"history": history_data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    """Handle stock-specific chatbot queries."""
    try:
        # Get context: stock info + some indicators
        info = fetch_stock_info(req.ticker)
        daily_df = fetch_daily_data(req.ticker, period="3mo")
        indicators = compute_indicators(daily_df)

        # Call analysis module specialized chat function
        response = analysis_module.get_ai_chat_response(req.ticker, req.message, info, indicators)

        return JSONResponse(content={"response": response})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
