import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.holiday import is_market_open

def test():
    print("Testing holiday checker...")
    res = is_market_open()
    print("Is market open today?", res)

if __name__ == "__main__":
    test()
