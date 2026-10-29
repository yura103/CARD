"""CardBenePICK demo API. All card terms are fictional sample data."""
import os
import re
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="CardBenePICK", version="0.1.0")
DB = os.getenv("CARD_DB", "data/card.db")
CATEGORIES = {"cafe": ["카페", "커피", "스타벅스"], "gas": ["주유", "기름"], "convenience": ["편의점", "CU", "GS25"]}
CARDS = [
    {"id": "daily", "name": "데일리 픽 (샘플)", "threshold": 300000, "benefits": {"cafe": .1, "convenience": .05}, "monthly_limit": 10000},
    {"id": "weekend", "name": "위켄드 픽 (샘플)", "threshold": 300000, "benefits": {"cafe": .08, "gas": .05}, "monthly_limit": 15000},
    {"id": "all", "name": "올라운드 픽 (샘플)", "threshold": 0, "benefits": {"cafe": .02, "gas": .02, "convenience": .02}, "monthly_limit": 5000},
]
# Auth is deliberately absent: the API only operates on this fixed demo user.
PROFILE = {"id": "demo", "previous_month_spend": 350000, "owned_cards": ["daily", "weekend", "all"], "used_limits": {"daily": 9500, "weekend": 0, "all": 0}}


@contextmanager
def connection():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript('''CREATE TABLE IF NOT EXISTS settlements (
      id TEXT PRIMARY KEY, merchant TEXT NOT NULL, total INTEGER NOT NULL, own_share INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS participants (
      id TEXT PRIMARY KEY, settlement_id TEXT NOT NULL REFERENCES settlements(id),
      name TEXT NOT NULL, amount INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending');''')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class Search(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    max_previous_spend: int | None = Field(default=None, ge=0)


class Payment(BaseModel):
    merchant: str = Field(min_length=1, max_length=100)
    amount: int = Field(gt=0, le=100000000)
    category: str | None = None


class Settlement(BaseModel):
    merchant: str = Field(min_length=1, max_length=100)
    total: int = Field(gt=0, le=100000000)
    friends: list[str] = Field(min_length=1, max_length=30)


def get_mcc_code(merchant: str, category: str | None = None):
    if category:
        if category not in CATEGORIES:
            raise HTTPException(422, "지원하지 않는 업종입니다")
        return category
    for key, words in CATEGORIES.items():
        if any(word.casefold() in merchant.casefold() for word in words):
            return key
    raise HTTPException(422, "업종을 확인할 수 없습니다. 업종을 직접 선택하세요.")


def get_sale(card, category, amount):
    eligible = PROFILE["previous_month_spend"] >= card["threshold"]
    remaining = max(0, card["monthly_limit"] - PROFILE["used_limits"].get(card["id"], 0))
    # Integer won, rounded down; demo discounts do not consume the limit.
    rate = card["benefits"].get(category, 0)
    discount = min(amount * round(rate * 10000) // 10000, remaining) if eligible else 0
    return {**card, "eligible": eligible, "remaining_limit": remaining, "discount": discount, "net_amount": amount - discount}


@app.get("/health")
def health():
    with connection() as conn:
        conn.execute("SELECT 1").fetchone()
    return {"status": "ok", "mode": "demo"}


@app.get("/api/profile")
def profile():
    return PROFILE


@app.post("/api/search")
def search(body: Search):
    required = [key for key, words in CATEGORIES.items() if any(w.casefold() in body.query.casefold() for w in words)]
    threshold = body.max_previous_spend
    if threshold is None:
        match = re.search(r"(\d+)\s*만\s*원", body.query)
        threshold = int(match.group(1)) * 10000 if match else None
    if not required:
        return {"engine": "demo-rule-filter", "required_categories": [], "cards": [], "message": "카페, 주유, 편의점 중 원하는 혜택을 입력하세요."}
    cards = [card for card in CARDS if all(c in card["benefits"] for c in required) and (threshold is None or card["threshold"] <= threshold)]
    cards.sort(key=lambda c: (-sum(c["benefits"][k] for k in required), c["threshold"]))
    return {"engine": "demo-rule-filter", "required_categories": required, "max_previous_spend": threshold, "cards": cards}


@app.post("/api/recommend")
def recommend(body: Payment):
    category = get_mcc_code(body.merchant, body.category)
    cards = [get_sale(c, category, body.amount) for c in CARDS if c["id"] in PROFILE["owned_cards"]]
    cards.sort(key=lambda c: (-c["discount"], c["id"]))
    return {"mode": "demo", "category": category, "cards": cards, "best_card_id": cards[0]["id"] if cards[0]["discount"] else None,
            "trace": ["get_user_id: demo", "get_mcc_code: " + category, "get_benefits_by_mcc", "get_user_benefit_limit", "get_sale"], "agent": "deterministic-demo-pipeline"}


def settlement_view(conn, sid):
    row = conn.execute("SELECT * FROM settlements WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise HTTPException(404, "정산을 찾을 수 없습니다")
    people = [dict(p) for p in conn.execute("SELECT * FROM participants WHERE settlement_id=? ORDER BY rowid", (sid,))]
    received = sum(p["amount"] for p in people if p["status"] == "confirmed_demo")
    return {**dict(row), "participants": people, "received": received, "net_expense": row["total"] - received, "mode": "demo"}


@app.post("/api/settlements", status_code=201)
def create_settlement(body: Settlement):
    names = [n.strip() for n in body.friends]
    if any(not n or len(n) > 50 for n in names) or len(set(names)) != len(names):
        raise HTTPException(422, "친구 이름은 1~50자로, 중복 없이 입력하세요.")
    if body.total < len(names) + 1:
        raise HTTPException(422, "참여자마다 최소 1원이 배분되어야 합니다")
    share, remainder = divmod(body.total, len(names) + 1)
    sid = str(uuid4())
    with connection() as conn:
        conn.execute("INSERT INTO settlements VALUES (?,?,?,?)", (sid, body.merchant, body.total, share + remainder))
        for name in names:
            conn.execute("INSERT INTO participants(id,settlement_id,name,amount) VALUES (?,?,?,?)", (str(uuid4()), sid, name, share))
        return settlement_view(conn, sid)


@app.get("/api/settlements")
def list_settlements():
    with connection() as conn:
        return [settlement_view(conn, r[0]) for r in conn.execute("SELECT id FROM settlements ORDER BY rowid DESC")]


@app.post("/api/settlements/{sid}/participants/{pid}/confirm-demo")
def confirm_demo(sid: str, pid: str):
    with connection() as conn:
        updated = conn.execute("UPDATE participants SET status='confirmed_demo' WHERE id=? AND settlement_id=?", (pid, sid))
        if updated.rowcount != 1:
            raise HTTPException(404, "참여자를 찾을 수 없습니다")
        return settlement_view(conn, sid)


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/api/tools/user", operation_id="get_user_id", tags=["mcp"])
def tool_user():
    return {"user_id": PROFILE["id"], "mode": "demo"}


@app.get("/api/tools/mcc", operation_id="get_mcc_code", tags=["mcp"])
def tool_mcc(merchant: str):
    return {"category": get_mcc_code(merchant), "source": "demo-name-mapping", "verified_mcc": False}


@app.get("/api/tools/benefits", operation_id="get_benefits_by_mcc", tags=["mcp"])
def tool_benefits(category: str):
    category = get_mcc_code("", category)
    return [c for c in CARDS if c["id"] in PROFILE["owned_cards"] and category in c["benefits"]]


@app.get("/api/tools/limits", operation_id="get_user_benefit_limit", tags=["mcp"])
def tool_limits():
    return {"previous_month_spend": PROFILE["previous_month_spend"], "cards": [
        {"card_id": c["id"], "remaining_limit": max(0, c["monthly_limit"] - PROFILE["used_limits"].get(c["id"], 0)),
         "eligible": PROFILE["previous_month_spend"] >= c["threshold"]} for c in CARDS]}


@app.post("/api/tools/sale", operation_id="get_sale", tags=["mcp"])
def tool_sale(body: Payment):
    return recommend(body)


from fastapi_mcp import FastApiMCP

# Only read-only demo tools are exposed; settlement confirmation is not an agent tool.
mcp = FastApiMCP(app, name="CardBenePICK demo tools", include_tags=["mcp"])
mcp.mount_http()
