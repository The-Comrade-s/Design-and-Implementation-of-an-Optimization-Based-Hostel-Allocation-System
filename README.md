# Hostel Optimization System (HOS)

An optimization-based hostel allocation system for a tertiary institution.
The system determines optimal hostel/room/bed allocations for eligible
students using mathematical optimization (Google OR-Tools CP-SAT), rather
than a simple first-come-first-served or greedy assignment.

## Features

- Modular Streamlit application with a clean layered architecture
  (UI → Services → Repositories → Models)
- Hostel / Block / Floor / Room / Bed-space infrastructure management with
  automatic bed-space generation
- Student profiles, eligibility checks, and hostel applications with
  ranked hostel preferences
- Configurable, weighted priority scoring (final year, special
  requirements, distance, academic level, returning student, etc.) with a
  full explainable score breakdown
- OR-Tools CP-SAT optimization engine that maximizes an overall
  allocation score subject to hard constraints (one bed per student, one
  student per bed, eligibility, gender/category compatibility, usable
  accommodation only)
- Full allocation workflow: proposed → reviewed → approved → published,
  with administrative override, release, and a complete audit trail
- Admin dashboard, hostel occupancy analytics, application/allocation
  analytics, preference-satisfaction metrics, and CSV export
- Student dashboard showing application status, eligibility, and
  published allocation only (no other students' data, ever)
- Role-based access control (ADMIN / STUDENT), audit logging, and secure
  bcrypt password hashing
- Alembic database migrations (SQLite for local development;
  PostgreSQL-ready via `DATABASE_URL`)
- Automated test suite (unit, integration, security, optimization,
  database) using pytest

## Architecture

```
app/
├── main.py                 Streamlit entrypoint / router
├── core/                   config, database, security, exceptions, logging
├── models/                 SQLAlchemy ORM models
├── repositories/           thin data-access layer
├── services/                business logic (auth, hostel, student,
│                            application, priority, optimization,
│                            allocation, dashboard, audit)
├── optimization/           OR-Tools CP-SAT engine
├── ui/                      Streamlit pages (admin + student)
└── utils/                   session/auth helpers

migrations/                 Alembic migrations
scripts/                    create_admin.py, seed_demo_data.py
tests/                      unit / integration / security / optimization / database
```

## Technology Stack

- Python 3.12+, Streamlit
- PostgreSQL (production) / SQLite (local development) via SQLAlchemy 2.x
- Alembic for migrations
- Google OR-Tools (CP-SAT) for the optimization engine
- bcrypt for password hashing
- Pandas / Plotly for analytics and charts
- pytest for automated testing

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed:

```
DATABASE_URL=sqlite:///./hos.db
# Production example:
# DATABASE_URL=postgresql+psycopg2://hos_user:password@localhost:5432/hos_db
SECRET_KEY=change-this-secret-key-in-production
APP_ENV=development
LOG_LEVEL=INFO
OPTIMIZATION_TIME_LIMIT_SECONDS=60
```

Never commit a real `.env` file — it is excluded via `.gitignore`.

## Database Setup & Migrations

```bash
# Apply all migrations to create/upgrade the schema
python -m alembic upgrade head

# Roll back the most recent migration
python -m alembic downgrade -1

# Generate a new migration after changing models
python -m alembic revision --autogenerate -m "Describe the change"
```

For PostgreSQL, set `DATABASE_URL` before running Alembic/the app; no
code changes are required.

## Creating the Initial Administrator

```bash
python scripts/create_admin.py
```

You will be prompted for an email and password. No password is ever
hard-coded.

## Demo / Seed Data (development only)

```bash
python scripts/seed_demo_data.py
```

Creates a fictional admin (`admin@hos.local` / `Admin@12345`), two
hostels with limited bed capacity, default scoring rules, and 10
fictional students with submitted/verified applications — enough to
run a meaningful optimization. **Never run this against production.**

## Running the Application

```bash
python run.py
# or directly:
python -m streamlit run app/main.py
```

Then open the URL Streamlit prints (typically `http://localhost:8501`).

## Testing

```bash
python -m pytest -q
```

Test suite covers: authentication, hostel infrastructure, student
eligibility, applications, the optimization engine (partial allocation,
capacity exhaustion, gender compatibility, no-eligible-applicants,
double-booking prevention), the full allocation review/approve/publish/
release workflow, access-control/data-isolation, and database integrity
constraints.

## Deployment

### Docker

```bash
docker compose up --build
```

This starts the application together with a PostgreSQL database. Set
`DATABASE_URL`, `SECRET_KEY` and other variables via a `.env` file or
your orchestration platform's secret management — never bake secrets
into the image.

### Manual / Bare-metal

1. Provision PostgreSQL and set `DATABASE_URL`.
2. `pip install -r requirements.txt`
3. `python -m alembic upgrade head`
4. `python scripts/create_admin.py`
5. Run behind a process manager, e.g. `streamlit run app/main.py --server.port=8501`.

## Backup & Recovery

- **What to back up:** the PostgreSQL database (all application data).
  Uploaded/generated files are not used by this system beyond report
  exports, which are generated on demand and not stored server-side.
- **Recommended frequency:** daily full backups (`pg_dump`), retained
  per institutional policy, plus point-in-time recovery (WAL archiving)
  if allocation publication windows are business-critical.
- **Restoration:** restore the most recent `pg_dump` into a fresh
  database, then run `alembic upgrade head` to confirm the schema
  matches the current migration history before starting the app.
- **Failed optimization:** the `OptimizationRun` record is marked
  `FAILED` with an error message; no partial `AllocationResult` rows are
  created for a failed run. Simply re-run the optimizer once the
  underlying issue (e.g. no eligible applicants) is resolved.
- **Incorrect allocation publication:** use the allocation release
  workflow (`Release`, with a mandatory reason) rather than editing the
  database directly; this preserves a full audit trail.
- **Accidental allocation release:** re-approve and re-publish the
  correct allocation; the prior state remains visible in
  `AllocationHistory`.
- **Migration problems:** never hand-edit the schema; fix forward with a
  new Alembic revision, or `alembic downgrade` to the last known-good
  revision and re-apply.

## Troubleshooting

- **"Database connection failed"** — verify `DATABASE_URL` and that the
  database server is reachable; check application logs for details.
- **bcrypt/password errors** — ensure the `bcrypt` package (not just
  `passlib`) is installed; this project hashes passwords directly with
  `bcrypt` to avoid known `passlib`/`bcrypt` version-detection issues.
- **Optimization run stuck at `RUNNING`** — this indicates the process
  was interrupted mid-run; only one run per academic session may be
  `RUNNING` at a time, so update that run's status manually via an
  administrator action before starting a new one.

## Project Status

All 8 planned modules are implemented: foundation, hostel infrastructure,
student/eligibility/applications, priority scoring, optimization engine,
allocation review/approval/publication, dashboards/analytics/reporting,
and security/testing/deployment hardening.

## Known Limitations

- Room-type "hard" incompatibility is not modeled as a hard constraint by
  default (it is a soft/scored preference); institutions that require a
  hard room-type match can extend `generate_candidates` accordingly.
- Waitlist re-processing when a bed becomes available is a manual
  administrator action, not an automatic re-optimization trigger (by
  design, per the original specification).
- Email/SMS notification delivery is not wired to an external provider;
  in-app notifications are fully functional and the service is modular
  enough to add a provider later.
