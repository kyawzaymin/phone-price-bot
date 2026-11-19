import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "prices.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier TEXT,
        model TEXT,
        ram_storage TEXT,
        color TEXT,
        region TEXT,
        price INTEGER,
        stock_status TEXT,
        raw_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

def save_quote(supplier, model, ram_storage, color, region, price, stock_status="instock", raw_text=""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO quotes (supplier, model, ram_storage, color, region, price, stock_status, raw_text)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (supplier, model, ram_storage, color, region, price, stock_status, raw_text))
    conn.commit()
    conn.close()

def clear_quotes():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM quotes")
    conn.commit()
    conn.close()

def get_best_supplier(query):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    q = f"%{query.strip()}%"
    cur.execute("""
    SELECT * FROM quotes 
    WHERE (model LIKE ? OR raw_text LIKE ?) 
      AND stock_status != 'oos' 
      AND price IS NOT NULL AND price > 0
    ORDER BY price ASC
    """, (q, q))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    
    best = rows[0]
    all_prices = {}
    for r in rows:
        if r["supplier"] not in all_prices:
            all_prices[r["supplier"]] = r["price"]
    
    savings = 0
    if len(all_prices) > 1:
        sorted_p = sorted([p for p in all_prices.values() if isinstance(p, (int, float))])
        if len(sorted_p) > 1:
            savings = sorted_p[1] - sorted_p[0]
            
    return {
        "model": best["model"],
        "ram_storage": best["ram_storage"],
        "color": best["color"],
        "region": best["region"],
        "cheapest_supplier": best["supplier"],
        "lowest_price": best["price"],
        "savings": savings,
        "all_prices": all_prices
    }

def get_all_comparison():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
    SELECT model, ram_storage, supplier, price 
    FROM quotes 
    WHERE stock_status != 'oos' AND price IS NOT NULL AND price > 0
    ORDER BY model ASC, ram_storage ASC, price ASC
    """)
    rows = cur.fetchall()
    conn.close()
    
    grouped = {}
    for r in rows:
        key = f"{r['model']}_{r['ram_storage']}"
        if key not in grouped:
            grouped[key] = {
                "model": r["model"],
                "ram_storage": r["ram_storage"],
                "prices": {}
            }
        grouped[key]["prices"][r["supplier"]] = r["price"]
        
    result = []
    for k, v in grouped.items():
        p_dict = v["prices"]
        sorted_p = sorted(p_dict.items(), key=lambda x: x[1])
        cheapest_s, lowest_p = sorted_p[0]
        savings = 0
        if len(sorted_p) > 1:
            savings = sorted_p[1][1] - sorted_p[0][1]
        result.append({
            "model": v["model"],
            "ram_storage": v["ram_storage"],
            "cheapest_supplier": cheapest_s,
            "lowest_price": lowest_p,
            "savings": savings,
            "all_prices": p_dict
        })
    return result
