"""Tests for project creation, team building, and milestone -> achievement -> certificate flow."""

from datetime import date
from database.database import db
from services import auth_service, challenge_service, project_service


def _setup_project():
    from database.models import Organization, University, ULB, Faculty

    ulb_org = Organization(name="ULB", org_type="ULB", status="VERIFIED")
    uni_org = Organization(name="Uni", org_type="UNIVERSITY", status="VERIFIED")
    db.session.add_all([ulb_org, uni_org])
    db.session.flush()
    db.session.add(ULB(organization_id=ulb_org.id, authorized_officer="Officer"))
    university = University(organization_id=uni_org.id, rep_name="Rep")
    db.session.add(university)
    db.session.commit()

    gov_user = auth_service.create_user("Gov", "gov3@test.local", "Demo@123", "GOVERNMENT_ADMIN")
    faculty_user = auth_service.create_user("Fac", "fac3@test.local", "Demo@123", "FACULTY",
                                              organization_id=uni_org.id)
    faculty = Faculty(user_id=faculty_user.id, university_id=university.id, department="CS")
    db.session.add(faculty)
    db.session.commit()

    challenge = challenge_service.create_challenge(ulb_org, {
        "title": "Test Challenge", "description": "Desc", "category": "General",
        "affected_population": 100, "urgency": "MEDIUM",
    })
    challenge_service.verify_challenge(challenge, gov_user, approve=True)
    challenge_service.assign_challenge(challenge, gov_user, university_id=university.id)

    project = project_service.create_project(challenge, university, faculty, {
        "name": "Test Project", "start_date": date(2026, 1, 1),
    })
    return project, university


def test_team_creation_links_and_never_duplicates(app):
    with app.app_context():
        project, university = _setup_project()
        members = [
            {"full_name": "Student A", "college_email": "a@uni.edu",
             "registration_number": "UNI2026CS001", "role_in_team": "Team Leader"},
        ]
        team1, new_count1 = project_service.create_team(project, "Team 1", members)
        assert new_count1 == 1

        team2, new_count2 = project_service.create_team(project, "Team 2", members)
        assert new_count2 == 0

        from database.models import StudentProfile
        count = StudentProfile.query.filter_by(
            institution_id=university.id, registration_number="UNI2026CS001").count()
        assert count == 1


def test_milestone_completion_triggers_achievements_and_certificates(app):
    with app.app_context():
        project, university = _setup_project()
        gov_user = __import__("database.models", fromlist=["User"]).User.query.filter_by(email="gov3@test.local").one()
        members = [
            {"full_name": "Student B", "college_email": "b@uni.edu",
             "registration_number": "UNI2026CS002", "role_in_team": "Developer"},
        ]
        project_service.create_team(project, "Team 1", members)

        for m in project.milestones:
            project_service.update_milestone_status(m, "COMPLETED")

        db.session.refresh(project)
        assert project.status == "COMPLETED"

        from database.models import StudentAchievement, Certificate
        assert StudentAchievement.query.count() == 0
        assert Certificate.query.count() == 0

        project_service.verify_project(project, gov_user)
        db.session.refresh(project)
        assert project.status == "VERIFIED"
        assert StudentAchievement.query.count() > 0
        assert Certificate.query.count() == 1


def test_student_recommendation_and_task_updates_are_authorized(app, client):
    with app.app_context():
        project, university = _setup_project()
        from database.models import StudentProfile, StudentSkill, Task
        student = StudentProfile(institution_id=university.id, registration_number="UNI2026CS003",
                                 full_name="Skilled Student", college_email="skilled@uni.edu", department="Computer Science")
        db.session.add(student)
        db.session.flush()
        db.session.add_all([StudentSkill(student_id=student.id, skill_name="IoT"),
                            StudentSkill(student_id=student.id, skill_name="Python")])
        challenge = project.challenge
        challenge.required_skills = "IoT, Python, Sensors"
        db.session.commit()
        recommendations = __import__("services.student_service", fromlist=["recommend_students_for_challenge"]).recommend_students_for_challenge(challenge, university)
        assert recommendations[0]["student"].id == student.id
        team, _ = project_service.create_team(project, "Recommended Team", [{
            "full_name": student.full_name, "college_email": student.college_email,
            "registration_number": student.registration_number, "role_in_team": "Developer",
        }])
        task = Task(project_id=project.id, title="Build sensor API", assigned_to_id=student.id)
        db.session.add(task)
        db.session.commit()
        task_id = task.id
        student_user = auth_service.create_user("Skilled Student", "student-task@test.local", "Demo@123", "STUDENT")
        student.user_id = student_user.id
        db.session.commit()

    client.post("/auth/login", data={"email": "student-task@test.local", "password": "Demo@123"})
    response = client.post(f"/dashboard/student/tasks/{task_id}/status", data={"status": "IN_PROGRESS"})
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Task, task_id).status == "IN_PROGRESS"


