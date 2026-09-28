from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="IDLE")  # IDLE | WORKING
    current_ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    current_ticket = db.relationship(
        "Ticket", foreign_keys=[current_ticket_id], post_update=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "current_ticket_id": self.current_ticket_id,
        }


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # PENDING -> ASSIGNED -> COMPLETED
    status = db.Column(db.String(20), nullable=False, default="PENDING")

    assigned_to = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
