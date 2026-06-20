# 📚 Library Management System

A full-featured, secure Library Management System built using Flask and SQLite. This system streamlines library operations through role-based access control, automated fine management, and comprehensive transaction tracking.

---

## 🚀 Features

### 👨‍🎓 Student Portal
* **Secure Authentication:** Sign in with encrypted password verification.
* **Smart Catalog:** Browse available books with integrated department-based book recommendations.
* **Loan Management:** Borrow books, view active loans, and track due dates in real-time.
* **Fine Tracker:** Monitor overdue books, check outstanding fines, and view suspension status.

### 👨‍💼 Librarian Portal
* **Analytics Dashboard:** Real-time library statistics (total books, active loans, defaulters).
* **Inventory Control:** Full CRUD operations (Add, update, and remove books) with automatic copy tracking.
* **User Management:** Manage student accounts, process suspensions, and reactivate accounts.
* **Fulfillment Desk:** Process book returns with automatic fine calculation and settlement workflows.
* **Audit Logs:** Monitor transactions and critical activity logs for accountability.

---

## 🛠 Technologies Used

* **Backend:** Python, Flask, Jinja2
* **Database:** SQLite (with robust data integrity and relations)
* **Security:** Secure SHA-256 password hashing
* **Frontend:** HTML5, CSS3, JavaScript

---

## 📂 Project Structure

```text
Library-Management-System/
│
├── app/
│   ├── routes/
│   │   ├── auth.py
│   │   ├── student.py
│   │   └── librarian.py
│   │
│   ├── services/
│   │   └── fine_service.py
│   │
│   ├── templates/
│   ├── static/
│   ├── db.py
│   └── __init__.py
│
├── run.py
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 🔐 Business Rules

* **Borrowing Eligibility:** Students can only borrow books if:
  * Their account status is **Active** (not suspended).
  * They have **zero** unpaid outstanding fines.
  * Their maximum borrowing limit has not been reached.
* **Automated Penalty:** Overdue returns automatically trigger fine calculations based on due dates.
* **Account Control:** Students with unpaid fines are automatically flagged/suspended until the fine workflow is settled by a librarian.
* **Inventory Sync:** Book inventory updates seamlessly in real-time upon every successful borrow and return transaction.

---

## ⚙️ Installation & Setup

Follow these steps to get the project running locally:

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/library-management-system.git
cd library-management-system
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
```

### 3. Activate the Environment
* **Windows:**
  ```bash
  venv\Scripts\activate
  ```
* **Linux/macOS:**
  ```bash
  source venv/bin/activate
  ```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the Application
```bash
python run.py
```

### 6. Access the App
Open your browser and navigate to: `http://127.0.0.1:5000`

---

## 🎯 Key Highlights

* **Role-Based Access Control (RBAC):** Strict separation between student and librarian capabilities.
* **Modular Architecture:** Clean blueprints and routing configuration for scalable development.
* **Data Security:** Bulletproof backend validation and secure credential encryption.
* **Automated Workflows:** Zero manual intervention needed for overdue detection or stock updates.

---

## 📸 Screenshots


| Login Page | Student Dashboard |
|------------|-------------------|
| *![Login Page](screenshots/login.png)* | *![Student Dashboard](screenshots/student-dashboard.png)* |

| Librarian Dashboard | Book Catalog |
|---------------------|--------------|
| *![Librarian Dashboard](screenshots/librarian-dashboard.png)* | *![Book Catalogue](screenshots/books.png)* |
