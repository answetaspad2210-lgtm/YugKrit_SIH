"""End-to-end tests for the Industry participant workflow."""

from database.database import db
from database.models import (
    Organization, ULB, University, IndustryProfile, IndustryCollaboration,
    IndustryCollaborationRequest, Notification, Challenge, ChallengeEvidence,
)
from services import auth_service, challenge_service, project_service


def _organization(name, org_type):
    organization = Organization(name=name, org_type=org_type, status="VERIFIED",
                                 state="Jharkhand", district="Ranchi")
    db.session.add(organization)
    db.session.flush()
    return organization


def test_industry_proposal_is_approved_and_linked_to_project(app, client):
    with app.app_context():
        gov_org = _organization("Government Test Office", "GOVERNMENT")
        gov_user = auth_service.create_user("Gov", "industry-gov@test.local", "Demo@123",
                                            "GOVERNMENT_ADMIN", organization_id=gov_org.id)
        ulb_org = _organization("Water ULB", "ULB")
        db.session.add(ULB(organization_id=ulb_org.id, authorized_officer="Officer"))
        uni_org = _organization("Test University", "UNIVERSITY")
        university = University(organization_id=uni_org.id, rep_name="Dean")
        db.session.add(university)
        db.session.flush()
        uni_user = auth_service.create_user("Dean", "industry-uni@test.local", "Demo@123",
                                            "UNIVERSITY_ADMIN", organization_id=uni_org.id)
        uni_user_id = uni_user.id
        industry_org = _organization("WaterTech Partner", "INDUSTRY")
        industry = IndustryProfile(organization_id=industry_org.id, organization_type="Technology Provider",
                                   sector="Water Management", expertise="IoT, water monitoring",
                                   technologies="Sensors, analytics", contact_person="Partner")
        db.session.add(industry)
        db.session.flush()
        industry_user = auth_service.create_user("Partner", "industry@test.local", "Demo@123",
                                                 "INDUSTRY", organization_id=industry_org.id)
        db.session.commit()

        challenge = challenge_service.create_challenge(ulb_org, {
            "title": "Village water monitoring", "description": "Sensor-based water quality reporting",
            "category": "Water & Sanitation", "subcategory": "Drinking water",
            "affected_population": 500, "urgency": "HIGH", "district": "Ranchi", "state": "Jharkhand",
        })
        challenge_service.verify_challenge(challenge, gov_user, approve=True)
        project = project_service.create_project(challenge, university, None, {
            "name": "Water Monitoring Project", "objective": "Deploy sensors",
        })
        project_id = project.id
        challenge_id = challenge.id

    client.post("/auth/login", data={"email": "industry@test.local", "password": "Demo@123"})
    dashboard_response = client.get("/industry/dashboard")
    assert dashboard_response.status_code == 200
    response = client.post(f"/industry/challenges/{challenge_id}/collaborate", data={
        "project_id": project_id, "support_types": ["Technical Mentorship", "Hardware"],
        "description": "Provide sensors and technical mentoring.", "expected_duration": "6 months",
    })
    assert response.status_code == 302

    with app.app_context():
        proposal = IndustryCollaborationRequest.query.one()
        proposal_id = proposal.id
        assert proposal.status == "REQUESTED"
        assert Notification.query.filter_by(user_id=uni_user_id).count() == 1

    client.post("/auth/logout")
    client.post("/auth/login", data={"email": "industry-uni@test.local", "password": "Demo@123"})
    response = client.post(f"/dashboard/university/collaboration-requests/{proposal_id}/review", data={
        "decision": "approve", "project_id": project_id, "review_note": "Approved for the student team.",
    })
    assert response.status_code == 302

    with app.app_context():
        collaboration = IndustryCollaboration.query.one()
        assert collaboration.project_id == project_id
        assert collaboration.status == "ACTIVE"
        assert IndustryCollaborationRequest.query.one().status == "ACTIVE"
        assert Notification.query.filter_by(title="Collaboration approved").count() == 1


