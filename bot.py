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
            data={
                "chat_id": CHAT_ID,
                "text": msg
            },
            timeout=5
        )
    except Exception as e:
        print(f"Telegram Error: {e}")

# ===== SYMBOLS =====
symbols = [
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "AXISBANK.NS",
    "KOTAKBANK.NS",
    "TATASTEEL.NS",
    "JSWSTEEL.NS",
    "ITC.NS",
    "HINDUNILVR.NS",
    "LT.NS",
    "BHARTIARTL.NS",
    "POWERGRID.NS"
]

# ===== ACCOUNT =====
balance = 100000
risk_percent = 0.02

# ===== STORAGE =====
range_data = {}
active_trades = []
done_stocks = set()
data_cache = {}

# ===== TIMEZONE =====
ist = pytz.timezone("Asia/Kolkata")

# ===== DATA FUNCTION =====
def get_data(symbol):

    try:
        df = yf.download(
            symbol,
            interval="5m",
            period="1d",
            progress=False,
            auto_adjust=False
        )

        if df is None or df.empty:
            return None

        # ===== RESET INDEX =====
        df = df.reset_index()

        # ===== FLATTEN MULTI INDEX COLUMNS =====
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        # ===== CLEAN COLUMN NAMES =====
        df.columns = [str(col).lower().strip() for col in df.columns]

        # ===== REQUIRED COLUMNS =====
        required = ["open", "high", "low", "close"]

        for col in required:
            if col not in df.columns:
                print(f"{symbol} missing column: {col}")
                return None

        # ===== FORCE NUMERIC =====
        for col in required:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # ===== DROP BAD ROWS =====
        df = df.dropna(subset=required)

        if len(df) == 0:
            return None

        return df

    except Exception as e:
        print(f"Data error {symbol}: {e}")
        return None

# ===== FETCH ONCE =====
def fetch_all_data():

    global data_cache
    data_cache = {}

    for symbol in symbols:

        df = get_data(symbol)

        if df is not None and len(df) > 0:
            data_cache[symbol] = df

# ===== PNL =====
def calculate_pnl(trade, exit_price):

    if trade["type"] == "BUY":
        gross = (exit_price - trade["entry"]) * trade["qty"]

    else:
        gross = (trade["entry"] - exit_price) * trade["qty"]

    turnover = (
        (trade["entry"] * trade["qty"]) +
        (exit_price * trade["qty"])
    )

    charges = (turnover * 0.0005) + 40

    net = gross - charges

    return gross, charges, net

