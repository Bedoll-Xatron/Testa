import requests,json
import time
from datetime import datetime, timedelta
from config import config
from utils.logger import logger

def with_backoff(func):
    def wrapper(*args, **kwargs):
        retries = 3
        backoff = 1
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"[KISBroker] {func.__name__} 오류: {e}, {backoff}초 후 재시도 ({i+1}/{retries})")
                time.sleep(backoff)
                backoff *= 2
        logger.error(f"[KISBroker] {func.__name__} 최종 실패")
        return None if 'get_' in func.__name__ else {'success': False, 'msg': 'API 통신(네트워크/한도 등) 최종 실패'}
    return wrapper

class KISBroker:
    def __init__(self):
        self.app_key=config.KIS_APP_KEY; self.app_secret=config.KIS_APP_SECRET
        self.base_url=config.KIS_BASE_URL; self.account_no=config.KIS_ACCOUNT_NO
        self.is_mock=config.KIS_IS_MOCK; self.token=None; self.token_expired_at=None
        self._get_access_token()
    def _get_access_token(self):
        token_file = "logs/kis_token.json"
        try:
            import os
            if os.path.exists(token_file):
                with open(token_file, "r") as f:
                    d = json.load(f)
                    if datetime.now().timestamp() < d.get('token_expired_at', 0) - 60:
                        self.token = d['access_token']
                        self.token_expired_at = d['token_expired_at']
                        return
        except Exception as e:
            pass
            
        url=f"{self.base_url}/oauth2/tokenP"
        body={"grant_type":"client_credentials","appkey":self.app_key,"appsecret":self.app_secret}
        res=requests.post(url,headers={"content-type":"application/json"},data=json.dumps(body))
        if res.status_code==200:
            d=res.json(); self.token=d['access_token']; self.token_expired_at=datetime.now().timestamp()+d['expires_in']
            try:
                with open(token_file, "w") as f:
                    json.dump({"access_token": self.token, "token_expired_at": self.token_expired_at}, f)
            except:
                pass
    def _check_token(self):
        if not self.token or datetime.now().timestamp()>self.token_expired_at-60: self._get_access_token()
    def _get_hashkey(self,body):
        url=f"{self.base_url}/uapi/hashkey"
        res=requests.post(url,headers={"content-type":"application/json","appkey":self.app_key,"appsecret":self.app_secret},data=json.dumps(body))
        return res.json()['HASH']
    @with_backoff
    def get_current_price(self,ticker):
        self._check_token()
        url=f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        h={"content-type":"application/json","authorization":f"Bearer {self.token}","appkey":self.app_key,"appsecret":self.app_secret,"tr_id":"FHKST01010100"}
        p={"fid_cond_mrkt_div_code":"J","fid_input_iscd":ticker}
        res=requests.get(url, timeout=10,headers=h,params=p)
        return int(res.json()['output']['stck_prpr']) if res.status_code==200 else None
    @with_backoff
    def send_order(self,ticker,qty,order_type='buy',price=0):
        self._check_token()
        url=f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        tr_id="VTTC0802U" if self.is_mock else "TTTC0802U"
        ord_dvsn="00" if price>0 else "01"
        cano = self.account_no.split('-')[0] if '-' in self.account_no else self.account_no
        acnt_prdt_cd = self.account_no.split('-')[1] if '-' in self.account_no else "01"
        body={"CANO":cano,"ACNT_PRDT_CD":acnt_prdt_cd,"PDNO":ticker,"ORD_DVSN":ord_dvsn,"ORD_QTY":str(qty),"ORD_UNPR":str(price)}
        h={"content-type":"application/json","authorization":f"Bearer {self.token}","appkey":self.app_key,"appsecret":self.app_secret,"tr_id":tr_id,"custtype":"P","hashkey":self._get_hashkey(body)}
        res=requests.post(url,headers=h,data=json.dumps(body))
        d=res.json()
        return {'success':d.get('rt_cd')=='0','order_no':d.get('output', {}).get('ODNO'),'msg':d.get('msg1', '알 수 없는 오류')}
    @with_backoff
    def get_balance(self):
        self._check_token()
        url=f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        tr_id="VTTC8434R" if self.is_mock else "TTTC8434R"
        h={"content-type":"application/json","authorization":f"Bearer {self.token}","appkey":self.app_key,"appsecret":self.app_secret,"tr_id":tr_id}
        cano = self.account_no.split('-')[0] if '-' in self.account_no else self.account_no
        acnt_prdt_cd = self.account_no.split('-')[1] if '-' in self.account_no else "01"
        p={"CANO":cano,"ACNT_PRDT_CD":acnt_prdt_cd,"AFHR_FLPR_YN":"N","OFL_YN":"","INQR_DVSN":"02","UNPR_DVSN":"01","FUND_STTL_ICLD_YN":"N","FNCG_AMT_AUTO_RDPT_YN":"N","PRCS_DVSN":"01","CTX_AREA_FK100":"","CTX_AREA_NK100":""}
        res=requests.get(url, timeout=10,headers=h,params=p)
        return res.json()['output1'] if res.status_code==200 else []
        
    @with_backoff
    def get_total_capital(self):
        self._check_token()
        url=f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        tr_id="VTTC8434R" if self.is_mock else "TTTC8434R"
        h={"content-type":"application/json","authorization":f"Bearer {self.token}","appkey":self.app_key,"appsecret":self.app_secret,"tr_id":tr_id}
        cano = self.account_no.split('-')[0] if '-' in self.account_no else self.account_no
        acnt_prdt_cd = self.account_no.split('-')[1] if '-' in self.account_no else "01"
        p={"CANO":cano,"ACNT_PRDT_CD":acnt_prdt_cd,"AFHR_FLPR_YN":"N","OFL_YN":"","INQR_DVSN":"02","UNPR_DVSN":"01","FUND_STTL_ICLD_YN":"N","FNCG_AMT_AUTO_RDPT_YN":"N","PRCS_DVSN":"01","CTX_AREA_FK100":"","CTX_AREA_NK100":""}
        res=requests.get(url, timeout=10,headers=h,params=p)
        if res.status_code==200:
            return int(res.json()['output2'][0]['tot_evlu_amt'])
        return 10000000 # default fallback

    @with_backoff
    def get_available_cash(self):
        """주문 가능 예수금 반환 (dnca_tot_amt)"""
        self._check_token()
        url=f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        tr_id="VTTC8434R" if self.is_mock else "TTTC8434R"
        h={"content-type":"application/json","authorization":f"Bearer {self.token}","appkey":self.app_key,"appsecret":self.app_secret,"tr_id":tr_id}
        cano = self.account_no.split('-')[0] if '-' in self.account_no else self.account_no
        acnt_prdt_cd = self.account_no.split('-')[1] if '-' in self.account_no else "01"
        p={"CANO":cano,"ACNT_PRDT_CD":acnt_prdt_cd,"AFHR_FLPR_YN":"N","OFL_YN":"","INQR_DVSN":"02","UNPR_DVSN":"01","FUND_STTL_ICLD_YN":"N","FNCG_AMT_AUTO_RDPT_YN":"N","PRCS_DVSN":"01","CTX_AREA_FK100":"","CTX_AREA_NK100":""}
        res=requests.get(url, timeout=10,headers=h,params=p)
        if res.status_code==200:
            return int(res.json()['output2'][0]['dnca_tot_amt'])
        return 0

    @with_backoff
    def get_minute_ohlcv(self, ticker, limit=120):
        self._check_token()
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        h = {
            "content-type": "application/json",
            "authorization": f"Bearer {self.token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST03010200",
            "custtype": "P"
        }
        
        all_bars = []
        target_time = datetime.now().strftime("%H%M%S")
        
        for _ in range(limit // 30 + 1):
            p = {
                "fid_etc_cls_code": "",
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": ticker,
                "fid_input_hour_1": target_time,
                "fid_pw_data_incu_yn": "N"
            }
            res = requests.get(url, timeout=10, headers=h, params=p)
            if res.status_code == 200:
                data = res.json().get('output2', [])
                if not data:
                    break
                all_bars.extend(data)
                target_time = data[-1]['stck_cntg_hour']
                # decrease 1 second from target_time to avoid duplicate
                try:
                    hh, mm, ss = int(target_time[:2]), int(target_time[2:4]), int(target_time[4:])
                    td = datetime(2000, 1, 1, hh, mm, ss) - timedelta(seconds=1)
                    target_time = td.strftime("%H%M%S")
                except Exception as e:
                    pass
            else:
                break
                
        return all_bars[:limit]

