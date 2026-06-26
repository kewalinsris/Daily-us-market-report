import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo


LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]


# =========================
# Indicators
# =========================

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

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period).mean()


def get_rsi_status(rsi_value):
    if rsi_value < 30:
        return "🔵 Oversold"
    if rsi_value > 70:
        return "🔴 Overbought"
    return "🟢 Normal"


def get_vix_status(vix_value):
    if vix_value < 15:
        return "🟢 Very Low"
    if vix_value < 20:
        return "🟢 Low"
    if vix_value < 30:
        return "🟡 Elevated"
    return "🔴 High"


# =========================
# LINE
# =========================

def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }

    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }

    response = requests.post(url, headers=headers, json=payload)
    print("LINE status:", response.status_code)
    print(response.text)
    response.raise_for_status()


# =========================
# Buy the Dip Logic v2.0
# =========================

def build_buy_the_dip_logic(
    latest_spx,
    latest_rsi,
    latest_vix,
    distance_from_ath,
    ma200,
    atr_percent,
):
    core_score = 0
    reasons = []

    if distance_from_ath <= -10:
        core_score += 1
        reasons.append("✓ ตลาดย่อตัวมากกว่า 10% จากจุดสูงสุด")

    if latest_vix > 25:
        core_score += 1
        reasons.append("✓ VIX สูงกว่า 25 แสดงว่าตลาดเริ่มมีความกังวล")

    if latest_rsi < 35:
        core_score += 1
        reasons.append("✓ RSI ต่ำกว่า 35 ตลาดเริ่มเข้าสู่ภาวะ Oversold")

    atr_is_high = atr_percent >= 3.5

    if core_score < 2:
        return "🟢 Continue DCA", "❌ Not Yet"

    if latest_spx > ma200:
        dca_status = "🟢 DCA + Buy the Dip (Top-up)"
        buy_dip_text = (
            "🔵 Strong\n\n"
            "เหตุผล\n"
            + "\n".join(reasons)
            + "\n✓ ราคาอยู่เหนือ 200 DMA แนวโน้มระยะยาวยังแข็งแรง"
        )
    else:
        dca_status = "🟢 DCA + Buy the Dip (Gradual)"
        buy_dip_text = (
            "🔵 Gradual / DCA\n\n"
            "เหตุผล\n"
            + "\n".join(reasons)
            + "\n✓ ราคาอยู่ต่ำกว่า 200 DMA จึงควรทยอยซื้อแบ่งไม้ ไม่ควรใส่เงินก้อนทีเดียว"
        )

    if atr_is_high:
        buy_dip_text += (
            "\n⚠️ ATR สูงผิดปกติ ตลาดยังผันผวนมาก "
            "ควรทยอยสะสมช้าลงหรือรอ 1–2 วันให้ตลาดนิ่งขึ้น"
        )

    return dca_status, buy_dip_text


# =========================
# Market Report
# =========================

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
    previous_spx = float(close.iloc[-2])
    spx_change_pct = (latest_spx - previous_spx) / previous_spx * 100

    latest_rsi = float(calculate_rsi(close).dropna().iloc[-1])
    latest_vix = float(vix_close.iloc[-1])

    ma50 = float(close.rolling(50).mean().iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1])

    atr_series = calculate_atr(high, low, close).dropna()
    latest_atr = float(atr_series.iloc[-1])
    atr_percent = latest_atr / latest_spx * 100

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

    dca_status, buy_dip_text = build_buy_the_dip_logic(
        latest_spx=latest_spx,
        latest_rsi=latest_rsi,
        latest_vix=latest_vix,
        distance_from_ath=distance_from_ath,
        ma200=ma200,
        atr_percent=atr_percent,
    )

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

