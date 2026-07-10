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
