# BloodLink

BloodLink is a blood inventory and hospital-request management project
built with **PostgreSQL**, **Python**, and **Streamlit**.

The database stores blood banks, hospitals, donors, donations, blood
units, screening results, hospital requests, and allocations. SQL files
define the database structure and business rules. Python connects the
application to PostgreSQL, while Streamlit provides the browser-based
interface.

> **Current status:** The PostgreSQL schema, constraints, sample data,
> views, reports, and blood-matching query have been created.
> Python-to-PostgreSQL connectivity has been tested, and the first
> Streamlit dashboard is being developed.

------------------------------------------------------------------------

## 1. Project Structure

The project is organized into a database layer and an application layer.

``` text
BloodLink/
│
├── database/
│   ├── schema.sql
│   ├── constraints.sql
│   ├── seed.sql
│   ├── views.sql
│   ├── reports.sql
│   └── blood_matching.sql
│
├── app/
│   ├── db.py
│   ├── main.py
│   ├── test_connection.py
│   └── test_blood_units.py
│
├── .venv/
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

Some files, such as `requirements.txt` or `.gitignore`, may need to be
created if they are not already present. The `.venv` directory is
generated when the virtual environment is created.

### What each part does

  -----------------------------------------------------------------------
  File or folder                      Responsibility
  ----------------------------------- -----------------------------------
  `database/`                         Contains SQL scripts used to build
                                      and query the PostgreSQL database.

  `app/`                              Contains the Python code for
                                      connecting to the database, testing
                                      it, and displaying the application.

  `.venv/`                            An isolated Python environment for
                                      this project and its installed
                                      packages. Do not commit it to Git.

  `.env`                              Stores local database connection
                                      settings, including the password.
                                      Do not commit it to Git.

  `.gitignore`                        Tells Git which local or generated
                                      files should not be tracked.

  `requirements.txt`                  Lists Python packages needed to run
                                      the application.

  `README.md`                         Explains the project, structure,
                                      setup, and how to run it.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 2. The Database Layer: `database/`

The SQL files separate database setup into manageable steps. Run them
against the `bloodlink` database in the order below when setting up a
fresh database.

### `schema.sql` --- creates the tables

This file defines the main database tables and their columns, primary
keys, and foreign-key relationships.

The project schema includes tables for entities such as:

-   `donor` --- donor records.
-   `blood_bank` --- blood-bank information.
-   `hospital` --- hospital information.
-   `blood_compatibility` --- component-specific compatibility rules.
-   `donation` --- donation records.
-   `blood_unit` --- individual blood units, including component, blood
    group, status, and expiry date.
-   `screening` --- screening results for blood units.
-   `blood_request` --- hospital requests for blood components.
-   `allocation` --- units reserved for or issued against requests.
-   `status_history` --- records of status changes.

**In simple terms:** `schema.sql` creates the database's basic
structure.

### `constraints.sql` --- protects data integrity

This file adds rules that prevent invalid data from being stored.
Constraints may enforce valid statuses, positive quantities, required
relationships, and other rules defined by the project.

**Why it matters:** Application code can contain bugs, but database
constraints provide an additional layer of protection against invalid
records.

### `seed.sql` --- inserts development data

This file inserts sample records for development and testing, such as
blood banks, hospitals, blood units, requests, screening results, and
allocations.

**Why it matters:** Sample data lets us test SQL queries and the
application before real data is available. Use only fictional or
appropriately authorized data during development.

### `views.sql` --- defines reusable database views

A view is a saved SQL query that can be queried like a table. BloodLink
currently uses views for:

-   `available_blood_inventory` --- inventory eligible to appear as
    available, according to the view's screening, expiry, status, and
    allocation rules.
-   `blood_request_summary` --- a summary of blood requests.
-   `blood_expiry_report` --- information used to identify units
    approaching or past expiry.
-   `allocation_summary` --- a summary of allocation information.

**Why it matters:** Views keep reusable query logic in PostgreSQL
instead of repeating it throughout Python code.

### `reports.sql` --- contains reporting queries

This file contains SQL queries for operational reports, including:

-   Available inventory grouped by blood bank, component, and blood
    group.
-   Hospital demand grouped by component and recipient blood group.
-   Blood units nearing expiry or already expired.
-   Request fulfillment, including reserved and issued quantities.

These queries help users understand inventory and demand. They do not
automatically change any records.

### `blood_matching.sql` --- finds candidate units for a request

This file contains the query used to find potentially compatible blood
units for a selected request. It considers factors such as the requested
component, recipient compatibility rules, unit availability, expiry,
screening approval, and active allocations.

**Important:** This query identifies database candidates; it does not
replace professional blood-bank verification or clinical transfusion
protocols. Compatibility and release decisions must follow applicable
medical procedures.

------------------------------------------------------------------------

## 3. The Python Application Layer: `app/`

### `db.py` --- the database connection module

This file loads the settings from `.env` and defines `get_connection()`,
which opens a connection to PostgreSQL using Psycopg 3.

Other Python files import this function instead of repeating connection
settings.

The flow is:

``` text
.env settings
     |
     v
   db.py
     |
     v
  Psycopg 3
     |
     v
