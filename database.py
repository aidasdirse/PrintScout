import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "printscout.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            opportunity_score INTEGER,
            demand_score INTEGER,
            competition_score INTEGER,
            trend TEXT,
            trend_note TEXT,
            avg_price_low REAL,
            avg_price_high REAL,
            margin_estimate TEXT,
            platform_scores TEXT,
            top_search_terms TEXT,
            why_buy TEXT,
            pitfalls TEXT,
            tips TEXT,
            related_niches TEXT,
            sources TEXT,
            reddit_mentions INTEGER DEFAULT 0,
            ebay_avg_price REAL,
            etsy_listing_count INTEGER,
            google_trend_score INTEGER,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(keyword)
        );

        CREATE TABLE IF NOT EXISTS keyword_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            opportunity_score INTEGER,
            demand_score INTEGER,
            competition_score INTEGER,
            google_trend_score INTEGER,
            recorded_at TEXT
        );

        CREATE TABLE IF NOT EXISTS app_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state TEXT DEFAULT 'idle',
            message TEXT DEFAULT 'Not yet run',
            updated_at TEXT
        );

        INSERT OR IGNORE INTO app_status (id, state, message, updated_at)
        VALUES (1, 'idle', 'Starting up...', datetime('now'));
    """)
    conn.commit()
    conn.close()

def set_status(state: str, message: str):
    conn = get_conn()
    conn.execute("""
        UPDATE app_status SET state=?, message=?, updated_at=datetime('now') WHERE id=1
    """, (state, message))
    conn.commit()
    conn.close()

def get_status():
    conn = get_conn()
    row = conn.execute("SELECT * FROM app_status WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else {}

def upsert_opportunity(data: dict):
    conn = get_conn()
    now = datetime.now().isoformat()
    existing = conn.execute("SELECT id FROM opportunities WHERE keyword=?", (data["keyword"],)).fetchone()

    fields = ["keyword","opportunity_score","demand_score","competition_score","trend","trend_note",
              "avg_price_low","avg_price_high","margin_estimate","platform_scores","top_search_terms",
              "why_buy","pitfalls","tips","related_niches","sources","reddit_mentions",
              "ebay_avg_price","etsy_listing_count","google_trend_score"]

    def serialize(v):
        return json.dumps(v) if isinstance(v, (list, dict)) else v

    values = {f: serialize(data.get(f)) for f in fields}

    if existing:
        sets = ", ".join(f"{f}=?" for f in fields)
        conn.execute(f"UPDATE opportunities SET {sets}, updated_at=? WHERE keyword=?",
                     [values[f] for f in fields] + [now, data["keyword"]])
    else:
        values["created_at"] = now
        values["updated_at"] = now
        cols = ", ".join(values.keys())
        placeholders = ", ".join("?" * len(values))
        conn.execute(f"INSERT INTO opportunities ({cols}) VALUES ({placeholders})", list(values.values()))

    conn.execute("""
        INSERT INTO keyword_history (keyword, opportunity_score, demand_score, competition_score, google_trend_score, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (data["keyword"], data.get("opportunity_score"), data.get("demand_score"),
          data.get("competition_score"), data.get("google_trend_score"), now))

    conn.commit()
    conn.close()

def get_opportunities(limit=50):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM opportunities ORDER BY opportunity_score DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    results = []
    json_fields = ["platform_scores","top_search_terms","why_buy","pitfalls","tips","related_niches","sources"]
    for row in rows:
        d = dict(row)
        for f in json_fields:
            if d.get(f):
                try: d[f] = json.loads(d[f])
                except: pass
        results.append(d)
    return results

def get_keyword_detail(keyword: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM opportunities WHERE keyword=?", (keyword,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    json_fields = ["platform_scores","top_search_terms","why_buy","pitfalls","tips","related_niches","sources"]
    for f in json_fields:
        if d.get(f):
            try: d[f] = json.loads(d[f])
            except: pass
    return d

def get_keyword_history(keyword: str, days: int = 14):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM keyword_history WHERE keyword=?
        AND recorded_at >= datetime('now', '-' || ? || ' days')
        ORDER BY recorded_at ASC
    """, (keyword, days)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
