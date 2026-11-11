"""Virtual fills only. This module deliberately has no exchange order interface."""
import config
from trade_management import next_stop

class PaperTrader:
    def __init__(self,database,risk_manager=None):
        from risk_manager import RiskManager
        self.db=database
        self.risk=risk_manager or RiskManager(database)

    def open_position(self,symbol,price,atr,side="LONG",source="futures",metadata=None,
                      stop_mult=None,rr=None,strategy=None):
        sized,reason=self.risk.calculate_position_size(symbol,source,side,float(price),float(atr),stop_mult,rr)
        if not sized:
            return {"success":False,"reason":reason}
        slip=config.SLIPPAGE_BPS/10000
        entry=price*(1+slip if side=="LONG" else 1-slip)
        stop=sized["stop_price"]
        # Recalculate risk against the actual simulated entry.
        risk=abs(entry-stop)*sized["quantity"]
        data={"symbol":symbol,"source":source,"side":side,"quantity":sized["quantity"],
              "entry_price":entry,"stop_price":stop,"target_price":sized["target_price"],
              "margin_used":entry*sized["quantity"],"risk_amount":risk,
              "opening_fee":entry*sized["quantity"]*config.FEE_RATE,
              "initial_stop":stop,"strategy":strategy,"metadata":metadata or {}}
        try:
            pos=self.db.create_position(data)
            return {"success":True,"position":pos}
        except (ValueError,Exception) as exc:
            return {"success":False,"reason":str(exc)}

    def close_position(self,pid,price,reason="MANUAL"):
        pos=self.db.get_position(pid)
        if not pos or pos["status"]!="OPEN":
            return None
        slip=config.SLIPPAGE_BPS/10000
        exit_price=price*(1-slip if pos["side"]=="LONG" else 1+slip)
        fee=exit_price*pos["quantity"]*config.FEE_RATE
        return self.db.close_position(pid,exit_price,reason,fee)

    def _manage_stop(self,pos,price):
        return next_stop(pos["side"],pos["entry_price"],pos.get("initial_stop"),pos["stop_price"],price)

    def update_market_prices(self,prices,source=None):
        results=[]
        for pos in self.db.get_open_positions():
            if source and pos["source"]!=source:
                continue
            item=prices.get(pos["symbol"])
            if not item:
                continue
            price=float(item.get("last_price",0))
            if price<=0:
                continue
            self.db.mark_position(pos["id"],price)
            new_stop=self._manage_stop(pos,price)
            if abs(new_stop-pos["stop_price"])>1e-12:
                self.db.update_stop(pos["id"],new_stop)
                pos["stop_price"]=new_stop
            initial=pos.get("initial_stop") or pos["stop_price"]
            stop_reason="TRAILING_STOP" if abs(pos["stop_price"]-initial)>1e-12 else "STOP_LOSS"
            hit=None
            if pos["side"]=="LONG":
                if price<=pos["stop_price"]: hit=stop_reason
                elif price>=pos["target_price"]: hit="TAKE_PROFIT"
            else:
                if price>=pos["stop_price"]: hit=stop_reason
                elif price<=pos["target_price"]: hit="TAKE_PROFIT"
            if hit:
                results.append(self.close_position(pos["id"],price,hit))
        return results

    def get_open_positions(self):
        return self.db.get_open_positions()