PostgreSQL database
```

`db.py` is responsible for connecting to the database. It does not build
the user interface.

### `main.py` --- the Streamlit application

This is the main entry point for the browser-based application.

The current dashboard code:

1.  Configures the Streamlit page.
2.  Calls database functions to retrieve summary counts.
3.  Displays metrics such as total units, available units, reserved
    units, units under testing, expired units, and pending requests.
4.  Queries `available_blood_inventory` to display eligible inventory.
5.  Shows database errors during development to help with
    troubleshooting.

The dashboard reads data from PostgreSQL; it does not replace the SQL
schema or views.

To run the application from the **project root**, use:

``` powershell
python -m streamlit run app/main.py
```

If the terminal is already inside the `app` directory, use:

``` powershell
python -m streamlit run main.py
```

Keep the terminal running while using the app. Streamlit normally
displays a local address such as `http://localhost:8501`.

### `test_connection.py` --- checks the database connection

This test imports `get_connection()` from `db.py` and runs a small query
to display the current database name and PostgreSQL version.

Run it from the project root:

``` powershell
python app/test_connection.py
```

A successful result confirms that Python can connect to the configured
PostgreSQL server. It does not by itself prove that every application
query is correct.

### `test_blood_units.py` --- checks access to blood-unit data

This test queries the `blood_unit` table and prints fields such as unit
ID, component, blood group, status, and expiry date.

Run it from the project root:

``` powershell
python app/test_blood_units.py
```

This confirms that Python can retrieve actual BloodLink records, not
just connect to the server.

------------------------------------------------------------------------

## 4. Configuration Files

### `.env` --- local database settings

Create `.env` in the project root, alongside `app/` and `database/`.

Example:

``` dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bloodlink
DB_USER=postgres
DB_PASSWORD=replace_with_your_local_password
```

Replace the password placeholder with your local PostgreSQL password.

Do not share this file or commit it to Git. If credentials are ever
exposed, change the affected password.

### `.gitignore` --- keeps local files out of Git

A suitable starting point is:

``` gitignore
.venv/
.env
__pycache__/
*.py[cod]
```

This prevents Git from tracking the virtual environment, local
credentials, and Python-generated cache files.

### `requirements.txt` --- Python dependencies

This file makes it easier to recreate the Python environment on another
machine. If the required packages are installed in the active virtual
environment, create or update the file from the project root with:

``` powershell
python -m pip freeze > requirements.txt
```

This records the installed package versions. For a larger project, the
dependency list can later be trimmed to the packages the application
directly needs.

------------------------------------------------------------------------

## 5. How the Pieces Work Together

