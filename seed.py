"""Quick local demo data: run `python seed.py` after starting the app once."""
from app import create_app
from models import db, Employee, Ticket

app = create_app()

with app.app_context():
    names = ["Asha", "Rohan", "Meera", "Kabir", "Zoya", "Dev", "Ishaan", "Priya"]
    for n in names:
        if not Employee.query.filter_by(name=n).first():
            db.session.add(Employee(name=n))
    for i in range(1, 31):
        db.session.add(Ticket(title=f"Ticket #{i}", description="Demo seed ticket"))
    db.session.commit()
    print(f"Seeded {len(names)} employees and 30 tickets.")
