import pandas as pd
from pykrx import stock
from datetime import datetime
import time

def calc_indicators(df):
    if df.empty: return df
    
    # VWAP (20-day rolling for daily swing approximation)
    df['typical_price'] = (df['고가'] + df['저가'] + df['종가']) / 3
    df['pv'] = df['typical_price'] * df['거래량']
    df['vwap'] = df['pv'].rolling(window=20).sum() / df['거래량'].rolling(window=20).sum()
    
    # BB (20, 2)
    df['ma20'] = df['종가'].rolling(window=20).mean()
    df['std20'] = df['종가'].rolling(window=20).std()
    df['bb_lower'] = df['ma20'] - (df['std20'] * 2)
    df['bb_upper'] = df['ma20'] + (df['std20'] * 2)
    
    # MACD (12, 26, 9)
    exp1 = df['종가'].ewm(span=12, adjust=False).mean()
    exp2 = df['종가'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # RSI (14)
    delta = df['종가'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def run_backtest(ticker, name):
    start_date = "20160520"
    end_date = "20260520"
    
    df = stock.get_market_ohlcv(start_date, end_date, ticker)
    if df.empty: return None
    
    df = calc_indicators(df)
    
    pos = 0
    entry_price = 0
    trades = []
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        
        if pd.isna(row['vwap']) or pd.isna(row['macd_signal']):
            continue
            
        close = row['종가']
        vwap = row['vwap']
        bb_lower = row['bb_lower']
        rsi = row['rsi']
        macd = row['macd']
        macd_signal = row['macd_signal']
        prev_macd = prev_row['macd']
        prev_macd_signal = prev_row['macd_signal']
        ma20 = row['ma20']
        
        if pos == 0:
            score = 0
            # VWAP 지지 (±1% 이내) - 40점
            if abs(close - vwap) / vwap <= 0.01:
                score += 40
            # BB 하단 지지 근접 (±2% 이내) - 30점
            if bb_lower > 0 and (close - bb_lower) / bb_lower <= 0.02 and close >= bb_lower:
                score += 30
            # RSI 과매도 (<= 40) - 15점
            if rsi <= 40:
                score += 15
            # MACD 골크 - 15점
            if macd > macd_signal and prev_macd <= prev_macd_signal:
                score += 15
            elif macd > macd_signal:
                score += 5
                
            if score >= 50:
                pos = 1
                entry_price = close
                trades.append({'date': df.index[i], 'type': 'BUY', 'price': close})
        
        elif pos == 1:
            # Sell condition: 20MA 2% break or VWAP 2% break or +5% profit (simple rule)
            if close < ma20 * 0.98 or close < vwap * 0.98 or close > entry_price * 1.05:
                pos = 0
                ret = (close / entry_price) - 1
                eq *= (1 + ret)
                peak = max(peak, eq)
                mdd = min(mdd, (eq / peak) - 1)
                trades.append({'date': df.index[i], 'type': 'SELL', 'price': close, 'ret': ret})
                
    sells = [t for t in trades if t['type'] == 'SELL']
    win_rate = sum(1 for t in sells if t['ret'] > 0) / len(sells) * 100 if sells else 0
    total_return = (eq - 1) * 100
    
    return {
        'name': name,
        'total_return': total_return,
        'win_rate': win_rate,
        'num_trades': len(sells),
        'mdd': mdd * 100
    }

tickers = [
    ("055550", "신한지주"),
    ("005930", "삼성전자"),
    ("105560", "KB금융"),
    ("051910", "LG화학"),
    ("035420", "NAVER")
]

results = []
for t, n in tickers:
    print(f"Backtesting {n} ({t}) for 10 years...")
    res = run_backtest(t, n)
    if res:
        results.append(res)
    time.sleep(1)

print("\n=== 10년 백테스트 결과 (Daily Swing Approximation) ===")
for r in results:
    print(f"[{r['name']}] 누적수익률: {r['total_return']:.2f}% | 승률: {r['win_rate']:.1f}% | 매매횟수: {r['num_trades']}회 | MDD: {r['mdd']:.2f}%")
