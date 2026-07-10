import requests
from datetime import datetime
from config import config
from utils.logger import logger

_HOLIDAY_CACHE = {}

def is_market_open() -> bool:
    """오늘이 주말이거나 공휴일이면 False 반환 (휴장)"""
    today = datetime.now()
    if today.weekday() >= 5: # 5: 토, 6: 일
        return False
        
    date_str = today.strftime("%Y%m%d")
    
    # 캐시 확인 (하루 한 번만 API 호출)
    if date_str in _HOLIDAY_CACHE:
        return not _HOLIDAY_CACHE[date_str]
        
    # API 키가 없으면 기존 holidays 모듈 사용
    if not config.HOLIDAY_API_KEY:
        import holidays
        kr_holidays = holidays.KR()
        is_hol = today in kr_holidays
        _HOLIDAY_CACHE[date_str] = is_hol
        return not is_hol
        
    # 특일정보 API 호출
    url = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"
    params = {
        "serviceKey": config.HOLIDAY_API_KEY,
        "solYear": today.strftime("%Y"),
        "solMonth": today.strftime("%m"),
        "_type": "json"
    }
    
    try:
        res = requests.get(url, params=params, timeout=5)
        res.raise_for_status()
        
        data = res.json()
        items = data.get('response', {}).get('body', {}).get('items', {})
        
        holiday_dates = []
        if items and 'item' in items:
            item_data = items['item']
            if isinstance(item_data, list):
                holiday_dates = [str(x['locdate']) for x in item_data if x.get('isHoliday') == 'Y']
            else:
                if item_data.get('isHoliday') == 'Y':
                    holiday_dates.append(str(item_data['locdate']))
                    
        is_hol = date_str in holiday_dates
        _HOLIDAY_CACHE[date_str] = is_hol
        
        return not is_hol
        
    except Exception as e:
        logger.error(f"공휴일 API 호출 실패, holidays 모듈로 대체합니다: {e}")
        import holidays
        kr_holidays = holidays.KR()
        is_hol = today in kr_holidays
        _HOLIDAY_CACHE[date_str] = is_hol
        return not is_hol
