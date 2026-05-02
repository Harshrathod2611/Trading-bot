import pandas as pd
import requests
import time
import os
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = str(os.getenv("CHAT_ID"))

# ===== CAPITAL =====
balance = 100000
risk_percent = 0.02

# ===== STATS =====
trade_count = 0
wins = 0
losses = 0
total_R = 0

peak_balance = balance
max_drawdown = 0

active_trades = []

cooldown = {}
cooldown_seconds = 300

fee_rate = 0.001  # 0.1%

# ===== HEARTBEAT =====
last_log_time = 0
log_interval = 10  # seconds

symbols = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
    "ADAUSDT","DOGEUSDT","LINKUSDT","AVAXUSDT","MATICUSDT"
]

# ===== TELEGRAM =====
def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=5
        )
    except:
        pass

# ===== DATA =====
def get_data(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
        response = requests.get(url, timeout=5)
        data = response.json()

        df = pd.DataFrame(data)

        df[4] = df[4].astype(float)
        df[3] = df[3].astype(float)

        return df
    except:
        return None

# ===== STRATEGY =====
def check_signal(df):

    df["ema50"] = df[4].ewm(span=50).mean()
    df["ema120"] = df[4].ewm(span=120).mean()

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    cross = prev["ema50"] < prev["ema120"] and curr["ema50"] > curr["ema120"]

    if cross:
        entry = curr[4]
        sl = min(df.iloc[-5:][3])

        risk = entry - sl
        if risk <= 0:
            return None

        target = entry + (2 * risk)

        return {
            "entry": entry,
            "sl": sl,
            "target": target,
            "risk": risk
        }

    return None

# ===== MAIN =====
def run():
    global balance, trade_count, wins, losses, total_R
    global peak_balance, max_drawdown
    global last_log_time

    send("BOT STARTED 🚀")

    while True:
        now = time.time()

        # ===== HEARTBEAT =====
        if now - last_log_time > log_interval:
            print(f"Bot alive | Balance: {balance:.2f} | Active trades: {len(active_trades)}")
            last_log_time = now

        # ===== ENTRY =====
        for symbol in symbols:

            if any(t["symbol"] == symbol for t in active_trades):
                continue

            if symbol in cooldown:
                if now - cooldown[symbol] < cooldown_seconds:
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
                fees = cost * fee_rate

                if cost > balance:
                    continue

                balance -= (cost + fees)

                trade = {
                    "symbol": symbol,
                    "entry": entry,
                    "sl": sl,
                    "target": signal["target"],
                    "qty": qty,
                    "remaining_qty": qty,
                    "partial_done": False,
                    "entry_time": datetime.now().strftime("%H:%M:%S"),
                    "risk": risk_amount
                }

                active_trades.append(trade)
                trade_count += 1

                send(f"""
BUY 🚀 {symbol}

Entry: {entry}
SL: {sl}
Target: {signal['target']}

Qty: {qty:.2f}
Balance Left: {balance:.2f}
Time: {trade['entry_time']}
""")

        # ===== MANAGEMENT =====
        for trade in active_trades[:]:

            df = get_data(trade["symbol"])
            if df is None:
                continue

            price = df.iloc[-1][4]

            # ===== PARTIAL =====
            if not trade["partial_done"] and price >= trade["target"]:

                sell_qty = trade["qty"] / 2
                trade["remaining_qty"] -= sell_qty

                gain = sell_qty * price
                fee = gain * fee_rate

                balance += (gain - fee)

                trade["sl"] = trade["entry"]
                trade["target"] = price + (price - trade["entry"])

                trade["partial_done"] = True

                send(f"""
PARTIAL PROFIT 💰

{trade['symbol']}

Sold 50%
New SL: {trade['sl']}
New Target: {trade['target']}
""")

            # ===== EXIT =====
            if price <= trade["sl"]:

                result = "LOSS" if not trade["partial_done"] else "BREAKEVEN"

                final_value = trade["remaining_qty"] * price
                fee = final_value * fee_rate

                balance += (final_value - fee)

                if result == "LOSS":
                    losses += 1
                    total_R -= 1
                    cooldown[trade["symbol"]] = time.time()
                else:
                    wins += 1

                active_trades.remove(trade)

                rr = (price - trade["entry"]) / (trade["entry"] - trade["sl"]) if (trade["entry"] - trade["sl"]) != 0 else 0

                send(f"""
TRADE CLOSED {result}

{trade['symbol']}

Entry: {trade['entry']}
Exit: {price}
RR: {rr:.2f}

Balance: {balance:.2f}
""")

        time.sleep(2)

run()