# ===== MAIN =====
def run():

    global balance

    send("ORB BOT STARTED 🚀")

    while True:

        try:

            now = datetime.now(ist)
            current_time = now.strftime("%H:%M")

            print(f"\nTIME: {current_time}")

            # ===== MARKET HOURS =====
            if current_time < "09:15" or current_time > "15:30":
                print("Market Closed")
                time.sleep(60)
                continue

            # ===== FETCH DATA =====
            fetch_all_data()

            # =====================================================
            # ===== BUILD OPENING RANGE =====
            # =====================================================

            if "09:15" <= current_time <= "09:30":

                print("Building ORB Range")

                for symbol, df in data_cache.items():

                    try:

                        last = df.iloc[-1]

                        high_value = float(last["high"])
                        low_value = float(last["low"])

                        if symbol not in range_data:

                            range_data[symbol] = {
                                "high": high_value,
                                "low": low_value
                            }

                        else:

                            range_data[symbol]["high"] = max(
                                float(range_data[symbol]["high"]),
                                high_value
                            )

                            range_data[symbol]["low"] = min(
                                float(range_data[symbol]["low"]),
                                low_value
                            )

                        print(
                            f"{symbol} RANGE "
                            f"HIGH={range_data[symbol]['high']:.2f} "
                            f"LOW={range_data[symbol]['low']:.2f}"
                        )

                    except Exception as e:
                        print(f"Range Error {symbol}: {e}")

            # =====================================================
            # ===== BREAKOUT ENTRIES =====
            # =====================================================

            if current_time > "09:30":

                for symbol, df in data_cache.items():

                    try:

                        if symbol in done_stocks:
                            continue

                        if symbol not in range_data:
                            continue

                        if len(df) < 2:
                            continue

                        last = df.iloc[-1]

                        close = float(last["close"])

                        high = float(range_data[symbol]["high"])
                        low = float(range_data[symbol]["low"])

                        # =========================================
                        # BUY BREAKOUT
                        # =========================================

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

                            send(
                                f"BUY 🚀 {symbol}\n"
                                f"Entry: {entry:.2f}\n"
                                f"SL: {sl:.2f}\n"
                                f"Qty: {qty}"
                            )

                            print(f"BUY {symbol}")

                        # =========================================
                        # SELL BREAKOUT
                        # =========================================

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

                            send(
                                f"SELL 🔻 {symbol}\n"
                                f"Entry: {entry:.2f}\n"
                                f"SL: {sl:.2f}\n"
                                f"Qty: {qty}"
                            )

                            print(f"SELL {symbol}")

                    except Exception as e:
                        print(f"Breakout Error {symbol}: {e}")

            # =====================================================
            # ===== TRADE MANAGEMENT =====
            # =====================================================

            for trade in active_trades[:]:

                try:

                    symbol = trade["symbol"]

                    if symbol not in data_cache:
                        continue

                    df = data_cache[symbol]

                    if len(df) < 2:
                        continue

                    last = df.iloc[-1]
                    prev = df.iloc[-2]

                    price = float(last["close"])

                    prev_high = float(prev["high"])
                    prev_low = float(prev["low"])

                    entry = trade["entry"]
                    risk = trade["risk"]

                    # =========================================
                    # PARTIAL
                    # =========================================

                    if not trade["partial"]:

                        if (
                            trade["type"] == "BUY"
                            and price >= entry + risk
                        ):

                            trade["partial"] = True
                            trade["sl"] = entry

                            send(f"PARTIAL 💰 {symbol}")

                        elif (
                            trade["type"] == "SELL"
                            and price <= entry - risk
                        ):

                            trade["partial"] = True
                            trade["sl"] = entry

                            send(f"PARTIAL 💰 {symbol}")

                    # =========================================
                    # TRAILING STOP
                    # =========================================

                    if trade["partial"]:

                        if trade["type"] == "BUY":

                            if prev_low > trade["sl"]:
                                trade["sl"] = prev_low

                        else:

                            if prev_high < trade["sl"]:
                                trade["sl"] = prev_high

                    # =========================================
                    # EXITS
                    # =========================================

                    if (
                        trade["type"] == "BUY"
                        and price <= trade["sl"]
                    ):

                        gross, charges, net = calculate_pnl(
                            trade,
                            price
                        )

                        balance += net

                        send(
                            f"EXIT 🚪 BUY {symbol}\n"
                            f"Exit: {price:.2f}\n"
                            f"Gross: {gross:.2f}\n"
                            f"Charges: {charges:.2f}\n"
                            f"Net: {net:.2f}\n"
                            f"Balance: {balance:.2f}"
                        )

                        active_trades.remove(trade)

                        print(f"EXIT BUY {symbol}")

                    elif (
                        trade["type"] == "SELL"
                        and price >= trade["sl"]
                    ):

                        gross, charges, net = calculate_pnl(
                            trade,
                            price
                        )

                        balance += net

                        send(
                            f"EXIT 🚪 SELL {symbol}\n"
                            f"Exit: {price:.2f}\n"
                            f"Gross: {gross:.2f}\n"
                            f"Charges: {charges:.2f}\n"
                            f"Net: {net:.2f}\n"
                            f"Balance: {balance:.2f}"
                        )

                        active_trades.remove(trade)

                        print(f"EXIT SELL {symbol}")

                except Exception as e:
                    print(f"Trade Management Error: {e}")

            # ===== LOOP DELAY =====
            time.sleep(60)

        except Exception as e:

            print(f"MAIN LOOP ERROR: {e}")

            send(f"BOT ERROR ⚠️\n{e}")

            time.sleep(60)

# ===== START =====
run()
