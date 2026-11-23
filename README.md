# DealerOS Reconciliation Dashboard

A full-stack web application that compares two systems (System A and System B) that record the same business events. It identifies disagreements between their records and displays them in a table while keeping each organisation's data isolated.

## Features

- **CSV Importer:** Imports all three supplied CSV files. Dirty rows are preserved, and importing the same data multiple times does not create duplicate records.
- **Comparison Engine:** Uses pure Python logic to identify four required disagreement types and three additional types.
- **Organisation-Level Data Isolation:** Filters records by organisation inside database queries to prevent data from other organisations from appearing in the response.
- **REST API:** Provides an endpoint to retrieve disagreements with organisation, reason, and sorting filters.
- **React Dashboard:** Displays disagreements in a table with an organisation selector, reason filter, sortable value column, loading state, error state, and empty state.
- **Automated Tests:** Includes 64 pytest tests covering comparison logic, data cleaning, importing, API behaviour, and organisation isolation.

## Technology Stack

**Backend**
- Python 3.11+
- Django
- Django REST Framework
- SQLite
- pytest
- pytest-django

**Frontend**
- React 18
- Vite
- JavaScript
- HTML
- CSS

## Prerequisites

Install the following before running the project:

- Python 3.11 or later
- Node.js 18 or later
- Git

Check the installed versions:

```powershell
python --version
node --version
npm --version
git --version
```

## Project Setup and Execution

The following instructions are for Windows PowerShell.

### 1. Open the project folder

Open PowerShell and navigate to the project directory:

```powershell
cd "$HOME\OneDrive\Desktop\dealeros-assessment"
```

### 2. Set up the Python environment

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Then activate the environment again:

