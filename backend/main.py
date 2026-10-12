from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import os
from pathlib import Path
import sqlite3
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = Path(os.environ.get("TURNOS_DB_PATH", "/tmp/turnos.db" if os.getenv("VERCEL") else Path(__file__).with_name("turnos.db")))
SERVICES = {"Depósitos", "Retiros", "Aclaraciones", "Pagos", "Atención preferente"}


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            service TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'waiting',
            counter INTEGER,
            created_at TEXT NOT NULL,
            appointment_at TEXT,
            called_at TEXT,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS counters (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        INSERT OR IGNORE INTO counters(id,name) VALUES (1,'Ventanilla 1'),(2,'Ventanilla 2'),(3,'Ventanilla 3'),(4,'Ventanilla 4');
        """)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Ventanilla Turnos API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class TurnCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=100)
    service: str
    priority: bool = False
    appointment_at: datetime | None = None


class CounterUpdate(BaseModel):
    active: bool


def serialize(row):
    return dict(row)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Ventanilla Turnos API"}


@app.get("/api/services")
def services():
    return sorted(SERVICES)


@app.post("/api/turns", status_code=201)
def create_turn(payload: TurnCreate):
    if payload.service not in SERVICES:
        raise HTTPException(422, "Servicio no válido")
    now = datetime.now()
    appointment = payload.appointment_at
    local_appointment = appointment.astimezone().replace(tzinfo=None) if appointment and appointment.tzinfo else appointment
    if appointment:
        if local_appointment < now:
            raise HTTPException(422, "La cita debe ser futura")
        if local_appointment.date() > date.today() + timedelta(days=122):
            raise HTTPException(422, "Las citas se pueden agendar hasta cuatro meses adelante")
    with connect() as db:
        day_code = now.strftime("%y%m%d")
        seq = db.execute("SELECT COUNT(*) + 1 FROM turns WHERE code LIKE ?", (f"T{day_code}%",)).fetchone()[0]
        code = f"T{day_code}-{seq:03d}"
        cur = db.execute("INSERT INTO turns(code,customer_name,service,priority,status,created_at,appointment_at) VALUES(?,?,?,?,?,?,?)", (code, payload.customer_name.strip(), payload.service, int(payload.priority), "scheduled" if appointment else "waiting", now.isoformat(timespec="seconds"), local_appointment.isoformat(timespec="minutes") if appointment else None))
        row = db.execute("SELECT * FROM turns WHERE id=?", (cur.lastrowid,)).fetchone()
    return serialize(row)


@app.get("/api/turns")
def list_turns(status: Literal["waiting", "called", "in_service", "completed", "scheduled"] | None = None):
    with connect() as db:
        if status:
            rows = db.execute("SELECT * FROM turns WHERE status=? ORDER BY priority DESC, created_at ASC", (status,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM turns WHERE date(created_at)=date('now','localtime') OR (appointment_at IS NOT NULL AND date(appointment_at)=date('now','localtime')) ORDER BY CASE status WHEN 'waiting' THEN 0 WHEN 'called' THEN 1 WHEN 'in_service' THEN 2 ELSE 3 END, priority DESC, created_at ASC").fetchall()
    return [serialize(row) for row in rows]


@app.get("/api/turns/{turn_id}")
def get_turn(turn_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM turns WHERE id=?", (turn_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Turno no encontrado")
    return serialize(row)


@app.post("/api/counters/{counter_id}/next")
def call_next(counter_id: int):
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as db:
        counter = db.execute("SELECT * FROM counters WHERE id=? AND active=1", (counter_id,)).fetchone()
        if not counter:
            raise HTTPException(404, "Ventanilla no encontrada o inactiva")
        existing = db.execute("SELECT id FROM turns WHERE counter=? AND status IN ('called','in_service')", (counter_id,)).fetchone()
        if existing:
            raise HTTPException(409, "Termina la atención actual antes de llamar otro turno")
        db.execute("UPDATE turns SET status='waiting' WHERE status='scheduled' AND appointment_at<=?", (now,))
        row = db.execute("SELECT * FROM turns WHERE status='waiting' ORDER BY priority DESC, created_at ASC LIMIT 1").fetchone()
        if not row:
            return {"message": "No hay turnos en espera", "turn": None}
        db.execute("UPDATE turns SET status='called',counter=?,called_at=? WHERE id=?", (counter_id, now, row["id"]))
        result = db.execute("SELECT * FROM turns WHERE id=?", (row["id"],)).fetchone()
    return {"message": "Turno llamado", "turn": serialize(result)}


@app.post("/api/turns/{turn_id}/start")
def start_turn(turn_id: int):
    with connect() as db:
        cur = db.execute("UPDATE turns SET status='in_service' WHERE id=? AND status='called'", (turn_id,))
        if not cur.rowcount:
            raise HTTPException(409, "El turno no está llamado")
        row = db.execute("SELECT * FROM turns WHERE id=?", (turn_id,)).fetchone()
    return serialize(row)


@app.post("/api/turns/{turn_id}/complete")
def complete_turn(turn_id: int):
    with connect() as db:
        cur = db.execute("UPDATE turns SET status='completed',completed_at=? WHERE id=? AND status IN ('called','in_service')", (datetime.now().isoformat(timespec="seconds"), turn_id))
        if not cur.rowcount:
            raise HTTPException(409, "El turno no está en atención")
        row = db.execute("SELECT * FROM turns WHERE id=?", (turn_id,)).fetchone()
    return serialize(row)


@app.get("/api/counters")
def list_counters():
    with connect() as db:
        counters = db.execute("SELECT * FROM counters ORDER BY id").fetchall()
        result = []
        for counter in counters:
            active_turn = db.execute("SELECT * FROM turns WHERE counter=? AND status IN ('called','in_service') ORDER BY called_at DESC LIMIT 1", (counter["id"],)).fetchone()
            result.append({**serialize(counter), "turn": serialize(active_turn) if active_turn else None})
    return result


@app.patch("/api/counters/{counter_id}")
def set_counter(counter_id: int, payload: CounterUpdate):
    with connect() as db:
        cur = db.execute("UPDATE counters SET active=? WHERE id=?", (int(payload.active), counter_id))
        if not cur.rowcount:
            raise HTTPException(404, "Ventanilla no encontrada")
        return serialize(db.execute("SELECT * FROM counters WHERE id=?", (counter_id,)).fetchone())


@app.get("/api/stats")
def stats():
    with connect() as db:
        today = db.execute("SELECT COUNT(*) total, SUM(status='waiting') waiting, SUM(status IN ('called','in_service')) serving, SUM(status='completed') completed FROM turns WHERE date(created_at)=date('now','localtime')").fetchone()
        return {key: (value or 0) for key, value in dict(today).items()}

