"""
Concurrency-safe ticket assignment.

The core guarantee this module provides: if N employees call
`assign_next_ticket` at the same moment, no two of them will ever
receive the same ticket, and each ticket is handed out exactly once.

How it works
------------
On PostgreSQL (used in production / Render):
    SELECT ... FOR UPDATE SKIP LOCKED
    This locks the row(s) it reads inside the transaction. A second,
    concurrent transaction trying to select the same PENDING ticket
    skips any row already locked by another transaction and moves on
    to the next one, instead of blocking or double-reading it.
    This is the standard pattern behind most production job/ticket
    queues (Postgres docs call it out explicitly for this use case).

On SQLite (used for local dev / tests):
    SQLite has no SKIP LOCKED. Instead we force every write
    transaction to open with `BEGIN IMMEDIATE`, which grabs SQLite's
    single write lock up front. A second concurrent request simply
    waits for the lock (does not read stale/uncommitted state), so
    the same "no double assignment" guarantee holds — just serialized
    rather than parallel. Good enough for correctness; PostgreSQL is
    what you'd actually scale with.

Either way, the row is flipped from PENDING -> ASSIGNED and committed
inside a single transaction, so there's no window where two requests
can both see it as available.
"""

from datetime import datetime
from models import db, Employee, Ticket


class AlreadyHasActiveTicket(Exception):
    pass


class EmployeeNotFound(Exception):
    pass


def assign_next_ticket(employee_id):
    """
    Atomically finds the oldest PENDING ticket and assigns it to
    employee_id. Returns the assigned Ticket, or None if no tickets
    are available. Raises AlreadyHasActiveTicket if the employee
    already has a ticket in progress (the "one active ticket per
    employee" rule from the spec).
    """
    employee = Employee.query.get(employee_id)
    if employee is None:
        raise EmployeeNotFound(employee_id)

    if employee.status == "WORKING" and employee.current_ticket_id:
        raise AlreadyHasActiveTicket(employee.current_ticket_id)

    query = Ticket.query.filter_by(status="PENDING").order_by(Ticket.created_at, Ticket.id)

    if db.engine.dialect.name == "postgresql":
        # Skip rows already locked by a concurrent transaction instead
        # of blocking on them.
        query = query.with_for_update(skip_locked=True)
    else:
        # SQLite: no SKIP LOCKED, but BEGIN IMMEDIATE (wired up in
        # app.py) already serializes writers, so a plain read here is
        # safe — nobody else can be mid-assignment at the same time.
        query = query.with_for_update()

    ticket = query.first()
    if ticket is None:
        return None

    ticket.status = "ASSIGNED"
    ticket.assigned_to = employee.id
    ticket.assigned_at = datetime.utcnow()

    employee.status = "WORKING"
    employee.current_ticket_id = ticket.id

    db.session.commit()
    return ticket


def complete_ticket(ticket_id, employee_id):
    """
    Marks a ticket COMPLETED (only if it belongs to employee_id),
    frees up the employee, then immediately tries to hand them the
    next PENDING ticket. Returns (completed_ticket, next_ticket_or_None).
    """
    ticket = Ticket.query.get(ticket_id)
    if ticket is None:
        return None, None
    if ticket.assigned_to != employee_id or ticket.status != "ASSIGNED":
        return None, None

    ticket.status = "COMPLETED"
    ticket.completed_at = datetime.utcnow()

    employee = Employee.query.get(employee_id)
    employee.status = "IDLE"
    employee.current_ticket_id = None

    db.session.commit()

    next_ticket = assign_next_ticket(employee_id)
    return ticket, next_ticket
