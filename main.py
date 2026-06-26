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
    print(response.status_code)
    print(response.text)
    response.raise_for_status()

def get_market_report():
    spx = yf.Ticker("^GSPC").history(period="1y", interval="1d")
    vix = yf.Ticker("^VIX").history(period="1mo", interval="1d")

    if spx.empty or vix.empty:
        raise ValueError("ไม่สามารถดึงข้อมูลตลาดได้")

    spx_close = spx["Close"].dropna()
    vix_close = vix["Close"].dropna()

    latest_spx = float(spx_close.iloc[-1])
    prev_spx = float(spx_close.iloc[-2])
    spx_change_pct = (latest_spx - prev_spx) / prev_spx * 100

    latest_rsi = float(calculate_rsi(spx_close).dropna().iloc[-1])
    latest_vix = float(vix_close.iloc[-1])

    ma50 = float(spx_close.rolling(50).mean().iloc[-1])
    ma200 = float(spx_close.rolling(200).mean().iloc[-1])

    ath = float(spx_close.max())
    distance_from_ath = (latest_spx - ath) / ath * 100

    date_th = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y")

    rsi_status = "🔴 Overbought" if latest_rsi >= 70 else "🔵 Oversold" if latest_rsi <= 30 else "🟢 Neutral"
    vix_status = "🟢 Low Volatility" if latest_vix < 20 else "🟡 Medium Volatility" if latest_vix < 30 else "🔴 High Volatility"

    trend50 = "เหนือ 50DMA ✅" if latest_spx > ma50 else "ต่ำกว่า 50DMA ⚠️"
    trend200 = "เหนือ 200DMA ✅" if latest_spx > ma200 else "ต่ำกว่า 200DMA ⚠️"

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
• แนวโน้มระยะยาว {"ยังเป็นบวก" if latest_spx > ma200 else "เริ่มอ่อนแอ ควรระวัง"}
• RSI {"เริ่มร้อนแรง" if latest_rsi >= 70 else "เริ่ม Oversold" if latest_rsi <= 30 else "ยังอยู่ในโซนปกติ"}
• ความผันผวน {"สูง" if latest_vix >= 30 else "ปานกลาง" if latest_vix >= 20 else "ยังต่ำ"}

Data source: Yahoo Finance via yfinance
"""
    return message

if __name__ == "__main__":
    report = get_market_report()
    print(report)
    send_line_message(report)
