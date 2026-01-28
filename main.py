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

SYMBOL = "IAU"
QTY = 1
SHORT_WINDOW = 5
LONG_WINDOW = 20
# ==========================

api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

def get_bars():
    bars = api.get_bars(
        SYMBOL,
        tradeapi.TimeFrame.Minute,
        limit=LONG_WINDOW
    )
    df = bars.df
    return df

def has_position():
    try:
        api.get_position(SYMBOL)
        return True
    except:
        return False

while True:
    try:
        df = get_bars()

        df["short_ma"] = df["close"].rolling(SHORT_WINDOW).mean()
        df["long_ma"] = df["close"].rolling(LONG_WINDOW).mean()

        short_ma = df["short_ma"].iloc[-1]
        long_ma = df["long_ma"].iloc[-1]

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

        time.sleep(60)  # run once per minute

    except Exception as e:
        print("Error:", e)
        time.sleep(60)
