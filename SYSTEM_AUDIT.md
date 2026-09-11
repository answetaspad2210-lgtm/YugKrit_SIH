# YugKrit System Audit

## 1. Current architecture

YugKrit is a single Flask application with multiple dashboard blueprints sharing the same backend, authentication layer, database, and service layer. The platform is designed as one interconnected civic innovation ecosystem rather than four isolated frontends.

Core flow:

- Citizen or ULB submits a challenge
- Government verifies or rejects it
- AI analysis scores and recommends skills/universities
- University accepts the challenge and creates a project
- Faculty assigns students and mentors
- Student receives project/workspace updates
- Industry can offer collaboration and support
- Project progresses through milestones to pilot/impact
- Citizen sees the public-safe lifecycle outcome

This is implemented as one application instance with shared models and one SQLite database by default.

## 2. Frontend technology

- HTML templates rendered via Jinja2
- Custom CSS and responsive layout rules
- Vanilla JavaScript for UI interactions
- Leaflet + OpenStreetMap for challenge maps
- Chart.js for analytics visuals
- Font Awesome for icons
- No SPA framework is used; the application is server-rendered Flask pages with API endpoints

## 3. Backend technology

- Python 3
- Flask
- Flask-SQLAlchemy
- Jinja2 templates
- role-based decorators and service layer pattern

## 4. Database technology

- SQLite is the default local development database
- SQLAlchemy ORM is used for schema and queries
- Models are declarative and persisted through Flask-SQLAlchemy
- Database configuration is environment-driven via `DATABASE_URL` in `config.py`

## 5. Authentication mechanism

- Session-based authentication using Flask session
- User login is stored with `session["user_id"]`
- Passwords are hashed using Werkzeug `generate_password_hash` and validated via `check_password_hash`
- OTP login is available through the mobile verification flow in `auth_routes.py`
- Account activation is controlled by user status and phone verification
- Role-based access is enforced with server-side decorators in `utils/decorators.py`

## 6. Role system

The RBAC catalog is seeded from `utils/permissions.py`.

Supported roles include:

- CITIZEN
- GOVERNMENT
- UNIVERSITY
- FACULTY
- STUDENT
- INDUSTRY
- ULB/NGO merged role: ULB_ADMIN / NGO_ADMIN
- Government platform head role: GOVT_IT_CELL_ADMIN
- ADMIN-like oversight is represented via platform roles and permissions rather than a separate standalone admin table

Protected routes are checked server-side. Frontend-only checks would not be sufficient.

## 7. Existing APIs

The project includes REST APIs under `/api` in `routes/api_routes.py`, including:

- auth login/logout/register
- challenge list and details
- challenge verify/assign
- university listing
- industry recommendations
- collaboration requests
- student/project info
- notifications
- analytics and audit log endpoints

## 8. Existing dashboards

The project already includes dashboards for:

- Government
- IT Cell
- University
- ULB / NGO
- Student
- Citizen
- Industry

These are separate blueprint URLs but share the same app, DB, auth, and services.

## 9. Existing workflow

A representative end-to-end workflow already exists:

- Challenge created in the ULB or citizen flow
- Government verifies challenge
- Challenge assigned to university
- University creates project
- Faculty mentors project
- Student team is formed by institution + registration number
- Milestones and tasks update project progress
- Industry may propose collaboration
- Completion triggers achievements / certificates

## 10. Current missing/incomplete features

The repository already has major architecture in place, but some product requirements are partly aspirational rather than fully wired end-to-end:

- Some advanced lifecycle states are represented conceptually but not fully enforced across every dashboard
- Some dynamic analytics and leaderboard sections are present but may not cover all described metrics consistently
- Some public-facing benefit sections are partial and may not yet show every stakeholder metric
- Documentation for the database and final system report was not yet created
- A production-grade environment and deployment guide were not yet consolidated
- Some product spec language (e.g., explicit impact, funding, leaderboard details) requires verification against stored data before being presented in UI

## 11. Changes implemented

For this task, the system was audited against the actual repository and aligned with the real architecture. The core implementation already matched the intended single-platform design, so changes focused on validating and documenting the existing system and filling missing project documentation.

The following were updated or created:

- `.env.example` expanded with all project-relevant variables and placeholders
- `SYSTEM_AUDIT.md` created with architecture and design findings
- Database and deployment notes were aligned to the real SQLite-backed Flask app
- The project was checked against its existing automated tests

## 12. Database location

The current default database is the local SQLite file at:

- `yugkrit/yugkrit.db`

It is configured from `config.py` via `DATABASE_URL`, defaulting to SQLite when no environment variable is provided.

## 13. How to access the database

By default, access it using SQLite tooling or by reading the database file directly.

Examples:

- `sqlite3 yugkrit.db`
- Python SQLAlchemy inspection from a Flask app context
- Browser-level database inspection is not built in; use the file or a local SQLite client

## 14. How to modify database records safely

- Use the application service layer (`services/*`) rather than direct SQL changes in routes
- Keep changes within a Flask app context
- Prefer `db.session.add(...)`, `db.session.commit()`, and `db.session.rollback()` on errors
- Never edit the database while bypassing the app logic for role checks, notifications, or audit logging
- Use the seeded data and service workflow to maintain data consistency

## 15. Required environment variables

See `.env.example` for the canonical list. The key variables are:

- `FLASK_APP`
- `FLASK_ENV`
- `FLASK_DEBUG`
- `SECRET_KEY`
- `JWT_SECRET`
- `FRONTEND_URL`
- `BACKEND_URL`
- `WEBSOCKET_URL`
- `DATABASE_URL`
- `AI_API_KEY`
- `EMAIL_API_KEY`
- `STORAGE_BUCKET`
- `WHATSAPP_PROVIDER`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`

## 16. Deployment requirements

For local development:

- Python 3.10+
- pip install from `requirements.txt`
- `python database/seed.py`
- `python app.py`

For production:

- Set a strong `SECRET_KEY`
- Set `FLASK_ENV=production`
- Set `SESSION_COOKIE_SECURE` appropriately
- Move away from the default SQLite file to a managed database if needed
- Use a real secret manager or environment manager instead of hardcoded values
- Serve behind a proper web server and TLS layer

## 17. Known limitations

- Default database is SQLite, which is suitable for local/dev/demo but not ideal for large multi-user production
- AI logic is rule-based mock AI, not a real LLM integration unless `AI_API_KEY` is wired into a provider
- Some advanced metrics and lifecycle views are seeded and computed from actual records but may need further UI polish to satisfy every product requirement exactly
- Real-time cross-dashboard live synchronization is not implemented as a WebSocket layer; the platform relies on normal refresh-driven database state updates
- Production deployment requires stronger environment separation and externalized secrets

## Summary

The repository is already a functioning single-platform civic innovation app built on Flask + SQLAlchemy + SQLite, with a shared authorization system and a full challenge-to-project lifecycle. The key work needed is not a full rebuild, but a disciplined verification and documentation pass to ensure the ecosystem is described accurately and configured safely for deployment.