def test_faculty_can_approve_recommended_team_from_existing_profiles(app, client):
    with app.app_context():
        project, university = _setup_project()
        from database.models import StudentProfile, StudentSkill, ProjectTeamMember
        student = StudentProfile(institution_id=university.id, registration_number="UNI2026CS004",
                                 full_name="Approved Student", college_email="approved@uni.edu",
                                 department="Computer Science")
        db.session.add(student)
        db.session.flush()
        db.session.add(StudentSkill(student_id=student.id, skill_name="Research"))
        project.challenge.required_skills = "Research"
        db.session.commit()
        student_user = auth_service.create_user("Approved Student", "approved-task@test.local", "Demo@123", "STUDENT")
        student.user_id = student_user.id
        db.session.commit()
        project_id = project.id
        student_id = student.id
        faculty_user = __import__("database.models", fromlist=["User"]).User.query.filter_by(email="fac3@test.local").one()

    client.post("/auth/login", data={"email": "fac3@test.local", "password": "Demo@123"})
    response = client.post(f"/dashboard/university/projects/{project_id}/recommended-team", data={
        "student_ids": [str(student_id)], "role_" + str(student_id): "Researcher", "team_name": "Approved Team",
    })
    assert response.status_code == 302
    with app.app_context():
        assert ProjectTeamMember.query.filter_by(student_id=student_id).count() == 1


def test_ai_role_specific_task_generation_and_submission_reviews(app):
    with app.app_context():
        project, university = _setup_project()
        from database.models import StudentProfile, StudentSkill, Task, TaskSubmission

        project.challenge.title = "Smart Irrigation for Rural Farmers"
        project.challenge.description = "Farmers are wasting water because irrigation is manually controlled."
        project.challenge.required_skills = "IoT, Python, Data Analysis, Embedded Systems, Dashboard Design"

        team_members = [
            ("Student A", "UNI2026CS101", "Problem Research", ["Research", "Agriculture", "Field Work"]),
            ("Student B", "UNI2026EC102", "IoT Developer", ["IoT", "Embedded Systems", "Python"]),
            ("Student C", "UNI2026CS103", "AI/Data Analyst", ["Python", "Machine Learning", "Data Analysis"]),
            ("Student D", "UNI2026CS104", "Dashboard Developer", ["Python", "Dashboard Design", "Web Development"]),
        ]

        for full_name, registration_number, role, skills in team_members:
            student = StudentProfile(
                institution_id=university.id,
                registration_number=registration_number,
                full_name=full_name,
                college_email=f"{registration_number.lower()}@uni.edu",
                department="Computer Science" if "Student" in full_name or registration_number.startswith("UNI") else "Electronics",
            )
            db.session.add(student)
            db.session.flush()
            for skill in skills:
                db.session.add(StudentSkill(student_id=student.id, skill_name=skill))
            db.session.flush()
            db.session.add_all([
                __import__("database.models", fromlist=["StudentProfile"]).StudentProfile.query.get(student.id)
            ])

        db.session.commit()
        project_service.create_team(project, "Smart Irrigation Team", [
            {"full_name": "Student A", "college_email": "uni2026cs101@uni.edu", "registration_number": "UNI2026CS101", "role_in_team": "Problem Research"},
            {"full_name": "Student B", "college_email": "uni2026ec102@uni.edu", "registration_number": "UNI2026EC102", "role_in_team": "IoT Developer"},
            {"full_name": "Student C", "college_email": "uni2026cs103@uni.edu", "registration_number": "UNI2026CS103", "role_in_team": "AI/Data Analyst"},
            {"full_name": "Student D", "college_email": "uni2026cs104@uni.edu", "registration_number": "UNI2026CS104", "role_in_team": "Dashboard Developer"},
        ])

        generated = project_service.generate_ai_task_plan(project)
        assert len(generated) >= 4
        titles = {task.role.lower(): task.title.lower() for task in generated}
        problem_title = titles.get("problem research", "")
        iot_title = titles.get("iot developer", "")
        data_title = titles.get("ai/data analyst", "")
        dashboard_title = titles.get("dashboard developer", "")
        assert "research" in problem_title or "field" in problem_title
        assert "iot" in iot_title or "sensor" in iot_title
        assert "data" in data_title or "model" in data_title
        assert "dashboard" in dashboard_title or "api" in dashboard_title

        research_task = next(task for task in generated if task.role == "Problem Research")
        research_task.assigned_to.user_id = auth_service.create_user("Student A", "student-phase2@test.local", "Demo@123", "STUDENT").id
        db.session.commit()
        project_service.submit_task_work(research_task, research_task.assigned_to, "I reviewed 6 papers and compared soil moisture systems.")
        assert research_task.status in ("AI_REVIEW", "FACULTY_REVIEW")
        assert research_task.submission is not None
        assert research_task.submission.ai_reviews
        assert any("reference" in review.summary.lower() or "missing" in review.summary.lower() or "review" in review.summary.lower() for review in research_task.submission.ai_reviews)

        faculty_user = __import__("database.models", fromlist=["User"]).User.query.filter_by(email="fac3@test.local").one()
        project_service.review_task(research_task, faculty_user, {"quality": 5, "relevance": 5, "completeness": 4, "evidence": 4}, "Good work; add 2 additional references.", "CHANGES_REQUESTED")
        assert research_task.status == "CHANGES_REQUESTED"
        assert research_task.review is not None
