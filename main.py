import os
import requests
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo


LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_atr(high, low, close, period=14):
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = tr1.to_frame("tr1")
    true_range["tr2"] = tr2
    true_range["tr3"] = tr3

    return true_range.max(axis=1).rolling(period).mean()


def get_rsi_status(rsi):
    if rsi < 30:
        return "🔵 Oversold"
    if rsi > 70:
        return "🔴 Overbought"
    return "🟢 Normal"


def get_vix_status(vix):
    if vix < 15:
        return "🟢 Very Low"
    if vix < 20:
        return "🟢 Low"
    if vix < 30:
        return "🟡 Elevated"
    return "🔴 High"


def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": text,
            }
        ],
    }

    response = requests.post(url, headers=headers, json=payload)
    print("LINE status:", response.status_code)
    print(response.text)
    response.raise_for_status()


def get_market_report():
    spx = yf.Ticker("^GSPC").history(period="1y", interval="1d")
    vix_data = yf.Ticker("^VIX").history(period="1mo", interval="1d")

    if spx.empty:
        raise ValueError("ไม่สามารถดึงข้อมูล S&P 500 ได้")

    if vix_data.empty:
        raise ValueError("ไม่สามารถดึงข้อมูล VIX ได้")

    close = spx["Close"].dropna()
    high = spx["High"].dropna()
    low = spx["Low"].dropna()
    vix_close = vix_data["Close"].dropna()

    latest_spx = float(close.iloc[-1])
    prev_spx = float(close.iloc[-2])
    spx_change_pct = (latest_spx - prev_spx) / prev_spx * 100

    latest_rsi = float(calculate_rsi(close).dropna().iloc[-1])
    latest_vix = float(vix_close.iloc[-1])

    ma50 = float(close.rolling(50).mean().iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])

    atr = calculate_atr(high, low, close).dropna()
    latest_atr = float(atr.iloc[-1])
    atr_pct = latest_atr / latest_spx * 100

    ath = float(close.max())
    distance_from_ath = (latest_spx - ath) / ath * 100

    rsi_status = get_rsi_status(latest_rsi)
    vix_status = get_vix_status(latest_vix)

    trend_50 = (
        "🟢 ระยะกลาง (50 DMA): ขาขึ้น"
        if latest_spx > ma50
        else "🔴 ระยะกลาง (50 DMA): ขาลง"
    )

    trend_200 = (
        "🟢 ระยะยาว (200 DMA): ขาขึ้น"
        if latest_spx > ma200
        else "🔴 ระยะยาว (200 DMA): ขาลง"
    )

    dca_status = "🟢 Continue" if latest_spx > ma200 else "🟡 Review"

    buy_the_dip = (
        latest_rsi < 30
        and latest_vix > 25
        and distance_from_ath <= -10
        and latest_spx > ma200
        and latest_spx < ema20
        and atr_pct < 3.5
    )

    if buy_the_dip:
        buy_dip_text = "\n".join(
            [
                "🔵 Yes",
                "",
                "เหตุผลที่ควร Buy the Dip",
                "✓ RSI อยู่ในภาวะ Oversold",
                "✓ VIX สูงกว่า 25 ตลาดมีความกังวล",
                "✓ ตลาดย่อตัวมากกว่า 10% จาก ATH",
                "✓ แนวโน้มระยะยาวยังเป็นขาขึ้น",
                "✓ ราคาอยู่ต่ำกว่า EMA20",
                "✓ ATR ยังไม่สูงผิดปกติ",
            ]
        )
    else:
        buy_dip_text = "❌ Not Yet"

    date_th = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y")

    message = f"""📊 Daily US Market Report
ประจำวันที่ {date_th}

━━━━━━━━━━━━━━

S&P 500
{latest_spx:,.2f} ({spx_change_pct:+.2f}%)

RSI (14)
{rsi_status} ({latest_rsi:.1f})

VIX
{vix_status} ({latest_vix:.1f})

Trend
{trend_50}
{trend_200}

ระดับราคา
{abs(distance_from_ath):.2f}% ต่ำกว่าจุดสูงสุด (ATH)

━━━━━━━━━━━━━━

DCA
{dca_status}

Buy the Dip
{buy_dip_text}
"""

    return message


if __name__ == "__main__":
    report = get_market_report()
    print(report)
    send_line_message(report)
