import requests
from bs4 import BeautifulSoup
from utils.logger import logger

def fetch_recent_news(ticker: str, limit: int = 5) -> str:
    """네이버 금융 종목 뉴스 탭에서 최신 기사 헤드라인을 수집하여 텍스트로 반환합니다."""
    url = f"https://finance.naver.com/item/news_news.naver?code={ticker}&page=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "lxml")
        news_titles = soup.select(".title a")
        
        if not news_titles:
            return "최신 뉴스가 없습니다."
            
        headlines = []
        for a_tag in news_titles[:limit]:
            headlines.append(f"- {a_tag.text.strip()}")
            
        return "\n".join(headlines)
        
    except Exception as e:
        logger.error(f"[{ticker}] 뉴스 수집 오류: {e}")
        return "뉴스 데이터를 가져올 수 없습니다."

def fetch_recent_notices(ticker: str, limit: int = 5) -> str:
    """네이버 금융 종목 공시 탭에서 최신 전자공시 제목을 수집하여 텍스트로 반환합니다."""
    url = f"https://finance.naver.com/item/news_notice.naver?code={ticker}&page=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "lxml")
        notice_titles = soup.select(".title a")
        
        if not notice_titles:
            return "최신 공시가 없습니다."
            
        notices = []
        for a_tag in notice_titles[:limit]:
            notices.append(f"- {a_tag.text.strip()}")
            
        return "\n".join(notices)
        
    except Exception as e:
        logger.error(f"[{ticker}] 공시 수집 오류: {e}")
        return "공시 데이터를 가져올 수 없습니다."
