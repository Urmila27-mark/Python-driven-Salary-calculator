from flask import Flask, render_template, request, jsonify, g
import sqlite3
from datetime import datetime

app = Flask(__name__)
DATABASE = 'salary.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.executescript("""
        DROP TABLE IF EXISTS employee_details;
        DROP TABLE IF EXISTS employee_work;
        DROP TABLE IF EXISTS salary_structure;
        DROP TABLE IF EXISTS salary_history;

        CREATE TABLE employee_details (
            employee_id INTEGER PRIMARY KEY,
            name TEXT,
            dob TEXT,
            address TEXT
        );

        CREATE TABLE employee_work (
            employee_id INTEGER,
            department TEXT,
            abilities TEXT
        );

        CREATE TABLE salary_structure (
            employee_id INTEGER,
            basic REAL,
            da REAL,
            deduction REAL,
            overtime_pay REAL,
            bonus REAL,
            leaves_taken INTEGER
        );

        CREATE TABLE salary_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            month TEXT,
            final_salary REAL,
            basic REAL,
            da REAL,
            deduction REAL,
            bonus REAL,
            overtime REAL,
            leave_penalty REAL
        );
        """)

        for i in range(1, 11):
            cursor.execute("INSERT INTO employee_details VALUES (?, ?, ?, ?)",
                           (i, f"Employee {i}", f"199{i}-01-01", f"Address {i}"))
            cursor.execute("INSERT INTO employee_work VALUES (?, ?, ?)",
                           (i, f"Department {i%3 + 1}", f"Skill{i}, Skill{i+1}"))
            cursor.execute("INSERT INTO salary_structure VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (i, 30000+i*1000, 10+i, 5+i, 500+i*20, 1000+i*50, i % 4))
        db.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/salary', methods=['POST'])
def get_salary():
    emp_id = request.json.get('employee_id')
    month = datetime.now().strftime("%Y-%m")
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM employee_details WHERE employee_id=?", (emp_id,))
    emp = cursor.fetchone()
    if not emp:
        return jsonify({"error": "Employee not found"}), 404

    cursor.execute("SELECT * FROM employee_work WHERE employee_id=?", (emp_id,))
    work = cursor.fetchone()

    cursor.execute("SELECT * FROM salary_structure WHERE employee_id=?", (emp_id,))
    salary = cursor.fetchone()

    basic = salary['basic']
    da_amt = basic * salary['da'] / 100
    deduction_amt = basic * salary['deduction'] / 100
    leave_penalty = salary['leaves_taken'] * 500
    final_salary = basic + da_amt + salary['overtime_pay'] + salary['bonus'] - deduction_amt - leave_penalty

    # Insert into salary history
    cursor.execute("""
        INSERT INTO salary_history (employee_id, month, final_salary, basic, da, deduction, bonus, overtime, leave_penalty)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (emp_id, month, final_salary, basic, da_amt, deduction_amt, salary['bonus'], salary['overtime_pay'], leave_penalty))
    db.commit()

    return jsonify({
        "name": emp['name'],
        "department": work['department'],
        "final_salary": round(final_salary, 2),
        "components": {
            "Basic Salary": basic,
            f"DA ({salary['da']}%)": round(da_amt, 2),
            f"Deductions ({salary['deduction']}%)": round(deduction_amt, 2),
            "Bonus": salary['bonus'],
            "Overtime Pay": salary['overtime_pay'],
            f"Leave Penalty ({salary['leaves_taken']} × ₹500)": leave_penalty
        }
    })

@app.route('/api/history/<int:emp_id>', methods=['GET'])
def salary_history(emp_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT name FROM employee_details WHERE employee_id=?", (emp_id,))
    emp = cursor.fetchone()
    if not emp:
        return jsonify({"error": "Employee not found"}), 404

    cursor.execute("""
        SELECT month, final_salary, basic, da, deduction, bonus, overtime, leave_penalty
        FROM salary_history WHERE employee_id=?
        ORDER BY month
    """, (emp_id,))
    history = [dict(row) for row in cursor.fetchall()]
    return jsonify({
        "employee_id": emp_id,
        "name": emp["name"],
        "history": history
    })

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
