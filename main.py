import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]

def calculate_rsi(close_prices, period=14):
    delta = close_prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def send_line_message(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}]
    }

    response = requests.post(url, headers=headers, json=payload)
    print("LINE status:", response.status_code)
    print(response.text)
    response.raise_for_status()

def get_market_report():
    spx = yf.download("^GSPC", period="1y", interval="1d", progress=False)
    vix = yf.download("^VIX", period="1mo", interval="1d", progress=False)

    if spx.empty or vix.empty:
        raise ValueError("ไม่สามารถดึงข้อมูลตลาดได้")

    spx_close = spx["Close"].dropna()
    vix_close = vix["Close"].dropna()

    latest_spx = float(spx_close.iloc[-1])
    prev_spx = float(spx_close.iloc[-2])
    spx_change_pct = (latest_spx - prev_spx) / prev_spx * 100

    rsi_series = calculate_rsi(spx_close)
    latest_rsi = float(rsi_series.dropna().iloc[-1])

    latest_vix = float(vix_close.iloc[-1])

    ma50 = float(spx_close.rolling(50).mean().dropna().iloc[-1])
    ma200 = float(spx_close.rolling(200).mean().dropna().iloc[-1])
    ath = float(spx_close.max())
    distance_from_ath = (latest_spx - ath) / ath * 100

    date_th = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y")

    if latest_rsi >= 70:
        rsi_status = "🔴 Overbought"
    elif latest_rsi <= 30:
        rsi_status = "🔵 Oversold"
    else:
        rsi_status = "🟢 Neutral"

    if latest_vix < 20:
        vix_status = "🟢 Low Volatility"
    elif latest_vix < 30:
        vix_status = "🟡 Medium Volatility"
    else:
        vix_status = "🔴 High Volatility"

    trend50 = "เหนือ 50DMA ✅" if latest_spx > ma50 else "ต่ำกว่า 50DMA ⚠️"
    trend200 = "เหนือ 200DMA ✅" if latest_spx > ma200 else "ต่ำกว่า 200DMA ⚠️"

    summary = []
    if latest_spx > ma200:
        summary.append("แนวโน้มระยะยาวยังเป็นบวก")
    else:
        summary.append("ราคาต่ำกว่าเส้น 200 วัน ควรระวังแนวโน้ม")

    if latest_rsi >= 70:
        summary.append("ตลาดเริ่มร้อนแรง อาจไม่เหมาะกับการไล่ราคา")
    elif latest_rsi <= 30:
        summary.append("ตลาดเริ่ม Oversold อาจมีโอกาสทยอยสะสม")
    else:
        summary.append("RSI ยังอยู่ในโซนปกติ")

    if latest_vix >= 30:
        summary.append("ความผันผวนสูง ควรระวังความเสี่ยง")
    elif latest_vix < 20:
        summary.append("ความผันผวนยังต่ำ")

    message = f"""📊 Daily US Market Report
ประจำวันที่ {date_th}

S&P 500
{latest_spx:,.2f} ({spx_change_pct:+.2f}%)

RSI(14)
{latest_rsi:.1f} {rsi_status}

VIX
{latest_vix:.2f} {vix_status}

Trend
{trend50}
{trend200}

Distance from ATH
{distance_from_ath:.2f}%

━━━━━━━━━━━━━━
Summary
• {summary[0]}
• {summary[1]}
• {summary[2]}

Data source: Yahoo Finance via yfinance
"""
    return message

if __name__ == "__main__":
    report = get_market_report()
    print(report)
    send_line_message(report)
