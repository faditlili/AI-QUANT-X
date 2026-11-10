"""Optional Telegram notifications and admin-only paper controls."""
import logging, html
import config

log=logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self,database,engine=None):
        self.db=database; self.engine=engine; self.app=None; self.enabled=False

    async def start(self):
        if not (config.TELEGRAM_TOKEN and config.TELEGRAM_ADMIN_ID):
            log.info("Telegram disabled (missing token/admin id)."); return
        try:
            from telegram.ext import Application, CommandHandler
            self.app=Application.builder().token(config.TELEGRAM_TOKEN).build()
            self.app.add_handler(CommandHandler("status",self.cmd_status))
            self.app.add_handler(CommandHandler("positions",self.cmd_positions))
            self.app.add_handler(CommandHandler("pause",self.cmd_pause))
            self.app.add_handler(CommandHandler("resume",self.cmd_resume))
            self.app.add_handler(CommandHandler("performance",self.cmd_performance))
            await self.app.initialize(); await self.app.start()
            await self.app.updater.start_polling()
            self.enabled=True
        except Exception:
            log.exception("Telegram startup failed"); self.enabled=False

    def _authorized(self,update):
        user=update.effective_user
        return bool(user and str(user.id)==str(config.TELEGRAM_ADMIN_ID))

    async def _guard(self,update):
        if not self._authorized(update):
            await update.effective_message.reply_text("غير مصرح.")
            return False
        return True

    async def cmd_status(self,update,context):
        if not await self._guard(update): return
        p=self.db.get_portfolio()
        await update.effective_message.reply_text(
            f"PAPER SIMULATION\nEquity: {p['equity']:.2f}\nOpen: {p['open_count']}\n"
            f"Realized PnL: {p['realized_pnl']:.2f}\nPaused: {self.engine.paused if self.engine else 'n/a'}")

    async def cmd_positions(self,update,context):
        if not await self._guard(update): return
        rows=self.db.get_open_positions()
        msg="\n".join(f"{x['source']} {x['symbol']} {x['side']} qty={x['quantity']:.6g}" for x in rows) or "No open paper positions."
        await update.effective_message.reply_text(msg[:4000])

    async def cmd_pause(self,update,context):
        if not await self._guard(update): return
        self.engine.set_paused(True); await update.effective_message.reply_text("Paper entries paused.")

    async def cmd_resume(self,update,context):
        if not await self._guard(update): return
        self.engine.set_paused(False); await update.effective_message.reply_text("Paper analysis resumed.")

    async def cmd_performance(self,update,context):
        if not await self._guard(update): return
        p=self.db.get_performance()
        pf=p['profit_factor']
        pf_text="n/a" if pf is None else f"{pf:.2f}"
        await update.effective_message.reply_text(
            f"Closed: {p['total_trades']} | Win rate: {p['win_rate']:.1f}% | "
            f"Net PnL: {p['net_pnl']:.2f} | PF: {pf_text}")

    async def send(self,message):
        if not self.enabled or not config.TELEGRAM_CHAT_ID: return False
        try:
            await self.app.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID,text=message)
            return True
        except Exception:
            log.exception("Telegram send failed"); return False

    async def notify_trade_opened(self, position):
        return await self.send(
            "PAPER POSITION OPENED\n"
            f"{position['source']} | {position['symbol']} | {position['side']}\n"
            f"Quantity: {position['quantity']:.8g}\n"
            f"Entry: {position['entry_price']:.8g}\n"
            f"Stop: {position['stop_price']:.8g} | Target: {position['target_price']:.8g}\n"
            f"Theoretical risk: {position['risk_amount']:.4f} USDT"
        )

    async def notify_trade_closed(self, position):
        return await self.send(
            "PAPER POSITION CLOSED\n"
            f"{position['source']} | {position['symbol']} | {position['side']}\n"
            f"Exit: {float(position['exit_price']):.8g}\n"
            f"Net simulated PnL: {float(position['net_pnl']):+.4f} USDT\n"
            f"Reason: {position.get('exit_reason') or 'N/A'}"
        )

    async def close(self):
        if self.app:
            try:
                if self.app.updater and self.app.updater.running: await self.app.updater.stop()
                await self.app.stop(); await self.app.shutdown()
            except Exception: log.exception("Telegram shutdown failed")
