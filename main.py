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

COOLDOWN = 300          # 5 minutes
STOP_LOSS_PCT = 0.02   # 2%

RSI_PERIOD = 14
RSI_BUY = 30
RSI_SELL = 55
# ==========================

api = tradeapi.REST(
    API_KEY,
    API_SECRET,
    BASE_URL,
    api_version="v2"
)

last_trade_time = 0

def market_is_open():
    return api.get_clock().is_open

def get_bars():
    try:
        bars = api.get_bars(
            SYMBOL,
            tradeapi.TimeFrame.Minute,
            limit=50
        ).df.reset_index()
        return bars
    except Exception as e:
        print("⚠️ Data fetch failed, retrying in 10s...", e)
        time.sleep(10)
        return None

def get_position_safe():
    try:
        return api.get_position(SYMBOL)
    except tradeapi.rest.APIError:
        return None

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def stop_loss_triggered(position):
    if position is None:
        return False

    entry_price = float(position.avg_entry_price)
    current_price = float(position.current_price or entry_price)

    loss_pct = (entry_price - current_price) / entry_price
    return loss_pct >= STOP_LOSS_PCT

while True:
    try:
        # if not market_is_open():
        #     print("⏰ Market closed — waiting...")
        #     time.sleep(60)
        #     continue

        df = get_bars()
        if df is None:
            continue

        # VWAP
        df["vwap"] = (
            (df["high"] + df["low"] + df["close"]) / 3
        ).cumsum() / df["volume"].cumsum()

        df["rsi"] = calculate_rsi(df["close"], RSI_PERIOD)

        latest = df.iloc[-1]
        price = latest["close"]
        vwap = latest["vwap"]
        rsi = latest["rsi"]

        if pd.isna(rsi):
            print("⏳ Waiting for RSI data...")
            time.sleep(60)
            continue

        position = get_position_safe()
        has_pos = position is not None
        now = time.time()

        print(f"Price: {price:.2f} | VWAP: {vwap:.2f} | RSI: {rsi:.1f}")

        # 🛑 STOP-LOSS (highest priority)
        if has_pos and stop_loss_triggered(position):
            print("🛑 STOP-LOSS SELL")
            api.submit_order(
                symbol=SYMBOL,
                qty=position.qty,
                side="sell",
                type="market",
                time_in_force="gtc"
            )
            last_trade_time = now

        # 📈 BUY (Mean Reversion)
        elif (
            price < vwap
            and rsi < RSI_BUY
            and not has_pos
            and now - last_trade_time > COOLDOWN
        ):
            print("📈 BUY (Mean Reversion)")
            api.submit_order(
                symbol=SYMBOL,
                qty=QTY,
                side="buy",
                type="market",
                time_in_force="gtc"
            )
            last_trade_time = now

        # 📉 SELL (Reversion Complete)
        elif (
            has_pos
            and (price >= vwap or rsi > RSI_SELL)
            and now - last_trade_time > COOLDOWN
        ):
            print("📉 SELL (Mean Reversion)")
            api.submit_order(
                symbol=SYMBOL,
                qty=position.qty,
                side="sell",
                type="market",
                time_in_force="gtc"
            )
            last_trade_time = now

        time.sleep(65)

    except Exception as e:
        print("❌ Error:", e)
        time.sleep(60)
