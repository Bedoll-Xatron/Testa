import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from live.broker_paper import PaperBroker

def check_results():
    broker = PaperBroker()
    print("=== 현재 가상 매매(Paper Trading) 계좌 상태 ===")
    cash = broker.get_available_cash()
    total_eval = broker.get_total_capital()
    print(f"가용 현금: {cash:,.0f} 원")
    print(f"총 평가 자산: {total_eval:,.0f} 원")
    
    holdings = broker.get_balance()
    if not holdings:
        print("\n현재 보유 중인 종목이 없습니다.")
    else:
        print("\n=== 보유 종목 ===")
        for h in holdings:
            ticker = h['pdno']
            name = h.get('prdt_name', ticker)
            qty = int(h['hldg_qty'])
            if qty == 0: continue
            avg_price = float(h['pchs_avg_pric'])
            
            cur_price = broker.get_current_price(ticker)
            if not cur_price:
                cur_price = avg_price # API 조회가 안되면 매입가로 처리
                
            pnl_pct = ((cur_price / avg_price) - 1) * 100
            print(f"- {name}({ticker}) : {qty}주 | 매입가: {avg_price:,.0f}원 | 현재가: {cur_price:,.0f}원 | 수익률: {pnl_pct:+.2f}%")
            
    # 매매 승률 통계 출력
    stats = broker.get_win_rate_stats()
    print("\n=== 누적 매매 통계 ===")
    print(f"총 매도 횟수: {stats['total_trades']}회")
    print(f"승률: {stats['win_rate']:.1f}%")
    print(f"평균 수익률: {stats['avg_pnl']:+.2f}%")

if __name__ == "__main__":
    check_results()
