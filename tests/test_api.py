import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    app = create_app(database_url=f"sqlite:///{path}")
    app.config["TESTING"] = True

    with app.test_client() as c:
        yield c

    os.close(fd)
    os.unlink(path)


def add_employee(client, name="Alice"):
    return client.post("/api/employees", json={"name": name}).get_json()


def add_ticket(client, title="Fix bug"):
    return client.post("/api/tickets", json={"title": title}).get_json()


def test_create_employee(client):
    emp = add_employee(client)
    assert emp["name"] == "Alice"
    assert emp["status"] == "IDLE"


def test_request_ticket_assigns_pending_ticket(client):
    emp = add_employee(client)
    add_ticket(client, "Ticket A")

    result = client.post(f"/api/employees/{emp['id']}/request-ticket").get_json()
    assert result["status"] == "ASSIGNED"
    assert result["assigned_to"] == emp["id"]


def test_no_tickets_available(client):
    emp = add_employee(client)
    result = client.post(f"/api/employees/{emp['id']}/request-ticket").get_json()
    assert "message" in result


def test_employee_cannot_hold_two_active_tickets(client):
    emp = add_employee(client)
    add_ticket(client, "Ticket A")
    add_ticket(client, "Ticket B")

    client.post(f"/api/employees/{emp['id']}/request-ticket")
    res = client.post(f"/api/employees/{emp['id']}/request-ticket")
    assert res.status_code == 409


def test_complete_ticket_auto_assigns_next(client):
    emp = add_employee(client)
    add_ticket(client, "Ticket A")
    add_ticket(client, "Ticket B")

    first = client.post(f"/api/employees/{emp['id']}/request-ticket").get_json()
    result = client.post(f"/api/tickets/{first['id']}/complete", json={"employee_id": emp["id"]}).get_json()

    assert result["completed_ticket"]["status"] == "COMPLETED"
    assert result["next_ticket"] is not None
    assert result["next_ticket"]["status"] == "ASSIGNED"


def test_cannot_complete_ticket_not_owned(client):
    emp1 = add_employee(client, "Alice")
    emp2 = add_employee(client, "Bob")
    add_ticket(client, "Ticket A")

    t = client.post(f"/api/employees/{emp1['id']}/request-ticket").get_json()
    res = client.post(f"/api/tickets/{t['id']}/complete", json={"employee_id": emp2["id"]})
    assert res.status_code == 400


def test_two_employees_never_get_same_ticket(client):
    emp1 = add_employee(client, "Alice")
    emp2 = add_employee(client, "Bob")
    add_ticket(client, "Only ticket")

    r1 = client.post(f"/api/employees/{emp1['id']}/request-ticket").get_json()
    r2 = client.post(f"/api/employees/{emp2['id']}/request-ticket").get_json()

    assert r1["status"] == "ASSIGNED"
    assert "message" in r2  # no tickets left for Bob
