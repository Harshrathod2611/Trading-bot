from binance.client import Client
from binance.client import Client
import pandas as pd
import requests
import time
import os

# ===== CONFIG =====

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

print("TOKEN:", TELEGRAM_TOKEN)
print("CHAT_ID:", CHAT_ID)

client = Client()

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
    "BTCUSDT",   # market leader (slow, stable)
    "ETHUSDT",   # strong trends
    "BNBUSDT",   # exchange-driven moves
    "SOLUSDT",   # fast momentum
    "XRPUSDT",   # spike behavior
    "ADAUSDT",   # smoother moves
    "DOGEUSDT",  # high volatility (chaotic)
    "LINKUSDT",  # DeFi (clean trends sometimes)
    "AVAXUSDT",  # breakout style
    "MATICUSDT"  # mixed structure
]

# ===== TELEGRAM =====
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message
    })

    print("Telegram response:", response.text)

# ===== DATA =====
def get_data(symbol):
    klines = client.get_klines(
        symbol=symbol,
        interval=Client.KLINE_INTERVAL_1MINUTE,
        limit=100
    )

    df = pd.DataFrame(klines)

    df[1] = df[1].astype(float)
    df[2] = df[2].astype(float)
    df[3] = df[3].astype(float)
    df[4] = df[4].astype(float)

    return df

# ===== STRATEGY (EMA CROSSOVER) =====
def check_signal(df):

    c = df.iloc[-1]

    open_price = float(c[1])
    close_price = float(c[4])
    high = float(c[2])
    low = float(c[3])

    body = abs(close_price - open_price)

    # condition: strong bullish candle
    if close_price > open_price and body > (0.002 * close_price):

        entry = close_price
        sl = low

        risk = entry - sl
        if risk <= 0:
            return None

        target = entry + (2 * risk)

        print("Momentum candle detected 🚀")

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

    send_telegram("TEST MESSAGE 🚀")
    
    global balance, trade_count, wins, losses
    global total_R, peak_balance, max_drawdown

    while True:
        print("Running check...")

        for symbol in symbols:

            try:
                df = get_data(symbol)
            except Exception as e:
                print("API Error:", e)
                continue

            price = df.iloc[-1][4]

            # ===== OPEN TRADES =====
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

            # ===== MANAGE TRADES =====
          # ===== MANAGE TRADES =====
for trade in active_trades[:]:
    if trade["symbol"] != symbol:
        continue

    entry = trade["entry"]
    sl = trade["sl"]
    target = trade["target"]

    exit_price = price
    result = None

    # LOSS
    if price <= sl:
        result = "LOSS"
        losses += 1
        loss_amount = trade["risk_amount"]
        balance -= loss_amount
        total_R -= 1

    # WIN
    elif price >= target:
        result = "WIN"
        wins += 1
        profit = trade["risk_amount"] * 2
        balance += profit
        total_R += 2

    if result:
        active_trades.remove(trade)

        # Drawdown update
        global peak_balance, max_drawdown
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

                # ===== DRAWDOWN =====
                if balance > peak_balance:
                    peak_balance = balance

                drawdown = (peak_balance - balance) / peak_balance * 100

                if drawdown > max_drawdown:
                    max_drawdown = drawdown

                win_rate = (wins / trade_count) * 100 if trade_count > 0 else 0
                expectancy = total_R / trade_count if trade_count > 0 else 0

                msg = f"""
TRADE CLOSED

Symbol: {symbol}

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

        time.sleep(5)

run()
