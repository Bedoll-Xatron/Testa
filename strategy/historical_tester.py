import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import os
import csv

def calc_indicators(df):
    if df.empty: return df
    
    df['typical_price'] = (df['고가'] + df['저가'] + df['종가']) / 3
    df['pv'] = df['typical_price'] * df['거래량']
    df['vwap'] = df['pv'].rolling(window=20).sum() / df['거래량'].rolling(window=20).sum()
    
    df['ma20'] = df['종가'].rolling(window=20).mean()
    df['std20'] = df['종가'].rolling(window=20).std()
    df['bb_lower'] = df['ma20'] - (df['std20'] * 2)
    df['bb_upper'] = df['ma20'] + (df['std20'] * 2)
    
    exp1 = df['종가'].ewm(span=12, adjust=False).mean()
    exp2 = df['종가'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    delta = df['종가'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

def run_10y_backtest(ticker, name):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3650)
    end_date_str = end_date.strftime("%Y%m%d")
    start_date_str = start_date.strftime("%Y%m%d")
    
    try:
        df = stock.get_market_ohlcv(start_date_str, end_date_str, ticker)
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
                if abs(close - vwap) / vwap <= 0.01: score += 40
                if bb_lower > 0 and (close - bb_lower) / bb_lower <= 0.02 and close >= bb_lower: score += 30
                if rsi <= 40: score += 15
                if macd > macd_signal and prev_macd <= prev_macd_signal: score += 15
                elif macd > macd_signal: score += 5
                    
                if score >= 50:
                    pos = 1
                    entry_price = close
                    trades.append({'date': df.index[i], 'type': 'BUY', 'price': close})
            
            elif pos == 1:
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
        
        res = {
            'ticker': ticker,
            'name': name,
            'total_return': total_return,
            'win_rate': win_rate,
            'num_trades': len(sells),
            'mdd': mdd * 100
        }
        
        save_backtest_result(res)
        return res
    except Exception as e:
        print(f"[Historical Test Error] {ticker}: {e}")
        return None

def save_backtest_result(res):
    if not res: return
    
    os.makedirs('data', exist_ok=True)
    csv_file = 'data/daily_backtest_results.csv'
    file_exists = os.path.isfile(csv_file)
    
    with open(csv_file, mode='a', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['date', 'ticker', 'name', 'total_return', 'win_rate', 'num_trades', 'mdd']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
            
        writer.writerow({
            'date': datetime.now().strftime("%Y-%m-%d"),
            'ticker': res['ticker'],
            'name': res['name'],
            'total_return': round(res['total_return'], 2),
            'win_rate': round(res['win_rate'], 2),
            'num_trades': res['num_trades'],
            'mdd': round(res['mdd'], 2)
        })
