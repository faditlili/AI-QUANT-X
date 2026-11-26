"""Telegram notifications with interactive Inline Buttons."""
import asyncio, json, logging
import re

_LRI, _PDI = "\u2066", "\u2069"          # Unicode left-to-right isolate / pop
_N = r"[+\-\u2212]?\d[\d,]*(?:\.\d+)?(?:\s?%)?(?:\s?USDT)?"
# one isolate per number OR per "a / b / c" series: two separate isolates would swap places inside an RTL line ("99.96 / 19.62")
_NUM = re.compile(r"(?<![\w.])(?:\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}(?:\s?UTC)?|" + _N + r"(?:\s?/\s?" + _N + r")*)(?![\w])")


def _b(text):
    """Telegram lays Arabic lines out right-to-left, which turns "-3.91 USDT" into "3.91- USDT" (a loss that looks like a
    gain) and "71.4%" into "%71.4". Isolating every number keeps its sign, decimals, % and unit in reading order."""
    return _NUM.sub(lambda m: _LRI + m.group(0) + _PDI, str(text))

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
            self.app.add_handler(CommandHandler("profit", self.cmd_profit))
            self.app.add_handler(CommandHandler("daily", self.cmd_daily))
            self.app.add_handler(CommandHandler("stats", self.cmd_stats))
            self.app.add_handler(CommandHandler("pairs", self.cmd_pairs))
            self.app.add_handler(CommandHandler("tiers", self.cmd_tiers))
            self.app.add_handler(CommandHandler("count", self.cmd_count))
            self.app.add_handler(CommandHandler("forceexit", self.cmd_forceexit))
            self.app.add_handler(CommandHandler("help", self.cmd_help))
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
                await update.effective_message.reply_text(_b("غير مصرح لك باستخدام هذا البوت."))
            elif update.callback_query:
                await update.callback_query.answer("غير مصرح.", show_alert=True)
            return False
        return True

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update): return
        keyboard = [[InlineKeyboardButton("إيقاف/تشغيل البوت", callback_data="toggle_pause")]]
        await update.effective_message.reply_text(_b(
            "أهلاً بك في AI QUANT X 🤖\nالبوت يعمل الآن في وضع المحاكاة.\nاستخدم الأزرار أدناه أو الأوامر للتحكم:"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_status(self,update,context):
        if not await self._guard(update): return
        p=self.db.get_portfolio()
        status = "متوقف ⏸" if self.engine.paused else "يعمل ▶️"
        keyboard = [[InlineKeyboardButton("إيقاف/تشغيل البوت", callback_data="toggle_pause")]]
        await update.effective_message.reply_text(_b(
            f"حالة البوت: {status}\nالرصيد: {p['equity']:.2f} USDT\nالصفقات المفتوحة: {p['open_count']}\nالأرباح المحققة: {p['realized_pnl']:.2f} USDT"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_balance(self,update,context):
        if not await self._guard(update): return
        p=self.db.get_portfolio()
        await update.effective_message.reply_text(_b(f"الرصيد النقدي: {p['cash_balance']:.2f}\nالربح العائم: {p['unrealized_pnl']:+.2f}\nالربح المحقق: {p['realized_pnl']:+.2f}"))

    async def cmd_performance(self,update,context):
        if not await self._guard(update): return
        p=self.db.get_performance()
        pf = p['profit_factor']
        pf_text = "n/a" if pf is None else f"{pf:.2f}"
        await update.effective_message.reply_text(_b(f"إجمالي الصفقات: {p['total_trades']}\nنسبة النجاح: {p['win_rate']:.1f}%\nمعامل الربح: {pf_text}\nصافي الربح: {p['net_pnl']:.2f} USDT"))

    async def cmd_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update): return
        r = self.engine.risk.get_risk_status()
        await update.effective_message.reply_text(_b(
            f"🛡️ تقرير المخاطر:\n"
            f"الرصيد الحالي: {r['equity']:.2f}\n"
            f"المخاطرة المفتوحة: {r['open_risk']:.2f} / {r['risk_cap']:.2f} (المتبقي {r['risk_remaining']:.2f})\n"
            f"تغير اليوم: {r['daily_change']:+.2f}\n"
            f"حد الخسارة اليومي: {r['daily_loss_limit']:.2f}"
        ))

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update): return
        closed_trades = self.db.get_closed_trades(10)
        if not closed_trades:
            await update.effective_message.reply_text(_b("لا توجد صفقات مغلقة مؤخراً."))
            return
        msg = f"📜 آخر {len(closed_trades)} صفقات مغلقة:\n\n"
        for t in closed_trades:
            emoji = "🟢" if float(t['net_pnl'] or 0) > 0 else "🔴"
            hhmm = (t["closed_at"] or "")[11:16]
            msg += f"{emoji} {t['symbol']} | {t['side']} | {hhmm} UTC\n"
            msg += f"PnL: {float(t['net_pnl'] or 0):+.2f} USDT ({t['exit_reason']})\n\n"
        await update.effective_message.reply_text(_b(msg))

    async def cmd_positions(self,update,context):
        if not await self._guard(update): return
        rows=self.db.get_open_positions()
        if not rows:
            await update.effective_message.reply_text(_b("لا توجد صفقات مفتوحة حالياً.")); return
        for x in rows:
            mark = float(x.get("mark_price") or 0)
            sign = 1 if x["side"] == "LONG" else -1
            pnl = (mark - x["entry_price"]) * x["quantity"] * sign if mark else 0.0
            text = (f"#{x['id']} {x['source']} {x['symbol']} {x['side']}\nالكمية: {x['quantity']:.4g}\n"
                    f"الدخول: {x['entry_price']:.4f}\nالربح العائم: {pnl:+.2f} USDT")
            keyboard = [[InlineKeyboardButton(f"إغلاق {x['symbol']}", callback_data=f"close_{x['id']}")]]
            await update.effective_message.reply_text(_b(text), reply_markup=InlineKeyboardMarkup(keyboard))

    async def cmd_pause(self,update,context):
        if not await self._guard(update): return
        self.engine.set_paused(True); await update.effective_message.reply_text(_b("تم إيقاف فتح صفقات جديدة."))

    async def cmd_resume(self,update,context):
        if not await self._guard(update): return
        self.engine.set_paused(False); await update.effective_message.reply_text(_b("تم استئناف عمل البوت."))

    # ---------- تقارير على طريقة Freqtrade ----------
    def _closed_trades(self, limit=5000):
        return sorted(self.db.get_closed_trades(limit), key=lambda t: t["closed_at"] or "")

    @staticmethod
    def _strategy_of(t):
        try:
            meta = t["metadata"]
            if isinstance(meta, str): meta = json.loads(meta or "{}")
            return (meta or {}).get("strategy") or "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def _summary(pnls):
        wins = [p for p in pnls if p > 0]; losses = [p for p in pnls if p < 0]
        gl = abs(sum(losses))
        return {"n": len(pnls), "wins": len(wins), "losses": len(losses), "net": sum(pnls),
                "wr": (len(wins) / len(pnls) * 100) if pnls else 0.0,
                "pf": (sum(wins) / gl) if gl > 0 else None,
                "avg_win": (sum(wins) / len(wins)) if wins else 0.0,
                "avg_loss": (sum(losses) / len(losses)) if losses else 0.0,
                "exp": (sum(pnls) / len(pnls)) if pnls else 0.0}

    async def cmd_help(self, update, context):
        if not await self._guard(update): return
        await update.effective_message.reply_text(_b(
            "الأوامر المتاحة:\n\n"
            "/status - حالة البوت\n/balance - الرصيد\n/positions - الصفقات المفتوحة (مع أرقامها)\n/tiers - الأداء حسب فئة سعر العملة\n"
            "/count - عدد الصفقات المفتوحة\n/profit - الربح الكلي والمقاييس\n/daily [أيام] - الأداء اليومي\n"
            "/stats - إحصاءات حسب سبب الخروج والاستراتيجية\n/pairs - الأداء حسب العملة\n"
            "/history - آخر 10 صفقات مغلقة\n/performance - ملخص سريع\n/risk - حالة المخاطرة\n"
            "/forceexit <رقم|all> - إغلاق صفقة أو كل الصفقات\n/pause - إيقاف فتح صفقات جديدة\n/resume - استئناف"))

    async def cmd_profit(self, update, context):
        if not await self._guard(update): return
        closed = self._closed_trades()
        if not closed:
            await update.effective_message.reply_text(_b("لا توجد صفقات مغلقة بعد.")); return
        pnls = [float(t["net_pnl"] or 0) for t in closed]
        s = self._summary(pnls)
        initial = float(self.db.get_state("initial_balance", config.INITIAL_BALANCE))
        port = self.db.get_portfolio()
        by_pair = {}
        for t in closed: by_pair[t["symbol"]] = by_pair.get(t["symbol"], 0.0) + float(t["net_pnl"] or 0)
        best = max(by_pair.items(), key=lambda kv: kv[1]); worst = min(by_pair.items(), key=lambda kv: kv[1])
        eq = peak = initial; mdd = 0.0
        for p in pnls:
            eq += p; peak = max(peak, eq)
            if peak: mdd = max(mdd, (peak - eq) / peak * 100)
        pf = "∞" if s["pf"] is None else f"{s['pf']:.2f}"
        await update.effective_message.reply_text(_b(
            "💰 الربح الكلي\n\n"
            f"الصفقات المغلقة: {s['n']} (رابحة {s['wins']} / خاسرة {s['losses']})\n"
            f"نسبة النجاح: {s['wr']:.1f}%\n"
            f"صافي الربح: {s['net']:+.2f} USDT ({s['net'] / initial * 100:+.2f}%)\n"
            f"الربح العائم: {port['unrealized_pnl']:+.2f} USDT\n"
            f"متوسط الربح: {s['avg_win']:+.2f} | متوسط الخسارة: {s['avg_loss']:+.2f}\n"
            f"التوقع لكل صفقة: {s['exp']:+.2f} USDT\n"
            f"معامل الربح: {pf}\n"
            f"أقصى تراجع محقق: {mdd:.1f}%\n"
            f"أفضل عملة: {best[0]} ({best[1]:+.2f})\n"
            f"أسوأ عملة: {worst[0]} ({worst[1]:+.2f})"))

    async def cmd_daily(self, update, context):
        if not await self._guard(update): return
        try: days = int(context.args[0]) if getattr(context, "args", None) else 7
        except (ValueError, TypeError, IndexError): days = 7
        days = max(1, min(days, 30))
        agg = {}
        for t in self._closed_trades():
            d = (t["closed_at"] or "")[:10]
            if d:
                a = agg.setdefault(d, [0.0, 0]); a[0] += float(t["net_pnl"] or 0); a[1] += 1
        last = sorted(agg.items(), reverse=True)[:days]
        if not last:
            await update.effective_message.reply_text(_b("لا توجد صفقات مغلقة بعد.")); return
        lines = [f"{'🟢' if v[0] > 0 else '🔴' if v[0] < 0 else '⚪'} {d}: {v[0]:+.2f} USDT ({v[1]} صفقات)" for d, v in last]
        total = sum(v[0] for _, v in last)
        await update.effective_message.reply_text(_b(f"📅 الأداء اليومي (UTC)\n\n" + "\n".join(lines) + f"\n\nالمجموع: {total:+.2f} USDT"))

    async def cmd_stats(self, update, context):
        if not await self._guard(update): return
        closed = self._closed_trades()
        if not closed:
            await update.effective_message.reply_text(_b("لا توجد صفقات مغلقة بعد.")); return
        def block(title, keyfn):
            groups = {}
            for t in closed: groups.setdefault(keyfn(t), []).append(float(t["net_pnl"] or 0))
            out = [title]
            for k, v in sorted(groups.items(), key=lambda kv: -sum(kv[1])):
                s = self._summary(v)
                out.append(f"• {k}: {s['n']} صفقة | نجاح {s['wr']:.0f}% | {s['net']:+.2f} USDT")
            return "\n".join(out)
        await update.effective_message.reply_text(_b(
            "📊 إحصاءات\n\n" + block("حسب سبب الخروج:", lambda t: t["exit_reason"] or "?") + "\n\n" +
            block("حسب الاستراتيجية:", self._strategy_of) + "\n\n" +
            block("حسب الاتجاه:", lambda t: t["side"]) + "\n\n" + block("حسب السوق:", lambda t: t["source"])))

    async def cmd_pairs(self, update, context):
        if not await self._guard(update): return
        closed = self._closed_trades()
        if not closed:
            await update.effective_message.reply_text(_b("لا توجد صفقات مغلقة بعد.")); return
        groups = {}
        for t in closed: groups.setdefault(t["symbol"], []).append(float(t["net_pnl"] or 0))
        ranked = sorted(groups.items(), key=lambda kv: -sum(kv[1]))
        best = ranked[:10]
        worst = [r for r in ranked[-5:] if r not in best]          # never hide the losing pairs

        def row(sym, v):
            s = self._summary(v)
            return f"{'🟢' if s['net'] > 0 else '🔴' if s['net'] < 0 else '⚪'} {sym}: {s['net']:+.2f} USDT ({s['n']} صفقة، نجاح {s['wr']:.0f}%)"
        text = "🪙 الأداء حسب العملة\n\n" + "\n".join(row(*r) for r in best)
        if worst:
            text += "\n\n⬇️ الأضعف:\n" + "\n".join(row(*r) for r in worst)
        await update.effective_message.reply_text(_b(text))


    async def cmd_tiers(self, update, context):
        """Performance grouped by the coin's price at entry. Price level itself has no bearing on % P&L (position
        size already adapts to it); this groups by entry_price only to let the real numbers answer the question
        instead of an impression from a handful of trades. A cheap/meme coin still gets the modelled 5bps slippage
        like a major one, so any edge shown here may be more optimistic than real execution on illiquid coins."""
        if not await self._guard(update): return
        closed = self._closed_trades()
        if not closed:
            await update.effective_message.reply_text(_b("لا توجد صفقات مغلقة بعد.")); return
        tiers = [("< 0.01$", 0, 0.01), ("0.01$ - 1$", 0.01, 1), ("1$ - 100$", 1, 100), ("> 100$", 100, float("inf"))]
        groups = {label: [] for label, _, _ in tiers}
        for t in closed:
            price = float(t["entry_price"] or 0)
            for label, low, high in tiers:
                if low <= price < high:
                    groups[label].append(float(t["net_pnl"] or 0))
                    break
        lines = []
        for label, _, _ in tiers:
            pnls = groups[label]
            if not pnls:
                lines.append(f"⚪ {label}: لا صفقات")
                continue
            s = self._summary(pnls)
            lines.append(f"{'🟢' if s['net'] > 0 else '🔴'} {label}: {s['net']:+.2f} USDT ({s['n']} صفقة، نجاح {s['wr']:.0f}%، متوسط {s['exp']:+.2f})")
        await update.effective_message.reply_text(_b(
            "💲 الأداء حسب فئة سعر العملة (عند الدخول)\n\n" + "\n".join(lines) +
            "\n\n⚠️ الانزلاق المحاكى ثابت لكل العملات، فقد يكون التنفيذ الحقيقي على العملات الضعيفة السيولة أسوأ مما تُظهره هذه الأرقام."))

    async def cmd_count(self, update, context):
        if not await self._guard(update): return
        pos = self.db.get_open_positions(); port = self.db.get_portfolio()
        longs = sum(1 for p in pos if p["side"] == "LONG")
        await update.effective_message.reply_text(_b(
            f"🔢 الصفقات المفتوحة: {len(pos)}/{config.MAX_OPEN_POSITIONS}\n"
            f"شراء: {longs} | بيع: {len(pos) - longs} (الحد في الاتجاه الواحد: {getattr(config, 'MAX_SAME_SIDE', '-')})\n"
            f"النقد المتاح: {port['cash_balance']:.2f} USDT"))

    async def cmd_forceexit(self, update, context):
        if not await self._guard(update): return
        args = getattr(context, "args", None) or []
        if not args:
            await update.effective_message.reply_text(_b("الاستخدام: /forceexit <رقم الصفقة> أو /forceexit all")); return
        target = str(args[0]).lower()
        positions = self.db.get_open_positions()
        if target != "all":
            try: pid = int(target.lstrip("#"))
            except ValueError:
                await update.effective_message.reply_text(_b("رقم غير صالح. استخدم رقم الصفقة من /positions.")); return
            positions = [p for p in positions if p["id"] == pid]
        if not positions:
            await update.effective_message.reply_text(_b("لا توجد صفقة مفتوحة مطابقة.")); return
        prices, done = {}, 0
        for p in positions:
            try:
                price = await self.engine._live_price(p["symbol"], p["source"], prices)
                if not price: continue
                res = self.engine.trader.close_position(p["id"], price, "FORCE_EXIT")
                if res:
                    done += 1; await self.notify_trade_closed(res)
            except Exception as exc:
                log.warning("forceexit failed for %s: %s", p["symbol"], exc)
        await update.effective_message.reply_text(_b(f"تم إغلاق {done} من {len(positions)} صفقة."))

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._guard(update): return
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "toggle_pause":
            self.engine.set_paused(not self.engine.paused)
            status = "متوقف ⏸" if self.engine.paused else "يعمل ▶️"
            await query.edit_message_text(_b(f"تم تغيير حالة البوت إلى: {status}"))
            
        elif data.startswith("close_"):
            try: pos_id = int(data.split("_", 1)[1])
            except (ValueError, IndexError):
                await query.edit_message_text(_b("طلب غير صالح.")); return
            pos = self.db.get_position(pos_id)
            if not pos or pos["status"] != "OPEN":
                await query.edit_message_text(_b("الصفقة مغلقة بالفعل أو غير موجودة.")); return
            try:
                price = await self.engine._live_price(pos["symbol"], pos["source"])
                if not price:
                    await query.edit_message_text(_b("❌ لا يتوفر سعر حي الآن؛ لم يتم الإغلاق. حاول لاحقاً.")); return
                closed = self.engine.trader.close_position(pos["id"], price, "MANUAL_TELEGRAM")
                if closed:
                    await query.edit_message_text(_b(f"✅ تم إغلاق {closed['symbol']} يدوياً.\nالربح: {float(closed['net_pnl']):+.2f} USDT"))
            except Exception as e:
                log.warning("Manual close failed: %s", e)
                await query.edit_message_text(_b("خطأ في الإغلاق، راجع السجلات."))

    async def send(self,message, reply_markup=None):
        if not self.enabled or not config.TELEGRAM_CHAT_ID: return False
        try:
            await self.app.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=_b(message), reply_markup=reply_markup)
            return True
        except Exception as e: 
            log.error(f"Telegram send error: {e}")
            return False

    async def notify_trade_opened(self, position):
        keyboard = [[InlineKeyboardButton("❌ إغلاق الصفقة", callback_data=f"close_{position['id']}")]]
        text = (f"🟢 تم فتح صفقة جديدة (محاكاة)\n{position['source']} | {position['symbol']} | {position['side']}\n"
                f"سعر الدخول: {position['entry_price']:.6g}\nوقف الخسارة: {position['stop_price']:.6g}\nالهدف: {position['target_price']:.6g}\n"
                f"الكمية: {position['quantity']:.6g}\nالمخاطرة: {position['risk_amount']:.2f} USDT")
        return await self.send(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def notify_trade_closed(self, position):
        risk = float(position.get("initial_risk") or 0)
        r_txt = f"\nR: {float(position['net_pnl']) / risk:+.2f}" if risk > 0 else ""
        text = (f"🔴 تم إغلاق صفقة\n{position['source']} | {position['symbol']} | {position['side']}\nسعر الخروج: {float(position['exit_price']):.6g}\n"
                f"صافي الربح (بعد الرسوم): {float(position['net_pnl']):+.4f} USDT{r_txt}\nالسبب: {position.get('exit_reason')}")
        return await self.send(text)

    async def notify_event(self, event):
        """Partial closes (scale-out) and similar events from the paper trader."""
        pos = event.get("position") or {}
        if event.get("type") == "SCALE_OUT":
            return await self.send(f"🟡 إغلاق جزئي\n{pos.get('symbol')} | {pos.get('side')}\nالكمية المغلقة: {event['quantity']:.6g} عند {event['price']:.6g}\n"
                                   f"تم نقل الوقف إلى نقطة التعادل: {pos.get('stop_price', 0):.6g}")
        return False

    async def close(self):
        if self.app:
            try:
                if self.app.updater and self.app.updater.running: await self.app.updater.stop()
                await self.app.stop(); await self.app.shutdown()
            except Exception: pass
