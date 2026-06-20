"""
Librarian routes
----------------
Dashboard  — overview metrics, transaction log, defaulters, audit log.
Return     — process a book return and calculate the correct fine.
Settle     — mark fines as paid and unfreeze the student account.
Books      — add / edit / delete books from the catalogue.
Users      — add / suspend / activate student accounts.
"""

from datetime import datetime

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for, current_app,
)
from werkzeug.security import generate_password_hash

from app.db import get_db, log_activity, new_id
from app.services.fine_service import calculate_fine

librarian_bp = Blueprint("librarian", __name__)


def _require_librarian():
    """Return the librarian's user_id if authenticated, else None."""
    if "user_id" not in session or session.get("role") != "Librarian":
        return None
    return session["user_id"]


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@librarian_bp.route("/librarian")
def dashboard():
    """
    Librarian dashboard.

    Aggregates:
    - Summary metrics (total books, active loans, collected / outstanding fines)
    - Recent transactions (last 50)
    - Defaulters (students with unpaid fines or suspended accounts)
    - Department loan distribution
    - Most-borrowed books (top 5)
    - Audit log (last 15 entries)
    """
    lib_id = _require_librarian()
    if not lib_id:
        return redirect(url_for("auth.login"))

    db = get_db()

    # Summary cards
    total_books     = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    active_loans    = db.execute("SELECT COUNT(*) FROM transactions WHERE status='Issued'").fetchone()[0]
    total_students  = db.execute("SELECT COUNT(*) FROM users WHERE role='Student'").fetchone()[0]
    fine_collected  = db.execute("SELECT COALESCE(SUM(amount),0) FROM fines WHERE is_paid=1").fetchone()[0]
    fine_outstanding = db.execute("SELECT COALESCE(SUM(amount),0) FROM fines WHERE is_paid=0").fetchone()[0]

    # Recent transactions (paginated to 50)
    transactions = db.execute(
        """SELECT t.txn_id, t.user_id, u.name, b.title, b.book_id,
                  t.issue_date, t.due_date, t.return_date, t.status
           FROM transactions t
           JOIN users u ON t.user_id = u.user_id
           JOIN books b ON t.book_id = b.book_id
           ORDER BY t.issue_date DESC
           LIMIT 50""",
    ).fetchall()

    # Flag overdue active loans
    txns = []
    for row in transactions:
        due = datetime.strptime(row["due_date"], "%Y-%m-%d %H:%M")
        txns.append({
            **dict(row),
            "is_overdue": row["status"] == "Issued" and datetime.now() > due,
        })

    # Defaulters: unpaid fines or suspended
    defaulters = db.execute(
        """SELECT u.user_id, u.name, u.dept, u.is_active,
                  COALESCE(SUM(f.amount), 0) AS total_fine,
                  COUNT(f.fine_id) AS fine_count
           FROM users u
           LEFT JOIN fines f ON u.user_id = f.user_id AND f.is_paid = 0
           WHERE u.role = 'Student' AND (u.is_active = 0 OR f.amount > 0)
           GROUP BY u.user_id
           ORDER BY total_fine DESC""",
    ).fetchall()

    # Department stats
    dept_stats = db.execute(
        "SELECT dept, SUM(borrow_count) AS total FROM books GROUP BY dept ORDER BY total DESC"
    ).fetchall()

    # Top books
    top_books = db.execute(
        "SELECT book_id, title, author, borrow_count FROM books ORDER BY borrow_count DESC LIMIT 5"
    ).fetchall()

    # All books for management table
    all_books = db.execute(
        "SELECT * FROM books ORDER BY dept, title"
    ).fetchall()

    # All students for user management
    all_students = db.execute(
        "SELECT user_id, name, dept, semester, is_active FROM users WHERE role='Student' ORDER BY name"
    ).fetchall()

    # Audit log
    audit_logs = db.execute(
        "SELECT * FROM activity_log ORDER BY log_id DESC LIMIT 15"
    ).fetchall()

    return render_template(
        "librarian.html",
        total_books=total_books,
        active_loans=active_loans,
        total_students=total_students,
        fine_collected=round(fine_collected, 2),
        fine_outstanding=round(fine_outstanding, 2),
        txns=txns,
        defaulters=defaulters,
        dept_stats=dept_stats,
        top_books=top_books,
        all_books=all_books,
        all_students=all_students,
        audit_logs=audit_logs,
    )


# ---------------------------------------------------------------------------
# Return a book
# ---------------------------------------------------------------------------

