import asyncio, sys
sys.path.insert(0, '.')
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from strategy.ai_scorer import TestaScorer
from live.broker_kis import KISBroker
from config import config

async def send_scan():
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    broker = KISBroker()
    scorer = TestaScorer()

    total_capital = broker.get_total_capital()
    await bot.send_message(config.TELEGRAM_CHAT_ID, '🔄 수동 스캔을 시작합니다...')

    buys = scorer.scan_market(total_capital=total_capital)[:5]
    if not buys:
        await bot.send_message(config.TELEGRAM_CHAT_ID, '🔍 오늘 포착된 눌림목 종목이 없습니다.')
        return

    msg = '📈 VWAP 스캐너 포착\n\n'
    kb = []
    for b in buys:
        msg += f"🟢 {b['name']} ({b['ticker']})\n"
        msg += f"  - 타점: {b['reason']} (점수: {b['score']}점)\n"
        msg += f"  - 매수가: {b['price']:,}원 (VWAP: {b['vwap']:,}원)\n"
        msg += f"  - 추천수량: {b['qty']}주 (자동손절가 {b['stop_loss']:,}원)\n"
        if b.get('bt_info'):
            msg += f"  - 📊 [10년 검증] {b['bt_info']}\n\n"
        else:
            msg += '\n'
        kb.append([InlineKeyboardButton(f"{b['name']} {b['qty']}주 매수", callback_data=f"buy_{b['ticker']}_{b['qty']}")])

    kb.append([
        InlineKeyboardButton('✅ 전체 승인', callback_data='buy_all'),
        InlineKeyboardButton('❌ 취소', callback_data='cancel_all')
    ])

    await bot.send_message(config.TELEGRAM_CHAT_ID, msg, reply_markup=InlineKeyboardMarkup(kb))
    print('✅ 텔레그램 전송 완료')

asyncio.run(send_scan())
