import alpaca_trade_api as tradeapi
import pandas as pd
import time
import os
from dotenv import load_dotenv

load_dotenv()

# ========= CONFIG =========
API_KEY = os.getenv("alpacakey")
API_SECRET = os.getenv("alpacasecret")
BASE_URL = "https://paper-api.alpaca.markets"

SYMBOL = "AAPL"
QTY = 1
SHORT_WINDOW = 5
LONG_WINDOW = 20
# ==========================

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

def market_is_open():
    clock = api.get_clock()
    return clock.is_open

def get_bars():
    bars = api.get_bars(
        SYMBOL,
        tradeapi.TimeFrame.Minute,
        limit=LONG_WINDOW
    ).df

    # Fix multi-index
    bars = bars[bars.index.get_level_values("symbol") == SYMBOL]
    bars = bars.reset_index()

    return bars

def has_position():
    try:
        api.get_position(SYMBOL)
        return True
    except tradeapi.rest.APIError:
        return False

while True:
    try:
        if not market_is_open():
            print("⏰ Market closed — waiting...")
            time.sleep(60)
            continue

        df = get_bars()

        df["short_ma"] = df["close"].rolling(SHORT_WINDOW).mean()
        df["long_ma"] = df["close"].rolling(LONG_WINDOW).mean()

        short_ma = df["short_ma"].iloc[-1]
        long_ma = df["long_ma"].iloc[-1]

        # Skip if MAs not ready
        if pd.isna(short_ma) or pd.isna(long_ma):
            print("⏳ Waiting for enough data...")
            time.sleep(60)
            continue

        print(f"Short MA: {short_ma:.2f}, Long MA: {long_ma:.2f}")

        if short_ma > long_ma and not has_position():
            print("📈 BUY signal")
            api.submit_order(
                symbol=SYMBOL,
                qty=QTY,
                side="buy",
                type="market",
                time_in_force="gtc"
            )

        elif short_ma < long_ma and has_position():
            print("📉 SELL signal")
            api.submit_order(
                symbol=SYMBOL,
                qty=QTY,
                side="sell",
                type="market",
                time_in_force="gtc"
            )

        time.sleep(60)

    except Exception as e:
        print("❌ Error:", e)
        time.sleep(60)