```powershell
.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```powershell
pip install -r requirements.txt
```

### 3. Run database migrations

Navigate to the backend folder:

```powershell
cd backend
```

Create the database tables:

```powershell
python manage.py migrate
```

### 4. Import the CSV data

Run the import command:

```powershell
python manage.py import_data
```

The importer reads the three original CSV files and displays a summary of the imported records and data-cleaning operations.

The import operation is safe to run more than once. Repeated imports do not create duplicate records.

### 5. Start the backend server

From the backend folder, run:

```powershell
python manage.py runserver
```

The backend API will be available at:

http://127.0.0.1:8000/

Keep this PowerShell window open while using the application.

### 6. Start the frontend

Open a **second PowerShell window** and navigate to the frontend folder:

```powershell
cd "$HOME\OneDrive\Desktop\dealeros-assessment\frontend"
```

Install frontend dependencies:

```powershell
npm install
```

Start the React development server:

```powershell
npm run dev
```

Open the application in your browser:

http://localhost:5173/

### 7. Run automated tests

Open another PowerShell window, navigate to the project root, and activate the virtual environment if necessary:

```powershell
cd "$HOME\OneDrive\Desktop\dealeros-assessment"
.venv\Scripts\Activate.ps1
cd backend
```

Run the tests:

```powershell
python -m pytest -v
```

The project currently contains 64 automated tests.

### 8. Optional: Run the data profiling script

From the backend folder, run:

```powershell
python ..\scripts\data_profile.py
```

This script helps inspect the original CSV files by counting records, blank values, and unusual data formats.

## API Documentation

### Endpoint

```http
GET /api/disagreements/
```

The API supports organisation selection, disagreement filtering, and sorting.

### Example Requests

Retrieve disagreements for ORG-A:

```http
GET /api/disagreements/?org=ORG-A
```

Retrieve only value mismatches for ORG-A:

```http
GET /api/disagreements/?org=ORG-A&reason=VALUE_MISMATCH
```

Sort ORG-A disagreements by value in descending order:

```http
GET /api/disagreements/?org=ORG-A&sort=-value
```

Retrieve ORG-B disagreements sorted by value:

```http
GET /api/disagreements/?org=ORG-B&sort=value
```

### Response Fields

Each disagreement contains the following fields:

- `reason`
- `record_id`
- `location`
- `b_location`
- `b_details_hidden`
- `a_value`
- `b_value`
- `difference`
- `b_entry_ids`

### Data Handling

- Monetary values use Python Decimal to avoid floating-point precision errors.
- Monetary values are returned as exact text in the API.
- Missing monetary values are represented as JSON `null`, never as zero.
- Missing or unknown organisation, reason, or sort parameters return HTTP 400 with an error message.

### Sorting

The `sort=value` and `sort=-value` options sort by System A's value. For orphan records, System B's value is used. Rows without a value appear last.

## Disagreement Types

The application identifies the following disagreement types.

| Reason | Description |
|---|---|
| `MISSING_IN_B` | A record exists in System A but has no corresponding entry in System B. |
| `ORPHAN_IN_B` | An entry exists in System B but has no corresponding record in System A. |
| `DUPLICATE_IN_B` | Multiple System B entries refer to the same System A record. |
| `VALUE_MISMATCH` | The total value in System A does not match the corresponding value or combined values in System B. |
| `LOCATION_MISMATCH` | The location associated with the corresponding records does not match. |
| `DATE_MISMATCH` | The event date in the two systems does not match. |
| `VOIDED_IN_A` | A record is marked VOIDED in System A but still has an entry in System B. |

The first four are the required disagreement types. The remaining three are additional checks.

## Results from the Supplied Dataset

The application was checked against the supplied CSV data.

| Organisation | Disagreements | Count |
|---|---|---:|
| ORG-A | REC-1015 missing in B; REC-1999 orphan in B; REC-1042 duplicate in B; REC-1027, REC-1064, REC-1088 value mismatches; REC-1077 location mismatch | 7 |
| ORG-B | REC-1061 missing in B; REC-1003 and REC-1050 value mismatches; REC-1009 date mismatch; REC-1019 voided in A | 5 |

The application correctly handles:

- REC-1055, where multiple System B entries add up to the System A total. It is not incorrectly flagged as a disagreement.
- Messy references such as `rec1034`, `REC - 1070`, and `1112`.
- Blank System B values without treating them as zero.
- Indian-style comma-separated monetary values.
- Missing actor IDs without replacing them with incorrect values.
- Cross-organisation location mismatches without exposing another organisation's details.

### Import Summary

The supplied dataset contains:

| Item | Result |
|---|---:|
| Locations read and saved | 5 |
| System A records read and saved | 120 |
| System B entries read and saved | 121 |
| Empty actor IDs preserved as NULL | 1 |
| Blank System B values preserved as NULL | 1 |
| References normalised | 3 |
| Unknown location codes | 0 |
| Unreadable dates | 0 |
| Import errors | 0 |

## Project Structure

```text
dealeros-assessment/
|
|-- README.md
|-- DECISIONS.md
|-- requirements.txt
|-- .gitignore
|-- scripts/
|   |-- data_profile.py
|
|-- backend/
|   |-- manage.py
|   |-- pytest.ini
|   |-- config/
|   |   |-- settings.py
|   |   |-- urls.py
|   |
|   |-- data/
|   |   |-- locations.csv
|   |   |-- system_a.csv
|   |   |-- system_b.csv
|   |
|   |-- reconcile/
|       |-- models.py
|       |-- cleaning.py
|       |-- importer.py
|       |-- compare.py
|       |-- services.py
|       |-- views.py
|       |-- urls.py
|       |-- management/
|       |   |-- commands/
|       |       |-- import_data.py
|       |-- tests/
|
|-- frontend/
    |-- package.json
    |-- vite.config.js
    |-- index.html
    |-- src/
        |-- App.jsx
        |-- main.jsx
        |-- styles.css
```

## How the Application Works

The application follows this data flow:

```text
Original CSV Files
       |
       v
    Importer
       |
       v
     SQLite
       |
       v
 Org-Filtered Database Queries
       |
       v
 Comparison Engine
       |
       v
 Organisation Data Protection
       |
       v
    REST API
       |
       v
 React Dashboard
