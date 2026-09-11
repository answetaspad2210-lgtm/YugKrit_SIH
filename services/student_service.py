"""
YugKrit - Student service.

The single most important rule in this whole application:

    A student is uniquely identified by (institution_id, registration_number).

`find_or_invite_student()` is the ONLY function that should ever be used to
attach a student to a project team. It guarantees no duplicate profiles are
ever created.
"""

from database.database import db
from database.models import StudentProfile
from utils.validators import validate_registration_number, validate_email, ValidationError


def find_student(institution_id, registration_number):
    reg_no = validate_registration_number(registration_number)
    return StudentProfile.query.filter_by(
        institution_id=institution_id, registration_number=reg_no
    ).first()


def find_or_invite_student(institution_id, registration_number, full_name, college_email,
                            department=None, course=None, year=None):
    """Look up a student by (institution_id, registration_number).
    If found -> return existing profile (LINK, never duplicate).
    If not found -> create an INVITED profile that becomes ACTIVE once the
    student logs in / registers using the same institution + reg number.
    """
    reg_no = validate_registration_number(registration_number)
    email = validate_email(college_email)

    existing = StudentProfile.query.filter_by(
        institution_id=institution_id, registration_number=reg_no
    ).first()
    if existing:
        return existing, False  # False = not newly created

    student = StudentProfile(
        institution_id=institution_id,
        registration_number=reg_no,
        full_name=full_name.strip(),
        college_email=email,
        department=department,
        course=course,
        year=year,
        status="INVITED",
    )
    db.session.add(student)
    db.session.commit()
    return student, True  # True = newly created / invited


def activate_student_on_registration(user, institution_id, registration_number):
    """Called when a student completes registration/login. Links their User
    account to any pre-existing invited profile, or creates a fresh one."""
    reg_no = validate_registration_number(registration_number)
    profile = StudentProfile.query.filter_by(
        institution_id=institution_id, registration_number=reg_no
    ).first()

    if profile:
        if profile.user_id and profile.user_id != user.id:
            raise ValidationError("This registration number is already linked to another account.",
                                   code="STUDENT_ALREADY_LINKED")
        profile.user_id = user.id
        profile.status = "ACTIVE"
        db.session.commit()
        return profile

    profile = StudentProfile(
        user_id=user.id,
        institution_id=institution_id,
        registration_number=reg_no,
        full_name=user.full_name,
        college_email=user.email,
        status="ACTIVE",
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def get_growth_profile(student):
    """Compute the permanent Innovation Growth Profile shown on the student
    dashboard, derived entirely from relationships (never duplicated data)."""
    memberships = student.team_memberships
    projects = [m.team.project for m in memberships]
    completed_projects = [p for p in projects if p.status in ("COMPLETED", "VERIFIED")]

    people_impacted = 0
    for p in completed_projects:
        if p.impact:
            people_impacted += p.impact.people_impacted or 0

    return {
        "projects_completed": len(completed_projects),
        "problems_addressed": len({p.challenge_id for p in completed_projects}),
        "solutions_proposed": len(projects),
        "certificates": len(student.certificates),
        "skills_count": len(student.skills),
        "people_impacted": people_impacted,
        "skills": [s.skill_name for s in student.skills],
        "projects": projects,
        "achievements": student.achievements,
        "certificates_list": student.certificates,
    }


def recommend_students_for_challenge(challenge, university, limit=8):
    """Rank students with an explainable weighted score.

    Score = 50% skill coverage + 20% department/domain fit + 20% availability
    + 10% experience. Availability is approximated by active project count;
    no embeddings are claimed or used here.
    """
    required = {value.strip().lower() for value in (challenge.required_skills or "").split(",") if value.strip()}
    candidates = StudentProfile.query.filter_by(institution_id=university.id).all()
    ranked = []
    for student in candidates:
        skills = {skill.skill_name.strip().lower() for skill in student.skills}
        matched = sorted(required & skills)
        skill_score = (len(matched) / len(required) * 50) if required else 0
        department_text = (student.department or "").lower()
        domain_terms = f"{challenge.title} {challenge.description or ''} {challenge.subcategory or ''}".lower()
        department_score = 20 if department_text and any(term in department_text for term in domain_terms.split()) else 0
        active_projects = sum(1 for membership in student.team_memberships
                              if membership.team.project.status not in ("COMPLETED", "VERIFIED"))
        availability_score = max(0, 20 - min(active_projects, 4) * 5)
        experience_score = min(10, sum(1 for membership in student.team_memberships
                                       if membership.team.project.status in ("COMPLETED", "VERIFIED")) * 5)
        score = round(skill_score + department_score + availability_score + experience_score)
        reasons = [f"{len(matched)}/{len(required)} required skills" if required else "profile skills available"]
        if department_score:
            reasons.append("department aligns with the problem domain")
        if availability_score >= 15:
            reasons.append("available capacity")
        ranked.append({"student": student, "score": score, "matched": matched, "reasons": reasons,
                       "active_projects": active_projects})
    ranked.sort(key=lambda item: (item["score"], -item["active_projects"]), reverse=True)
    return ranked[:limit]
