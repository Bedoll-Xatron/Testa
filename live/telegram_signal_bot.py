from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import Application,CallbackQueryHandler,MessageHandler,filters
from pykrx import stock
import FinanceDataReader as fdr
from datetime import datetime
import asyncio
from strategy.ai_scorer import TestaScorer
from live.broker_kis import KISBroker
from risk.overtrade import RiskManager
from config import config

class SignalBot:
    def __init__(self):
        self.app = (
            Application.builder()
            .token(config.TELEGRAM_BOT_TOKEN)
            .read_timeout(30)
            .write_timeout(30)
            .connect_timeout(10)
            .pool_timeout(10)
            .build()
        )
        self.scorer=TestaScorer(); self.risk=RiskManager()
        if getattr(config, 'PAPER_TRADING_MODE', False):
            from live.broker_paper import PaperBroker
            self.broker = PaperBroker()
        else:
            self.broker = KISBroker()
        self.active_sessions={}
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,self.qty_input_handler))
    def check_market_regime(self):
        try:
            kospi = fdr.DataReader('KS11', "2024-01-01")
            if len(kospi) < 60:
                return True
            return kospi['Close'].iloc[-1] > kospi['Close'].rolling(60).mean().iloc[-1]
        except Exception:
            return True # 조회 실패 시 기본값으로 True 반환하여 스캔 진행
    async def send_daily_signal(self,context=None, update=None):
        bot = context.bot if context else self.app.bot
        
        # 한국 공휴일 및 주말 휴장일 스킵
        from utils.holiday import is_market_open
        if not is_market_open():
            if update:
                await update.message.reply_text("오늘은 휴장일입니다.")
            return
            
        wait_msg = None
        if update:
            wait_msg = await update.message.reply_text("🔄 시장 스캔 및 AI(NVIDIA 70B) 분석 중입니다... (최대 1~3분 소요)")
            
        def _get_cash():
            return self.broker.get_available_cash()
            
        available_cash = await asyncio.to_thread(_get_cash)
        
        def _scan():
            return self.scorer.scan_market(total_capital=available_cash, max_picks=5)
            
        buys = await asyncio.to_thread(_scan)
        
        if not buys: 
            if wait_msg:
                await wait_msg.edit_text("❌ 조건에 맞는 종목이 없어 매수를 진행하지 않습니다.")
            return
            
        msg = "🤖 [자동 매수 완료]\n\n"
        bought_count = 0
        
        for b in buys:
            try:
                self.risk.check_pre_trade(b['ticker'])
                def _order():
                    return self.broker.send_order(b['ticker'], b['qty'])
                res = await asyncio.to_thread(_order)
                
                if res['success']:
                    msg += f"✅ {b['name']} {b['qty']}주 (단가: {b['price']:,}원)\n"
                    if 'ai_reason' in b:
                        msg += f"  └ 🤖 AI: {b['ai_reason']} (확신도: {b.get('ai_confidence', 0)}%)\n"
                    bought_count += 1
            except Exception:
                pass
                
        if bought_count > 0:
            if wait_msg:
                await wait_msg.edit_text(msg)
            else:
                await bot.send_message(config.TELEGRAM_CHAT_ID, msg)
        else:
            if wait_msg:
                await wait_msg.edit_text("❌ 종목을 찾았으나 매수 주문에 실패했습니다.")
    async def button_handler(self,update,context):
        q=update.callback_query
        try:
            await q.answer()
        except Exception:
            pass
        data=q.data
        
        chat_id = str(q.message.chat_id)
        if data == "buy_all":
            sess = self.active_sessions.get(chat_id)
            if not sess or not sess.get('buys'):
                await q.edit_message_text("❌ 유효한 스캔 세션이 없거나 이미 처리되었습니다.", reply_markup=InlineKeyboardMarkup([]))
                return

            results = []
            for b in sess['buys']:
                ticker = b['ticker']
                qty = b['qty']
                try:
                    self.risk.check_pre_trade(ticker)
                    res = self.broker.send_order(ticker, qty)
                    msg_text = res.get('msg', '알 수 없는 오류')
                    results.append(f"🟢 {b['name']}: {'매수 주문 성공' if res['success'] else f'주문 실패 ({msg_text})'}")
                except Exception as e:
                    results.append(f"🔴 {b['name']}: 실패 ({str(e)})")

            result_text = "✅ [전체 승인 결과]\n" + "\n".join(results)
            await q.edit_message_text(result_text, reply_markup=InlineKeyboardMarkup([]))
            del self.active_sessions[chat_id]

        elif data == "cancel_all":
            await q.edit_message_text("❌ [스캔 취소됨]", reply_markup=InlineKeyboardMarkup([]))
            if chat_id in self.active_sessions:
                del self.active_sessions[chat_id]

        elif data.startswith('buy_'):
            try:
                parts = data.split('_', 2)
                if len(parts) != 3:
                    raise ValueError(f"잘못된 callback 데이터: {data}")
                _, t, qty_str = parts
                qty = int(qty_str)
            except (ValueError, IndexError) as e:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ 버튼 데이터 오류: {str(e)}")
                return

            sess = self.active_sessions.get(chat_id)
            # 이미 개별 처리된 종목이면 중복 주문 방지
            if sess and t not in sess.get('pending', []):
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {t} 은(는) 이미 주문 처리되었습니다.")
                return

            try:
                self.risk.check_pre_trade(t)
                res = self.broker.send_order(t, qty)
                msg_text = res.get('msg', '알 수 없는 오류')
                name = next((b['name'] for b in sess['buys'] if b['ticker'] == t), t) if sess else t
                result_msg = f"🟢 {name}({t}) {qty}주: {'매수 주문 성공' if res['success'] else f'주문 실패 ({msg_text})'}"
            except Exception as e:
                result_msg = f"🔴 {t} ({qty}주): 주문 실패 ({str(e)})"

            # 세션에서 처리된 ticker 제거 (이중 주문 방지)
            if sess and 'pending' in sess:
                sess['pending'] = [p for p in sess['pending'] if p != t]
                sess['buys'] = [b for b in sess['buys'] if b['ticker'] != t]
                if not sess['pending']:
                    del self.active_sessions[chat_id]

            await context.bot.send_message(chat_id=chat_id, text=result_msg)
    async def qty_input_handler(self,update,context):
        chat=str(update.effective_chat.id)
        sess=self.active_sessions.get(chat)
        text = update.message.text.strip()
        
        if not sess or 'waiting_ticker' not in sess:
            ticker = text
            if not (text.isdigit() and len(text) == 6):
                # 종목명으로 입력한 경우 fdr을 통해 코드 검색
                try:
                    df = fdr.StockListing('KRX')
                    matches = df[df['Name'] == text]
                    if not matches.empty:
                        ticker = matches.iloc[0]['Code']
                    else:
                        await update.message.reply_text(f"❌ '{text}' 종목을 찾을 수 없습니다. 정확한 종목명이나 6자리 코드를 입력해주세요.")
                        return
                except Exception:
                    await update.message.reply_text("❌ 종목 검색 중 오류가 발생했습니다.")
                    return
                    
            await update.message.reply_text(f"🔍 {text}({ticker}) 종목을 분석 중입니다...")
            report = self.scorer.analyze_single_ticker(ticker)
            await update.message.reply_text(report)
            return
            
        t=sess['waiting_ticker']
        if not text.isdigit():
            await update.message.reply_text("수량은 숫자로만 입력해주세요.")
            return
            
        qty=int(text)
        self.risk.check_pre_trade(t)
        res=self.broker.send_order(t,qty)
        del sess['waiting_ticker']
        await update.message.reply_text(f"주문 {res}")
