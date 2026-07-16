import json
import re
from openai import OpenAI
from config import config
from utils.news_fetcher import fetch_recent_news, fetch_recent_notices
from utils.logger import logger

class AITradingAgent:
    def __init__(self):
        self.api_key = getattr(config, 'NVIDIA_API_KEY', None)
        self.client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=self.api_key) if self.api_key else None
        
        self.primary_model = "meta/llama-3.1-70b-instruct"
        self.fallback_model = "meta/llama-3.1-70b-instruct"
        self.current_model = self.primary_model
        
    def evaluate_stock(self, ticker: str, name: str, current_price: int, chart_reason: str) -> dict:
        """뉴스 및 공시 데이터를 바탕으로 2차 필터링(Veto)을 수행하여 최종 매수 여부를 결정합니다."""
        if not self.client:
            logger.warning("NVIDIA API Key가 없어 AI 에이전트 분석을 건너뜁니다.")
            return {"decision": "BUY", "confidence": 100, "reason": "AI 통신 불가로 차트 알고리즘 채택"}
            
        # 뉴스 및 공시 스크래핑 (Tool 사용 대체)
        news_headlines = fetch_recent_news(ticker, limit=5)
        dart_notices = fetch_recent_notices(ticker, limit=5)
        
        system_msg = "당신은 상위 1% 수익률을 올리는 수석 퀀트 트레이더이자 냉철한 리스크 관리자입니다. 응답은 반드시 JSON 포맷으로만 출력하세요."
        user_msg = f"""
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
        위 정보(차트 통과 사유, 최근 뉴스 흐름, DART 공시 내용)를 종합적으로 평가하여, 이 종목이 현재 장에서 단기적(수일 내) 수익을 낼 수 있는 적극적인 투자 대상인지 판별하세요.
        - 매우 유망하고 강한 모멘텀이 있다면 "STRONG BUY"
        - 양호한 상승 여력이 있다면 "BUY"
        - 애매하거나 지켜봐야 한다면 "HOLD"
        - 치명적 악재(유상증자, 배임 등)가 있거나 전혀 모멘텀이 없다면 "PASS"
        
        응답은 반드시 아래 JSON 형식으로만 출력하세요. (마크다운 백틱 없이 순수 JSON만 작성할 것)
        {{
            "decision": "STRONG BUY" 또는 "BUY" 또는 "HOLD" 또는 "PASS",
            "confidence": 0~100 사이의 정수 (결정에 대한 확신도, 70점 이상일 때만 실제 매수됨),
            "reason": "결정 사유 1줄 요약 (차트, 뉴스, 공시를 종합한 핵심 근거)"
        }}
        """
        
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=messages
            )
            text = response.choices[0].message.content.strip()
            text = re.sub(r'```[a-zA-Z]*', '', text).replace('```', '').strip()
            result = json.loads(text)
            
        except Exception as e:
            logger.warning(f"[{ticker}] {self.current_model} 분석 중 오류(또는 토큰 에러) 발생: {e}. 대체 모델로 전환합니다.")
            # 에러 발생 시 수시로 모델 스왑
            if self.current_model == self.primary_model:
                self.current_model = self.fallback_model
            else:
                self.current_model = self.primary_model
                
            try:
                response = self.client.chat.completions.create(
                    model=self.current_model,
                    messages=messages
                )
                text = response.choices[0].message.content.strip()
                text = re.sub(r'```[a-zA-Z]*', '', text).replace('```', '').strip()
                result = json.loads(text)
                
            except Exception as e2:
                logger.error(f"[{ticker}] 대체 모델({self.current_model}) 분석 중 오류 발생: {e2}")
                return {"decision": "BUY", "confidence": 100, "reason": "AI 분석(두 모델 모두) 실패로 차트 알고리즘 채택"}
                
        decision = result.get('decision', 'BUY').upper()
        confidence = int(result.get('confidence', 50))
        reason = result.get('reason', '분석 사유 파싱 실패')
        
        if decision not in ["STRONG BUY", "BUY", "HOLD", "PASS"]:
            decision = "PASS"
            
        return {"decision": decision, "confidence": confidence, "reason": reason}
