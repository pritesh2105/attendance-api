"""
Employee Attendance & Analytics API - STARTER

Run:  uvicorn app.main:app --port 8000
Env:  MONGO_URI, MONGO_DB (a local .env is loaded for convenience)

This file was written quickly by a colleague who has left the company. The happy path
works, but nobody has reviewed it. Read PROBLEM_STATEMENT.docx for what is expected of you,
openapi.yaml for the contract and DATA_MODEL.md for what is stored in MongoDB.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), tz_aware=True)
db = client[os.getenv("MONGO_DB", "attendance_db")]

IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def to_ist(ms: Optional[int]) -> datetime:
    """Epoch milliseconds (or now) -> India time, whole seconds only (R1)."""
    if ms is None:
        dt = datetime.now(IST)
    else:
        dt = datetime.fromtimestamp(ms / 1000, tz=IST)
    return dt.replace(microsecond=0)

def compute_late_minutes(punch_in: datetime, shift_start: str, shift_end: str) -> int:
    sh, sm = map(int, shift_start.split(":"))
    eh, em = map(int, shift_end.split(":"))
    pin = punch_in.astimezone(IST).replace(microsecond=0)
    start = pin.replace(hour=sh, minute=sm, second=0)
    # overnight shift, punched in early morning: the shift started the previous day
    if (eh, em) <= (sh, sm) and (pin.hour, pin.minute, pin.second) < (eh, em, 0):
        start -= timedelta(days=1)
    seconds = (pin - start).total_seconds()
    return int(seconds // 60) if seconds > 600 else 0


from decimal import Decimal, ROUND_HALF_UP

def compute_work_hours(punch_in: datetime, punch_out: datetime) -> float:
    seconds = int((punch_out - punch_in).total_seconds())
    hours = Decimal(seconds) / Decimal(3600)
    return float(hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_overtime(punch_in: datetime, punch_out: datetime, shift_start: str, shift_end: str) -> int:
    sh, sm = map(int, shift_start.split(":"))
    eh, em = map(int, shift_end.split(":"))
    pin = punch_in.astimezone(IST)
    end = pin.replace(hour=eh, minute=em, second=0, microsecond=0)
    # overnight shift, and punched in at/after the end time: it ends the next day
    if (eh, em) <= (sh, sm) and (pin.hour, pin.minute, pin.second) >= (eh, em, 0):
        end += timedelta(days=1)
    minutes = int((punch_out.replace(microsecond=0) - end).total_seconds()) // 60
    return minutes if minutes >= 30 else 0

def to_ms(dt: Optional[datetime]) -> Optional[int]:
    return None if dt is None else int(dt.timestamp() * 1000)


def record_view(rec: dict) -> dict:
    return {
        "emp_code": rec["emp_code"],
        "date": rec["date"],
        "status": rec["status"],
        "punch_in": to_ms(rec.get("punch_in")),
        "punch_out": to_ms(rec.get("punch_out")),
        "work_hours": rec.get("work_hours"),
        "late_minutes": rec.get("late_minutes", 0),
        "overtime_minutes": rec.get("overtime_minutes", 0),
        "half_day": rec.get("half_day", False),
        "history": rec.get("history", []),
    }

def attendance_date(ts: datetime, shift_start: str, shift_end: str) -> str:
    """R1: the IST calendar date a punch-in belongs to."""
    sh, sm = map(int, shift_start.split(":"))
    eh, em = map(int, shift_end.split(":"))
    t = ts.astimezone(IST)
    d = t.date()
    if (eh, em) <= (sh, sm) and (t.hour, t.minute, t.second) < (eh, em, 0):
        d -= timedelta(days=1)
    return d.isoformat()


def derive(emp: dict, in_ts: Optional[datetime], out_ts: Optional[datetime]) -> dict:
    late = compute_late_minutes(in_ts, emp["shift_start"], emp["shift_end"]) if in_ts else 0
    if in_ts and out_ts:
        wh = compute_work_hours(in_ts, out_ts)
        ot = compute_overtime(in_ts, out_ts, emp["shift_start"], emp["shift_end"])
        return {"late_minutes": late, "work_hours": wh, "overtime_minutes": ot, "half_day": wh < 4.5}
    return {"late_minutes": late, "work_hours": None, "overtime_minutes": 0, "half_day": False}

# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class EmployeeIn(BaseModel):
    emp_code: str
    name: str
    email: str
    department: str
    shift_start: str = "09:30"
    shift_end: str = "18:30"
    joined_on: str


class PunchInIn(BaseModel):
    emp_code: str
    punched_at: Optional[int] = None
    status: str = "PRESENT"
class PunchOutIn(BaseModel):
    emp_code: str
    punched_at: Optional[int] = None

class RegularizeIn(BaseModel):
    status: Optional[Literal["PRESENT", "ABSENT", "LEAVE", "WFH", "ON_DUTY"]] = None
    punch_in: Optional[int] = None
    punch_out: Optional[int] = None
    reason: str = Field(min_length=5, max_length=200)
    regularized_by: str = Field(min_length=1, max_length=50)

# --------------------------------------------------------------------------- #
# Endpoints provided
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/employees", status_code=201)
def create_employee(body: EmployeeIn):
    if db.employees.find_one({"emp_code": body.emp_code}):
        raise HTTPException(409, "emp_code already exists")
    doc = body.model_dump()
    doc["created_at"] = datetime.now()
    db.employees.insert_one(doc)
    doc.pop("_id", None)
    return doc


@app.get("/employees")
def list_employees(department: Optional[str] = None, page: int = 1, page_size: int = 20):
    q = {}
    if department:
        q["department"] = department
    skip = (page-1)* page_size
    total = db.employees.count_documents({})
    items = list(db.employees.find(q, {"_id": 0}).skip(skip).limit(page_size))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.post("/attendance/punch-in", status_code=201)
def punch_in(body: PunchInIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    ts = datetime.fromtimestamp(body.punched_at / 1000) if body.punched_at else datetime.now()
    d = ts.date().isoformat()
    if db.attendance_logs.find_one({"emp_code": body.emp_code, "date": d}):
        raise HTTPException(409, "already punched in for this date")
    doc = {
        "emp_code": body.emp_code,
        "date": d,
        "status": body.status,
        "punch_in": ts,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": compute_late_minutes(ts, emp["shift_start"], emp["shift_end"]),
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }
    res = db.attendance_logs.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    doc.pop("_id", None)
    return doc


@app.get("/attendance")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    q = {}
    if emp_code:
        q["emp_code"] = emp_code
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from
        if date_to:
            q["date"]["$lte"] = date_to
    if status:
        q["status"] = status
    docs = list(db.attendance_logs.find(q))
    docs.sort(key=lambda d: d["date"], reverse=True)
    total = len(docs)
    page_docs = docs[(page - 1) * page_size : page * page_size]
    for d in page_docs:
        d["id"] = str(d.pop("_id"))
    return {"items": page_docs, "total": total, "page": page, "page_size": page_size}
@app.post("/attendance/punch-out")

@app.post("/attendance/punch-out")
def punch_out(body: PunchOutIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, "employee not found")
    out_ts = to_ist(body.punched_at)

    rec = db.attendance_logs.find_one(
        {"emp_code": body.emp_code, "punch_in": {"$lte": out_ts}},
        sort=[("punch_in", -1)],
    )
    if not rec:
        raise HTTPException(404, "no punch-in found")
    if rec.get("punch_out") is not None:
        raise HTTPException(409, "already punched out")

    in_ts = rec["punch_in"].replace(microsecond=0)
    if out_ts <= in_ts or out_ts - in_ts > timedelta(hours=24):
        raise HTTPException(422, "punched_at must be after punch_in and within 24 hours")

    work_hours = compute_work_hours(in_ts, out_ts)
    res = db.attendance_logs.update_one(
        {"_id": rec["_id"], "punch_out": None},
        {"$set": {
            "punch_out": out_ts,
            "work_hours": work_hours,
            "overtime_minutes": compute_overtime(in_ts, out_ts, emp["shift_start"], emp["shift_end"]),
            "half_day": work_hours < 4.50,
        }},
    )
    if res.modified_count == 0:
        raise HTTPException(409, "already punched out")
    return record_view(db.attendance_logs.find_one({"_id": rec["_id"]}))

@app.patch("/attendance/{emp_code}/{date}")
def regularize(emp_code: str, date: str, body: RegularizeIn):
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, "employee not found")
    rec = db.attendance_logs.find_one({"emp_code": emp_code, "date": date})
    if not rec:
        raise HTTPException(404, "no record for that date")
        shift_start, shift_end = emp["shift_start"], emp["shift_end"]
    new_status = body.status or rec["status"]
    old_in = rec.get("punch_in")
    old_out = rec.get("punch_out")

    if new_status in ("ABSENT", "LEAVE"):
        if body.punch_in is not None or body.punch_out is not None:
            raise HTTPException(422, "ABSENT/LEAVE cannot have punch times")
        new_in = new_out = None
    else:
        new_in = to_ist(body.punch_in) if body.punch_in is not None else old_in
        new_out = to_ist(body.punch_out) if body.punch_out is not None else old_out
        if new_in is None:
            raise HTTPException(422, "a presence status requires a punch_in")
        if attendance_date(new_in, shift_start, shift_end) != date:
            raise HTTPException(422, "punch_in must stay on the record's attendance date")
        if new_out is not None and (new_out <= new_in or new_out - new_in > timedelta(hours=24)):
            raise HTTPException(422, "punch_out must be after punch_in and within 24 hours")

    new = {"status": new_status, "punch_in": new_in, "punch_out": new_out, **derive(emp, new_in, new_out)}
    changes = {}
    for k, v in new.items():
        old = rec.get(k)
        if v != old:
            if k in ("punch_in", "punch_out"):
                changes[k] = {"from": to_ms(old), "to": to_ms(v)}
            else:
                changes[k] = {"from": old, "to": v}
    if not changes:
        raise HTTPException(422, "request changes nothing")

        entry = {
        "at": to_ms(datetime.now(timezone.utc)),
        "by": body.regularized_by,
        "reason": body.reason,
        "changes": changes,
    }
    old_history = rec.get("history", [])
    res = db.attendance_logs.update_one(
        {
            "_id": rec["_id"],
            "history": {"$size": len(old_history)},
            "punch_out": old_out,
        },
        {
            "$set": new,
            "$push": {"history": entry},
        },
    )
    if res.modified_count == 0:
        raise HTTPException(409, "record was modified by someone else, please retry")
    return record_view(db.attendance_logs.find_one({"_id": rec["_id"]}))
# --------------------------------------------------------------------------- #
# TODO - the rest of the contract (see openapi.yaml):
#   POST  /attendance/punch-out
#   PATCH /attendance/{emp_code}/{date}
#   GET   /analytics/employees/{emp_code}/monthly
#   GET   /analytics/departments/summary
#   GET   /analytics/leaderboard/late
#   GET   /analytics/departments/{department}/trend
#   GET   /admin/explain/{endpoint}
# --------------------------------------------------------------------------- #
