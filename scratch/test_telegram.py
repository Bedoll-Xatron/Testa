import asyncio
import sys
import os
from telegram import Bot

# 부모 디렉토리(TESTA)를 경로에 추가하여 config.py를 가져올 수 있게 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import config

async def test_telegram():
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("❌ 오류: .env 파일에 TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 설정되지 않았습니다.")
        return

    print("텔레그램 메시지 전송 시도 중...")
    try:
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        # 봇 상태 메시지 전송
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID, 
            text="🤖 [TESTA AI Trader] 텔레그램 연동 테스트 메시지입니다.\n\n정상적으로 통신이 이루어지고 있습니다. ✅"
        )
        print("✅ 메시지 전송 성공!")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(test_telegram())
