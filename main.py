from fastapi import FastAPI, Request
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google.genai.errors import ServerError
import os

app = FastAPI()

# Initialize Gemini Client (reads API key from host environment variables)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@app.post("/high-winrate-signal")
async def process_signal(request: Request):
    data = await request.json()
    
    symbol = data.get("symbol", "GBPUSD")
    action = data.get("action", "BUY")
    entry_price = float(data.get("price", 0.0))
    timeframe = data.get("timeframe", "15")
    sl_pips = float(data.get("sl_pips", 20))
    tp_pips = float(data.get("tp_pips", 40))
    rsi = float(data.get("rsi", 50))
    
    # 1. Enforce strict timeframe rule (15m and above only)
    tf_minutes = int(timeframe) if str(timeframe).isdigit() else 15
    if tf_minutes < 15:
        return {"status": "rejected", "reason": "Timeframes under 15 minutes are disabled for high win rate."}
    
    is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()

    prompt = f"""
    You are an elite quantitative forex trader enforcing strict high-win-rate trade execution rules.

    Signal Data:
    - Pair/Asset: {symbol}
    - Direction: {action}
    - Entry Price: {entry_price}
    - Timeframe: {timeframe}M (Must be >= 15M)
    - Momentum RSI: {rsi}
    - Planned Stop Loss: {sl_pips} pips
    - Planned Take Profit: {tp_pips} pips

    Rules to verify:
    1. Timeframe Check: Confirm setup is on 15m, 1h, or 4h.
    2. Confluence Check: Confirm entry price relative to SL/TP keeps a clean 1:2 Risk-to-Reward ratio.
    3. Asset Rules: {"Apply 50-pip ATR volatility buffer for Gold." if is_gold else "Enforce 20-pip tight structural SL for Fiat forex."}

    Output Format:
    If valid, return a clean broadcast message formatted as:
    🚨 **HIGH CONFLUENCE TRADE SIGNAL** 🚨
    • Asset: {symbol} ({action})
    • Timeframe: {timeframe}M
    • Entry Price: [Price]
    • Stop Loss: [Calculated SL Price] ({sl_pips} pips)
    • Take Profit: [Calculated TP Price] ({tp_pips} pips)
    • R:R Ratio: 1:2
    • Trade Notes: [Key confirmation factor]
    """

    @retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=15),
    retry=retry_if_exception_type(ServerError)
)
def call_gemini(prompt_text: str):
    return client.models.generate_content(
        model='gemini-3.8-flash',
        contents=prompt_text
    )

# Then call it like this:
response = call_gemini(prompt)

    return {"status": "approved", "signal_card": response.text}
