import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]


def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": text}]}
    r = requests.post(url, headers=headers, json=payload)
    print(r.status_code)
    print(r.text)
    r.raise_for_status()


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_atr(high, low, close, period=14):
    prev = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev).abs(), (low - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def rsi_status(value):
    if value < 30:
        return "🔵 Oversold"
    if value > 70:
        return "🔴 Overbought"
    return "🟢 Normal"


def vol_status(value):
    if value < 15:
        return "🟢 Very Low"
    if value < 20:
        return "🟢 Low"
    if value < 30:
        return "🟡 Elevated"
    return "🔴 High"


def fetch_history(ticker, period="1y"):
    data = yf.Ticker(ticker).history(period=period, interval="1d")
    if data.empty:
        raise ValueError(f"ไม่สามารถดึงข้อมูล {ticker} ได้")
    return data


def fetch_volatility(primary_ticker, fallback_ticker="^VIX"):
    try:
        data = fetch_history(primary_ticker, "1mo")
        return data, primary_ticker
    except Exception:
        data = fetch_history(fallback_ticker, "1mo")
        return data, fallback_ticker


def build_sp500_buy_logic(price, rsi, vol, drawdown, ma200, atr_percentile):
    core_score = 0
    reasons = []

    if drawdown <= -10:
        core_score += 1
        reasons.append("✓ ตลาดย่อตัวมากกว่า 10% จากจุดสูงสุด")

    if vol > 25:
        core_score += 1
        reasons.append("✓ VIX สูงกว่า 25 แสดงว่าตลาดเริ่มมีความกังวล")

    if rsi < 35:
        core_score += 1
        reasons.append("✓ RSI ต่ำกว่า 35 ตลาดเริ่มเข้าสู่ภาวะ Oversold")

    if core_score < 2:
        return "🟢 Continue DCA", "❌ Not Yet"

    if price > ma200:
        dca = "🟢 DCA + Buy the Dip (Top-up)"
        action = (
            "🔵 Strong\n\n"
            "เหตุผล\n"
            + "\n".join(reasons)
            + "\n✓ ราคาอยู่เหนือ 200 DMA แนวโน้มระยะยาวยังแข็งแรง"
        )
    else:
        dca = "🟢 DCA + Buy the Dip (Gradual)"
        action = (
            "🔵 Gradual / DCA\n\n"
            "เหตุผล\n"
            + "\n".join(reasons)
            + "\n✓ ราคาอยู่ต่ำกว่า 200 DMA จึงควรทยอยซื้อแบ่งไม้ ไม่ควรใส่เงินก้อนทีเดียว"
        )

    if atr_percentile >= 80:
        action += "\n⚠️ ตลาดยังผันผวนสูง ควรทยอยสะสมเป็นหลายไม้"

    return dca, action


def build_nasdaq_buy_logic(price, rsi, vol, drawdown, ma200, atr_percentile, vol_name):
    core_score = 0
    reasons = []

    if rsi < 38:
        core_score += 1
        reasons.append("✓ RSI ต่ำกว่า 38 ตลาดเริ่มเข้าโซน Near Oversold")

    if vol > 28:
        core_score += 1
        reasons.append(f"✓ {vol_name} สูงกว่า 28 แสดงว่าหุ้นเทคเริ่มมีความกังวล")

    if drawdown <= -10:
        core_score += 1
        reasons.append("✓ NASDAQ 100 ย่อตัวมากกว่า 10% จากจุดสูงสุด")

    if core_score >= 2:
        if price > ma200:
            dca = "🟢 DCA + Buy the Dip (Top-up)"
            action = (
                "🔵 Strong\n\n"
                "เหตุผล\n"
                + "\n".join(reasons)
                + "\n✓ ราคาอยู่เหนือ 200 DMA แนวโน้มระยะยาวยังแข็งแรง"
            )
        else:
            dca = "🟢 DCA + Buy the Dip (Gradual)"
            action = (
                "🔵 Gradual / DCA\n\n"
                "เหตุผล\n"
                + "\n".join(reasons)
                + "\n✓ ราคาอยู่ต่ำกว่า 200 DMA จึงควรทยอยซื้อแบ่งไม้ ไม่ควรใส่เงินก้อนทีเดียว"
            )

        if atr_percentile >= 80:
            action += "\n⚠️ ตลาดยังผันผวนสูง ควรทยอยสะสมเป็นหลายไม้"

        return dca, action

    early_dip = rsi < 40 and drawdown <= -7.5 and price > ma200

    if early_dip:
        dca = "🟢 Continue DCA"
        action = (
            "🟡 Early Dip / Watchlist\n\n"
            "เหตุผล\n"
            "✓ RSI ต่ำกว่า 40 ตลาดเริ่มอ่อนตัว\n"
            "✓ NASDAQ 100 ย่อตัวมากกว่า 7.5% จากจุดสูงสุด\n"
            "✓ ราคาอยู่เหนือ 200 DMA ยังเป็นการพักฐานในแนวโน้มขาขึ้น"
        )

        if atr_percentile >= 80:
            action += "\n⚠️ ตลาดยังผันผวนสูง ควรรอ 1–2 วันหรือทยอยสะสมเป็นหลายไม้"

        return dca, action

    return "🟢 Continue DCA", "❌ Not Yet"


def build_report(name, emoji, price_ticker, vol_ticker, is_nasdaq=False):
    data = fetch_history(price_ticker, "1y")
    vol_data, used_vol_ticker = fetch_volatility(vol_ticker)

    close = data["Close"].dropna()
    high = data["High"].dropna()
    low = data["Low"].dropna()

    price = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    change = (price - prev) / prev * 100

    latest_rsi = float(calculate_rsi(close).dropna().iloc[-1])

    ma50 = float(close.rolling(50).mean().iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])

    ath = float(close.max())
    drawdown = (price - ath) / ath * 100

    atr_series = calculate_atr(high, low, close).dropna()
    atr_percentile = atr_series.tail(252).rank(pct=True).iloc[-1] * 100

    vol_close = vol_data["Close"].dropna()
    latest_vol = float(vol_close.iloc[-1])

    trend50 = "🟢 ระยะกลาง (50 DMA): ขาขึ้น" if price > ma50 else "🔴 ระยะกลาง (50 DMA): ขาลง"
    trend200 = "🟢 ระยะยาว (200 DMA): ขาขึ้น" if price > ma200 else "🔴 ระยะยาว (200 DMA): ขาลง"

    vol_name = "VXN" if used_vol_ticker == "^VXN" else "VIX"

    if is_nasdaq:
        dca, buy_dip = build_nasdaq_buy_logic(
            price, latest_rsi, latest_vol, drawdown, ma200, atr_percentile, vol_name
        )
    else:
        dca, buy_dip = build_sp500_buy_logic(
            price, latest_rsi, latest_vol, drawdown, ma200, atr_percentile
        )

    date_th = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y")

    return f"""{emoji} Daily {name} Report
ประจำวันที่ {date_th}

━━━━━━━━━━━━━━

{name}
{price:,.2f} ({change:+.2f}%)

RSI (14)
{rsi_status(latest_rsi)} ({latest_rsi:.1f})

{vol_name}
{vol_status(latest_vol)} ({latest_vol:.1f})

Trend
{trend50}
{trend200}

ระดับราคา
{abs(drawdown):.2f}% ต่ำกว่าจุดสูงสุด (ATH)

━━━━━━━━━━━━━━

DCA
{dca}

Buy the Dip
{buy_dip}
"""


if __name__ == "__main__":
    sp500_report = build_report(
        name="S&P 500",
        emoji="📊",
        price_ticker="^GSPC",
        vol_ticker="^VIX",
        is_nasdaq=False,
    )

    nasdaq_report = build_report(
        name="NASDAQ 100",
        emoji="📈",
        price_ticker="^NDX",
        vol_ticker="^VXN",
        is_nasdaq=True,
    )

    print(sp500_report)
    send_line_message(sp500_report)

    print(nasdaq_report)
    send_line_message(nasdaq_report)
