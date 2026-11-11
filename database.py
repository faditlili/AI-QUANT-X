"""SQLite persistence for virtual portfolio only."""
import sqlite3, threading, json, logging
from pathlib import Path
from datetime import datetime, timezone, date
import config

def utc_now():
    return datetime.now(timezone.utc).isoformat()

class Database:
    def __init__(self, db_path=None, initial_balance=None):
        self.path = str(db_path or config.DB_PATH)
        if self.path != ":memory:":
            try:
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
                probe = Path(self.path).parent / ".write_test"
                probe.write_text("ok"); probe.unlink()
            except OSError:
                fallback = Path("./data/ai_quant_x.db")
                logging.getLogger(__name__).warning(
                    "DB path %s not writable; using %s (data will not persist across deploys)",
                    self.path, fallback)
                fallback.parent.mkdir(parents=True, exist_ok=True)
                self.path = str(fallback)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=20)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=20000")
        self._schema()
        with self.lock:
            row = self.conn.execute("SELECT value FROM state WHERE key='initial_balance'").fetchone()
            if not row:
                self.conn.execute("INSERT INTO state(key,value) VALUES('initial_balance',?)",
                                  (str(initial_balance or config.INITIAL_BALANCE),))
                self.conn.execute("INSERT OR IGNORE INTO state(key,value) VALUES('daily_baseline',?)",
                                  (str(initial_balance or config.INITIAL_BALANCE),))
                self.conn.execute("INSERT OR IGNORE INTO state(key,value) VALUES('cash_balance',?)",
                                  (str(initial_balance or config.INITIAL_BALANCE),))
                self.conn.commit()

    def _schema(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS positions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, source TEXT NOT NULL,
          side TEXT NOT NULL, quantity REAL NOT NULL, entry_price REAL NOT NULL,
          stop_price REAL NOT NULL, target_price REAL NOT NULL, margin_used REAL NOT NULL,
          risk_amount REAL NOT NULL, opening_fee REAL NOT NULL, status TEXT NOT NULL,
          opened_at TEXT NOT NULL, closed_at TEXT, exit_price REAL, gross_pnl REAL,
          net_pnl REAL, closing_fee REAL, exit_reason TEXT, metadata TEXT,
          CHECK(source IN ('spot','futures')), CHECK(side IN ('LONG','SHORT'))
        );
        CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
        CREATE TABLE IF NOT EXISTS decisions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, action TEXT,
          score REAL, reason TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS equity_snapshots(
          id INTEGER PRIMARY KEY AUTOINCREMENT, equity REAL, created_at TEXT NOT NULL
        );
        """)
        cols={r["name"] for r in self.conn.execute("PRAGMA table_info(positions)").fetchall()}
        if "strategy" not in cols:
            self.conn.execute("ALTER TABLE positions ADD COLUMN strategy TEXT")
        if "initial_stop" not in cols:
            self.conn.execute("ALTER TABLE positions ADD COLUMN initial_stop REAL")
        self.conn.commit()

    def get_state(self,key,default=None):
        with self.lock:
            r=self.conn.execute("SELECT value FROM state WHERE key=?",(key,)).fetchone()
            return r["value"] if r else default

    def set_state(self,key,value):
        with self.lock:
            self.conn.execute("INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                              (key,str(value)))
            self.conn.commit()

    def refresh_daily_baseline(self):
        today = datetime.now(timezone.utc).date().isoformat()
        if self.get_state("daily_date") != today:
            equity = self.get_portfolio()["equity"]
            with self.lock:
                self.conn.execute("INSERT OR REPLACE INTO state(key,value) VALUES('daily_baseline',?)",(str(equity),))
                self.conn.execute("INSERT OR REPLACE INTO state(key,value) VALUES('daily_date',?)",(today,))
                self.conn.commit()
        return float(self.get_state("daily_baseline", config.INITIAL_BALANCE))

    def get_portfolio(self):
        with self.lock:
            cash = float(self.get_state("cash_balance", self.get_state("initial_balance", config.INITIAL_BALANCE)))
            rows=self.conn.execute("SELECT * FROM positions WHERE status='OPEN'").fetchall()
        margin=sum(float(r["margin_used"]) for r in rows)
        unrealized=0.0
        for r in rows:
            # Last mark stored in state by paper trader; absent means entry price.
            mark=float(self.get_state(f"mark:{r['id']}", r["entry_price"]))
            sign=1 if r["side"]=="LONG" else -1
            unrealized += (mark-r["entry_price"])*r["quantity"]*sign
        realized=float(self.get_state("realized_pnl",0))
        return {"cash_balance":cash,"open_margin":margin,"unrealized_pnl":unrealized,
                "realized_pnl":realized,"equity":cash+margin+unrealized,
                "open_count":len(rows)}

    def get_open_positions(self):
        with self.lock:
            rows=self.conn.execute("SELECT * FROM positions WHERE status='OPEN' ORDER BY opened_at").fetchall()
        return [dict(r) for r in rows]

    def get_position(self,pid):
        with self.lock:
            r=self.conn.execute("SELECT * FROM positions WHERE id=?",(pid,)).fetchone()
        return dict(r) if r else None

    def create_position(self, data):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                if self.conn.execute("SELECT 1 FROM positions WHERE symbol=? AND source=? AND status='OPEN'",
                                     (data["symbol"],data["source"])).fetchone():
                    raise ValueError("Position already open for this symbol/source")
                state={r["key"]:r["value"] for r in self.conn.execute("SELECT key,value FROM state").fetchall()}
                cash=float(state.get("cash_balance",state.get("initial_balance",config.INITIAL_BALANCE)))
                opened=self.conn.execute("SELECT * FROM positions WHERE status='OPEN'").fetchall()
                margin=sum(float(r["margin_used"]) for r in opened)
                unreal=0.0
                risk=sum(float(r["risk_amount"]) for r in opened)
                for r in opened:
                    mark=float(state.get(f"mark:{r['id']}",r["entry_price"]))
                    sign=1 if r["side"]=="LONG" else -1
                    unreal+=(mark-r["entry_price"])*r["quantity"]*sign
                equity=cash+margin+unreal
                if risk+float(data["risk_amount"]) > equity*config.MAX_PORTFOLIO_RISK_PCT/100+1e-8:
                    raise ValueError("Aggregate portfolio risk cap exceeded")
                if float(data["margin_used"])+float(data["opening_fee"]) > cash:
                    raise ValueError("Insufficient virtual cash")
                cur=self.conn.execute("""INSERT INTO positions
                (symbol,source,side,quantity,entry_price,stop_price,target_price,margin_used,
                 risk_amount,opening_fee,status,opened_at,metadata,strategy,initial_stop)
                 VALUES(?,?,?,?,?,?,?,?,?,?,'OPEN',?,?,?,?)""",
                (data["symbol"],data["source"],data["side"],data["quantity"],data["entry_price"],
                 data["stop_price"],data["target_price"],data["margin_used"],data["risk_amount"],
                 data["opening_fee"],utc_now(),json.dumps(data.get("metadata",{})),
                 data.get("strategy"),data.get("initial_stop",data["stop_price"])))
                pid=cur.lastrowid
                self.conn.execute("INSERT OR REPLACE INTO state(key,value) VALUES('cash_balance',?)",
                                  (str(cash-data["margin_used"]-data["opening_fee"]),))
                self.conn.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)",(f"mark:{pid}",str(data["entry_price"])))
                self.conn.commit()
                return self.get_position(pid)
            except Exception:
                self.conn.rollback()
                raise

    def update_stop(self,pid,stop):
        with self.lock:
            self.conn.execute("UPDATE positions SET stop_price=? WHERE id=? AND status='OPEN'",(stop,pid))
            self.conn.commit()

    def mark_position(self,pid,price):
        self.set_state(f"mark:{pid}",price)

    def close_position(self,pid,exit_price,reason,closing_fee):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                row=self.conn.execute("SELECT * FROM positions WHERE id=? AND status='OPEN'",(pid,)).fetchone()
                if not row:
                    self.conn.rollback()
                    return None
                sign=1 if row["side"]=="LONG" else -1
                gross=(exit_price-row["entry_price"])*row["quantity"]*sign
                net=gross-row["opening_fee"]-closing_fee
                cash=float(self.get_state("cash_balance",self.get_state("initial_balance",config.INITIAL_BALANCE)))
                cash += row["margin_used"]+gross-closing_fee
                self.conn.execute("INSERT OR REPLACE INTO state(key,value) VALUES('cash_balance',?)",(str(cash),))
                realized=float(self.get_state("realized_pnl",0))+net
                self.conn.execute("INSERT OR REPLACE INTO state(key,value) VALUES('realized_pnl',?)",(str(realized),))
                self.conn.execute("""UPDATE positions SET status='CLOSED',closed_at=?,exit_price=?,
                  gross_pnl=?,net_pnl=?,closing_fee=?,exit_reason=? WHERE id=?""",
                  (utc_now(),exit_price,gross,net,closing_fee,reason,pid))
                self.conn.execute("DELETE FROM state WHERE key=?",(f"mark:{pid}",))
                self.conn.commit()
                return self.get_position(pid)
            except Exception:
                self.conn.rollback()
                raise

    def add_decision(self,symbol,source,action,score,reason):
        with self.lock:
            self.conn.execute("INSERT INTO decisions(symbol,source,action,score,reason,created_at) VALUES(?,?,?,?,?,?)",
                              (symbol,source,action,score,reason,utc_now()))
            self.conn.commit()

    def get_recent_decisions(self,limit=50):
        with self.lock:
            rows=self.conn.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_recent_trades(self,limit=50):
        with self.lock:
            rows=self.conn.execute("SELECT * FROM positions ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_today_pnl(self):
        today=datetime.now(timezone.utc).date().isoformat()
        with self.lock:
            rows=self.conn.execute("SELECT COALESCE(SUM(net_pnl),0) p FROM positions WHERE status='CLOSED' AND substr(closed_at,1,10)=?",(today,)).fetchone()
        return float(rows["p"])

    def get_performance(self):
        with self.lock:
            rows=self.conn.execute("SELECT net_pnl FROM positions WHERE status='CLOSED'").fetchall()
        vals=[float(r["net_pnl"] or 0) for r in rows]
        wins=[x for x in vals if x>0]; losses=[x for x in vals if x<0]
        gp=sum(wins); gl=abs(sum(losses))
        return {"total_trades":len(vals),"wins":len(wins),"losses":len(losses),
                "win_rate":(len(wins)/len(vals)*100 if vals else 0),
                "profit_factor":(gp/gl if gl else (None if gp else 0)),
                "net_pnl":sum(vals),"gross_profit":gp,"gross_loss":gl}

    def get_performance_by_strategy(self):
        with self.lock:
            rows=self.conn.execute("SELECT COALESCE(strategy,'unknown') s, net_pnl FROM positions WHERE status='CLOSED'").fetchall()
        groups={}
        for r in rows:
            groups.setdefault(r["s"],[]).append(float(r["net_pnl"] or 0))
        out={}
        for name,vals in groups.items():
            wins=[x for x in vals if x>0]; gl=abs(sum(x for x in vals if x<0)); gp=sum(wins)
            out[name]={"trades":len(vals),"wins":len(wins),"win_rate":len(wins)/len(vals)*100,
                       "net_pnl":sum(vals),"profit_factor":(gp/gl if gl else None)}
        return out

    def get_peak_equity(self):
        base=float(self.get_state("initial_balance",config.INITIAL_BALANCE))
        floor=self.get_state("peak_floor"); since=self.get_state("peak_since")
        with self.lock:
            if since:
                r=self.conn.execute("SELECT MAX(equity) m FROM equity_snapshots WHERE created_at>=?",(since,)).fetchone()
                return max(float(floor or 0),float(r["m"] or 0))
            r=self.conn.execute("SELECT MAX(equity) m FROM equity_snapshots").fetchone()
        return max(base,float(r["m"] or 0))

    def reset_peak(self,equity):
        self.set_state("peak_floor",equity); self.set_state("peak_since",utc_now())

    def snapshot(self):
        eq=self.get_portfolio()["equity"]
        with self.lock:
            self.conn.execute("INSERT INTO equity_snapshots(equity,created_at) VALUES(?,?)",(eq,utc_now()))
            self.conn.commit()
        return eq

    def close(self):
        with self.lock:
            self.conn.close()
