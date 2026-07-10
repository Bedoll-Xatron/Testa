from pykrx import stock
import sqlite3
from datetime import datetime

def collect():
    conn=sqlite3.connect('krx_data.db')
    tickers=stock.get_market_ticker_list("KOSPI")+stock.get_market_ticker_list("KOSDAQ")
    for t in tickers[:100]:
        df=stock.get_market_ohlcv("20140101",datetime.now().strftime('%Y%m%d'),t)
        df.to_sql('ohlcv',conn,if_exists='append')
    conn.close()
if __name__=='__main__': collect()
