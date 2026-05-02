import pandas as pd
import requests
import time
import os

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

symbols = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "MATICUSDT"
]

# ===== TELEGRAM =====
def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram not configured ❌")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    try:
        response = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message
        })
        print("Telegram response:", response.text)
    except Exception as e:
        print("Telegram error:", e)

# ===== DATA =====
def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=100"
    data = requests.get(url).json()

    df = pd.DataFrame(data)

    df[1] = df[1].astype(float)  # open
    df[2] = df[2].astype(float)  # high
    df[3] = df[3].astype(float)  # low
    df[4] = df[4].astype(float)  # close

    return df

# ===== STRATEGY (TEST - MOMENTUM CANDLE) =====
def check_signal(df):

    # EMA
    df["ema20"] = df[4].ewm(span=20).mean()

    # RSI
    delta = df[4].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    price = curr[4]

    # ===== TREND =====
    trend = price > curr["ema20"] and curr["ema20"] > prev["ema20"]

    # ===== PULLBACK =====
    pullback = curr["rsi"] < 45 or price <= curr["ema20"] * 1.002

    # ===== ENTRY =====
    bullish = curr[4] > curr[1]

    if trend and pullback and bullish:

        entry = price

        sl = min(
            df.iloc[-1][3],
            df.iloc[-2][3],
            df.iloc[-3][3],
            df.iloc[-4][3],
            df.iloc[-5][3]
        )

        risk = entry - sl
        if risk <= 0:
            return None

        target = entry + (2 * risk)

        print("TREND PULLBACK SIGNAL 🚀")

        return {
            "entry": entry,
            "sl": sl,
            "target": target
        }

    return None

def has_active_trade(symbol):
    for trade in active_trades:
        if trade["symbol"] == symbol:
            return True
    return False

# ===== MAIN LOOP =====
def run():
    global balance, trade_count, wins, losses
    global total_R, peak_balance, max_drawdown

    send_telegram("BOT STARTED ✅")

    while True:
        print("Running check...")

        for symbol in symbols:
            try:
                df = get_data(symbol)
            except Exception as e:
                print("API Error:", e)
                continue

            price = df.iloc[-1][4]

            # ===== OPEN TRADE =====
            signal = check_signal(df)

            if signal and not has_active_trade(symbol):
                risk_amount = balance * risk_percent
                entry = signal["entry"]
                sl = signal["sl"]

                risk_per_unit = entry - sl
                if risk_per_unit <= 0:
                    continue

                quantity = risk_amount / risk_per_unit

                trade = {
                    "symbol": symbol,
                    "entry": entry,
                    "sl": sl,
                    "target": signal["target"],
                    "quantity": quantity,
                    "risk_amount": risk_amount
                }

                active_trades.append(trade)
                trade_count += 1

                msg = f"""
TRADE OPENED 🚀

Symbol: {symbol}
Entry: {entry}
SL: {sl}
Target: {signal['target']}

Balance: {balance:.2f}
"""
                send_telegram(msg)
                print(msg)

            # ===== MANAGE TRADES =====
            for trade in active_trades[:]:
                if trade["symbol"] != symbol:
                    continue

                entry = trade["entry"]
                sl = trade["sl"]
                target = trade["target"]

                result = None
                exit_price = price

                if price <= sl:
                    result = "LOSS"
                    losses += 1
                    balance -= trade["risk_amount"]
                    total_R -= 1

                elif price >= target:
                    result = "WIN"
                    wins += 1
                    profit = trade["risk_amount"] * 2
                    balance += profit
                    total_R += 2

                if result:
                    active_trades.remove(trade)

                    if balance > peak_balance:
                        peak_balance = balance

                    drawdown = (peak_balance - balance) / peak_balance * 100
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown

                    win_rate = (wins / trade_count) * 100 if trade_count > 0 else 0
                    expectancy = total_R / trade_count if trade_count > 0 else 0

                    msg = f"""
TRADE CLOSED {result}

Symbol: {symbol}

Entry: {entry}
Exit: {exit_price}

Balance: {balance:.2f}

Trades: {trade_count}
Wins: {wins}
Losses: {losses}

Win Rate: {win_rate:.2f}%
Total R: {total_R}
Expectancy: {expectancy:.2f}

Max DD: {max_drawdown:.2f}%
"""
                    send_telegram(msg)
                    print(msg)

        time.sleep(5)

run()