When a user opens the Streamlit application:

1.  `main.py` starts the Streamlit interface.
2.  `main.py` imports database functions from `db.py`.
3.  `db.py` loads connection settings from `.env`.
4.  Psycopg connects to the `bloodlink` PostgreSQL database.
5.  Python executes SQL queries against tables or views.
6.  PostgreSQL returns the results.
7.  Streamlit displays the returned data in the browser.

The overall architecture is:

``` text
User in browser
      |
      v
Streamlit interface (app/main.py)
      |
      v
Python database connection (app/db.py)
      |
      v
Psycopg 3
      |
      v
PostgreSQL 18 (bloodlink)
      |
      +--> Tables
      +--> Constraints
      +--> Views
      +--> Matching query
      +--> Reports
```

**Key design principle:** PostgreSQL stores and protects the data, SQL
implements reusable database logic, Python connects the database to the
application, and Streamlit presents information to the user.

------------------------------------------------------------------------

## 6. Setup Instructions (Windows / VS Code)

### Step 1: Open the project root

Open the `BloodLink` folder in VS Code. The terminal should be at the
root directory, where `app/` and `database/` are located.

### Step 2: Create a virtual environment

Run this once from the project root:

``` powershell
python -m venv .venv
```

### Step 3: Activate the virtual environment

In PowerShell:

``` powershell
.\.venv\Scripts\Activate.ps1
```

The terminal prompt should show `(.venv)` when activation succeeds.

### Step 4: Install dependencies

If `requirements.txt` exists and is up to date:

``` powershell
python -m pip install -r requirements.txt
```

Alternatively, install the packages used by the current application:

``` powershell
python -m pip install "psycopg[binary]" streamlit python-dotenv
```

### Step 5: Configure `.env`

Create the `.env` file as described above. Confirm that the database
name, port, username, and password match your local PostgreSQL
configuration.

### Step 6: Prepare the PostgreSQL database

Create a PostgreSQL database named `bloodlink` if it does not already
exist. Run the SQL scripts from the `database/` directory in this order
for a fresh setup:

1.  `schema.sql`
2.  `constraints.sql`
3.  `seed.sql`
4.  `views.sql`

`reports.sql` and `blood_matching.sql` contain queries to run when you
want to inspect reports or test blood matching. They are not necessarily
setup scripts that must be executed as part of every launch.

If the database and its objects already exist, do not blindly rerun
creation or seed scripts. Some scripts may fail on existing objects or
insert duplicate sample data. Inspect the script contents and current
database state first.

### Step 7: Test the connection

From the project root:

``` powershell
python app/test_connection.py
```

### Step 8: Test access to blood-unit records

``` powershell
python app/test_blood_units.py
```

### Step 9: Launch the application

``` powershell
python -m streamlit run app/main.py
```

Open the local URL shown in the terminal.

------------------------------------------------------------------------

## 7. Current Scope and Next Steps

The current project has a working PostgreSQL database, reusable SQL
views and reports, a blood-matching candidate query, and a tested Python
connection.

The Streamlit dashboard is the first part of the user interface.
Additional pages can be built incrementally for:

-   Inventory search and filtering.
-   Hospital request creation and tracking.
-   Blood-matching candidate review.
-   Allocation and issue workflows with appropriate validation.
-   Operational reports.

These are next development steps unless their implementation has already
been added to the application.

Before using BloodLink with real patient or donor information, add
appropriate authentication, authorization, audit logging, privacy
protections, transaction handling, and operational safeguards. Never use
a development database or this prototype alone to make clinical
transfusion decisions.

------------------------------------------------------------------------

## 8. Technology Stack

-   **Database:** PostgreSQL 18
-   **Backend/database connectivity:** Python and Psycopg 3
-   **User interface:** Streamlit
-   **Configuration:** `python-dotenv`
-   **SQL:** Tables, constraints, views, matching queries, and reports
