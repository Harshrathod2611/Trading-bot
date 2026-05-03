import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime

# ===== TELEGRAM CONFIG =====


def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

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

# ===== DATA =====
def get_data(symbol):
    try:
        df = yf.download(symbol, interval="5m", period="1d", progress=False)
        df = df.reset_index()

        df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close"
        }, inplace=True)

        return df
    except:
        return None

# ===== MAIN =====
def run():
    global balance

    send("ORB BOT STARTED 🚀")

    while True:

        now = datetime.now()
        current_time = now.strftime("%H:%M")

        # ===== BUILD RANGE =====
        if "09:15" <= current_time <= "09:30":

            for symbol in symbols:
                df = get_data(symbol)
                if df is None or len(df) == 0:
                    continue

                last = df.iloc[-1]

                if symbol not in range_data:
                    range_data[symbol] = {
                        "high": last["high"],
                        "low": last["low"]
                    }
                else:
                    range_data[symbol]["high"] = max(
                        range_data[symbol]["high"], last["high"]
                    )
                    range_data[symbol]["low"] = min(
                        range_data[symbol]["low"], last["low"]
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
                close = last["close"]

                high = range_data[symbol]["high"]
                low = range_data[symbol]["low"]

                # BUY
                if close > high:
                    entry = close
                    sl = low
                    risk = entry - sl

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

                    send(f"BUY 🚀 {symbol}\nEntry: {entry}\nSL: {sl}")

                # SELL
                elif close < low:
                    entry = close
                    sl = high
                    risk = sl - entry

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

                    send(f"SELL 🔻 {symbol}\nEntry: {entry}\nSL: {sl}")

        # ===== MANAGEMENT =====
        for trade in active_trades[:]:

            df = get_data(trade["symbol"])
            if df is None or len(df) < 2:
                continue

            last = df.iloc[-1]
            prev = df.iloc[-2]

            price = last["close"]

            entry = trade["entry"]
            risk = trade["risk"]

            # ===== PARTIAL =====
            if not trade["partial"]:

                if trade["type"] == "BUY" and price >= entry + risk:
                    trade["partial"] = True
                    trade["sl"] = entry
                    send(f"PARTIAL PROFIT 💰 {trade['symbol']}")

                elif trade["type"] == "SELL" and price <= entry - risk:
                    trade["partial"] = True
                    trade["sl"] = entry
                    send(f"PARTIAL PROFIT 💰 {trade['symbol']}")

            # ===== TRAILING =====
            if trade["partial"]:

                if trade["type"] == "BUY":
                    new_sl = prev["low"]
                    if new_sl > trade["sl"]:
                        trade["sl"] = new_sl

                else:
                    new_sl = prev["high"]
                    if new_sl < trade["sl"]:
                        trade["sl"] = new_sl

            # ===== EXIT =====
            if trade["type"] == "BUY" and price <= trade["sl"]:
                send(f"EXIT 🚪 BUY {trade['symbol']} @ {price}")
                active_trades.remove(trade)

            elif trade["type"] == "SELL" and price >= trade["sl"]:
                send(f"EXIT 🚪 SELL {trade['symbol']} @ {price}")
                active_trades.remove(trade)

        time.sleep(60)

run()
