"""
YugKrit - Database initialization.
Single SQLAlchemy instance shared across the whole application.
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

db = SQLAlchemy()

CHALLENGE_CATEGORIES = [
    "Agriculture & Food Technology", "Climate & Sustainability", "Clean Energy & Energy Access",
    "Water Quality & Conservation", "Health Technology", "Education Technology",
    "Accessibility & Assistive Technology", "Digital Public Services", "Mobility & Safety Technology",
    "Civic Data & Community Research", "Livelihood & Skill Development", "Disaster Resilience Technology",
    "Smart Manufacturing & IoT", "Cybersecurity & Digital Inclusion", "General Innovation Challenge",
]

STUDENT_SOLVABLE_SUBCATEGORIES = {
    "Agriculture & Food Technology": ["Smart irrigation", "Crop health monitoring", "Post-harvest storage", "Farm market access"],
    "Climate & Sustainability": ["Waste tracking and circular economy", "Air-quality monitoring", "Urban heat mapping", "Carbon reduction"],
    "Clean Energy & Energy Access": ["Solar performance monitoring", "Energy efficiency", "Battery and storage", "Clean cooking"],
    "Water Quality & Conservation": ["Water quality sensing", "Leak detection", "Rainwater harvesting", "Water-use analytics"],
    "Health Technology": ["Preventive health screening", "Remote care access", "Medicine availability", "Public health analytics"],
    "Education Technology": ["Learning access", "Teacher support tools", "Assistive learning", "Skills assessment"],
    "Accessibility & Assistive Technology": ["Accessible navigation", "Assistive communication", "Inclusive design", "Disability support tools"],
    "Digital Public Services": ["Service discovery", "Citizen information access", "Document workflow", "Multilingual interfaces"],
    "Mobility & Safety Technology": ["Safe route mapping", "Pedestrian analytics", "Emergency alert systems", "Transport optimization"],
    "Civic Data & Community Research": ["Community surveys", "Open data tools", "Evidence mapping", "Impact measurement"],
    "Livelihood & Skill Development": ["Local job matching", "Micro-enterprise tools", "Digital skills", "Market intelligence"],
    "Disaster Resilience Technology": ["Flood early warning", "Heatwave alerts", "Emergency resource mapping", "Resilient infrastructure data"],
    "Smart Manufacturing & IoT": ["Predictive maintenance", "Low-cost automation", "Sensor networks", "Quality monitoring"],
    "Cybersecurity & Digital Inclusion": ["Security awareness", "Privacy tools", "Connectivity access", "Fraud prevention"],
    "General Innovation Challenge": ["Prototype and pilot", "Data-driven decision support", "Community research", "Sustainable design"],
}


def init_db(app):
    """Attach SQLAlchemy to the Flask app and create tables if needed."""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        ensure_project_workflow_schema()


def ensure_project_workflow_schema():
    """Additive upgrade for task workflow fields on existing local databases."""
    if db.engine.dialect.name != "sqlite":
        return
    columns = {column["name"] for column in inspect(db.engine).get_columns("tasks")}
    additions = {
        "role": "VARCHAR(100)",
        "objective": "TEXT",
        "instructions": "TEXT",
        "required_skills": "VARCHAR(300)",
        "required_technologies": "TEXT",
        "expected_deliverables": "TEXT",
        "submission_type": "VARCHAR(40)",
        "acceptance_criteria": "TEXT",
        "estimated_effort": "VARCHAR(80)",
        "priority": "VARCHAR(20)",
        "dependencies": "TEXT",
        "deadline": "DATE",
        "ai_reason": "TEXT",
        "approved_by_id": "INTEGER",
        "approved_at": "DATETIME",
    }
    for name, definition in additions.items():
        if name not in columns:
            db.session.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {definition}"))
    if any(name not in columns for name in additions):
        db.session.commit()

    analysis_columns = {column["name"] for column in inspect(db.engine).get_columns("ai_analyses")}
    analysis_additions = {
        "category_candidates": "TEXT", "secondary_categories": "TEXT", "subcategory": "VARCHAR(100)", "domains": "TEXT",
        "affected_users": "TEXT", "root_causes": "TEXT", "required_technologies": "TEXT",
        "matched_evidence": "TEXT", "solution_areas": "TEXT", "complexity": "VARCHAR(20)", "recommended_departments": "TEXT",
        "industry_capabilities": "TEXT", "recommended_roles": "TEXT", "explanation": "TEXT",
        "confidence_score": "FLOAT", "source": "VARCHAR(80)", "corrected_category_id": "INTEGER",
        "corrected_by_id": "INTEGER", "corrected_at": "DATETIME", "correction_reason": "TEXT",
    }
    for name, definition in analysis_additions.items():
        if name not in analysis_columns:
            db.session.execute(text(f"ALTER TABLE ai_analyses ADD COLUMN {name} {definition}"))
    if any(name not in analysis_columns for name in analysis_additions):
        db.session.commit()


def ensure_rbac():
    """Create the role and permission catalog required by registration/login."""
    from database.models import Permission, Role
    from utils.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS

    permission_objects = {}
    for code, description in ALL_PERMISSIONS:
        permission = Permission.query.filter_by(code=code).first()
        if not permission:
            permission = Permission(code=code, description=description)
            db.session.add(permission)
        permission_objects[code] = permission
    db.session.flush()

    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=role_name.replace("_", " ").title())
            db.session.add(role)
            db.session.flush()
        role.permissions = [permission_objects[code] for code in permission_codes]
    db.session.commit()


def ensure_challenge_categories():
    """Keep the category catalog available for every app startup."""
    from database.models import ChallengeCategory

    for name in CHALLENGE_CATEGORIES:
        if not ChallengeCategory.query.filter_by(name=name).first():
            db.session.add(ChallengeCategory(name=name))
    db.session.commit()
