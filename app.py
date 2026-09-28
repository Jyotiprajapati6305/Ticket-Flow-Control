import os
from flask import Flask, request, jsonify, render_template
from sqlalchemy import event

from models import db, Employee, Ticket
from assignment import assign_next_ticket, complete_ticket, AlreadyHasActiveTicket, EmployeeNotFound


def create_app(database_url=None):
    app = Flask(__name__)

    db_url = database_url or os.environ.get("DATABASE_URL") or "sqlite:///ticket_system.db"

    # Render/Heroku-style Postgres URLs start with "postgres://" but
    # SQLAlchemy 1.4+ requires "postgresql://".
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if db_url.startswith("sqlite"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"check_same_thread": False, "timeout": 30}
        }

    db.init_app(app)

    with app.app_context():
        if db.engine.dialect.name == "sqlite":
            # Force every write transaction to grab SQLite's write lock
            # up front (BEGIN IMMEDIATE) instead of lazily on first
            # write. This is what makes assign_next_ticket() safe under
            # concurrent requests on SQLite — see assignment.py.
            @event.listens_for(db.engine, "connect")
            def _set_isolation(dbapi_conn, _):
                dbapi_conn.isolation_level = None

            @event.listens_for(db.engine, "begin")
            def _begin_immediate(conn):
                conn.exec_driver_sql("BEGIN IMMEDIATE")

        db.create_all()

    register_routes(app)
    return app


def register_routes(app):

    @app.route("/")
    def dashboard():
        return render_template("index.html")

    # ---------- employees ----------

    @app.route("/api/employees", methods=["POST"])
    def create_employee():
        data = request.get_json(force=True)
        name = (data or {}).get("name", "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        employee = Employee(name=name)
        db.session.add(employee)
        db.session.commit()
        return jsonify(employee.to_dict()), 201

    @app.route("/api/employees", methods=["GET"])
    def list_employees():
        employees = Employee.query.order_by(Employee.id).all()
        return jsonify([e.to_dict() for e in employees])

    @app.route("/api/employees/<int:employee_id>", methods=["GET"])
    def get_employee(employee_id):
        employee = Employee.query.get(employee_id)
        if not employee:
            return jsonify({"error": "employee not found"}), 404
        return jsonify(employee.to_dict())

    # ---------- tickets ----------

    @app.route("/api/tickets", methods=["POST"])
    def create_ticket():
        data = request.get_json(force=True)
        title = (data or {}).get("title", "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        ticket = Ticket(title=title, description=(data or {}).get("description", ""))
        db.session.add(ticket)
        db.session.commit()
        return jsonify(ticket.to_dict()), 201

    @app.route("/api/tickets", methods=["GET"])
    def list_tickets():
        status = request.args.get("status")
        q = Ticket.query
        if status:
            q = q.filter_by(status=status.upper())
        tickets = q.order_by(Ticket.id).all()
        return jsonify([t.to_dict() for t in tickets])

    @app.route("/api/tickets/seed", methods=["POST"])
    def seed_tickets():
        """Bulk create N demo tickets. Body: {"count": 50}"""
        count = int((request.get_json(force=True) or {}).get("count", 20))
        count = max(1, min(count, 1000))
        created = []
        for i in range(count):
            t = Ticket(title=f"Ticket #{Ticket.query.count() + 1}", description="Auto-seeded demo ticket")
            db.session.add(t)
            created.append(t)
        db.session.commit()
        return jsonify({"created": len(created)}), 201

    # ---------- assignment engine ----------

    @app.route("/api/employees/<int:employee_id>/request-ticket", methods=["POST"])
    def request_ticket(employee_id):
        try:
            ticket = assign_next_ticket(employee_id)
        except EmployeeNotFound:
            return jsonify({"error": "employee not found"}), 404
        except AlreadyHasActiveTicket as e:
            return jsonify({"error": "employee already has an active ticket", "ticket_id": e.args[0]}), 409

        if ticket is None:
            return jsonify({"message": "no pending tickets available"}), 200
        return jsonify(ticket.to_dict()), 200

    @app.route("/api/tickets/<int:ticket_id>/complete", methods=["POST"])
    def complete(ticket_id):
        data = request.get_json(force=True)
        employee_id = (data or {}).get("employee_id")
        if not employee_id:
            return jsonify({"error": "employee_id is required"}), 400

        completed, next_ticket = complete_ticket(ticket_id, employee_id)
        if completed is None:
            return jsonify({"error": "ticket not found, not assigned to this employee, or not in progress"}), 400

        return jsonify({
            "completed_ticket": completed.to_dict(),
            "next_ticket": next_ticket.to_dict() if next_ticket else None,
        })

    @app.route("/api/stats", methods=["GET"])
    def stats():
        return jsonify({
            "employees": Employee.query.count(),
            "tickets_pending": Ticket.query.filter_by(status="PENDING").count(),
            "tickets_assigned": Ticket.query.filter_by(status="ASSIGNED").count(),
            "tickets_completed": Ticket.query.filter_by(status="COMPLETED").count(),
        })


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
