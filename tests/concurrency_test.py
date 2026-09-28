"""
Starts the real Flask app on a background process (not the test
client — an actual HTTP server, so requests genuinely run in
parallel), then fires N simultaneous "request next ticket" calls and
verifies no ticket was ever handed to more than one employee.

Run with:
    python tests/concurrency_test.py [num_employees] [num_tickets]

Example:
    python tests/concurrency_test.py 100 60
"""

import json
import os
import sys
import time
import urllib.request
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HOST = "127.0.0.1"
PORT = 5057
BASE = f"http://{HOST}:{PORT}"


def run_server(db_path):
    from app import create_app
    app = create_app(database_url=f"sqlite:///{db_path}")
    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)


def call(path, payload=None):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def call_get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as resp:
        return json.loads(resp.read())


def wait_for_server(timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            call_get("/api/stats")
            return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    num_employees = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    num_tickets = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    db_path = os.path.abspath("concurrency_test.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    proc = multiprocessing.Process(target=run_server, args=(db_path,), daemon=True)
    proc.start()

    try:
        assert wait_for_server(), "server did not start in time"

        print(f"Creating {num_employees} employees and {num_tickets} tickets...")
        employee_ids = []
        for i in range(num_employees):
            emp = call("/api/employees", {"name": f"Employee {i+1}"})
            employee_ids.append(emp["id"])

        call("/api/tickets/seed", {"count": num_tickets})

        print(f"Firing {num_employees} concurrent request-ticket calls...")
        with ThreadPoolExecutor(max_workers=num_employees) as pool:
            results = list(pool.map(
                lambda eid: call(f"/api/employees/{eid}/request-ticket"),
                employee_ids,
            ))

        assigned_ticket_ids = [r["id"] for r in results if "id" in r]
        no_ticket_count = sum(1 for r in results if "message" in r)

        unique_ids = set(assigned_ticket_ids)
        duplicates = len(assigned_ticket_ids) - len(unique_ids)

        print(f"  employees that got a ticket:   {len(assigned_ticket_ids)}")
        print(f"  employees with no ticket left: {no_ticket_count}")
        print(f"  unique ticket ids assigned:    {len(unique_ids)}")
        print(f"  duplicate assignments:         {duplicates}")

        assert len(assigned_ticket_ids) == min(num_employees, num_tickets), "wrong number of tickets handed out"
        assert duplicates == 0, "a ticket was assigned to more than one employee!"

        print("\nPASS: no duplicate assignments under concurrent load.")

    finally:
        proc.terminate()
        proc.join(timeout=5)
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    main()
