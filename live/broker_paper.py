import sqlite3
import time
from datetime import datetime
from config import config
from pykrx import stock
from live.broker_kis import KISBroker
from utils.logger import logger

class PaperBroker:
    def __init__(self):
        self.kis_broker = KISBroker() # 가격 조회를 위해 내부적으로 KIS 사용
        self.db_path = config.DB_PATH.replace('sqlite:///', '') if config.DB_PATH else 'krx_data.db'
        self.initial_cash = config.PAPER_INITIAL_CASH
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 가상 계좌 테이블 (예수금)
        c.execute('''CREATE TABLE IF NOT EXISTS paper_account (
            id INTEGER PRIMARY KEY,
            cash INTEGER
        )''')
        
        # 계좌 초기화 (최초 1회만)
        c.execute('SELECT cash FROM paper_account WHERE id=1')
        row = c.fetchone()
        if not row:
            c.execute('INSERT INTO paper_account (id, cash) VALUES (1, ?)', (self.initial_cash,))
        
        # 가상 보유 종목 테이블
        c.execute('''CREATE TABLE IF NOT EXISTS paper_positions (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            qty INTEGER,
            avg_price INTEGER
        )''')
        
        # 가상 거래 내역 (승률 기록용)
        c.execute('''CREATE TABLE IF NOT EXISTS paper_trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            ticker TEXT,
            name TEXT,
            action TEXT,
            qty INTEGER,
            price INTEGER,
            pnl_pct REAL,
            is_win INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()

    def _get_access_token(self):
        """KISBroker 토큰 발급/갱신 (호환성을 위함)"""
        if hasattr(self.kis_broker, '_get_access_token'):
            self.kis_broker._get_access_token()

    def get_current_price(self, ticker):
        """실제 시장 가격은 KISBroker를 통해 조회"""
        return self.kis_broker.get_current_price(ticker)

    def get_minute_ohlcv(self, ticker, limit=120):
        """실제 시장 분봉은 KISBroker를 통해 조회"""
        return self.kis_broker.get_minute_ohlcv(ticker, limit)

    def get_available_cash(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT cash FROM paper_account WHERE id=1')
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0

    def get_total_capital(self):
        cash = self.get_available_cash()
        positions = self.get_balance()
        
        total_eval = cash
        for p in positions:
            ticker = p['pdno']
            qty = int(p['hldg_qty'])
            cur_price = self.get_current_price(ticker) or int(p['pchs_avg_pric'])
            total_eval += qty * cur_price
            
        return total_eval

    def get_balance(self):
        """KISBroker의 리턴 형식({'pdno', 'hldg_qty', 'pchs_avg_pric', 'prdt_name'})과 맞춤"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT ticker, name, qty, avg_price FROM paper_positions WHERE qty > 0')
        rows = c.fetchall()
        conn.close()
        
        balance = []
        for r in rows:
            balance.append({
                'pdno': r[0],
                'prdt_name': r[1],
                'hldg_qty': str(r[2]),
                'pchs_avg_pric': str(r[3])
            })
        return balance

    def send_order(self, ticker, qty, order_type='buy', price=0):
        """가상 매수/매도 실행"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        cur_price = price if price > 0 else self.get_current_price(ticker)
        if not cur_price:
            return {'success': False, 'msg': '현재가 조회 실패'}
            
        name = stock.get_market_ticker_name(ticker)
        today = datetime.now().strftime('%Y-%m-%d')
        cash = self.get_available_cash()
        
        if order_type.lower() == 'buy':
            total_cost = cur_price * qty
            if cash < total_cost:
                return {'success': False, 'msg': '가상 예수금 부족'}
                
            # 잔고 차감
            c.execute('UPDATE paper_account SET cash = cash - ? WHERE id=1', (total_cost,))
            
            # 포지션 추가 (물타기 평균단가 계산)
            c.execute('SELECT qty, avg_price FROM paper_positions WHERE ticker=?', (ticker,))
            pos = c.fetchone()
            if pos:
                old_qty, old_avg = pos
                new_qty = old_qty + qty
                new_avg = int(((old_qty * old_avg) + total_cost) / new_qty)
                c.execute('UPDATE paper_positions SET qty=?, avg_price=? WHERE ticker=?', (new_qty, new_avg, ticker))
            else:
                c.execute('INSERT INTO paper_positions (ticker, name, qty, avg_price) VALUES (?, ?, ?, ?)', (ticker, name, qty, cur_price))
                
            # 내역 기록
            c.execute('INSERT INTO paper_trade_history (date, ticker, name, action, qty, price, pnl_pct, is_win) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                      (today, ticker, name, 'BUY', qty, cur_price, 0.0, 0))
            
            conn.commit()
            conn.close()
            return {'success': True, 'msg': f'가상 매수 완료 ({name})'}
            
        elif order_type.lower() == 'sell':
            c.execute('SELECT qty, avg_price FROM paper_positions WHERE ticker=?', (ticker,))
            pos = c.fetchone()
            if not pos or pos[0] < qty:
                return {'success': False, 'msg': '매도 가능 수량 부족'}
                
            old_qty, avg_price = pos
            total_revenue = cur_price * qty
            
            # 예수금 증가
            c.execute('UPDATE paper_account SET cash = cash + ? WHERE id=1', (total_revenue,))
            
            # 포지션 차감
            new_qty = old_qty - qty
            if new_qty == 0:
                c.execute('DELETE FROM paper_positions WHERE ticker=?', (ticker,))
            else:
                c.execute('UPDATE paper_positions SET qty=? WHERE ticker=?', (new_qty, ticker))
                
            # 수익률 계산 및 내역 기록
            pnl_pct = ((cur_price / avg_price) - 1) * 100
            is_win = 1 if pnl_pct > 0 else 0
            
            c.execute('INSERT INTO paper_trade_history (date, ticker, name, action, qty, price, pnl_pct, is_win) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                      (today, ticker, name, 'SELL', qty, cur_price, pnl_pct, is_win))
            
            conn.commit()
            conn.close()
            return {'success': True, 'msg': f'가상 매도 완료 ({pnl_pct:+.1f}%)'}

    def get_win_rate_stats(self):
        """가상 매매 승률 계산"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(is_win), AVG(pnl_pct) FROM paper_trade_history WHERE action='SELL'")
        row = c.fetchone()
        conn.close()
        
        total_sells = row[0] or 0
        total_wins = row[1] or 0
        avg_pnl = row[2] or 0.0
        win_rate = (total_wins / total_sells * 100) if total_sells > 0 else 0.0
        
        return {
            'total_trades': total_sells,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl
        }
