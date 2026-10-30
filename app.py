import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

app = FastAPI(title="World Clock API - Python")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "postgres"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "worldclock"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}


def get_conn(retries: int = 20):
    last_err = None
    for _ in range(retries):
        try:
            return psycopg2.connect(**DB_CONFIG)
        except psycopg2.OperationalError as err:
            last_err = err
            time.sleep(2)
    raise last_err


class Clock(BaseModel):
    country: str
    timezone: str


def current_time(timezone: str) -> str:
    try:
        return datetime.now(ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "unknown"


def serialize(row):
    return {
        "id": row["id"],
        "country": row["country"],
        "timezone": row["timezone"],
        "created_at": row["created_at"].isoformat(),
        "current_time": current_time(row["timezone"]),
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "python"}


@app.get("/api/clocks")
def list_clocks():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, country, timezone, created_at "
                        "FROM world_clocks ORDER BY id")
            rows = cur.fetchall()
    finally:
        conn.close()
    return {"service": "python", "data": [serialize(r) for r in rows]}


@app.post("/api/clocks", status_code=201)
def add_clock(clock: Clock):
    try:
        ZoneInfo(clock.timezone)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid timezone")

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO world_clocks (country, timezone) VALUES (%s, %s) "
                "RETURNING id, country, timezone, created_at",
                (clock.country, clock.timezone),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    return {"service": "python", "data": serialize(row)}
