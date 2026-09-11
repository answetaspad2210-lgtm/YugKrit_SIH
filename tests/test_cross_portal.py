"""Integration checks for the shared challenge lifecycle across portals."""

from database.database import db
from database.models import Challenge, Organization, University, ULB, UniversityApplication, Notification
from services import auth_service, challenge_service


def test_challenge_lifecycle_notifies_originating_portal(app):
    with app.app_context():
        org = Organization(name="Cross Portal ULB", org_type="ULB", status="VERIFIED")
        db.session.add(org)
        db.session.flush()
        db.session.add(ULB(organization_id=org.id, authorized_officer="Officer"))
        ulb_user = auth_service.create_user("ULB Officer", "cross-ulb@test.local", "Demo@123",
                                            "ULB_ADMIN", organization_id=org.id)
        gov_user = auth_service.create_user("Gov Officer", "cross-gov@test.local", "Demo@123",
                                            "GOVERNMENT_ADMIN")
        challenge = challenge_service.create_challenge(org, {
            "title": "Cross portal water issue", "description": "Shared lifecycle test",
            "category": "Water & Sanitation", "affected_population": 100,
            "urgency": "HIGH", "district": "Ranchi", "state": "Jharkhand",
        })

        challenge_service.verify_challenge(challenge, gov_user, approve=True)
        challenge_service.assign_challenge(challenge, gov_user)

        notifications = Notification.query.filter_by(user_id=ulb_user.id).all()
        assert challenge.status == "VERIFIED"
        assert any("Challenge review completed" == note.title for note in notifications)
        assert all(note.link.startswith("/dashboard/") for note in notifications if note.link)


def test_university_cannot_apply_twice_to_one_challenge(app, client):
    with app.app_context():
        org = Organization(name="Application University", org_type="UNIVERSITY", status="VERIFIED")
        db.session.add(org)
        db.session.flush()
        university = University(organization_id=org.id, rep_name="Rep")
        db.session.add(university)
        ulb_org = Organization(name="Application ULB", org_type="ULB", status="VERIFIED")
        db.session.add(ulb_org)
        db.session.flush()
        db.session.add(ULB(organization_id=ulb_org.id, authorized_officer="Officer"))
        db.session.commit()
        uni_user = auth_service.create_user("University Admin", "application-uni@test.local", "Demo@123",
                                            "UNIVERSITY_ADMIN", organization_id=org.id)
        gov_user = auth_service.create_user("Application Gov", "application-gov@test.local", "Demo@123",
                                            "GOVERNMENT_ADMIN")
        challenge = challenge_service.create_challenge(ulb_org, {
            "title": "Application dedupe issue", "description": "Apply once",
            "category": "General Societal Challenge", "affected_population": 50,
            "urgency": "MEDIUM",
        })
        challenge_service.verify_challenge(challenge, gov_user, approve=True)
        challenge_id = challenge.id

    client.post("/auth/login", data={"email": "application-uni@test.local", "password": "Demo@123"})
    first = client.post(f"/dashboard/university/challenges/{challenge_id}/apply", data={"pitch": "First"})
    second = client.post(f"/dashboard/university/challenges/{challenge_id}/apply", data={"pitch": "Second"})

    with app.app_context():
        assert first.status_code == 302
        assert second.status_code == 302
        assert UniversityApplication.query.filter_by(challenge_id=challenge_id).count() == 1


def test_registered_university_appears_in_student_registration(app, client):
    with app.app_context():
        organization = Organization(name="New Registered University", org_type="UNIVERSITY", status="PENDING")
        db.session.add(organization)
        db.session.flush()
        db.session.add(University(organization_id=organization.id, rep_name="Registrar"))
        db.session.commit()

    response = client.get("/auth/register/student")
    assert response.status_code == 200
    assert b"New Registered University" in response.data
    assert b"Pending" in response.data


def test_university_acceptance_assigns_same_verified_challenge_to_students(app, client):
    with app.app_context():
        university_org = Organization(name="Workflow University", org_type="UNIVERSITY", status="VERIFIED")
        challenge_org = Organization(name="Workflow Civic Body", org_type="ULB", status="VERIFIED")
        db.session.add_all([university_org, challenge_org])
        db.session.flush()
        university = University(organization_id=university_org.id, rep_name="Dean")
        db.session.add(university)
        db.session.flush()
        db.session.add(ULB(organization_id=challenge_org.id, authorized_officer="Officer"))
        db.session.commit()
        university_user = auth_service.create_user("Dean", "workflow-uni@test.local", "Demo@123",
                                                   "UNIVERSITY_ADMIN", organization_id=university_org.id)
        government_user = auth_service.create_user("Gov", "workflow-gov@test.local", "Demo@123",
                                                   "GOVERNMENT_ADMIN")
        challenge = challenge_service.create_challenge(challenge_org, {
            "title": "Verified workflow problem", "description": "A persisted cross-portal problem",
            "category": "Water & Sanitation", "subcategory": "Water quality", "urgency": "HIGH",
            "affected_population": 300, "district": "Ranchi", "state": "Jharkhand",
        })
        challenge_service.verify_challenge(challenge, government_user, approve=True)
        challenge_id = challenge.id
        university_id = university.id

    client.post("/auth/login", data={"email": "workflow-uni@test.local", "password": "Demo@123"})
    marketplace = client.get("/dashboard/university/marketplace")
    assert marketplace.status_code == 200
    assert b"Verified workflow problem" in marketplace.data
    accepted = client.post(f"/dashboard/university/challenges/{challenge_id}/apply",
                           data={"pitch": "Our department can solve this."})
    assert accepted.status_code == 302

    with app.app_context():
        persisted = db.session.get(Challenge, challenge_id)
        application = UniversityApplication.query.filter_by(challenge_id=challenge_id).one()
        assert persisted.assigned_university_id == university_id
        assert persisted.status == "ASSIGNED"
        assert application.status == "ACCEPTED"

    client.post("/auth/logout")
    student_page = client.get("/dashboard/student/problems")
    assert student_page.status_code == 302