@librarian_bp.route("/return", methods=["POST"])
def return_book():
    """
    Process a book return.

    Steps:
    1. Validate the transaction ID.
    2. Mark the transaction as Returned.
    3. Restore available_copies (capped at total_copies).
    4. Calculate the fine using fine_service (0.0 if returned on time).
    5. If fine > 0: create a fine record and suspend the student.
    6. Commit and log.
    """
    if not _require_librarian():
        return redirect(url_for("auth.login"))

    txn_id = request.form.get("txn_id", "").strip().upper()
    if not txn_id:
        flash("Please enter a valid transaction ID.", "danger")
        return redirect(url_for("librarian.dashboard"))

    db  = get_db()
    txn = db.execute(
        "SELECT * FROM transactions WHERE txn_id = ? AND status = 'Issued'", (txn_id,)
    ).fetchone()

    if not txn:
        flash(f"No active loan found for transaction ID '{txn_id}'.", "danger")
        return redirect(url_for("librarian.dashboard"))

    return_date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    rate            = current_app.config["FINE_RATE_PER_DAY"]
    fine_amount     = calculate_fine(txn["due_date"], return_date_str, rate)

    # Update transaction
    db.execute(
        "UPDATE transactions SET return_date = ?, status = 'Returned' WHERE txn_id = ?",
        (return_date_str, txn_id),
    )

    # Restore copy (never exceed total_copies)
    db.execute(
        """UPDATE books
           SET available_copies = MIN(available_copies + 1, total_copies)
           WHERE book_id = ?""",
        (txn["book_id"],),
    )

    if fine_amount > 0:
        fine_id = new_id("FIN")
        db.execute(
            "INSERT INTO fines (fine_id, txn_id, user_id, amount, is_paid) VALUES (?,?,?,?,0)",
            (fine_id, txn_id, txn["user_id"], fine_amount),
        )
        # Suspend the student until fine is paid
        db.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (txn["user_id"],))

    db.commit()

    details = (
        f"Returned txn {txn_id}. "
        f"Fine: Rs.{fine_amount:.2f} ({'charged' if fine_amount > 0 else 'none — on time'})"
    )
    log_activity(txn["user_id"], "BOOK_RETURNED", "SUCCESS", details)

    if fine_amount > 0:
        flash(
            f"Book returned. An overdue fine of Rs.{fine_amount:.2f} has been charged "
            f"and the student's account suspended until payment.", "warning"
        )
    else:
        flash("Book returned on time. No fine charged.", "success")

    return redirect(url_for("librarian.dashboard"))


# ---------------------------------------------------------------------------
# Settle fines
# ---------------------------------------------------------------------------

@librarian_bp.route("/settle_fine", methods=["POST"])
def settle_fine():
    """
    Mark all outstanding fines for a student as paid and reactivate their account.

    Only the librarian can do this (cash desk settlement).
    """
    if not _require_librarian():
        return redirect(url_for("auth.login"))

    student_id = request.form.get("student_id", "").strip().upper()
    if not student_id:
        flash("Please provide a student ID.", "danger")
        return redirect(url_for("librarian.dashboard"))

    db = get_db()
    student = db.execute("SELECT * FROM users WHERE user_id = ? AND role = 'Student'", (student_id,)).fetchone()
    if not student:
        flash(f"Student '{student_id}' not found.", "danger")
        return redirect(url_for("librarian.dashboard"))

    amount_cleared = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM fines WHERE user_id = ? AND is_paid = 0", (student_id,)
    ).fetchone()[0]

    if amount_cleared == 0:
        flash(f"No outstanding fines for {student['name']}.", "info")
        return redirect(url_for("librarian.dashboard"))

    db.execute("UPDATE fines SET is_paid = 1 WHERE user_id = ? AND is_paid = 0", (student_id,))
    db.execute("UPDATE users SET is_active = 1 WHERE user_id = ?", (student_id,))
    db.commit()

    log_activity(
        session["user_id"], "FINE_SETTLED", "SUCCESS",
        f"Cleared Rs.{amount_cleared:.2f} in fines for {student_id}. Account reactivated."
    )
    flash(f"Rs.{amount_cleared:.2f} cleared for {student['name']}. Account is now active.", "success")
    return redirect(url_for("librarian.dashboard"))


# ---------------------------------------------------------------------------
# Book management — Add
# ---------------------------------------------------------------------------

@librarian_bp.route("/books/add", methods=["POST"])
def add_book():
    """Add a new book to the catalogue."""
    if not _require_librarian():
        return redirect(url_for("auth.login"))

    title   = request.form.get("title", "").strip()
    author  = request.form.get("author", "").strip()
    dept    = request.form.get("dept", "").strip().upper()
    isbn    = request.form.get("isbn", "").strip() or None
    try:
        copies = int(request.form.get("copies", 1))
        if copies < 1:
            raise ValueError
    except ValueError:
        flash("Number of copies must be a positive integer.", "danger")
        return redirect(url_for("librarian.dashboard"))

    if not all([title, author, dept]):
        flash("Title, author, and department are required.", "danger")
        return redirect(url_for("librarian.dashboard"))

    book_id = new_id("BK")
    db = get_db()
    db.execute(
        "INSERT INTO books (book_id, title, author, dept, isbn, total_copies, available_copies) VALUES (?,?,?,?,?,?,?)",
        (book_id, title, author, dept, isbn, copies, copies),
    )
    db.commit()

    log_activity(session["user_id"], "BOOK_ADDED", "SUCCESS", f"Added '{title}' ({book_id})")
    flash(f'"{title}" added to the catalogue.', "success")
    return redirect(url_for("librarian.dashboard"))


