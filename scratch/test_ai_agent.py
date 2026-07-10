import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from strategy.ai_agent import AITradingAgent

def test():
    agent = AITradingAgent()
    print("Testing AI Agent on Samsung Electronics...")
    
    res = agent.evaluate_stock(
        ticker="005930",
        name="삼성전자",
        current_price=70000,
        chart_reason="VWAP 지지 및 RSI 과매도"
    )
    
    print("\n[AI Agent Result]")
    print(res)

if __name__ == "__main__":
    test()
