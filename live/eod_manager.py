from risk.overtrade import RiskManager
from live.broker_kis import KISBroker
from datetime import datetime,timedelta
from config import config

class EODManager:
    def __init__(self):
        self.risk=RiskManager(); self.broker=KISBroker()
    def run_eod_check(self):
        from utils.holiday import is_market_open
        if not is_market_open():
            return
            
        today=datetime.now().strftime('%Y-%m-%d')
        holdings=self.broker.get_balance()
        if not holdings: return
        total_asset=sum(int(h['evlu_amt']) for h in holdings)
        total_purchase=sum(int(h['pchs_amt']) for h in holdings)
        pnl=total_asset-total_purchase
        self.risk.update_daily_pnl(today,pnl)