```

### Main Components

- **models.py:** Defines the database tables for locations, System A records, and System B entries.
- **cleaning.py:** Contains helper functions for normalising references, parsing monetary values, and handling dates.
- **importer.py:** Reads CSV files, preserves dirty data, and imports records safely.
- **import_data.py:** Provides the Django management command for importing the CSV data.
- **compare.py:** Contains the core comparison rules using pure Python.
- **services.py:** Retrieves organisation-specific records, runs comparisons, and handles cross-organisation data protection.
- **views.py:** Implements API request validation and returns disagreement results.
- **App.jsx:** Displays the React dashboard and handles filters, sorting, loading, error, and empty states.
- **data_profile.py:** Profiles the original CSV data.

## Organisation Data Isolation

The application uses `locations.csv` as the source of organisation ownership.

Each location belongs to an organisation. Database queries are filtered by the requested organisation before comparison results are returned.

System B entries are not directly linked to System A records through a mandatory foreign key because orphan entries must also be preserved and reported.

When a record refers to a location belonging to another organisation, the application avoids exposing that organisation's location details.

**Important limitation:** This assessment implementation does not include user authentication. The organisation is selected through the API's `org` parameter. In a production application, organisation access should be determined from the authenticated user's permissions rather than trusting a URL parameter.

## What Is Implemented

- Importing all three original CSV files.
- Idempotent data importing.
- Preserving dirty and incomplete data.
- Normalising inconsistent record references.
- Exact monetary calculations using Decimal.
- Four required disagreement types.
- Three additional disagreement types.
- Organisation-level database filtering.
- Protection against cross-organisation data exposure.
- React dashboard with filtering and sorting.
- Automated tests for cleaning, importing, comparison, and API behaviour.

## What Is Not Implemented

The following features are outside the current assessment implementation:

- User login and authentication.
- Pagination.
- Docker configuration.
- Production database configuration.
- Production deployment settings.
- Advanced dashboard styling.

## Known Limitations

1. **Authentication:** The API currently accepts an organisation identifier through the URL. A production system should obtain organisation access from the authenticated user.
2. **Unknown locations:** A record with a location code that does not exist in `locations.csv` is preserved but cannot be assigned to an organisation. Therefore, it does not appear in an organisation's dashboard.
3. **Cross-organisation mismatches:** The application hides the other organisation's details for cross-organisation location mismatches. The decision is documented in `DECISIONS.md`.
4. **VOIDED records:** The treatment of VOIDED records follows the interpretation documented in `DECISIONS.md`.
5. **Sorting and scalability:** Sorting currently happens in Python after comparison. This is suitable for the supplied dataset but should be optimised for larger datasets.
6. **Frontend deployment:** The Vite proxy is configured for local development. Production deployment would require additional configuration.

## Working with the AI Agent

The following section should describe the actual development process. Update the AI agent name if necessary.

- **Which AI agent I used:** [Enter the actual AI coding agent used.]

- **What I asked it to build:** I asked the AI agent to develop a full-stack reconciliation dashboard using Django, React, and SQLite. The application needed to import the supplied CSV files, identify disagreements between two systems, and maintain organisation-level data separation.

- **What I personally reviewed or changed:** I reviewed the project structure, setup instructions, importer output, API responses, frontend dashboard, and automated test results. I also checked that the supplied CSV records were imported correctly and that the application ran locally.

- **How I verified its output:** I ran the data importer, checked the imported record counts, tested the API for both organisations, executed all 64 automated tests, and successfully built the React frontend.

## Assessment Reflection

### a. One thing the AI agent got wrong. How did I notice?

[Describe one actual mistake made by the AI agent and explain how you identified it while reviewing or testing the application. Do not invent a mistake.]

### b. The part I am least confident about, and why

I am least confident about how the application would perform with a much larger dataset. The current implementation works with the supplied CSV files, but sorting and comparison happen in Python. Further performance testing and optimisation would be needed for larger datasets.

### c. If I had a second day, what would I fix first?

I would improve authentication and organisation access control so that the organisation is determined from the logged-in user's permissions rather than a URL parameter. I would also consider adding pagination and more efficient database operations to support larger datasets.

---

## Author

Developed as part of the DealerOS Full-Stack Developer assessment.