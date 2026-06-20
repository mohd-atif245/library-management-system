"""
Student routes
--------------
Dashboard — shows active loans, unpaid fines, book catalogue,
            and department-based book suggestions.
Issue     — borrow a book (POST).
"""

from datetime import datetime, timedelta

from flask import (
    Blueprint, flash, redirect, render_template,
    request, session, url_for, current_app,
)

from app.db import get_db, log_activity, new_id

student_bp = Blueprint("student", __name__)


def _require_student():
    """Return the student_id if authenticated, else None."""
    if "user_id" not in session or session.get("role") != "Student":
        return None
    return session["user_id"]


@student_bp.route("/student")
def dashboard():
    """
    Student dashboard.

    Loads:
    - Account active status (re-checked from DB, not just session)
    - Active loans with overdue flag
    - Unpaid fines
    - Full book catalogue for browsing
    - Department book suggestions (popular books the student hasn't borrowed)
    """
    student_id = _require_student()
    if not student_id:
        return redirect(url_for("auth.login"))

    db         = get_db()
    student    = db.execute("SELECT * FROM users WHERE user_id = ?", (student_id,)).fetchone()

    if not student:
        session.clear()
        return redirect(url_for("auth.login"))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Active loans — flag overdue rows in Python (keeps the query simple)
    loans_raw = db.execute(
        """SELECT t.txn_id, b.title, b.author, b.book_id,
                  t.issue_date, t.due_date
           FROM transactions t
           JOIN books b ON t.book_id = b.book_id
           WHERE t.user_id = ? AND t.status = 'Issued'
           ORDER BY t.due_date""",
        (student_id,),
    ).fetchall()

    loans = []
    for row in loans_raw:
        due  = datetime.strptime(row["due_date"], "%Y-%m-%d %H:%M")
        loans.append({
            "txn_id":     row["txn_id"],
            "title":      row["title"],
            "author":     row["author"],
            "book_id":    row["book_id"],
            "issue_date": row["issue_date"],
            "due_date":   row["due_date"],
            "is_overdue": datetime.now() > due,
            "days_left":  (due - datetime.now()).days,
        })

    # Unpaid fines
    fines = db.execute(
        """SELECT f.fine_id, f.amount, t.due_date, b.title
           FROM fines f
           JOIN transactions t ON f.txn_id = t.txn_id
           JOIN books b ON t.book_id = b.book_id
           WHERE f.user_id = ? AND f.is_paid = 0
           ORDER BY f.amount DESC""",
        (student_id,),
    ).fetchall()

    total_fine = sum(r["amount"] for r in fines)

    # Books the student has already borrowed (to exclude from catalogue)
    issued_book_ids = {loan["book_id"] for loan in loans}

    # Full catalogue — available books only
    catalogue = db.execute(
        """SELECT book_id, title, author, dept, isbn,
                  total_copies, available_copies, borrow_count
           FROM books
           ORDER BY dept, title""",
    ).fetchall()

    # Suggestions: popular books in the student's dept not currently on loan
    suggestions = db.execute(
        """SELECT book_id, title, author, dept, borrow_count
           FROM books
           WHERE dept = ? AND available_copies > 0 AND book_id NOT IN (
               SELECT book_id FROM transactions
               WHERE user_id = ? AND status = 'Issued'
           )
           ORDER BY borrow_count DESC
           LIMIT 3""",
        (student["dept"], student_id),
    ).fetchall()

    return render_template(
        "student.html",
        student=student,
        loans=loans,
        fines=fines,
        total_fine=total_fine,
        catalogue=catalogue,
        suggestions=suggestions,
        issued_book_ids=issued_book_ids,
        max_loans=current_app.config["MAX_LOANS_PER_STUDENT"],
    )


@student_bp.route("/issue", methods=["POST"])
def issue_book():
    """
    Issue (borrow) a book.

    Checks (in order):
    1. Authenticated as student
    2. Account is active
    3. Student has not reached the loan limit
    4. Student has no unpaid fines (policy: must clear fines before borrowing)
    5. Book exists and has available copies
    6. Student doesn't already have this book on loan
    """
    student_id = _require_student()
    if not student_id:
        return redirect(url_for("auth.login"))

    book_id = request.form.get("book_id", "").strip().upper()
    if not book_id:
        flash("Please select a book to borrow.", "danger")
        return redirect(url_for("student.dashboard"))

    db      = get_db()
    student = db.execute("SELECT * FROM users WHERE user_id = ?", (student_id,)).fetchone()

    # --- Guard: account active ---
    if not student or not student["is_active"]:
        log_activity(student_id, "ISSUE_DENIED", "FAILED", "Account is suspended.")
        flash("Your account is suspended. Please contact the librarian.", "danger")
        return redirect(url_for("student.dashboard"))

    # --- Guard: unpaid fines ---
    unpaid_count = db.execute(
        "SELECT COUNT(*) FROM fines WHERE user_id = ? AND is_paid = 0", (student_id,)
    ).fetchone()[0]
    if unpaid_count > 0:
        flash("You have unpaid fines. Please settle them at the library desk before borrowing.", "warning")
        return redirect(url_for("student.dashboard"))

    # --- Guard: loan limit ---
    active_loans = db.execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND status = 'Issued'", (student_id,)
    ).fetchone()[0]
    max_loans = current_app.config["MAX_LOANS_PER_STUDENT"]
    if active_loans >= max_loans:
        flash(f"You have reached the maximum of {max_loans} simultaneous loans.", "warning")
        return redirect(url_for("student.dashboard"))

    # --- Guard: book exists and is available ---
    book = db.execute(
        "SELECT * FROM books WHERE book_id = ?", (book_id,)
    ).fetchone()
    if not book:
        flash("Book not found. Please choose from the catalogue.", "danger")
        return redirect(url_for("student.dashboard"))
    if book["available_copies"] <= 0:
        flash(f'"{book["title"]}" is currently unavailable. Check back later.', "warning")
        return redirect(url_for("student.dashboard"))

    # --- Guard: already borrowed ---
    already = db.execute(
        "SELECT 1 FROM transactions WHERE user_id = ? AND book_id = ? AND status = 'Issued'",
        (student_id, book_id),
    ).fetchone()
    if already:
        flash("You already have this book on loan.", "warning")
        return redirect(url_for("student.dashboard"))

    # --- Issue ---
    loan_days  = current_app.config["LOAN_PERIOD_DAYS"]
    txn_id     = new_id("TXN")
    issue_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    due_date   = (datetime.now() + timedelta(days=loan_days)).strftime("%Y-%m-%d %H:%M")

    db.execute(
        """UPDATE books
           SET available_copies = available_copies - 1,
               borrow_count = borrow_count + 1
           WHERE book_id = ?""",
        (book_id,),
    )
    db.execute(
        """INSERT INTO transactions (txn_id, user_id, book_id, issue_date, due_date, status)
           VALUES (?, ?, ?, ?, ?, 'Issued')""",
        (txn_id, student_id, book_id, issue_date, due_date),
    )
    db.commit()

    log_activity(student_id, "BOOK_ISSUED", "SUCCESS",
                 f"Issued '{book['title']}' (ID: {book_id}). Txn: {txn_id}. Due: {due_date}")
    flash(f'"{book["title"]}" borrowed successfully. Return by {due_date}.', "success")
    return redirect(url_for("student.dashboard"))