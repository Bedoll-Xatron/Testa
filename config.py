import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    KIS_APP_KEY = os.getenv('KIS_APP_KEY')
    KIS_APP_SECRET = os.getenv('KIS_APP_SECRET')
    KIS_BASE_URL = os.getenv('KIS_BASE_URL')
    KIS_ACCOUNT_NO = os.getenv('KIS_ACCOUNT_NO')
    KIS_IS_MOCK = os.getenv('KIS_IS_MOCK','true').lower()=='true'
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    DB_PATH = os.getenv('DB_PATH')
    SIGNAL_TIME = os.getenv('SIGNAL_TIME')
    ORDER_TIMEOUT = os.getenv('ORDER_TIMEOUT')
    MAX_POSITION_PCT = float(os.getenv('MAX_POSITION_PCT',10))
    DAILY_LOSS_LIMIT_PCT = float(os.getenv('DAILY_LOSS_LIMIT_PCT',5))
    STOP_LOSS_PCT = float(os.getenv('STOP_LOSS_PCT',2))
    TAKE_PROFIT_PCT = float(os.getenv('TAKE_PROFIT_PCT', 5.0))
    PAPER_TRADING_MODE = os.getenv('PAPER_TRADING_MODE', 'true').lower() == 'true'
    PAPER_INITIAL_CASH = int(os.getenv('PAPER_INITIAL_CASH', 10000000))
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GEMINI_BASIC_MODEL = os.getenv('GEMINI_BASIC_MODEL', 'gemini-1.5-flash')
    GEMINI_BOSS_MODEL = os.getenv('GEMINI_BOSS_MODEL', 'gemini-1.5-pro')
    NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
    NVIDIA_MODEL = os.getenv('NVIDIA_MODEL', 'meta/llama-3.1-70b-instruct')
    HOLIDAY_API_KEY = os.getenv('HOLIDAY_API_KEY')
config = Config()
