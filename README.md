# Ticket Flow Control & Automatic Assignment System

A backend system where many employees can work concurrently, each holding exactly **one** active ticket at a time, with a guarantee that **no ticket is ever assigned to two employees** — even when dozens of requests land at the same instant.

**[Live demo →](#)** <!-- replace once deployed on Render -->

## The problem

> How can 100+ employees work on tickets simultaneously while ensuring each employee gets only one active ticket, and the same ticket is never handed to more than one employee?

## Workflow

```
Employee completes a ticket
        ↓
Server marks it COMPLETED
        ↓
Assignment engine finds the next PENDING ticket
        ↓
Ticket is assigned automatically
        ↓
Employee immediately receives the next task
```

## How the concurrency guarantee actually works

The core of this project is `assignment.py::assign_next_ticket()`. When an employee asks for a ticket, the engine has to pick the oldest `PENDING` ticket and flip it to `ASSIGNED` — and if two employees ask at the same millisecond, they must not both get the same row.

- **On PostgreSQL** (production): the query uses `SELECT ... FOR UPDATE SKIP LOCKED`. This locks the row it reads for the duration of the transaction; a concurrent transaction trying to read the same row skips it and moves to the next available one instead of blocking or double-reading. This is the standard pattern behind most production job/ticket queues.
- **On SQLite** (local dev/tests): there's no `SKIP LOCKED`, so every write transaction is forced to open with `BEGIN IMMEDIATE` (wired up via a SQLAlchemy `connect`/`begin` event in `app.py`). That grabs SQLite's single write lock immediately, so a second concurrent request simply waits its turn rather than reading stale state. Same correctness guarantee, serialized instead of parallel.

Either way, the read-check-write happens inside one transaction, so there's never a window where two requests both see a ticket as available.

**This isn't just a claim** — `tests/concurrency_test.py` spins up the real Flask server as a separate process and fires genuinely parallel HTTP requests from 100 threads at once. Verified result: 100 employees requesting against a 60-ticket pool → exactly 60 unique tickets assigned, 0 duplicates, 40 employees correctly told nothing was left.

```bash
python tests/concurrency_test.py 100 60
```

## Stack

- Python + Flask, REST API
- SQLAlchemy ORM (SQLite for dev, PostgreSQL in production)
- Vanilla HTML/CSS/JS dashboard (no framework, no build step)
- Pytest for functional tests, a dedicated multi-process script for concurrency testing
- Gunicorn + Render for deployment

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/employees` | Create an employee `{name}` |
| GET | `/api/employees` | List employees + status |
| POST | `/api/tickets` | Create a ticket `{title, description}` |
| POST | `/api/tickets/seed` | Bulk-create demo tickets `{count}` |
| GET | `/api/tickets` | List tickets, optional `?status=PENDING` |
| POST | `/api/employees/<id>/request-ticket` | Atomically assign the next ticket |
| POST | `/api/tickets/<id>/complete` | Complete a ticket `{employee_id}`, auto-assigns the next one |
| GET | `/api/stats` | Counts by status |

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python seed.py                  # optional demo data
python app.py
```

Visit `http://localhost:5000` for the dashboard.

### Run the tests

```bash
pytest tests/test_api.py -v
python tests/concurrency_test.py 100 60
```

## Deploy on Render

1. Push this repo to GitHub.
2. On Render, **New → Blueprint**, point it at the repo — `render.yaml` provisions both the web service and a free PostgreSQL database automatically.
   - Or manually: **New → Web Service**, build command `pip install -r requirements.txt`, start command `gunicorn app:app`, and add a Render PostgreSQL instance with its connection string set as the `DATABASE_URL` env var.
3. Once deployed, swap the placeholder link at the top of this README for your live URL.

## What this project covers

Backend API design · database transactions · row-level locking · concurrency & race conditions · queue-style assignment logic · REST APIs · automated + concurrency testing · production deployment.

## License

MIT
