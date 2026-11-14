import config
import json

class Brain:
    def __init__(self, db):
        self.db = db

    def get_dynamic_risk(self):
        """حساب المخاطرة بناءً على معادلة كيلي"""
        trades = [t for t in self.db.get_recent_trades(50) if t["status"] == "CLOSED"]
        if len(trades) < 10:
            return config.RISK_PER_TRADE_PCT

        wins = sum(1 for t in trades if float(t["net_pnl"]) > 0)
        losses = len(trades) - wins
        win_rate = wins / len(trades)
        
        gross_win = sum(float(t["net_pnl"]) for t in trades if float(t["net_pnl"]) > 0)
        gross_loss = abs(sum(float(t["net_pnl"]) for t in trades if float(t["net_pnl"]) < 0))
        
        avg_win = gross_win / wins if wins > 0 else 0
        avg_loss = gross_loss / losses if losses > 0 else 0
        
        if avg_loss == 0 or win_rate == 0: return 0.5 
            
        payoff_ratio = avg_win / avg_loss
        kelly = win_rate - ((1 - win_rate) / payoff_ratio)
        
        # نستخدم نصف كيلي (Half-Kelly) لتقليل المخاطرة
        half_kelly = kelly / 2
        # الحد الأدنى 0.5% والأقصى 3.5%
        return max(0.5, min(half_kelly * 100, 3.5))

    def is_strategy_healthy(self, strategy_name, metadata):
        """مفتاح إيقاف الاستراتيجية (Kill-Switch)"""
        trades = [t for t in self.db.get_recent_trades(50) if t["status"] == "CLOSED"]
        
        strat_trades = []
        for t in trades:
            try:
                meta = json.loads(t["metadata"] or "{}") if isinstance(t["metadata"], str) else t["metadata"]
                if (meta or {}).get("strategy") == strategy_name:
                    strat_trades.append(t)
            except Exception:
                continue
                
        if len(strat_trades) < 4: return True
            
        last_4 = strat_trades[:4]
        if all(float(t["net_pnl"]) < 0 for t in last_4):
            return False # إيقاف الاستراتيجية إذا خسرت 4 مرات متتالية
        return True
