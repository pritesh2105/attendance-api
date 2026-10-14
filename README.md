# Employee Attendance & Analytics API

FastAPI + MongoDB (PyMongo). All code is in `app/main.py`.

## Run
    python -m venv .venv
    .venv\Scripts\activate          (Mac/Linux: source .venv/bin/activate)
    pip install -r requirements.txt
    # create a .env file with:
    #   MONGO_URI=<your MongoDB connection string>
    #   MONGO_DB=attendance_db
    python sample_seed.py
    uvicorn app.main:app --port 8000 --reload

Docs page: http://localhost:8000/docs

## Done
- `POST /attendance/punch-out`: finds the latest open record, validates (404/409/422),
  computes work hours, overtime and half day, and saves with an atomic conditional
  update so only one of two simultaneous punch-outs succeeds.
- `PATCH /attendance/{emp_code}/{date}`: manual correction. Recomputes derived fields,
  appends one history entry with from/to for every changed field, and uses an optimistic
  check (history length + punch_out) so concurrent edits return 409 instead of losing history.
- Fixed helpers: late minutes (R2), work hours with half-up rounding (R4),
  overtime with the 30-minute minimum and overnight shifts (R3, R1).
- Fixed pagination offset in `GET /employees`; MongoDB client now returns
  timezone-aware datetimes.
- Review findings are in `REVIEW.md`.

## Not done yet
- Analytics endpoints: employee monthly, department summary, late leaderboard, department trend.
- `GET /admin/explain/{endpoint}` and index creation at startup.
- Remaining fixes in the starter endpoints: `POST /attendance/punch-in` (IST date and
  epoch-millisecond responses, race condition), `GET /attendance` (pagination, sorting, filters),
  `POST /employees` (validation, unique index).
- `DECISIONS.md` answers.