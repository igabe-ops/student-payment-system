from flask import Flask, render_template, request, redirect, url_for, session
import json
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATA_FILE = "students.json"

# ------------------ INITIALIZE DATA FILE ------------------
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)

# ------------------ USERS ------------------
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "teacher": {"password": "teacher123", "role": "teacher"},
    "bursar": {"password": "bursar123", "role": "bursar"}
}

# ------------------ LOGIN DECORATOR ------------------
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                return "Access denied!", 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ------------------ HELPER FUNCTIONS ------------------
def load_students():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_students(students):
    with open(DATA_FILE, "w") as f:
        json.dump(students, f, indent=4)

# ------------------ LOGIN & LOGOUT ------------------
@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = USERS.get(username)
        if user and user["password"] == password:
            session["user"] = username
            session["role"] = user["role"]
            if user["role"] == "admin":
                return redirect(url_for("dashboard"))
            elif user["role"] == "teacher":
                return redirect(url_for("attendance"))
            elif user["role"] == "bursar":
                return redirect(url_for("payments"))
        else:
            error = "Invalid username or password"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ------------------ DASHBOARD (ADMIN) ------------------
@app.route("/dashboard")
@login_required("admin")
def dashboard():
    students = load_students()
    total_students = len(students)
    total_payments = sum(sum(map(float, s["payments"])) for s in students if s["payments"])
    return render_template(
        "dashboard.html",
        user=session.get("user"),
        students=students,
        total_students=total_students,
        total_payments=total_payments
    )

# ------------------ STUDENTS ------------------
@app.route("/students", methods=["GET", "POST"])
@login_required("admin")
def students():
    students = load_students()
    if request.method == "POST":
        name = request.form["name"]
        age = int(request.form["age"])
        student_class = request.form["class"]
        student = {
            "id": len(students) + 1,
            "name": name,
            "age": age,
            "class": student_class,
            "attendance": [],
            "payments": []
        }
        students.append(student)
        save_students(students)
        return redirect(url_for("students"))
    return render_template("students.html", students=students)

# ------------------ EDIT STUDENT ------------------
@app.route("/students/edit/<int:id>", methods=["GET", "POST"])
@login_required()
def edit_student(id):
    students = load_students()
    student = next((s for s in students if s["id"] == id), None)
    if not student:
        return "Student not found", 404

    role = session.get("role")
    if role == "teacher":
        editable_fields = ["attendance"]
    elif role == "bursar":
        editable_fields = ["payments"]
    elif role == "admin":
        editable_fields = ["name", "age", "class", "attendance", "payments"]
    else:
        return "Access denied!", 403

    if request.method == "POST":
        if "name" in editable_fields:
            student["name"] = request.form.get("name", student["name"])
        if "age" in editable_fields:
            student["age"] = int(request.form.get("age", student["age"]))
        if "class" in editable_fields:
            student["class"] = request.form.get("class", student["class"])
        if "attendance" in editable_fields:
            attendance_entry = request.form.get("attendance")
            if attendance_entry:
                student["attendance"].append(attendance_entry)
        if "payments" in editable_fields:
            payment_entry = request.form.get("payments")
            if payment_entry:
                student["payments"].append(int(payment_entry))
        save_students(students)
        return redirect(url_for("dashboard") if role == "admin" else url_for(role))

    return render_template("edit_student.html", student=student, role=role)

# ------------------ DELETE STUDENT ------------------
@app.route("/students/delete/<int:id>")
@login_required()
def delete_student(id):
    students = load_students()
    student = next((s for s in students if s["id"] == id), None)
    if not student:
        return "Student not found", 404

    role = session.get("role")
    if role == "admin":
        students = [s for s in students if s["id"] != id]
    elif role == "teacher":
        student["attendance"] = []
    elif role == "bursar":
        student["payments"] = []
    else:
        return "Access denied!", 403

    for i, s in enumerate(students, start=1):
        s["id"] = i
    save_students(students)
    return redirect(url_for("dashboard") if role == "admin" else url_for(role))

# ------------------ ATTENDANCE ------------------
@app.route("/attendance", methods=["GET", "POST"])
@login_required()
def attendance():
    if session.get("role") not in ["teacher", "admin"]:
        return "Access denied!"
    students = load_students()
    if request.method == "POST":
        student_id = int(request.form["student_id"])
        status = request.form.get("status", "Present")
        students[student_id-1]["attendance"].append(status)
        save_students(students)
        return redirect(url_for("attendance"))
    return render_template("attendance.html", students=students)

# ------------------ EDIT ATTENDANCE ------------------
@app.route("/edit_attendance/<int:student_id>/<int:index>", methods=["GET", "POST"])
@login_required()
def edit_attendance(student_id, index):
    if session.get("role") not in ["teacher", "admin"]:
        return "Access denied!"
    
    students = load_students()
    student = next((s for s in students if s["id"] == student_id), None)
    
    if not student:
        return "Student not found", 404
    
    # Check if index is valid
    if index < 0 or index >= len(student["attendance"]):
        return "Invalid attendance index", 400
    
    if request.method == "POST":
        new_status = request.form["status"]
        student["attendance"][index] = new_status
        save_students(students)
        return redirect(url_for("attendance"))
    
    current_status = student["attendance"][index]
    return render_template("edit_attendance.html", student=student, index=index, current_status=current_status)

# ------------------ DELETE ATTENDANCE ------------------
@app.route("/delete_attendance/<int:student_id>/<int:index>")
@login_required()
def delete_attendance(student_id, index):
    if session.get("role") not in ["teacher", "admin"]:
        return "Access denied!"
    
    students = load_students()
    student = next((s for s in students if s["id"] == student_id), None)
    
    if not student:
        return "Student not found", 404
    
    # Check if index is valid
    if 0 <= index < len(student["attendance"]):
        student["attendance"].pop(index)
    
    save_students(students)
    return redirect(url_for("attendance"))

# ------------------ PAYMENTS ------------------
@app.route("/payments", methods=["GET", "POST"])
@login_required()
def payments():
    if session.get("role") not in ["bursar", "admin"]:
        return "Access denied!"
    students = load_students()
    if request.method == "POST":
        student_id = int(request.form["student_id"])
        amount = int(request.form.get("amount"))
        for s in students:
            if s["id"] == student_id:
                s["payments"].append(amount)
                break
        save_students(students)
        return redirect(url_for("payments"))
    return render_template("payments.html", students=students)

# ------------------ EDIT PAYMENT ------------------
@app.route("/payments/edit/<int:student_id>/<int:index>", methods=["GET", "POST"])
@login_required("bursar")
def edit_payment(student_id, index):
    students = load_students()
    student = next((s for s in students if s["id"] == student_id), None)

    if not student:
        return "Student not found", 404

    if request.method == "POST":
        new_amount = int(request.form["amount"])
        student["payments"][index] = new_amount   # update existing payment
        save_students(students)
        return redirect(url_for("payments"))

    return render_template("edit_payment.html", student=student, index=index)

# ------------------ DELETE PAYMENT ------------------
@app.route("/payments/delete/<int:student_id>/<int:index>")
@login_required("bursar")
def delete_payment(student_id, index):
    students = load_students()
    student = next((s for s in students if s["id"] == student_id), None)

    if not student:
        return "Student not found", 404

    if 0 <= index < len(student["payments"]):
        student["payments"].pop(index)

    save_students(students)
    return redirect(url_for("payments"))

# ------------------ RUN APP ------------------
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)