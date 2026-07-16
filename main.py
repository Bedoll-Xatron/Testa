import asyncio
from datetime import datetime, timedelta
from telegram.ext import CommandHandler
from telegram.error import NetworkError, TimedOut, RetryAfter
import platform
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from config import config
from live.telegram_signal_bot import SignalBot
from live.eod_manager import EODManager
from live.broker_kis import KISBroker
from strategy.ai_scorer import TestaScorer
from risk.overtrade import RiskManager
from pykrx import stock
from utils.logger import logger

class KRXTrader:
    def __init__(self):
        if getattr(config, 'PAPER_TRADING_MODE', False):
            from live.broker_paper import PaperBroker
            self.broker = PaperBroker()
        else:
            self.broker = KISBroker()
        self.scorer = TestaScorer()
        self.risk = RiskManager()
        self.signal_bot = SignalBot()
        self.eod_manager = EODManager()
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Seoul'))
        self._started_at = datetime.now(pytz.timezone('Asia/Seoul'))
    def setup_schedule(self):
        # 장중 실시간 스캔 (오전 9시 ~ 오후 2시 30분, 매 30분마다)
        self.scheduler.add_job(self.signal_bot.send_daily_signal, CronTrigger(hour='9-14', minute='0,30', day_of_week='mon-fri'))
        self.scheduler.add_job(self.run_eod_check, CronTrigger(hour=15, minute=20, day_of_week='mon-fri'))
        self.scheduler.add_job(self.eod_manager.run_eod_check, CronTrigger(hour=15, minute=30, day_of_week='mon-fri'))
    async def run_eod_check(self):
        from utils.holiday import is_market_open
        if not is_market_open():
            return
            
        today = datetime.now().strftime('%Y%m%d')
        holdings = self.broker.get_balance()
        if not holdings:
            await self.signal_bot.app.bot.send_message(config.TELEGRAM_CHAT_ID, "✅ 보유종목 없음")
            return
            
        alerts=[]
        start_date = (datetime.now() - timedelta(days=150)).strftime('%Y%m%d')
        
        for h in holdings:
            ticker=h['pdno']
            qty=int(h['hldg_qty'])
            avg=int(float(h['pchs_avg_pric']))
            if qty==0: continue
            
            df=stock.get_market_ohlcv(start_date, today, ticker)
            if df.empty or len(df) < 20: continue
            
            ma20=df['종가'].rolling(20).mean().iloc[-1]
            ma10=df['종가'].rolling(10).mean().iloc[-1]
            cur=self.broker.get_current_price(ticker)
            if not cur: cur = int(df['종가'].iloc[-1])
            name=stock.get_market_ticker_name(ticker)
            pnl=(cur/avg-1)*100
            
            if cur < ma20 * 0.98:
                res = self.broker.send_order(ticker, qty, order_type='sell', price=0)
                if res['success']:
                    alerts.append(f"🚨 [자동손절/익절] {name} 20일선 이탈! 전량 매도 완료 ({pnl:+.1f}%)")
                else:
                    alerts.append(f"❌ [주문실패] {name} 매도 실패: {res['msg']}")
            elif pnl >= getattr(config, 'TAKE_PROFIT_PCT', 5.0):
                res = self.broker.send_order(ticker, qty, order_type='sell', price=0)
                if res['success']:
                    alerts.append(f"🎉 [목표익절] {name} 목표수익 도달! 전량 매도 완료 ({pnl:+.1f}%)")
                else:
                    alerts.append(f"❌ [주문실패] {name} 익절 실패: {res['msg']}")
            elif pnl <= -getattr(config, 'STOP_LOSS_PCT', 2.0):
                res = self.broker.send_order(ticker, qty, order_type='sell', price=0)
                if res['success']:
                    alerts.append(f"📉 [자동손절] {name} 손절라인 이탈! 전량 매도 완료 ({pnl:+.1f}%)")
                else:
                    alerts.append(f"❌ [주문실패] {name} 손절 실패: {res['msg']}")
            elif cur < ma10: 
                alerts.append(f"🟡 [주의] {name} 10일선 이탈 ({pnl:+.1f}%)")
            else:
                alerts.append(f"✅ [보유] {name} 홀딩중 ({pnl:+.1f}%)")
                
        msg="\n".join(alerts)
        await self.signal_bot.app.bot.send_message(config.TELEGRAM_CHAT_ID, msg)
    async def startup_check(self):
        self.broker._get_access_token()
        self.risk.init_db()
        return True
    async def run(self):
        logger.info("서버 시작 중: 시스템 초기화 및 데이터베이스 확인...")
        await self.startup_check()

        logger.info("스케줄러 설정 중...")
        self.setup_schedule()
        self.scheduler.start()

        async def _signal_cmd(update, context):
            await self.signal_bot.send_daily_signal(context, update=update)

        async def _error_handler(update, context):
            err = context.error
            if isinstance(err, (NetworkError, TimedOut)):
                logger.warning(f"텔레그램 네트워크 오류 (자동 재시도): {err}")
            elif isinstance(err, RetryAfter):
                logger.warning(f"텔레그램 Rate Limit: {err.retry_after}초 후 재시도")
            else:
                logger.error(f"봇 오류: {err}", exc_info=err)

        async def _status_cmd(update, context):
            now = datetime.now(pytz.timezone('Asia/Seoul'))
            uptime = now - self._started_at
            uptime_h, rem = divmod(int(uptime.total_seconds()), 3600)
            uptime_m, uptime_s = divmod(rem, 60)

            jobs = self.scheduler.get_jobs()
            next_runs = []
            for job in jobs:
                if job.next_run_time:
                    next_runs.append(
                        f"  • {job.name.split('.')[-1]}: {job.next_run_time.strftime('%H:%M')}"
                    )

            try:
                cash = self.broker.get_available_cash()
                if getattr(config, 'PAPER_TRADING_MODE', False) and hasattr(self.broker, 'get_win_rate_stats'):
                    wrs = self.broker.get_win_rate_stats()
                    cash_extra = f"\n📊 가상매매 승률: {wrs['win_rate']:.1f}% ({wrs['total_trades']}전 | 평균 {wrs['avg_pnl']:+.2f}%)"
                else:
                    cash_extra = ""
            except Exception:
                cash = 0
                cash_extra = ""

            # 보유 종목별 상세 + 미실현 손익 합산
            holdings_detail = ""
            unrealized_pnl = 0
            unrealized_invested = 0
            try:
                raw_holdings = [hd for hd in (self.broker.get_balance() or []) if int(hd.get('hldg_qty', 0)) > 0]
                if raw_holdings:
                    holdings_detail = "\n━━━━━━━━━━━━━━━\n📦 보유 종목 현황\n"
                    for hd in raw_holdings:
                        ticker = hd['pdno']
                        name = hd.get('prdt_name', stock.get_market_ticker_name(ticker)) or ticker
                        qty = int(hd['hldg_qty'])
                        avg_price = float(hd['pchs_avg_pric'])
                        cur_price = self.broker.get_current_price(ticker) or avg_price
                        pnl_amt = (cur_price - avg_price) * qty
                        pnl_pct = (cur_price / avg_price - 1) * 100
                        unrealized_pnl += pnl_amt
                        unrealized_invested += avg_price * qty
                        icon = "🔴" if pnl_pct >= 0 else "🔵"
                        holdings_detail += (
                            f"  {icon} {name}({ticker})\n"
                            f"     {qty}주 | 평균 {avg_price:,.0f}원 → {cur_price:,.0f}원\n"
                            f"     손익: {pnl_amt:+,.0f}원 ({pnl_pct:+.2f}%)\n"
                        )
                else:
                    holdings_detail = "\n━━━━━━━━━━━━━━━\n📦 보유 종목 없음"
            except Exception as e:
                holdings_detail = f"\n📦 보유 종목 조회 실패: {e}"

            # 총 투자 성과: 초기 원금 vs 현재 총 평가자산 직접 비교
            try:
                initial_capital = getattr(config, 'PAPER_INITIAL_CASH', 0)
                current_total = self.broker.get_total_capital()  # 현금 + 보유종목 평가액 합산
                total_pnl = current_total - initial_capital
                roi = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0.0
                pnl_icon = "📈" if total_pnl >= 0 else "📉"
                
                # 실현/미실현 세부 내역
                stats = self.risk.get_overall_stats()
                perf_line = (
                    f"━━━━━━━━━━━━━━━\n"
                    f"📊 투자 성과 (원금 대비)\n"
                    f"  초기 원금: {initial_capital:,.0f}원\n"
                    f"  현재 총 평가: {current_total:,.0f}원\n"
                    f"  {pnl_icon} 총 손익: {total_pnl:+,.0f}원 ({roi:+.2f}%)\n"
                    f"  ├ 미실현: {unrealized_pnl:+,.0f}원\n"
                    f"  └ 실현({stats['total_trades']}건·승률{stats['win_rate']:.0f}%): {stats['total_pnl']:+,.0f}원"
                )
            except Exception as e:
                perf_line = f"📊 성과 조회 실패: {e}"


            msg = (
                f"🤖 TESTA 봇 상태\n"
                f"━━━━━━━━━━━━━━━\n"
                f"가동시간: {uptime_h}시간 {uptime_m}분 {uptime_s}초\n"
                f"서버시각: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"예수금: {cash:,}원{cash_extra}\n"
                f"{perf_line}"
                f"{holdings_detail}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"다음 스케줄:\n" + "\n".join(next_runs or ["  (없음)"])
            )
            await update.message.reply_text(msg)


        async def _balance_cmd(update, context):
            wait_msg = await update.message.reply_text("🔄 증권사 API 실시간 잔고/단가 조회 중입니다...\n(종목 수에 따라 최대 10초 정도 소요될 수 있습니다)")
            try:
                cash = self.broker.get_available_cash()
                if getattr(config, 'PAPER_TRADING_MODE', False) and hasattr(self.broker, 'get_total_capital'):
                    total_eval = self.broker.get_total_capital()
                    msg = f"=== 가상 매매 현황 ===\n💰 가용 현금: {cash:,.0f}원\n📈 총 평가자산: {total_eval:,.0f}원\n\n"
                else:
                    msg = f"=== 실제 매매 현황 ===\n💰 가용 현금: {cash:,.0f}원\n\n"
                    
                holdings = self.broker.get_balance()
                if not holdings:
                    msg += "보유 중인 종목이 없습니다."
                else:
                    for h in holdings:
                        ticker = h['pdno']
                        name = h.get('prdt_name', stock.get_market_ticker_name(ticker))
                        qty = int(h['hldg_qty'])
                        if qty == 0: continue
                        avg_price = float(h['pchs_avg_pric'])
                        
                        cur_price = self.broker.get_current_price(ticker)
                        if not cur_price:
                            cur_price = avg_price
                            
                        pnl_pct = ((cur_price / avg_price) - 1) * 100
                        icon = "🔴" if pnl_pct > 0 else "🔵"
                        msg += f"{icon} {name}: {qty}주\n  └ {avg_price:,.0f}원 → {cur_price:,.0f}원 ({pnl_pct:+.2f}%)\n"
                await wait_msg.edit_text(msg)
            except Exception as e:
                await wait_msg.edit_text(f"❌ 잔고 조회 실패: {str(e)}")

        self.signal_bot.app.add_handler(CommandHandler("signal", _signal_cmd))
        self.signal_bot.app.add_handler(CommandHandler("status", _status_cmd))
        self.signal_bot.app.add_handler(CommandHandler("sta", _status_cmd))
        self.signal_bot.app.add_handler(CommandHandler("balance", _balance_cmd))
        self.signal_bot.app.add_handler(CommandHandler("bla", _balance_cmd))
        self.signal_bot.app.add_handler(CommandHandler("bal", _balance_cmd))
        self.signal_bot.app.add_error_handler(_error_handler)
        await self.signal_bot.app.initialize()
        await self.signal_bot.app.start()

        logger.info("텔레그램 봇 폴링 시작 (수신 대기 중)...")
        await self.signal_bot.app.updater.start_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
            read_timeout=30,
            write_timeout=30,
            connect_timeout=10,
            pool_timeout=10,
        )

        logger.info("✅ 자동매매 봇 서버가 성공적으로 실행되었습니다! (Ctrl+C를 눌러 종료)")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info("봇 종료 신호 수신")
        finally:
            await self.signal_bot.app.updater.stop()
            await self.signal_bot.app.stop()
            await self.signal_bot.app.shutdown()

if __name__=="__main__":
    asyncio.run(KRXTrader().run())
