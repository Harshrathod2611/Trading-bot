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

# ===== ACCOUNT =====
balance = 100000
risk_percent = 0.02

range_data = {}
active_trades = []
done_stocks = set()

# ===== TIMEZONE =====
ist = pytz.timezone('Asia/Kolkata')

# ===== DATA CACHE =====
data_cache = {}

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

def fetch_all_data():
    global data_cache
    data_cache = {}

    for symbol in symbols:
        df = get_data(symbol)
        if df is not None and len(df) > 0:
            data_cache[symbol] = df

# ===== PNL CALC =====
def calculate_pnl(trade, exit_price):
    if trade["type"] == "BUY":
        pnl = (exit_price - trade["entry"]) * trade["qty"]
    else:
        pnl = (trade["entry"] - exit_price) * trade["qty"]

    charges = (trade["entry"] + exit_price) * trade["qty"] * 0.0005 + 40
    net = pnl - charges

    return pnl, charges, net

# ===== MAIN =====
def run():
    global balance

    send("ORB BOT STARTED 🚀")

    while True:

        now = datetime.now(ist)
        current_time = now.strftime("%H:%M")

        # ===== MARKET HOURS =====
        if current_time < "09:15" or current_time > "15:30":
            time.sleep(60)
            continue

        # ===== FETCH DATA ONCE =====
        fetch_all_data()

        # ===== BUILD RANGE =====
        if "09:15" <= current_time <= "09:30":

            for symbol, df in data_cache.items():
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

            for symbol, df in data_cache.items():

                if symbol in done_stocks:
                    continue

                if symbol not in range_data:
                    continue

                if len(df) < 2:
                    continue

                last = df.iloc[-1]
                close = last["close"]

                high = range_data[symbol]["high"]
                low = range_data[symbol]["low"]

                # ===== BUY =====
                if close > high:
                    entry = close
                    sl = low
                    risk_per_share = entry - sl

                    if risk_per_share <= 0:
                        continue

                    risk_amount = balance * risk_percent
                    qty = int(risk_amount / risk_per_share)

                    if qty <= 0:
                        continue

                    trade = {
                        "symbol": symbol,
                        "type": "BUY",
                        "entry": entry,
                        "sl": sl,
                        "risk": risk_per_share,
                        "qty": qty,
                        "partial": False
                    }

                    active_trades.append(trade)
                    done_stocks.add(symbol)

                    send(f"BUY 🚀 {symbol}\nEntry: {entry:.2f}\nSL: {sl:.2f}\nQty: {qty}")

                # ===== SELL =====
                elif close < low:
                    entry = close
                    sl = high
                    risk_per_share = sl - entry

                    if risk_per_share <= 0:
                        continue

                    risk_amount = balance * risk_percent
                    qty = int(risk_amount / risk_per_share)

                    if qty <= 0:
                        continue

                    trade = {
                        "symbol": symbol,
                        "type": "SELL",
                        "entry": entry,
                        "sl": sl,
                        "risk": risk_per_share,
                        "qty": qty,
                        "partial": False
                    }

                    active_trades.append(trade)
                    done_stocks.add(symbol)

                    send(f"SELL 🔻 {symbol}\nEntry: {entry:.2f}\nSL: {sl:.2f}\nQty: {qty}")

        # ===== TRADE MANAGEMENT =====
        for trade in active_trades[:]:

            symbol = trade["symbol"]

            if symbol not in data_cache:
                continue

            df = data_cache[symbol]

            if len(df) < 2:
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
                    send(f"PARTIAL 💰 {symbol}")

                elif trade["type"] == "SELL" and price <= entry - risk:
                    trade["partial"] = True
                    trade["sl"] = entry
                    send(f"PARTIAL 💰 {symbol}")

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
                pnl, charges, net = calculate_pnl(trade, price)
                balance += net

                send(
                    f"EXIT 🚪 BUY {symbol} @ {price:.2f}\n"
                    f"PnL: {net:.2f}\nCharges: {charges:.2f}\nBalance: {balance:.2f}"
                )

                active_trades.remove(trade)

            elif trade["type"] == "SELL" and price >= trade["sl"]:
                pnl, charges, net = calculate_pnl(trade, price)
                balance += net

                send(
                    f"EXIT 🚪 SELL {symbol} @ {price:.2f}\n"
                    f"PnL: {net:.2f}\nCharges: {charges:.2f}\nBalance: {balance:.2f}"
                )

                active_trades.remove(trade)

        time.sleep(60)

run()
