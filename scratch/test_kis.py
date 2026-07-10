import requests, json
from config import config

# 1. Get Token
url = f"{config.KIS_BASE_URL}/oauth2/tokenP"
body = {"grant_type":"client_credentials", "appkey":config.KIS_APP_KEY, "appsecret":config.KIS_APP_SECRET}
try:
    res = requests.post(url, headers={"content-type":"application/json"}, data=json.dumps(body), timeout=5)
    print(f"Token Gen Response Status: {res.status_code}")
    print(f"Token Gen Response: {res.text}")
except Exception as e:
    print(f"Error during Token Gen: {e}")