# ---------------------------------------------------------------------------
# Book management — Edit
# ---------------------------------------------------------------------------

@librarian_bp.route("/books/edit/<book_id>", methods=["POST"])
def edit_book(book_id):
    """Update an existing book's metadata."""
    if not _require_librarian():
        return redirect(url_for("auth.login"))

    db   = get_db()
    book = db.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("librarian.dashboard"))

    title  = request.form.get("title",  book["title"]).strip()
    author = request.form.get("author", book["author"]).strip()
    dept   = request.form.get("dept",   book["dept"]).strip().upper()
    isbn   = request.form.get("isbn",   book["isbn"] or "").strip() or None
    try:
        new_total = int(request.form.get("total_copies", book["total_copies"]))
        if new_total < 0:
            raise ValueError
    except ValueError:
        flash("Total copies must be a non-negative integer.", "danger")
        return redirect(url_for("librarian.dashboard"))

    # Adjust available_copies proportionally
    on_loan = book["total_copies"] - book["available_copies"]
    new_available = max(new_total - on_loan, 0)

    db.execute(
        """UPDATE books SET title=?, author=?, dept=?, isbn=?,
           total_copies=?, available_copies=? WHERE book_id=?""",
        (title, author, dept, isbn, new_total, new_available, book_id),
    )
    db.commit()

    log_activity(session["user_id"], "BOOK_EDITED", "SUCCESS", f"Edited '{book_id}'")
    flash(f'"{title}" updated.', "success")
    return redirect(url_for("librarian.dashboard"))


# ---------------------------------------------------------------------------
# Book management — Delete
# ---------------------------------------------------------------------------

@librarian_bp.route("/books/delete/<book_id>", methods=["POST"])
def delete_book(book_id):
    """
    Remove a book from the catalogue.
    Blocked if any copies are currently on loan.
    """
    if not _require_librarian():
        return redirect(url_for("auth.login"))

    db   = get_db()
    book = db.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
    if not book:
        flash("Book not found.", "danger")
        return redirect(url_for("librarian.dashboard"))

    on_loan = book["total_copies"] - book["available_copies"]
    if on_loan > 0:
        flash(f'Cannot delete "{book["title"]}" — {on_loan} copy/copies still on loan.', "danger")
        return redirect(url_for("librarian.dashboard"))

    db.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
    db.commit()

    log_activity(session["user_id"], "BOOK_DELETED", "SUCCESS", f"Deleted '{book['title']}' ({book_id})")
    flash(f'"{book["title"]}" removed from the catalogue.', "success")
    return redirect(url_for("librarian.dashboard"))


# ---------------------------------------------------------------------------
# User management — Add student
# ---------------------------------------------------------------------------

@librarian_bp.route("/users/add", methods=["POST"])
def add_student():
    """Register a new student account."""
    if not _require_librarian():
        return redirect(url_for("auth.login"))

    user_id  = request.form.get("user_id",  "").strip().upper()
    name     = request.form.get("name",     "").strip()
    dept     = request.form.get("dept",     "").strip().upper()
    password = request.form.get("password", "").strip()
    try:
        semester = int(request.form.get("semester", 1))
        if not 1 <= semester <= 8:
            raise ValueError
    except ValueError:
        flash("Semester must be between 1 and 8.", "danger")
        return redirect(url_for("librarian.dashboard"))

    if not all([user_id, name, dept, password]):
        flash("All fields are required when adding a student.", "danger")
        return redirect(url_for("librarian.dashboard"))

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone():
        flash(f"User ID '{user_id}' already exists.", "danger")
        return redirect(url_for("librarian.dashboard"))

    db.execute(
        "INSERT INTO users VALUES (?,?,?,?,?,?,?)",
        (user_id, name, "Student", generate_password_hash(password), dept, semester, 1),
    )
    db.commit()

    log_activity(session["user_id"], "USER_ADDED", "SUCCESS", f"Added student {user_id} ({name})")
    flash(f"Student {name} ({user_id}) added successfully.", "success")
    return redirect(url_for("librarian.dashboard"))


# ---------------------------------------------------------------------------
# User management — Toggle suspend/activate
# ---------------------------------------------------------------------------

@librarian_bp.route("/users/toggle/<user_id>", methods=["POST"])
def toggle_student(user_id):
    """Suspend or reactivate a student account."""
    if not _require_librarian():
        return redirect(url_for("auth.login"))

    db      = get_db()
    student = db.execute("SELECT * FROM users WHERE user_id = ? AND role='Student'", (user_id,)).fetchone()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("librarian.dashboard"))

    new_status = 0 if student["is_active"] else 1
    db.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (new_status, user_id))
    db.commit()

    action = "reactivated" if new_status else "suspended"
    log_activity(session["user_id"], "USER_TOGGLED", "SUCCESS", f"Account {action}: {user_id}")
    flash(f"{student['name']}'s account has been {action}.", "success")
    return redirect(url_for("librarian.dashboard"))