def test_non_industry_cannot_access_industry_dashboard(app, client):
    with app.app_context():
        user = auth_service.create_user("Citizen", "industry-citizen@test.local", "Demo@123", "CITIZEN")
    client.post("/auth/login", data={"email": "industry-citizen@test.local", "password": "Demo@123"})
    response = client.get("/industry/dashboard")
    assert response.status_code == 302


def test_industry_registration_persists_structured_capabilities(app, client):
    response = client.post("/industry/register", data={
        "organization_name": "Agri Systems Lab", "organization_type": "Technology Provider",
        "sector": "Agriculture Technology", "sub_sector": "Precision Agriculture",
        "organization_size": "Startup", "location": "Ranchi", "district": "Ranchi",
        "state": "Jharkhand", "website": "https://agri.example", "contact_person": "Asha Rao",
        "official_email": "asha@agri.example", "phone": "9876543210", "description": "Smart farming",
        "expertise": ["IoT", "Agricultural Technology"],
        "technologies": ["IoT", "Sensors", "Data Analytics"],
        "services": ["Technical Mentoring", "Prototype Development"],
        "csr_focus_areas": ["Agriculture", "Rural Development"],
        "available_resources": ["Technical Experts", "Sensors", "Prototyping Facility"],
        "password": "StrongPass@123", "confirm_password": "StrongPass@123",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        profile = IndustryProfile.query.one()
        assert profile.sector == "Agriculture Technology"
        assert '"IoT"' in profile.expertise
        assert '"Sensors"' in profile.technologies
        assert profile.organization.website == "https://agri.example"


def test_industry_can_submit_challenge_for_government_review(app, client):
    with app.app_context():
        organization = _organization("Agri Challenge Partner", "INDUSTRY")
        organization_id = organization.id
        profile = IndustryProfile(organization_id=organization.id, organization_type="Industry",
                                  sector="Agriculture Technology", sub_sector="Smart Irrigation",
                                  expertise='["IoT"]', technologies='["Sensors"]', contact_person="Partner")
        db.session.add(profile)
        user = auth_service.create_user("Partner", "challenge-industry@test.local", "Demo@123",
                                        "INDUSTRY", organization_id=organization.id)
        db.session.commit()

    client.post("/auth/login", data={"email": "challenge-industry@test.local", "password": "Demo@123"})
    response = client.post("/industry/submit-challenge", data={
        "title": "Smart irrigation for water-efficient farming",
        "description": "Farmers need sensor-based irrigation and crop monitoring.",
        "category": "Agriculture & Livelihoods", "subcategory": "Smart Irrigation",
        "urgency": "HIGH", "affected_population": "1200", "district": "Ranchi", "state": "Jharkhand",
        "expected_outcome": "Reduce water use and improve crop yields.",
    }, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        challenge = Challenge.query.filter_by(title="Smart irrigation for water-efficient farming").one()
        assert challenge.submitted_by_org_id == organization_id
        assert challenge.status == "SUBMITTED"
        assert challenge.ai_analysis is not None
        assert "IoT" in challenge.required_skills or "Research" in challenge.required_skills
        assert ChallengeEvidence.query.filter_by(challenge_id=challenge.id).count() == 0


def test_pending_industry_account_login_resumes_signup_verification(app, client):
    with app.app_context():
        organization = _organization("Pending Industry", "INDUSTRY")
        db.session.add(IndustryProfile(organization_id=organization.id, organization_type="Industry",
                                       sector="IoT", sub_sector="Smart Cities", contact_person="Owner"))
        user = auth_service.create_user("Owner", "pending-industry@test.local", "Demo@123",
                                        "INDUSTRY", organization_id=organization.id, phone="9876543212")
        auth_service.deactivate_user(user)
        db.session.commit()

    response = client.post("/auth/login", data={
        "email": "pending-industry@test.local", "password": "Demo@123",
    }, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/signup/otp/verify")
