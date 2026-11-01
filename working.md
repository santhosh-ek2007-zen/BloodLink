# Day 1

## Definition of each files
- **schema.sql:** creates your tables relationships.
- **constraints.sql:** contains addtional database integrity rules
- **reports.sql:** defines indexes for important queries.
- **views.sql:** defines reusable database views.
- **seed.sql:** inserts fictional demonstration data.
- **services/:** contains Python functions that perform application operations.
- **pages/:** contains the Streamlit pages.
- **tests/:** contains tests for database operations and business rules.
- **db.py:** manages database connectivity.
- **app.py:** serves as the Streamlit entry point.
- **.env:** stores local database configuration.
- **requirements.txt:** lists Python dependencies.

## Designing the Database 
| Table | Purpose |
|---|---|
| Donar | Stores donor information |
| BloodBank | Stores blood bank details |
| Hospital | Stores hospital information |
| Donation | Records individual donation events |
| BloodUnit | Tracks each blood unit or component |
| Screening	| Records screening outcomes and history |
| BloodRequest | Stores hospital requests for blood |
| Allocation | Records units assigned to requests |
| StatusHistory | Tracks changes in a unit's status |
| BloodCompatibility | Stores the compatibility rules approved for your educational prototype |

# Possible entity Questions 
**Why do we need Donation separately?**
Suppose a donor makes one donation, and that donation produces multiple separately tracked blood units or components.
The donation represents the event. The resulting units are separate records.
**Donor (1) → Donation (M)**
**BloodBank (1) → Donation (M)**

A hospital may submit multiple requests over time.
Therefore, hospital details should not be repeated in every request record.

# creation of tables 
- why do we use generated always as Identity primary key
**Reason:** 
In most of the cases we don't fill that column so if we use that  
the column is automatically filled 

- Why do we need this table?(blood_compatibility)

# Day 2 

## Populate the Database

inserting dummy data's in seed.sql

## Inspect the hospital table
- Before inserting data, we need to check its column names and identity configuration, just as we did with the previous tables.
