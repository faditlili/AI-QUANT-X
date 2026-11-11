"""Telegram notifications with interactive Inline Buttons."""
import asyncio, logging
import config
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

log=logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self,database,engine=None):
        self.db=database; self.engine=engine; self.app=None; self.enabled=False

    async def start(self):
        if not (config.TELEGRAM_TOKEN and config.TELEGRAM_ADMIN_ID):
            log.info("Telegram disabled (missing token/admin id)."); return
        try:
            self.app=Application.builder().token(config.TELEGRAM_TOKEN).build()
            self.app.add_handler(CommandHandler("status",self.cmd_status))
            self.app.add_handler(CommandHandler("positions",self.cmd_positions))
            self.app.add_handler(CommandHandler("pause",self.cmd_pause))
            self.app.add_handler(CommandHandler("resume",self.cmd_resume))
            self.app.add_handler(CallbackQueryHandler(self.handle_callback)) # <--- جديد
            await self.app.initialize(); await self.app.start(); await self.app.updater.start_polling()
            self.enabled=True
        except Exception as e:
            log.exception("Telegram startup failed"); self.enabled=False

    def _authorized(self,update):
        user=update.effective_user
        return bool(user and str(user.id)==str(config.TELEGRAM_ADMIN_ID))

    async def _guard(self,update):
        if not self._authorized(update):
            if update.effective_message:
                await update.effective_message.reply_text("غير مصرح.")
            elif update.callback_query:
                await update.callback_query.answer("غير مصرح.", show_alert=True)
            return False
        return True

    # --- Callback Handler (للأزرار) ---
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update): return
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "toggle_pause":
            self.engine.set_paused(not self.engine.paused)
            status = "متوقف ⏸" if self.engine.paused else "يعمل ▶️"
            await query.edit_message_text(f"تم تغيير حالة البوت إلى: {status}")
            
        elif data.startswith("close_"):
            pos_id = int(data.split("_")[1])
            pos = self.db.get_position(pos_id)
            if pos and pos["status"] == "OPEN":
                prices = await self.engine.market.get_last_prices(pos["source"])
                if pos["symbol"] in prices:
                    price = prices[pos["symbol"]]["last_price"]
                    closed = self.engine.trader.close_position(pos["id"], price, "MANUAL_TELEGRAM")
                    if closed:
                        await query.edit_message_text(f"✅ تم إغلاق {closed['symbol']} يدوياً. الربح: {float(closed['net_pnl']):+.2f} USDT")

    async def cmd_status(self,update,context):
        if not await self._guard(update): return
        p=self.db.get_portfolio()
        status = "متوقف ⏸" if self.engine.paused else "يعمل ▶️"
        keyboard = [[InlineKeyboardButton("إيقاف/تشغيل البوت", callback_data="toggle_pause")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_message.reply_text(
            f"حالة البوت: {status}\nEquity: {p['equity']:.2f}\nOpen: {p['open_count']}\nRealized PnL: {p['realized_pnl']:.2f}",
            reply_markup=reply_markup
        )

    async def cmd_positions(self,update,context):
        if not await self._guard(update): return
        rows=self.db.get_open_positions()
        if not rows:
            await update.effective_message.reply_text("لا توجد صفقات مفتوحة."); return
        for x in rows:
            text = f"{x['source']} {x['symbol']} {x['side']} qty={x['quantity']:.4g}\nEntry: {x['entry_price']:.4f}"
            keyboard = [[InlineKeyboardButton(f"إغلاق {x['symbol']}", callback_data=f"close_{x['id']}")]]
            await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def cmd_pause(self,update,context):
        if not await self._guard(update): return
        self.engine.set_paused(True); await update.effective_message.reply_text("تم إيقاف البوت.")

    async def cmd_resume(self,update,context):
        if not await self._guard(update): return
        self.engine.set_paused(False); await update.effective_message.reply_text("تم تشغيل البوت.")

    async def send(self,message, reply_markup=None):
        if not self.enabled or not config.TELEGRAM_CHAT_ID: return False
        try:
            await self.app.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=message, reply_markup=reply_markup)
            return True
        except Exception: return False

    async def notify_trade_opened(self, position):
        keyboard = [[InlineKeyboardButton("❌ إغلاق الصفقة", callback_data=f"close_{position['id']}")]]
        text = (f"🟢 PAPER POSITION OPENED\n{position['source']} | {position['symbol']} | {position['side']}\n"
                f"Entry: {position['entry_price']:.4g} | Risk: {position['risk_amount']:.2f}")
        return await self.send(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def notify_trade_closed(self, position):
        text = (f"🔴 POSITION CLOSED\n{position['source']} | {position['symbol']} | {position['side']}\n"
                f"Exit: {float(position['exit_price']):.4g}\nNet PnL: {float(position['net_pnl']):+.4f} USDT\nReason: {position.get('exit_reason')}")
        return await self.send(text)

    async def close(self):
        if self.app:
            try:
                if self.app.updater and self.app.updater.running: await self.app.updater.stop()
                await self.app.stop(); await self.app.shutdown()
            except Exception: pass
