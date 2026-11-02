# BloodLink

BloodLink is a Blood Donor Matching and Inventory Management System built
for a college DBMS project. It demonstrates relational database design,
SQL queries and joins, data integrity, transactions, compatibility-based
search, and operational reporting.

**Technology stack:** PostgreSQL · Python · Psycopg 3 · Streamlit

---

## Features

| Feature | Status |
|---|---|
| Database-driven dashboard | ✅ |
| Emergency blood search (read-only, compatibility-aware) | ✅ |
| Donor registration and history | ✅ |
| Blood inventory management | ✅ |
| Hospital blood request management | ✅ |
| Concurrency-safe allocation with transactions | ✅ |
| Unit issue workflow | ✅ |
| Status history audit trail | ✅ |
| SQL-based reports and analytics | ✅ |
| Input validation and error handling | ✅ |

---

## Project Structure

```
BloodLink/
│
├── app/
│   ├── main.py              ← Streamlit entry point and navigation
│   ├── db.py                ← PostgreSQL connection helper (psycopg 3)
│   ├── test_connection.py   ← Verify database connectivity
│   └── test_blood_units.py  ← Verify blood_unit table access
│
├── pages/                   ← One file per Streamlit page
│   ├── dashboard.py
│   ├── emergency_search.py
│   ├── donors.py
│   ├── inventory.py
│   ├── requests.py
│   ├── allocation.py
│   ├── history.py
│   └── reports.py
│
├── services/                ← Database operations, separated from UI
│   ├── dashboard_service.py
│   ├── search_service.py
│   ├── donor_service.py
│   ├── inventory_service.py
│   ├── request_service.py
│   ├── allocation_service.py
│   └── reports_service.py
│
├── database/                ← SQL scripts
│   ├── schema.sql           ← Table definitions, PKs, FKs, CHECKs
│   ├── constraints.sql      ← Additional constraints (unique partial index)
│   ├── seed.sql             ← Sample data for development
│   ├── views.sql            ← Reusable views (available_blood_inventory, etc.)
│   ├── reports.sql          ← Standalone SQL reporting queries
│   └── blood_matching.sql   ← Candidate matching query (demonstration)
│
├── tests/
│   ├── test_search.py       ← Automated search and compatibility tests
│   └── test_allocation.py   ← Automated allocation integrity tests
│
├── .env                     ← Local DB credentials (do NOT commit)
├── .env.example             ← Template without credentials
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Database Architecture

### Tables

| Table | Purpose |
|---|---|
| `donor` | Donor personal information and blood group |
| `blood_bank` | Blood bank name, address, and contact |
| `hospital` | Hospital information |
| `blood_compatibility` | Component-specific compatible donor/recipient group pairs |
| `donation` | Donation events linking donors to blood banks |
| `blood_unit` | Individual blood units: component, blood group, status, expiry |
| `screening` | Screening results per unit (pending / approved / rejected) |
| `blood_request` | Hospital blood requests with urgency and status |
| `allocation` | Units reserved or issued against requests |
| `status_history` | Audit trail of blood unit status changes |

### Key Views

| View | Purpose |
|---|---|
| `available_blood_inventory` | Units that are available, not expired, screening-approved, not allocated |
| `blood_request_summary` | Requests joined with hospital details |
| `blood_expiry_report` | All units with expiry category and days remaining |
| `allocation_summary` | Allocations joined with request, unit, bank, and hospital |

### Key Integrity Rules

- All blood-group and component values are enforced by CHECK constraints.
- `allocation.uq_allocation_active_unit` — a partial unique index on `unit_id`
  (where status is `reserved` or `issued`) prevents the same unit from being
  double-allocated, even under concurrent transactions.
- Allocation transactions use `SELECT … FOR UPDATE SKIP LOCKED` for concurrency
  safety.
- All status changes are recorded in `status_history`.

---

## Setup Instructions (Windows / VS Code)

### 1. Open the project root

Open the `BloodLink` folder in VS Code. The terminal should be at the
root directory, where `app/`, `pages/`, and `database/` are located.

### 2. Create and activate the virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

Or install the core packages directly:

```powershell
python -m pip install "psycopg[binary]" streamlit python-dotenv pandas
```

### 4. Configure `.env`

Create `.env` in the project root:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bloodlink
DB_USER=postgres
DB_PASSWORD=replace_with_your_local_password
```

Replace the password placeholder with your local PostgreSQL password.
**Never commit this file to Git.**

### 5. Initialise the PostgreSQL database

Create a database named `bloodlink` if it does not already exist:

```sql
CREATE DATABASE bloodlink;
```

Run the SQL scripts **in this order** for a fresh setup:

```powershell
psql -U postgres -d bloodlink -f database/schema.sql
psql -U postgres -d bloodlink -f database/constraints.sql
psql -U postgres -d bloodlink -f database/seed.sql
psql -U postgres -d bloodlink -f database/views.sql
```

> **If the database already exists:** do not blindly re-run the scripts.
> `schema.sql` will fail on existing tables; `seed.sql` will insert duplicate
> sample data. Inspect the current database state first.

### 6. Test the connection

```powershell
python app/test_connection.py
python app/test_blood_units.py
```

### 7. Launch the application

```powershell
python -m streamlit run app/main.py
```

Open the local URL shown in the terminal (usually `http://localhost:8501`).

---

## Running Automated Tests

Install pytest if it is not already available:

```powershell
python -m pip install pytest
```

Run all tests from the project root:

```powershell
python -m pytest tests/ -v
```

Tests connect to the real development database (read-only, plus self-contained
fixtures that clean up after themselves). Database connection is required.

---

## Important Limitations

- **Not for clinical use.** This is an educational prototype. Blood search
  results are database candidates only — they do not constitute clinical
  authorisation for transfusion. Final compatibility and release decisions must
  follow applicable blood-bank and clinical protocols.
- **Compatibility table is partially seeded.** Only `red_cells` compatibility
  rows are included in `seed.sql`. Emergency search will report a compatibility
  gap for other components until those rows are added.
- **No authentication or authorisation.** Any user can perform any action.
  Do not deploy with real patient or donor data without adding authentication,
  authorisation, audit logging, and privacy protections.
- **Single database.** All data is stored in one PostgreSQL database. There is
  no replication or backup mechanism in this prototype.

---

## Sample Demonstration Workflow

1. **Dashboard** — review inventory counts and available units by blood group.
2. **Find Blood Now** — search for `O+` `Red Cells` and observe compatible
   donor groups (`O+`, `O-`) and available inventory.
3. **Donors** — register a new donor; view donation history for an existing donor.
4. **Inventory** — register a new donation and blood unit; update its status
   from `under_testing` to `available` after screening.
5. **Blood Requests** — create a new hospital request (e.g. City Care Hospital,
   `red_cells`, `O+`, 2 units, urgent).
6. **Allocation** — preview eligible units for the new request; reserve 2 units.
7. **Allocation → Issue Units** — mark the reserved units as issued. Request
   status updates to `fulfilled`.
8. **Status History** — view the audit trail for the allocated units.
9. **Reports** — review inventory by bank, expiring units, demand, and
   fulfillment status.

---

## Technology Stack

| Component | Technology |
|---|---|
| Database | PostgreSQL 18 |
| DB connectivity | Psycopg 3 (`psycopg[binary]`) |
| User interface | Streamlit 1.66 |
| Configuration | `python-dotenv` |
| Data display | pandas |
| Testing | pytest |
