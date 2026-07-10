import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import time
from google import genai
from live.broker_kis import KISBroker
from config import config
from strategy.historical_tester import run_10y_backtest
from utils.logger import logger

class TestaScorer:
    def __init__(self):
        self.broker = KISBroker()
        
        # Gemini 설정
        if config.GEMINI_API_KEY:
            self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        else:
            self.client = None
            
        # 전략 가중치 및 설정 파라미터
        self.config = {
            'top_n_volume': 50,       # 거래대금 상위 N개 종목 필터링
            'max_risk_pct': 0.02,     # 1회 진입 시 총 자산의 최대 손실 허용치 (2%)
            'min_score': 50           # 매수 추천을 위한 최소 점수
        }

    def _get_recent_business_day(self):
        """가장 최근 영업일 문자열 반환 (실제 KRX 데이터 기준)"""
        today = datetime.now().strftime("%Y%m%d")
        try:
            df = stock.get_market_ohlcv("20240101", today, "005930")
            if not df.empty:
                return df.index[-1].strftime("%Y%m%d")
        except Exception:
            pass
        return today

    def calc_position_size(self, current_price, stop_loss_price, total_capital):
        """총 자산 대비 2% 리스크(Kelly Rule 응용)를 감안한 포지션 사이징"""
        if total_capital <= 0 or current_price <= stop_loss_price:
            return 0
        
        risk_per_share = current_price - stop_loss_price
        max_loss_amount = total_capital * self.config['max_risk_pct']
        
        qty = int(max_loss_amount / risk_per_share)
        max_qty_by_capital = int((total_capital * 0.3) / current_price)
        return max(1, min(qty, max_qty_by_capital))

    def fetch_and_calc(self, ticker):
        """KIS API를 통해 분봉 데이터를 가져오고 VWAP, BB, RSI, MACD 지표를 계산"""
        bars = self.broker.get_minute_ohlcv(ticker, limit=200)
        if not bars or len(bars) < 120:
            return None
            
        # KIS 분봉은 최신순(내림차순)이므로 과거순(오름차순)으로 뒤집기
        bars = bars[::-1]
        
        df = pd.DataFrame({
            'time': [b['stck_cntg_hour'] for b in bars],
            'open': [int(b['stck_oprc']) for b in bars],
            'high': [int(b['stck_hgpr']) for b in bars],
            'low': [int(b['stck_lwpr']) for b in bars],
            'close': [int(b['stck_prpr']) for b in bars],
            'volume': [int(b['cntg_vol']) for b in bars]
        })
        
        # 1. VWAP (장중 누적 거래량 가중 평균)
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        
        # 2. 볼린저밴드 (기존 20, 2 및 듀얼 BB 120·1, 20·1)
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['std20'] = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['ma20'] + (df['std20'] * 2)
        df['bb_lower'] = df['ma20'] - (df['std20'] * 2)
        
        # 듀얼 BB 추가
        df['bb20_upper_1'] = df['ma20'] + (df['std20'] * 1)
        
        df['ma120'] = df['close'].rolling(window=120).mean()
        df['std120'] = df['close'].rolling(window=120).std()
        df['bb120_upper_1'] = df['ma120'] + (df['std120'] * 1)
        
        # 3. MACD (12, 26, 9)
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        # 4. RSI (14)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df

    def score_ticker(self, df):
        """각 지표를 평가하여 종합 점수(Score) 산출"""
        if df is None or df.empty:
            return 0, [], None
            
        latest = df.iloc[-1]
        score = 0
        reasons = []
        
        close = latest['close']
        vwap = latest['vwap']
        rsi = latest['rsi']
        bb_lower = latest['bb_lower']
        macd = latest['macd']
        macd_signal = latest['macd_signal']
        bb120_upper = latest.get('bb120_upper_1')
        bb20_upper = latest.get('bb20_upper_1')
        
        # 듀얼 BB 조건 1: 대세 상승 (120·1 상단 돌파) (30점)
        if not pd.isna(bb120_upper) and close > bb120_upper:
            score += 30
            reasons.append("120·1 돌파(대세상승)")
            
        # 듀얼 BB 조건 2: 단기 모멘텀 (20·1 상단 돌파) (20점)
        if not pd.isna(bb20_upper) and close >= bb20_upper:
            score += 20
            reasons.append("20·1 돌파(모멘텀)")
        
        # 조건 1: VWAP 지지 (±1% 이내) - 핵심 (40점)
        vwap_proximity = abs(close - vwap) / vwap
        if vwap_proximity <= 0.01:
            score += 40
            reasons.append("VWAP 지지")
            
        # 조건 2: BB 하단 지지 근접 (±2% 이내) (30점)
        bb_proximity = (close - bb_lower) / bb_lower
        if bb_proximity <= 0.02 and close >= bb_lower:
            score += 30
            reasons.append("BB하단 지지")
            
        # 조건 3: RSI 과매도 권역 진입 혹은 탈출 초입 (RSI <= 40) (15점)
        if not pd.isna(rsi) and rsi <= 40:
            score += 15
            reasons.append("RSI 과매도")
            
        # 조건 4: MACD 상향 턴 또는 골든크로스 초입 (15점)
        if not pd.isna(macd) and not pd.isna(macd_signal):
            if macd > macd_signal and df.iloc[-2]['macd'] <= df.iloc[-2]['macd_signal']:
                score += 15
                reasons.append("MACD 골크")
            elif macd > macd_signal:
                # 이미 골크 상태라도 가점 일부 부여
                score += 5
                
        return score, reasons, latest

    def scan_market(self, total_capital=10000000, target_date=None, max_picks=5):
        """전체 시장 스캔 후 다중 지표 점수가 높은 순으로 추천 종목 리스트 반환.

        포지션 사이징: 잔고를 N등분하여 각 종목에 1/N의 50%만 투입.
        """
        if target_date is None:
            target_date = self._get_recent_business_day()

        logger.info(f"[{target_date}] 시장 주도주(거래대금 상위 {self.config['top_n_volume']}) 추출 중...")

        universe = [
            "005930", "000660", "373220", "207940", "005380",
            "068270", "000270", "005490", "105560", "051910",
            "035420", "028260", "012330", "001040", "035720",
            "032830", "066570", "055550", "096770", "033780"
        ][:self.config['top_n_volume']]

        res = []
        logger.info(f"총 {len(universe)}개 종목 실시간 VWAP/지표 분석 중...")

        for ticker in universe:
            try:
                df = self.fetch_and_calc(ticker)
                score, reasons, latest = self.score_ticker(df)

                if score >= self.config['min_score']:
                    price = int(latest['close'])
                    vwap_val = int(latest['vwap'])
                    stop_loss = int(vwap_val * 0.98)

                    res.append({
                        'ticker': ticker,
                        'name': stock.get_market_ticker_name(ticker),
                        'action': 'BUY',
                        'price': price,
                        'vwap': vwap_val,
                        'score': score,
                        'stop_loss': stop_loss,
                        'reason': " + ".join(reasons),
                        'bt_info': "백테스트 생략(실시간 속도 최적화)"
                    })
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"[{ticker}] 분석 중 오류: {e}")

        top_picks = sorted(res, key=lambda x: x['score'], reverse=True)[:max_picks]

        # AI 에이전트 (2차 뉴스 심층 면접)
        from strategy.ai_agent import AITradingAgent
        ai_agent = AITradingAgent()
        
        final_picks = []
        if top_picks:
            logger.info("차트 통과 종목 대상 AI 에이전트 심층 뉴스 분석(Veto 검사) 시작...")
            for pick in top_picks:
                ai_eval = ai_agent.evaluate_stock(
                    ticker=pick['ticker'],
                    name=pick['name'],
                    current_price=pick['price'],
                    chart_reason=pick['reason']
                )
                
                if ai_eval['decision'] == 'BUY':
                    pick['ai_confidence'] = ai_eval['confidence']
                    pick['ai_reason'] = ai_eval['reason']
                    final_picks.append(pick)
                else:
                    logger.info(f"[{pick['ticker']}] AI 거부(VETO): {ai_eval['reason']}")

        # 잔고 1/N의 50% 투입 (N = 실제 최종 통과 종목 수)
        n = len(final_picks)
        if n > 0:
            budget_per_stock = (total_capital / n) * 0.5
            for pick in final_picks:
                pick['qty'] = max(1, int(budget_per_stock / pick['price']))
            logger.info(
                f"포지션 사이징: 잔고 {total_capital:,}원 ÷ {n}종목 × 50% "
                f"= 종목당 {int(budget_per_stock):,}원"
            )

        return final_picks

    def analyze_single_ticker(self, ticker: str) -> str:
        """단일 종목 분석 후 마크다운 포맷 문자열 반환"""
        try:
            df = self.fetch_and_calc(ticker)
            score, reasons, latest = self.score_ticker(df)
            
            if df is None:
                return f"❌ {ticker} 분봉 데이터가 부족합니다 (장중 데이터 필요)"
                
            dt_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            name = stock.get_market_ticker_name(ticker) or ticker
            
            report = f"📊 {name} ({ticker}) 진짜 거래량 매매법 분석 ({dt_str} 기준)\n\n"
            report += f"현재가: {int(latest['close']):,}원\n"
            report += f"VWAP: {int(latest['vwap']):,}원\n"
            report += f"BB 하단: {int(latest['bb_lower']):,}원\n"
            report += f"RSI: {latest['rsi']:.1f}\n"
            report += f"MACD: {latest['macd']:.2f} (Signal: {latest['macd_signal']:.2f})\n\n"
            
            report += f"💡 지표별 평가 점수: **총 {score}점**\n"
            if reasons:
                report += f"✅ 충족 조건: {', '.join(reasons)}\n\n"
            else:
                report += f"❌ 충족된 매수 조건이 없습니다.\n\n"
                
            if score >= self.config['min_score']:
                report += f"🔥 **'강력 매수 타점'**입니다. 1천억 단타 천재가 강조하는 다중 지표 조건(VWAP 지지 등)을 만족합니다!\n\n"
                # 백테스트 실행
                bt_res = run_10y_backtest(ticker, name)
                if bt_res:
                    report += f"📊 **[10년 자동 검증]** 누적수익: +{bt_res['total_return']}%, 승률: {bt_res['win_rate']}%, MDD: {bt_res['mdd']}%\n\n"
            else:
                report += f"⚠️ **'조건 미달'**입니다. 아직 세력의 확고한 지지(VWAP 근접 및 보조지표 턴어라운드)가 보이지 않습니다.\n\n"
                
            # Gemini AI 코멘트 추가
            if self.client:
                prompt = f"""
                당신은 20년차 주식 단타 트레이더이자 1천억 단타 천재의 'VWAP 실전 매매법' 신봉자입니다.
                종목명: {name}
                현재가: {latest['close']}원
                VWAP: {latest['vwap']:.2f}원
                BB하단: {latest['bb_lower']:.2f}원
                RSI: {latest['rsi']:.1f}
                MACD: {latest['macd']:.2f}
                
                위 지표를 보고, 이 종목이 현재 장중 진입하기에 적합한 눌림목 타점인지 3줄 이내로 프로페셔널하게 분석해주세요.
                """
                try:
                    response = self.client.models.generate_content(
                        model=config.GEMINI_BASIC_MODEL,
                        contents=prompt
                    )
                    report += f"🤖 **AI(Gemini) 트레이딩 뷰**\n{response.text.strip()}"
                except Exception as e:
                    report += f"🤖 **AI 분석 오류**: {str(e)}"
                    
            return report
        except Exception as e:
            return f"❌ {ticker} 분석 중 오류가 발생했습니다: {str(e)}"
