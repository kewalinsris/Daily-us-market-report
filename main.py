import os
import requests

LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]

url = "https://api.line.me/v2/bot/message/push"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
}

payload = {
    "to": LINE_USER_ID,
    "messages": [
        {
            "type": "text",
            "text": "✅ ทดสอบระบบสำเร็จ\nGitHub Actions สามารถส่งข้อความเข้า LINE ได้แล้ว"
        }
    ]
}

response = requests.post(url, headers=headers, json=payload)

print("Status:", response.status_code)
print(response.text)

response.raise_for_status()
