import pandas as pd
import requests
import time
import os
from datetime import datetime

# ===== CONFIG =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = str(os.getenv("CHAT_ID"))

# ===== GLOBAL STATE =====
balance = 100000
risk_percent = 0.01

trade_count = 0
wins = 0
losses = 0
total_R = 0

peak_balance = balance
max_drawdown = 0

active_trades = []
last_loss_time = {}

cooldown_seconds = 300

# ===== 30 DIVERSE COINS =====
symbols = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
    "ADAUSDT","DOGEUSDT","LINKUSDT","AVAXUSDT","MATICUSDT",
    "LTCUSDT","TRXUSDT","ATOMUSDT","NEARUSDT","FTMUSDT",
    "SANDUSDT","APEUSDT","AXSUSDT","GALAUSDT","ALGOUSDT",
    "ICPUSDT","FILUSDT","ETCUSDT","EGLDUSDT","THETAUSDT",
    "AAVEUSDT","UNIUSDT","XLMUSDT","HBARUSDT","VETUSDT"
]

# ===== TELEGRAM =====
def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        print("Telegram failed")

# ===== DATA =====
def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
    data = requests.get(url).json()

    df = pd.DataFrame(data)

    df[1] = df[1].astype(float)
    df[2] = df[2].astype(float)
    df[3] = df[3].astype(float)
    df[4] = df[4].astype(float)

    return df

# ===== RSI STRATEGY (CANDLE CLOSE BASED) =====
def check_signal(df):

    delta = df[4].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    curr = df.iloc[-1]

    if curr["rsi"] <= 35:
        entry = curr[4]

        sl = min(df.iloc[-5:][3])

        risk = entry - sl
        if risk <= 0:
            return None

        target = entry + (2 * risk)

        return {
            "entry": entry,
            "sl": sl,
            "target": target
        }

    return None

# ===== MAIN LOOP =====
def run():
    global balance, wins, losses, total_R, trade_count
    global peak_balance, max_drawdown

    send_telegram("BOT STARTED ✅")

    while True:

        now = time.time()

        # =====================
        # 1. CHECK NEW ENTRIES (every 60 sec)
        # =====================
        for symbol in symbols:

            # skip if already in trade
            if any(t["symbol"] == symbol for t in active_trades):
                continue

            # cooldown check
            if symbol in last_loss_time:
                if now - last_loss_time[symbol] < cooldown_seconds:
                    continue

            try:
                df = get_data(symbol)
            except:
                continue

            signal = check_signal(df)

            if signal:

                entry_time = datetime.now().strftime("%H:%M:%S")

                risk_amount = balance * risk_percent
                risk_per_unit = signal["entry"] - signal["sl"]

                if risk_per_unit <= 0:
                    continue

                trade = {
                    "symbol": symbol,
                    "entry": signal["entry"],
                    "sl": signal["sl"],
                    "target": signal["target"],
                    "risk": risk_amount,
                    "entry_time": entry_time
                }

                active_trades.append(trade)
                trade_count += 1

                send_telegram(f"""
TRADE OPENED 🚀

{symbol}
Entry: {signal['entry']}
SL: {signal['sl']}
Target: {signal['target']}

Time: {entry_time}
""")

        # =====================
        # 2. MANAGE TRADES (every loop ~2 sec)
        # =====================
        for trade in active_trades[:]:

            symbol = trade["symbol"]

            try:
                df = get_data(symbol)
            except:
                continue

            price = df.iloc[-1][4]

            result = None

            if price <= trade["sl"]:
                result = "LOSS"
                losses += 1
                balance -= trade["risk"]
                total_R -= 1
                last_loss_time[symbol] = time.time()

            elif price >= trade["target"]:
                result = "WIN"
                wins += 1
                balance += trade["risk"] * 2
                total_R += 2

            if result:

                exit_time = datetime.now().strftime("%H:%M:%S")

                active_trades.remove(trade)

                if balance > peak_balance:
                    peak_balance = balance

                dd = (peak_balance - balance) / peak_balance * 100
                max_drawdown = max(max_drawdown, dd)

                win_rate = (wins / trade_count) * 100 if trade_count else 0
                expectancy = total_R / trade_count if trade_count else 0

                send_telegram(f"""
TRADE CLOSED {result}

{symbol}

Entry: {trade['entry']}
Exit: {price}

Entry Time: {trade['entry_time']}
Exit Time: {exit_time}

Balance: {balance:.2f}

Trades: {trade_count}
Win Rate: {win_rate:.2f}%
Expectancy: {expectancy:.2f}
Max DD: {max_drawdown:.2f}%
""")

        # =====================
        # LOOP SPEED
        # =====================
        time.sleep(2)

run()
