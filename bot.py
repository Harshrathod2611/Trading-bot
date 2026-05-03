import pandas as pd
import requests
import time
import os
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = str(os.getenv("CHAT_ID"))

balance = 100000
risk_percent = 0.02
fee_rate = 0.001

active_trades = []
cooldown = {}

last_log_time = 0
log_interval = 10

symbols = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
    "ADAUSDT","DOGEUSDT","LINKUSDT","AVAXUSDT","MATICUSDT"
]

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=5
        )
    except:
        pass

def get_data(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
        response = requests.get(url, timeout=5)
        df = pd.DataFrame(response.json())

        df[4] = df[4].astype(float)
        df[3] = df[3].astype(float)

        return df
    except:
        return None

def check_signal(df):

    df["ema50"] = df[4].ewm(span=50).mean()
    df["ema120"] = df[4].ewm(span=120).mean()

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    cross = prev["ema50"] <= prev["ema120"] and curr["ema50"] > curr["ema120"]

    if cross:
        entry = curr[4]
        sl = min(df.iloc[-5:][3])

        risk = entry - sl
        if risk <= 0:
            return None

        return {
            "entry": entry,
            "sl": sl,
            "risk": risk
        }

    return None

def run():
    global balance, last_log_time

    send("BOT STARTED 🚀")

    while True:
        now = time.time()

        # ===== HEARTBEAT =====
        if now - last_log_time > log_interval:
            print(f"Alive | Balance: {balance:.2f} | Trades: {len(active_trades)}")
            last_log_time = now

        # ===== ENTRY =====
        for symbol in symbols:

            if any(t["symbol"] == symbol for t in active_trades):
                continue

            df = get_data(symbol)
            if df is None:
                continue

            signal = check_signal(df)

            if signal:
                entry = signal["entry"]
                sl = signal["sl"]
                risk = signal["risk"]

                risk_amount = balance * risk_percent
                qty = risk_amount / risk

                cost = qty * entry
                fee = cost * fee_rate

                if cost > balance:
                    continue

                balance -= (cost + fee)

                trade = {
                    "symbol": symbol,
                    "entry": entry,
                    "sl": sl,
                    "qty": qty,
                    "remaining_qty": qty,
                    "partial_done": False,
                    "entry_time": datetime.now().strftime("%H:%M:%S"),
                    "risk": risk,
                    "trail_sl": sl
                }

                active_trades.append(trade)

                send(f"""
BUY 🚀 {symbol}

Entry: {entry}
SL: {sl}
Qty: {qty:.2f}

Balance: {balance:.2f}
""")

        # ===== MANAGEMENT =====
        for trade in active_trades[:]:

            df = get_data(trade["symbol"])
            if df is None:
                continue

            price = df.iloc[-1][4]

            entry = trade["entry"]
            risk = trade["risk"]

            # ===== PARTIAL EXIT (1R) =====
            if not trade["partial_done"] and price >= entry + risk:

                sell_qty = trade["qty"] / 2
                trade["remaining_qty"] -= sell_qty

                gain = sell_qty * price
                fee = gain * fee_rate

                balance += (gain - fee)

                trade["trail_sl"] = entry  # breakeven
                trade["partial_done"] = True

                send(f"""
PARTIAL PROFIT 💰

{trade['symbol']}

Sold 50%
SL moved to breakeven
""")

            # ===== TRAILING STOP =====
            if trade["partial_done"]:
                new_sl = price - risk
                if new_sl > trade["trail_sl"]:
                    trade["trail_sl"] = new_sl

            # ===== EXIT =====
            if price <= trade["trail_sl"]:

                final_value = trade["remaining_qty"] * price
                fee = final_value * fee_rate

                balance += (final_value - fee)

                active_trades.remove(trade)

                send(f"""
EXIT 🚪

{trade['symbol']}

Exit Price: {price}
Final Balance: {balance:.2f}
""")

        time.sleep(5)

run()
