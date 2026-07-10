"""
scanner_vwap_genius.py

유튜브 "1천억 단타 천재" 거래량 매매법(VWAP 전략) 스캐너
- KIS API 실시간 분봉(장중 데이터) 활용
- VWAP 지지 여부 판별
- 볼린저밴드, RSI, MACD 다중 지표 스코어링 결합
"""

import pandas as pd
from strategy.ai_scorer import TestaScorer
from datetime import datetime

def main():
    print("=== 1천억 단타 천재 실시간 VWAP 스캐너 시작 ===")
    dt_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"기준시간: {dt_str}")
    
    scorer = TestaScorer()
    
    # 전략 실행 (총자산은 임시로 1000만원 가정)
    results = scorer.scan_market(total_capital=10000000)
    
    print("\n=== [스캐너 포착 종목] VWAP 지지 및 보조지표 턴어라운드 ===")
    if not results:
        print("포착된 종목이 없습니다.")
    else:
        df_res = pd.DataFrame(results)
        for _, row in df_res.iterrows():
            print(f"[매수] {row['name']} ({row['ticker']}) | 종가: {row['price']:,}원 | VWAP: {row['vwap']:,}원 | 점수: {row['score']}점 | 사유: {row['reason']}")

if __name__ == "__main__":
    main()
