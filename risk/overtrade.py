import sqlite3
from datetime import datetime
from config import config

class RiskManager:
    def __init__(self):
        self.db_path='krx_data.db'; self.init_db()
    def init_db(self):
        conn=sqlite3.connect(self.db_path); c=conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS trade_log(id INTEGER PRIMARY KEY,date TEXT,ticker TEXT,name TEXT,action TEXT,qty INTEGER,price INTEGER,stop_loss INTEGER,order_no TEXT,reason TEXT,confidence REAL,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS daily_risk(date TEXT PRIMARY KEY,trade_count INTEGER DEFAULT 0,realized_pnl INTEGER DEFAULT 0,account_value INTEGER,is_blocked INTEGER DEFAULT 0,block_reason TEXT)')
        conn.commit(); conn.close()
    def check_pre_trade(self,ticker):
        today=datetime.now().strftime('%Y-%m-%d')
        if self.get_today_trade_count(today)>=2: raise Exception("하루 2종목 초과")
        return True
    def get_today_trade_count(self,date):
        conn=sqlite3.connect(self.db_path); c=conn.cursor()
        c.execute("SELECT COUNT(*) FROM trade_log WHERE date=? AND action='BUY'",(date,))
        n=c.fetchone()[0]; conn.close(); return n
    def log_trade(self,ticker,name,qty,price,stop_loss,order_no,reason,conf):
        today=datetime.now().strftime('%Y-%m-%d')
        conn=sqlite3.connect(self.db_path); c=conn.cursor()
        c.execute('INSERT INTO trade_log(date,ticker,name,action,qty,price,stop_loss,order_no,reason,confidence) VALUES (?,?,?,?,?,?,?,?,?,?)',(today,ticker,name,'BUY',qty,price,stop_loss,order_no,reason,conf))
        conn.commit(); conn.close()
    def update_daily_pnl(self,date,pnl):
        conn=sqlite3.connect(self.db_path); c=conn.cursor()
        c.execute('INSERT OR IGNORE INTO daily_risk(date,realized_pnl) VALUES (?,0)',(date,))
        c.execute('UPDATE daily_risk SET realized_pnl=realized_pnl+? WHERE date=?',(pnl,date))
        conn.commit(); conn.close()

    def log_sell_trade(self, ticker, name, qty, buy_price, sell_price, order_no, reason):
        """매도 기록 저장 (손익 계산용)"""
        today = datetime.now().strftime('%Y-%m-%d')
        pnl_amt = (sell_price - buy_price) * qty
        conn = sqlite3.connect(self.db_path); c = conn.cursor()
        c.execute('INSERT INTO trade_log(date,ticker,name,action,qty,price,stop_loss,order_no,reason,confidence) VALUES (?,?,?,?,?,?,?,?,?,?)',
                  (today, ticker, name, 'SELL', qty, sell_price, buy_price, order_no, reason, pnl_amt))
        conn.commit(); conn.close()
        # 일별 손익 업데이트
        self.update_daily_pnl(today, pnl_amt)

    def get_overall_stats(self):
        """전체 매매 통계: 총 투자 원금, 실현 손익, 승률 반환"""
        conn = sqlite3.connect(self.db_path); c = conn.cursor()
        
        # 매수 기록
        c.execute("SELECT ticker, qty, price FROM trade_log WHERE action='BUY'")
        buys = c.fetchall()
        
        # 매도 기록 (confidence 필드에 pnl_amt 저장)
        c.execute("SELECT confidence FROM trade_log WHERE action='SELL'")
        sells = c.fetchall()
        
        conn.close()
        
        total_invested = sum(qty * price for _, qty, price in buys)  # 총 투자 원금
        total_pnl = sum(row[0] for row in sells if row[0] is not None)  # 총 실현 손익
        total_trades = len(sells)
        wins = sum(1 for row in sells if row[0] and row[0] > 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        roi = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
        
        return {
            'total_invested': total_invested,
            'total_pnl': total_pnl,
            'roi': roi,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'wins': wins,
        }
