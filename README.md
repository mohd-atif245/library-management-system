📚 Library Management System

A full-featured Library Management System built using Flask and SQLite that streamlines library operations through role-based access control, automated fine management, and transaction tracking.

---

🚀 Features

👨‍🎓 Student Portal

- Secure authentication
- Browse available books
- Borrow books
- View active loans
- Track due dates
- View overdue books
- Check outstanding fines
- Receive department-based book recommendations

👨‍💼 Librarian Portal

- Dashboard with library statistics
- Add, update, and remove books
- Manage student accounts
- Process book returns
- Automatic fine calculation
- Fine settlement management
- Student suspension/reactivation
- Transaction monitoring
- Activity and audit logs

---

🛠️ Technologies Used

- Python
- Flask
- SQLite
- HTML5
- CSS3
- JavaScript
- Jinja2

---

📂 Project Structure

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
│   └── _init_.py
│
├── run.py
├── requirements.txt
├── README.md
└── .gitignore

---

🔐 Business Rules

- Students can only borrow books if:
  
  - Their account is active
  - No unpaid fines exist
  - Borrowing limit has not been reached

- Overdue returns automatically generate fines.

- Students with unpaid fines are suspended until fines are settled.

- Book inventory updates automatically after borrowing and returning.

---

📊 Core Functionalities

Book Management

- Add books
- Edit books
- Delete books
- Track available copies

Loan Management

- Borrow books
- Return books
- Due date tracking
- Overdue detection

Fine Management

- Automatic fine calculation
- Outstanding fine tracking
- Fine settlement workflow

Reporting & Monitoring

- Dashboard statistics
- Transaction history
- Activity logs
- Defaulter tracking

---

⚙️ Installation

1. Clone Repository

git clone https://github.com/your-username/library-management-system.git
cd library-management-system

2. Create Virtual Environment

python -m venv venv

3. Activate Environment

Windows:

venv\Scripts\activate

Linux/Mac:

source venv/bin/activate

4. Install Dependencies

pip install -r requirements.txt

5. Run Application

python run.py

6. Open Browser

http://127.0.0.1:5000

---

🎯 Key Highlights

- Role-Based Authentication
- Modular Flask Architecture
- Secure Password Hashing
- Automated Fine System
- Student Account Control
- Department-Based Recommendations
- Activity Logging
- Scalable Project Structure

---

📸 Screenshots

## Screenshots

### Login Page

![Login Page](screenshots/login.png)

### Student Dashboard

![Student Dashboard](screenshots/student-dashboard.png)

### Librarian Dashboard

![Librarian Dashboard](screenshots/librarian-dashboard.png)

### Book Catalogue

![Book Catalogue](screenshots/books.png)

---"# library-management-system" 
