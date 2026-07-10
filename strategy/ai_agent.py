import json
import re
from google import genai
from config import config
from utils.news_fetcher import fetch_recent_news, fetch_recent_notices
from utils.logger import logger

class AITradingAgent:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = config.GEMINI_BASIC_MODEL # Pro 모델 Quota 제한 방지를 위해 Flash 모델 사용
        
    def evaluate_stock(self, ticker: str, name: str, current_price: int, chart_reason: str) -> dict:
        """뉴스 및 공시 데이터를 바탕으로 2차 필터링(Veto)을 수행하여 최종 매수 여부를 결정합니다."""
        if not self.client:
            logger.warning("Gemini API Key가 없어 AI 에이전트 분석을 건너뜁니다.")
            return {"decision": "BUY", "confidence": 50, "reason": "AI 미사용 (알고리즘 통과)"}
            
        # 뉴스 및 공시 스크래핑 (Tool 사용 대체)
        news_headlines = fetch_recent_news(ticker, limit=5)
        dart_notices = fetch_recent_notices(ticker, limit=5)
        
        prompt = f"""
        당신은 상위 1% 수익률을 올리는 수석 퀀트 트레이더이자 냉철한 리스크 관리자입니다.
        현재 아래 종목이 1차 차트 알고리즘(VWAP 지지 등)을 통과하여 매수 후보에 올랐습니다.
        
        [종목 정보]
        종목코드: {ticker}
        종목명: {name}
        현재가: {current_price}원
        1차 통과사유: {chart_reason}
        
        [오늘의 최신 뉴스 헤드라인]
        {news_headlines}

        [오늘의 최신 DART 전자공시]
        {dart_notices}
        
        임무:
        위 뉴스 헤드라인과 특히 전자공시 내역을 면밀히 분석하여 이 종목에 '치명적인 악재'가 있는지 확인하세요.
        호재나 무난한 뉴스, 단순 테마성 공시라면 "BUY"를 선택하고,
        공시 내역이나 뉴스에 유상증자, 주주배정증자, 배임, 횡령, 거래정지, 검찰조사, 관리종목지정, 감자, 대규모 실적악화 등 주가 하락이 뻔한 치명적 악재가 명시되어 있다면 무조건 "PASS"(매수 거부)를 결정하세요.
        
        응답은 반드시 아래 JSON 형식으로만 출력하세요. (마크다운 백틱 없이 순수 JSON만 작성할 것)
        {{
            "decision": "BUY" 또는 "PASS",
            "confidence": 0~100 사이의 정수 (확신도),
            "reason": "결정 사유 1줄 요약 (공시나 뉴스를 근거로)"
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            text = response.text.strip()
            # JSON 포맷이 마크다운(```)으로 감싸진 경우를 처리
            text = re.sub(r'```[a-zA-Z]*', '', text).replace('```', '').strip()
            
            result = json.loads(text)
            
            decision = result.get('decision', 'BUY').upper()
            confidence = int(result.get('confidence', 50))
            reason = result.get('reason', '분석 사유 파싱 실패')
            
            # 응답 검증
            if decision not in ["BUY", "PASS"]:
                decision = "BUY"
                
            return {"decision": decision, "confidence": confidence, "reason": reason}
            
        except Exception as e:
            logger.error(f"[{ticker}] AI 에이전트 분석 중 오류 발생: {e}")
            # 에러 시 기본적으로 1차 알고리즘 결과를 신뢰
            return {"decision": "BUY", "confidence": 50, "reason": f"AI 분석 실패로 알고리즘 채택"}
