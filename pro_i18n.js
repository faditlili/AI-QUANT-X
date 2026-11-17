
"use strict";
(function () {
  window.QI18N = {
    en: {
      nav_overview: "Overview", nav_positions: "Positions", nav_history: "History", nav_signals: "Signals", nav_tools: "System",
      running: "LIVE", paused: "PAUSED", offline: "OFFLINE", pause: "Pause", resume: "Resume",
      equity: "Total equity", since_start: "since start", cash: "Cash", floating: "Floating", in_trades: "In trades", open_risk: "Open risk",
      risk_heat: "Risk heat", daily_pnl: "Today", daily_limit: "Daily loss limit", used: "used",
      limit_hit: "Daily limit reached: new entries are blocked until the next UTC day.",
      drawdown: "Drawdown", max_dd: "Max drawdown",
      win_rate: "Win rate", profit_factor: "Profit factor", expectancy: "Per trade", avg_win: "Avg win", avg_loss: "Avg loss",
      trades: "Trades", net: "Net P&L", payoff: "Payoff",
      market: "Market pulse", compass: "BTC/ETH compass", breadth: "Breadth", bullish: "Bullish", bearish: "Bearish", neutral: "Neutral",
      last_scan: "Last scan", movers: "Top movers", gainers: "Gainers", losers: "Losers", chart: "Chart",
      r6h: "6H", r1d: "1D", r7d: "7D", rall: "ALL", no_data: "No data yet",
      no_positions: "No open positions", long: "LONG", short: "SHORT", entry: "Entry", now: "Now", stop: "Stop", target: "Target",
      size: "Size", risk: "Risk", close: "Close", close_q: "Close this position at the market price?", cancel: "Cancel", confirm: "Confirm",
      closed_ok: "Position closed", open_pnl: "Open P&L", open_count: "Open",
      f_all: "All", f_wins: "Wins", f_losses: "Losses", by_strategy: "By strategy", exits: "Exit reasons", recent: "Recent results",
      no_trades: "No closed trades yet", best: "Best", worst: "Worst", cum: "Cumulative P&L",
      why_none: "Why no trades?", top_blockers: "Top blockers in recent scans", feed: "Decision feed",
      f_entries: "Entries", f_blocked: "Blocked", search: "Search symbol", no_signals: "No decisions yet",
      decisions: "Decisions", entries_n: "Entries", entry_rate: "Entry rate", all_clear: "No blockers recorded",
      engine: "Engine", strategies: "Strategies", ml: "ML filter", ml_none: "Not trained yet", ml_off: "Inactive: no proven edge, so it does not filter",
      ml_on: "Active", accuracy: "Accuracy", baseline: "Baseline", age: "Model age", protection: "Protection", ok: "All clear",
      symbols: "Symbols watched", scan_every: "Scan every", risk_cfg: "Risk settings", per_trade: "Per trade", portfolio: "Portfolio cap",
      max_pos: "Max positions", backtest: "Backtest", run: "Run", autotune: "Auto-Tune", working: "Working...", symbol: "Symbol",
      strategy: "Strategy", language: "Language", version: "Version", tune_ok: "Auto-Tune applied", tune_fail: "Auto-Tune result",
      healthy: "healthy", paused_s: "paused", auto_active: "Auto-Tune active", hours: "h", min: "m", sec: "s", ago: "ago",
      err_load: "Connection problem", missing: "Some files are missing or incomplete:"
    },
    ar: {
      nav_overview: "الرئيسية", nav_positions: "الصفقات", nav_history: "السجل", nav_signals: "الإشارات", nav_tools: "النظام",
      running: "يعمل", paused: "متوقف", offline: "غير متصل", pause: "إيقاف", resume: "استئناف",
      equity: "إجمالي الرصيد", since_start: "منذ البداية", cash: "السيولة", floating: "العائم", in_trades: "داخل الصفقات", open_risk: "المخاطرة المفتوحة",
      risk_heat: "حرارة المخاطر", daily_pnl: "اليوم", daily_limit: "حد الخسارة اليومي", used: "مستخدم",
      limit_hit: "تم بلوغ الحد اليومي: الدخول الجديد متوقف حتى اليوم التالي بتوقيت UTC.",
      drawdown: "التراجع", max_dd: "أقصى تراجع",
      win_rate: "نسبة الربح", profit_factor: "عامل الربح", expectancy: "لكل صفقة", avg_win: "متوسط الربح", avg_loss: "متوسط الخسارة",
      trades: "الصفقات", net: "صافي الربح", payoff: "نسبة العائد",
      market: "نبض السوق", compass: "بوصلة BTC/ETH", breadth: "اتساع السوق", bullish: "صاعد", bearish: "هابط", neutral: "محايد",
      last_scan: "آخر مسح", movers: "الأكثر حركة", gainers: "الرابحون", losers: "الخاسرون", chart: "الرسم",
      r6h: "6س", r1d: "يوم", r7d: "7أيام", rall: "الكل", no_data: "لا بيانات بعد",
      no_positions: "لا توجد صفقات مفتوحة", long: "شراء", short: "بيع", entry: "الدخول", now: "الآن", stop: "الوقف", target: "الهدف",
      size: "الحجم", risk: "المخاطرة", close: "إغلاق", close_q: "إغلاق هذه الصفقة بسعر السوق؟", cancel: "إلغاء", confirm: "تأكيد",
      closed_ok: "تم إغلاق الصفقة", open_pnl: "الربح المفتوح", open_count: "مفتوحة",
      f_all: "الكل", f_wins: "رابحة", f_losses: "خاسرة", by_strategy: "حسب الاستراتيجية", exits: "أسباب الخروج", recent: "آخر النتائج",
      no_trades: "لا توجد صفقات مغلقة بعد", best: "الأفضل", worst: "الأسوأ", cum: "الربح التراكمي",
      why_none: "لماذا لا توجد صفقات؟", top_blockers: "أكثر أسباب الحجب في المسوحات الأخيرة", feed: "سجل القرارات",
      f_entries: "دخول", f_blocked: "محجوبة", search: "ابحث عن عملة", no_signals: "لا قرارات بعد",
      decisions: "القرارات", entries_n: "الدخول", entry_rate: "نسبة الدخول", all_clear: "لا أسباب حجب مسجلة",
      engine: "المحرك", strategies: "الاستراتيجيات", ml: "فلتر ML", ml_none: "لم يُدرَّب بعد", ml_off: "غير مفعّل: لا تفوق مثبت، فلا يحجب شيئاً",
      ml_on: "مفعّل", accuracy: "الدقة", baseline: "الخط الأساسي", age: "عمر النموذج", protection: "الحماية", ok: "كل شيء سليم",
      symbols: "العملات المراقبة", scan_every: "المسح كل", risk_cfg: "إعدادات المخاطرة", per_trade: "لكل صفقة", portfolio: "سقف المحفظة",
      max_pos: "أقصى صفقات", backtest: "الباكتست", run: "تشغيل", autotune: "الضبط التلقائي", working: "جارٍ العمل...", symbol: "العملة",
      strategy: "الاستراتيجية", language: "اللغة", version: "الإصدار", tune_ok: "تم تطبيق الضبط التلقائي", tune_fail: "نتيجة الضبط التلقائي",
      healthy: "سليمة", paused_s: "موقوفة", auto_active: "الضبط التلقائي مفعّل", hours: "س", min: "د", sec: "ث", ago: "منذ",
      err_load: "مشكلة في الاتصال", missing: "بعض الملفات ناقصة أو غير مكتملة:"
    }
  };
  (window.__mods = window.__mods || []).push("i18n");
})();
