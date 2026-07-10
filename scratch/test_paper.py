import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from live.broker_paper import PaperBroker

def test():
    print("=== Paper Broker Test ===")
    broker = PaperBroker()
    print("Initial Cash:", broker.get_available_cash())
    
    print("\n--- Buy 005930 (Samsung) ---")
    res = broker.send_order("005930", 10, "buy")
    print("Buy Result:", res)
    
    print("\n--- Current Balance ---")
    print(broker.get_balance())
    print("Available Cash:", broker.get_available_cash())
    
    print("\n--- Sell 005930 (Samsung) ---")
    # For testing profit/loss, we just sell it back at current price (should be ~0% profit minus rounding, or slightly different if price changed)
    res = broker.send_order("005930", 10, "sell")
    print("Sell Result:", res)
    
    print("\n--- Win Rate Stats ---")
    print(broker.get_win_rate_stats())

if __name__ == "__main__":
    test()
