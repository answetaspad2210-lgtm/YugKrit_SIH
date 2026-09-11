# YugKrit Database Guide

## 1. Database technology

YugKrit uses SQLAlchemy with Flask-SQLAlchemy and SQLite by default.

This means:

- Database type: SQLite in local development
- ORM: SQLAlchemy
- App binding: Flask app factory in `app.py` and `database/database.py`
- Schema is defined in `database/models.py`
- Tables are created automatically via `db.create_all()`

The project is intentionally structured so a PostgreSQL or other SQL database can be used later by changing `DATABASE_URL` in the environment.

## 2. Local development database

The local development database file is:

- `yugkrit.db`

This file is in the project root by default.

## 3. Production database

Production should use a managed database such as PostgreSQL or another SQL engine. The app supports it by reading `DATABASE_URL` from the environment.

Example:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/yugkrit
```

Do not hardcode real credentials in code or documentation.

## 4. Database connection configuration

Database configuration lives in:

- `config.py`

The actual connection is determined by `DATABASE_URL` in the environment. If it is not set, the app falls back to SQLite at:

```python
sqlite:///yugkrit.db
```

## 5. Environment variable names

Key variables:

```env
DATABASE_URL=your_database_url_here
SECRET_KEY=your_secret_key_here
FLASK_ENV=development
FLASK_DEBUG=1
```

For example, copy the template from `.env.example` and fill in your own values.

## 6. Schema/models

The core schema is defined in `database/models.py`.

Key models include:

- `User`
- `Role`
- `Permission`
- `Organization`
- `University`
- `Faculty`
- `StudentProfile`
- `Challenge`
- `ChallengeLocation`
- `ChallengeEvidence`
- `AIAnalysis`
- `Project`
- `Milestone`
- `Task`
- `ProjectTeam`
- `ProjectTeamMember`
- `IndustryProfile`
- `IndustryCollaborationRequest`
- `IndustryCollaboration`
- `Notification`
- `AuditLog`
- `Certificate`
- `StudentAchievement`

## 7. Main collections/tables

In a SQLite database, these appear as tables. The main ones are:

- `users`
- `roles`
- `permissions`
- `organizations`
- `universities`
- `faculty`
- `student_profiles`
- `challenges`
- `challenge_locations`
- `challenge_evidence`
- `ai_analyses`
- `projects`
- `milestones`
- `tasks`
- `project_teams`
- `project_team_members`
- `industry_profiles`
- `industry_collaboration_requests`
- `industry_collaborations`
- `notifications`
- `audit_logs`

## 8. Relationships

The platform keeps the database as the source of truth across the ecosystem:

- `User -> Role`
- `User -> Organization`
- `Organization -> University / ULB / Government`
- `Challenge -> ChallengeLocation`
- `Challenge -> AIAnalysis`
- `Challenge -> Project`
- `Project -> Milestone`
- `Project -> ProjectTeam`
- `ProjectTeam -> StudentProfile`
- `Project -> IndustryCollaboration`
- `User -> Notification`
- `User -> AuditLog`

This keeps the challenge lifecycle, project workflow, and stakeholder visibility connected to the same records.

## 9. Migration commands

This project does not include a formal migration framework in the repository at the moment. The application creates tables automatically via `db.create_all()` when the app starts.

Typical process:

```bash
python app.py
```

or via a custom initialization route or a management script. For a production system, a SQLAlchemy migration tool such as Alembic should be introduced if schema evolution becomes important.

## 10. Seed commands if any

Seed script:

```bash
python database/seed.py
```

This script creates:

- roles and permissions
- challenge categories
- development demo accounts
- sample organizations and universities
- demo projects and milestones

## 11. How to inspect data

Use SQLite CLI or a Python shell:

```bash
sqlite3 yugkrit.db
```

Then query tables like:

```sql
SELECT * FROM users;
SELECT * FROM challenges;
SELECT * FROM projects;
SELECT * FROM notifications;
```

Or from Python:

```python
from app import app
from database.database import db
from database.models import Challenge

with app.app_context():
    print(Challenge.query.count())
```

## 12. How to safely modify data

Use the app’s service-layer functions whenever possible instead of modifying raw tables.

Examples:

- use `auth_service.create_user(...)` for user creation
- use `challenge_service.verify_challenge(...)`
- use `project_service.update_milestone_status(...)`
- use `notify(...)` for notification insertion

This keeps audit logs, status changes, and lifecycle rules consistent.

## 13. How to backup data

Simple file backup:

```bash
copy yugkrit.db yugkrit_backup.db
```

or on Linux/macOS:

```bash
cp yugkrit.db yugkrit_backup.db
```

For production, back up the database using a managed database backup process.

## 14. How to reset development data

Delete the local SQLite file and reseed:

```bash
rm yugkrit.db
python database/seed.py
```

On Windows PowerShell:

```powershell
Remove-Item yugkrit.db
python database/seed.py
```

## 15. How production data is protected

Production protection requires:

- strong `SECRET_KEY`
- proper TLS / HTTPS
- no secrets in repository or docs
- environment-based configuration
- restricted database access
- separate credentials for development and production
- limited public exposure of private user data

## Summary

YugKrit currently runs on a shared SQLAlchemy-backed SQLite database with all platform roles and lifecycle tables in the same system. The database is the source of truth for challenges, projects, users, notifications, and impact tracking. For production, move to a hosted SQL database and store connection values in environment variables rather than in code or git-tracked files.
