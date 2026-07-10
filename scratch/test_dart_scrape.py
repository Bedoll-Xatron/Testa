import requests
from bs4 import BeautifulSoup

def test_fetch_dart(ticker: str):
    url = f"https://finance.naver.com/item/news_notice.naver?code={ticker}&page=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "lxml")
        notices = soup.select(".title a")
        if not notices:
            print("No notices found.")
            return
            
        for a in notices[:5]:
            print(a.text.strip())
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_fetch_dart("005930")
