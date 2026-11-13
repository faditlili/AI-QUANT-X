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
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("status", self.cmd_status))
            self.app.add_handler(CommandHandler("positions", self.cmd_positions))
            self.app.add_handler(CommandHandler("pause", self.cmd_pause))
            self.app.add_handler(CommandHandler("resume", self.cmd_resume))
            self.app.add_handler(CommandHandler("performance", self.cmd_performance))
            self.app.add_handler(CommandHandler("balance", self.cmd_balance))
            self.app.add_handler(CommandHandler("risk", self.cmd_risk))          # <--- جديد
            self.app.add_handler(CommandHandler("history", self.cmd_history))    # <--- جديد
            self.app.add_handler(CallbackQueryHandler(self.handle_callback)) 
            
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            self.enabled=True
            log.info("Telegram Bot Started Successfully!")
        except Exception as e:
            log.exception(f"Telegram startup failed: {e}")
            self.enabled=False

    def _authorized(self,update):
        user=update.effective_user
        return bool(user and str(user.id)==str(config.TELEGRAM_ADMIN_ID))

    async def _guard(self,update):
        if not self._authorized(update):
            if update.effective_message:
                await update.effective_message.reply_text("غير مصرح لك باستخدام هذا البوت.")
            elif update.callback_query:
                await update.callback_query.answer("غير مصرح.", show_alert=True)
            return False
        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update): return
        keyboard = [[InlineKeyboardButton("إيقاف/تشغيل البوت", callback_data="toggle_pause")]]
        await update.effective_message.reply_text(
            "أهلاً بك في AI QUANT X 🤖\nالبوت يعمل الآن في وضع المحاكاة.\nاستخدم الأزرار أدناه أو الأوامر للتحكم:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_status(self,update,context):
        if not await self._guard(update): return
        p=self.db.get_portfolio()
        status = "متوقف ⏸" if self.engine.paused else "يعمل ▶️"
        keyboard = [[InlineKeyboardButton("إيقاف/تشغيل البوت", callback_data="toggle_pause")]]
        await update.effective_message.reply_text(
            f"حالة البوت: {status}\nالرصيد: {p['equity']:.2f} USDT\nالصفقات المفتوحة: {p['open_count']}\nالأرباح المحققة: {p['realized_pnl']:.2f} USDT",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_balance(self,update,context):
        if not await self._guard(update): return
        p=self.db.get_portfolio()
        await update.effective_message.reply_text(f"الرصيد النقدي: {p['cash_balance']:.2f}\nالربح العائم: {p['unrealized_pnl']:+.2f}\nالربح المحقق: {p['realized_pnl']:+.2f}")

    async def cmd_performance(self,update,context):
        if not await self._guard(update): return
        p=self.db.get_performance()
        pf = p['profit_factor']
        pf_text = "n/a" if pf is None else f"{pf:.2f}"
        await update.effective_message.reply_text(f"إجمالي الصفقات: {p['total_trades']}\nنسبة النجاح: {p['win_rate']:.1f}%\nمعامل الربح: {pf_text}\nصافي الربح: {p['net_pnl']:.2f} USDT")

    async def cmd_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update): return
        r = self.engine.risk.get_risk_status()
        await update.effective_message.reply_text(
            f"🛡️ تقرير المخاطر:\n"
            f"الرصيد الحالي: {r['equity']:.2f}\n"
            f"المخاطرة المفتوحة: {r['open_risk']:.2f} / {r['risk_cap']:.2f}\n"
            f"تغير اليوم: {r['daily_change']:+.2f}\n"
            f"حد الخسارة اليومي: {r['daily_loss_limit']:.2f}"
        )

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update): return
        trades = self.db.get_recent_trades(200)
        closed_trades = sorted([t for t in trades if t["status"] == "CLOSED"],
                               key=lambda t: t["closed_at"] or "", reverse=True)[:10]
        if not closed_trades:
            await update.effective_message.reply_text("لا توجد صفقات مغلقة مؤخراً.")
            return
        msg = f"📜 آخر {len(closed_trades)} صفقات مغلقة:\n\n"
        for t in closed_trades:
            emoji = "🟢" if float(t['net_pnl']) > 0 else "🔴"
            hhmm = (t["closed_at"] or "")[11:16]
            msg += f"{emoji} {t['symbol']} | {t['side']} | {hhmm} UTC\n"
            msg += f"PnL: {float(t['net_pnl']):+.2f} USDT ({t['exit_reason']})\n\n"
        await update.effective_message.reply_text(msg)

    async def cmd_positions(self,update,context):
        if not await self._guard(update): return
        rows=self.db.get_open_positions()
        if not rows:
            await update.effective_message.reply_text("لا توجد صفقات مفتوحة حالياً."); return
        for x in rows:
            text = f"{x['source']} {x['symbol']} {x['side']}\nالكمية: {x['quantity']:.4g}\nالدخول: {x['entry_price']:.4f}"
            keyboard = [[InlineKeyboardButton(f"إغلاق {x['symbol']}", callback_data=f"close_{x['id']}")]]
            await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def cmd_pause(self,update,context):
        if not await self._guard(update): return
        self.engine.set_paused(True); await update.effective_message.reply_text("تم إيقاف فتح صفقات جديدة.")

    async def cmd_resume(self,update,context):
        if not await self._guard(update): return
        self.engine.set_paused(False); await update.effective_message.reply_text("تم استئناف عمل البوت.")

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
                try:
                    prices = await self.engine.market.get_last_prices(pos["source"])
                    if pos["symbol"] in prices:
                        price = prices[pos["symbol"]]["last_price"]
                        closed = self.engine.trader.close_position(pos["id"], price, "MANUAL_TELEGRAM")
                        if closed:
                            await query.edit_message_text(f"✅ تم إغلاق {closed['symbol']} يدوياً.\nالربح: {float(closed['net_pnl']):+.2f} USDT")
                except Exception as e:
                    await query.edit_message_text(f"خطأ في الإغلاق: {e}")

    async def send(self,message, reply_markup=None):
        if not self.enabled or not config.TELEGRAM_CHAT_ID: return False
        try:
            await self.app.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=message, reply_markup=reply_markup)
            return True
        except Exception as e: 
            log.error(f"Telegram send error: {e}")
            return False

    async def notify_trade_opened(self, position):
        keyboard = [[InlineKeyboardButton("❌ إغلاق الصفقة", callback_data=f"close_{position['id']}")]]
        text = (f"🟢 تم فتح صفقة جديدة\n{position['source']} | {position['symbol']} | {position['side']}\nسعر الدخول: {position['entry_price']:.4g}\nالمخاطرة: {position['risk_amount']:.2f} USDT")
        return await self.send(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def notify_trade_closed(self, position):
        text = (f"🔴 تم إغلاق صفقة\n{position['source']} | {position['symbol']} | {position['side']}\nسعر الخروج: {float(position['exit_price']):.4g}\nصافي الربح: {float(position['net_pnl']):+.4f} USDT\nالسبب: {position.get('exit_reason')}")
        return await self.send(text)

    async def close(self):
        if self.app:
            try:
                if self.app.updater and self.app.updater.running: await self.app.updater.stop()
                await self.app.stop(); await self.app.shutdown()
            except Exception: pass
