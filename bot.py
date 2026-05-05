import yfinance as yf
import pandas as pd
import time
import requests
import os
from datetime import datetime
import pytz

# ===== TELEGRAM CONFIG =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=5
        )
    except:
        print("Telegram failed")

# ===== SYMBOLS =====
symbols = [
    "RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","AXISBANK.NS",
    "KOTAKBANK.NS","TATASTEEL.NS","JSWSTEEL.NS","ITC.NS",
    "HINDUNILVR.NS","LT.NS","BHARTIARTL.NS","POWERGRID.NS"
]

balance = 100000
risk_percent = 0.02

range_data = {}
active_trades = []
done_stocks = set()

# ===== TIMEZONE =====
ist = pytz.timezone('Asia/Kolkata')

# ===== SAFE VALUE FUNCTION =====
def safe_float(value):
    try:
        if isinstance(value, pd.Series):
            return float(value.iloc[0])
        return float(value)
    except:
        return None

# ===== DATA =====
def get_data(symbol):
    try:
        df = yf.download(symbol, interval="5m", period="1d", progress=False)
        if df is None or df.empty:
            return None

        df = df.reset_index()

        df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close"
        }, inplace=True)

        return df
    except Exception as e:
        print(f"Data error {symbol}: {e}")
        return None

# ===== MAIN =====
def run():
    global balance

    send("ORB BOT STARTED 🚀")

    while True:

        try:
            now = datetime.now(ist)
            current_time = now.strftime("%H:%M")

            # ===== MARKET HOURS FILTER =====
            if current_time < "09:15" or current_time > "15:30":
                time.sleep(60)
                continue

            # ===== BUILD RANGE =====
            if "09:15" <= current_time <= "09:30":

                for symbol in symbols:
                    df = get_data(symbol)
                    if df is None or len(df) == 0:
                        continue

                    last = df.iloc[-1]

                    high_val = safe_float(last["high"])
                    low_val = safe_float(last["low"])

                    if high_val is None or low_val is None:
                        continue

                    if symbol not in range_data:
                        range_data[symbol] = {
                            "high": high_val,
                            "low": low_val
                        }
                    else:
                        range_data[symbol]["high"] = max(
                            range_data[symbol]["high"], high_val
                        )
                        range_data[symbol]["low"] = min(
                            range_data[symbol]["low"], low_val
                        )

            # ===== BREAKOUT =====
            if current_time > "09:30":

                for symbol in symbols:

                    if symbol in done_stocks:
                        continue

                    if symbol not in range_data:
                        continue

                    df = get_data(symbol)
                    if df is None or len(df) < 2:
                        continue

                    last = df.iloc[-1]

                    close = safe_float(last["close"])
                    high = range_data[symbol]["high"]
                    low = range_data[symbol]["low"]

                    if close is None:
                        continue

                    # ===== BUY =====
                    if close > high:
                        entry = close
                        sl = low
                        risk = entry - sl

                        if risk <= 0:
                            continue

                        trade = {
                            "symbol": symbol,
                            "type": "BUY",
                            "entry": entry,
                            "sl": sl,
                            "risk": risk,
                            "partial": False
                        }

                        active_trades.append(trade)
                        done_stocks.add(symbol)

                        send(f"BUY 🚀 {symbol}\nEntry: {entry:.2f}\nSL: {sl:.2f}")

                    # ===== SELL =====
                    elif close < low:
                        entry = close
                        sl = high
                        risk = sl - entry

                        if risk <= 0:
                            continue

                        trade = {
                            "symbol": symbol,
                            "type": "SELL",
                            "entry": entry,
                            "sl": sl,
                            "risk": risk,
                            "partial": False
                        }

                        active_trades.append(trade)
                        done_stocks.add(symbol)

                        send(f"SELL 🔻 {symbol}\nEntry: {entry:.2f}\nSL: {sl:.2f}")

            # ===== TRADE MANAGEMENT =====
            for trade in active_trades[:]:

                df = get_data(trade["symbol"])
                if df is None or len(df) < 2:
                    continue

                last = df.iloc[-1]
                prev = df.iloc[-2]

                price = safe_float(last["close"])
                entry = trade["entry"]
                risk = trade["risk"]

                if price is None:
                    continue

                # ===== PARTIAL =====
                if not trade["partial"]:

                    if trade["type"] == "BUY" and price >= entry + risk:
                        trade["partial"] = True
                        trade["sl"] = entry
                        send(f"PARTIAL 💰 {trade['symbol']}")

                    elif trade["type"] == "SELL" and price <= entry - risk:
                        trade["partial"] = True
                        trade["sl"] = entry
                        send(f"PARTIAL 💰 {trade['symbol']}")

                # ===== TRAILING =====
                if trade["partial"]:

                    prev_high = safe_float(prev["high"])
                    prev_low = safe_float(prev["low"])

                    if trade["type"] == "BUY" and prev_low is not None:
                        if prev_low > trade["sl"]:
                            trade["sl"] = prev_low

                    elif trade["type"] == "SELL" and prev_high is not None:
                        if prev_high < trade["sl"]:
                            trade["sl"] = prev_high

                # ===== EXIT =====
                if trade["type"] == "BUY" and price <= trade["sl"]:
                    send(f"EXIT 🚪 BUY {trade['symbol']} @ {price:.2f}")
                    active_trades.remove(trade)

                elif trade["type"] == "SELL" and price >= trade["sl"]:
                    send(f"EXIT 🚪 SELL {trade['symbol']} @ {price:.2f}")
                    active_trades.remove(trade)

        except Exception as e:
            print("ERROR:", e)

        time.sleep(60)

run()
