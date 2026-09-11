"""YugKrit - University dashboard routes."""

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import or_
from database.database import db
from database.models import (
    Challenge, University, Project, Faculty, StudentProfile, UniversityApplication,
    ChallengeCategory, Milestone, IndustryCollaborationRequest, IndustryCollaboration, Task
)
from utils.decorators import role_required, get_current_user
from services import project_service, student_service
from services.notification_service import notify
from services.audit_service import log_action

university_bp = Blueprint("university", __name__, template_folder="../templates/university")

UNI_ROLES = ("UNIVERSITY_ADMIN", "FACULTY")


def _current_university():
    user = get_current_user()
    if not user or not user.organization:
        return None
    return University.query.filter_by(organization_id=user.organization_id).first()


@university_bp.route("/")
@role_required(*UNI_ROLES)
def overview():
    university = _current_university()
    verified_challenges = Challenge.query.filter(or_(
        Challenge.status == "VERIFIED",
        Challenge.assigned_university_id == university.id if university else False,
    )).order_by(
        Challenge.priority_score.desc(), Challenge.created_at.desc()).limit(8).all()
    stats = {
        "challenges_available": Challenge.query.filter(or_(
            Challenge.status == "VERIFIED",
            Challenge.assigned_university_id == university.id if university else False,
        )).count(),
        "active_projects": Project.query.filter_by(university_id=university.id)
                            .filter(Project.status.in_(["PLANNING", "IN_PROGRESS"])).count() if university else 0,
        "students": StudentProfile.query.filter_by(institution_id=university.id).count() if university else 0,
        "faculty": Faculty.query.filter_by(university_id=university.id).count() if university else 0,
        "pending_reviews": Milestone.query.join(Project).filter(
            Project.university_id == university.id, Milestone.status == "SUBMITTED"
        ).count() if university else 0,
        "completed_projects": Project.query.filter_by(university_id=university.id)
                               .filter(Project.status.in_(["COMPLETED", "VERIFIED"])).count() if university else 0,
    }
    my_projects = Project.query.filter_by(university_id=university.id).order_by(
        Project.created_at.desc()).limit(5).all() if university else []
    return render_template("university/overview.html", university=university, stats=stats,
                           my_projects=my_projects, verified_challenges=verified_challenges)


@university_bp.route("/marketplace")
@role_required(*UNI_ROLES)
def marketplace():
    university = _current_university()
    q = Challenge.query.filter(or_(
        Challenge.status == "VERIFIED",
        Challenge.assigned_university_id == university.id if university else False,
    ))
    category = request.args.get("category")
    district = request.args.get("district")
    if category:
        q = q.join(ChallengeCategory).filter(ChallengeCategory.name == category)
    if district:
        q = q.join(Challenge.location).filter_by(district=district)
    challenges = q.order_by(Challenge.priority_score.desc()).all()
    categories = ChallengeCategory.query.all()
    return render_template("university/marketplace.html", challenges=challenges, categories=categories)


@university_bp.route("/collaboration-requests")
@role_required(*UNI_ROLES)
def collaboration_requests():
    university = _current_university()
    requests = IndustryCollaborationRequest.query.filter_by(university_id=university.id).order_by(
        IndustryCollaborationRequest.created_at.desc()).all() if university else []
    projects = Project.query.filter_by(university_id=university.id).order_by(
        Project.created_at.desc()).all() if university else []
    return render_template("university/collaboration_requests.html", requests=requests, projects=projects)


@university_bp.route("/collaboration-requests/<int:request_id>/review", methods=["POST"])
@role_required(*UNI_ROLES)
def review_collaboration(request_id):
    collaboration_request = IndustryCollaborationRequest.query.get_or_404(request_id)
    university = _current_university()
    if not university or collaboration_request.university_id != university.id:
        flash("You do not have access to this collaboration request.", "danger")
        return redirect(url_for("university.collaboration_requests"))
    decision = request.form.get("decision")
    previous = collaboration_request.status
    collaboration_request.reviewed_by_id = get_current_user().id
    collaboration_request.review_note = request.form.get("review_note")
    if decision == "approve":
        project = db.session.get(Project, request.form.get("project_id", type=int))
        if not project or project.university_id != university.id or project.challenge_id != collaboration_request.challenge_id:
            flash("Select a valid project for this challenge before approving.", "warning")
            return redirect(url_for("university.collaboration_requests"))
        collaboration_request.status = "ACTIVE"
        collaboration_request.project_id = project.id
        collaboration = IndustryCollaboration(
            request_id=collaboration_request.id, industry_id=collaboration_request.industry_id,
            project_id=project.id, approved_by_id=get_current_user().id,
            role=collaboration_request.support_types,
        )
        db.session.add(collaboration)
        for user in collaboration_request.industry.organization.users:
            notify(user, "Collaboration approved", f"Your proposal for {project.name} was approved by the university.",
                   link=f"/industry/projects")
        for team in project.teams:
            for member in team.members:
                if member.student.user:
                    notify(member.student.user, "Industry partner added",
                           f"{collaboration_request.industry.organization.name} is now supporting {project.name}.",
                           link=f"/dashboard/student/projects/{project.id}")
        message = "Collaboration approved and activated."
    elif decision == "reject":
        collaboration_request.status = "REJECTED"
        for user in collaboration_request.industry.organization.users:
            notify(user, "Collaboration request declined", f"Your proposal for {collaboration_request.challenge.title} was declined.",
                   link="/industry/")
        message = "Collaboration request rejected."
    else:
        collaboration_request.status = "UNDER_REVIEW"
        message = "Collaboration request moved to review."
    db.session.commit()
    log_action(get_current_user(), "COLLABORATION_REVIEW", "IndustryCollaborationRequest",
               collaboration_request.id, previous, collaboration_request.status,
               collaboration_request.review_note)
    flash(message, "success")
    return redirect(url_for("university.collaboration_requests"))


@university_bp.route("/challenges/<int:challenge_id>")
@role_required(*UNI_ROLES)
def challenge_detail(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    university = _current_university()
    existing_application = UniversityApplication.query.filter_by(
        challenge_id=challenge_id, university_id=university.id).first() if university else None
    recommendations = student_service.recommend_students_for_challenge(challenge, university) if university else []
    return render_template("university/challenge_detail.html", challenge=challenge,
                            existing_application=existing_application, recommendations=recommendations,
                            university=university)


@university_bp.route("/challenges/<int:challenge_id>/apply", methods=["POST"])
@role_required(*UNI_ROLES)
def apply_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    university = _current_university()
    user = get_current_user()
    if not university or challenge.status not in ("VERIFIED", "ASSIGNED"):
        flash("This challenge is not available for university applications.", "warning")
        return redirect(url_for("university.marketplace"))
    if challenge.assigned_university_id and challenge.assigned_university_id != university.id:
        flash("This challenge is already assigned to another university.", "warning")
        return redirect(url_for("university.marketplace"))
    existing = UniversityApplication.query.filter_by(
        challenge_id=challenge.id, university_id=university.id).first()
    if existing:
        flash("Your university has already applied to this challenge.", "info")
        return redirect(url_for("university.challenge_detail", challenge_id=challenge_id))
    application = UniversityApplication(challenge_id=challenge.id, university_id=university.id,
                                          applied_by_id=user.id, pitch=request.form.get("pitch"))
    application.status = "ACCEPTED"
    challenge.assigned_university_id = university.id
    challenge.status = "ASSIGNED"
    db.session.add(application)
    db.session.commit()
    for recipient in university.organization.users:
        notify(recipient, "Challenge accepted", f"Your university accepted '{challenge.title}'. Create a project to begin team formation.",
               link=url_for("university.create_project", challenge_id=challenge.id))
    log_action(user, "CHALLENGE_ACCEPT", "Challenge", challenge.id, "VERIFIED", "ASSIGNED")
    flash("Application submitted for this challenge.", "success")
    return redirect(url_for("university.challenge_detail", challenge_id=challenge_id))


@university_bp.route("/projects")
@role_required(*UNI_ROLES)
def projects():
    university = _current_university()
    project_list = Project.query.filter_by(university_id=university.id).order_by(
        Project.created_at.desc()).all() if university else []
    return render_template("university/projects.html", projects=project_list)


@university_bp.route("/challenges/<int:challenge_id>/create-project", methods=["GET", "POST"])
@role_required("UNIVERSITY_ADMIN")
def create_project(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    university = _current_university()
    if not university or challenge.assigned_university_id != university.id:
        flash("This challenge is not assigned to your university.", "danger")
        return redirect(url_for("university.marketplace"))
    faculty_list = Faculty.query.filter_by(university_id=university.id).all()

    if request.method == "POST":
        f = request.form
        faculty = Faculty.query.get(f.get("faculty_mentor_id")) if f.get("faculty_mentor_id") else None
        data = {
            "name": f["name"], "objective": f.get("objective"), "description": f.get("description"),
            "expected_outcome": f.get("expected_outcome"),
            "start_date": datetime.strptime(f["start_date"], "%Y-%m-%d").date() if f.get("start_date") else None,
            "expected_completion": datetime.strptime(f["expected_completion"], "%Y-%m-%d").date()
                                    if f.get("expected_completion") else None,
        }
        project = project_service.create_project(challenge, university, faculty, data)
        flash("Project created. Now build your team.", "success")
        return redirect(url_for("university.project_workspace", project_id=project.id, tab="team"))

    return render_template("university/create_project.html", challenge=challenge, faculty_list=faculty_list)


@university_bp.route("/projects/<int:project_id>")
@role_required(*UNI_ROLES)
def project_workspace(project_id):
    project = Project.query.get_or_404(project_id)
    university = _current_university()
    if not university or project.university_id != university.id:
        flash("You do not have access to this project.", "danger")
        return redirect(url_for("university.overview"))
    tab = request.args.get("tab", "overview")
    recommendations = student_service.recommend_students_for_challenge(project.challenge, university)
    return render_template("university/project_workspace.html", project=project, tab=tab,
                           recommendations=recommendations)


@university_bp.route("/projects/<int:project_id>/team", methods=["POST"])
@role_required("UNIVERSITY_ADMIN")
def add_team(project_id):
    project = Project.query.get_or_404(project_id)
    university = _current_university()
    if not university or project.university_id != university.id:
        flash("You do not have access to this project.", "danger")
        return redirect(url_for("university.overview"))
    f = request.form
    names = f.getlist("member_name[]")
    emails = f.getlist("member_email[]")
    regnos = f.getlist("member_regno[]")
    roles = f.getlist("member_role[]")
    members = []
    for i in range(len(names)):
        if names[i].strip():
            members.append({"full_name": names[i], "college_email": emails[i],
                             "registration_number": regnos[i], "role_in_team": roles[i] or "Developer"})
    try:
        team, new_count = project_service.create_team(project, f.get("team_name", "Project Team"), members)
        generated = project_service.generate_ai_task_plan(project)
        flash(f"Team created with {len(members)} member(s) ({new_count} new invitation(s) sent). "
              f"AI assigned {len(generated)} starter task(s).", "success")
    except Exception as e:
        flash(f"Could not create team: {e}", "danger")
    return redirect(url_for("university.project_workspace", project_id=project_id, tab="team"))


@university_bp.route("/projects/<int:project_id>/recommended-team", methods=["POST"])
@role_required("UNIVERSITY_ADMIN", "FACULTY")
def approve_recommended_team(project_id):
    project = Project.query.get_or_404(project_id)
    university = _current_university()
    if not university or project.university_id != university.id:
        flash("You do not have access to this project.", "danger")
        return redirect(url_for("university.overview"))
    selected_ids = {value for value in request.form.getlist("student_ids") if value.isdigit()}
    if not selected_ids:
        flash("Select at least one recommended student.", "warning")
        return redirect(url_for("university.project_workspace", project_id=project_id, tab="team"))
    profiles = StudentProfile.query.filter(
        StudentProfile.id.in_([int(value) for value in selected_ids]),
        StudentProfile.institution_id == university.id,
    ).all()
    selected = [(profile, request.form.get(f"role_{profile.id}", "Developer"))
                for profile in profiles]
    project_service.create_team_from_profiles(project, request.form.get("team_name", f"{project.name} Team"), selected)
    generated = project_service.generate_ai_task_plan(project)
    flash(f"Recommended team approved and assigned. AI created {len(generated)} skill-matched task(s).", "success")
    return redirect(url_for("university.project_workspace", project_id=project_id, tab="tasks"))


@university_bp.route("/projects/<int:project_id>/tasks/generate", methods=["POST"])
@role_required(*UNI_ROLES)
def generate_tasks(project_id):
    project = Project.query.get_or_404(project_id)
    university = _current_university()
    if not university or project.university_id != university.id:
        flash("You do not have access to this project.", "danger")
        return redirect(url_for("university.overview"))
    generated = project_service.generate_ai_task_plan(project)
    flash(f"AI task plan ready: {len(generated)} task(s) assigned using team roles and skills.", "success")
    return redirect(url_for("university.project_workspace", project_id=project_id, tab="tasks"))


@university_bp.route("/tasks/<int:task_id>/approve", methods=["POST"])
@role_required(*UNI_ROLES)
def approve_task(task_id):
    task = Task.query.get_or_404(task_id)
    university = _current_university()
    if not university or task.project.university_id != university.id:
        flash("You do not have access to this task.", "danger")
        return redirect(url_for("university.overview"))
    project_service.approve_task(task, get_current_user())
    flash("AI task approved and activated for the assigned student.", "success")
    return redirect(url_for("university.project_workspace", project_id=task.project_id, tab="tasks"))


@university_bp.route("/projects/<int:project_id>/tasks", methods=["POST"])
@role_required(*UNI_ROLES)
def create_task(project_id):
    project = Project.query.get_or_404(project_id)
    university = _current_university()
    if not university or project.university_id != university.id:
        flash("You do not have access to this project.", "danger")
        return redirect(url_for("university.overview"))
    student_id = request.form.get("assigned_to_id", type=int)
    allowed_ids = {member.student_id for team in project.teams for member in team.members}
    if student_id and student_id not in allowed_ids:
        flash("Tasks can only be assigned to approved project team members.", "warning")
        return redirect(url_for("university.project_workspace", project_id=project_id, tab="tasks"))
    task = Task(project_id=project.id, milestone_id=request.form.get("milestone_id", type=int),
                title=request.form.get("title", "").strip(), description=request.form.get("description"),
                assigned_to_id=student_id, status="NOT_STARTED", due_date=datetime.strptime(request.form["due_date"], "%Y-%m-%d").date()
                if request.form.get("due_date") else None)
    if not task.title:
        flash("Task title is required.", "warning")
        return redirect(url_for("university.project_workspace", project_id=project_id, tab="tasks"))
    db.session.add(task)
    db.session.commit()
    if task.assigned_to and task.assigned_to.user:
        notify(task.assigned_to.user, "New project task", f"You were assigned '{task.title}' in {project.name}.",
               link=url_for("student.project_workspace", project_id=project.id, tab="tasks"))
    flash("Task created and assigned.", "success")
    return redirect(url_for("university.project_workspace", project_id=project_id, tab="tasks"))


@university_bp.route("/milestones/<int:milestone_id>/update", methods=["POST"])
@role_required(*UNI_ROLES)
def update_milestone(milestone_id):
    milestone = Milestone.query.get_or_404(milestone_id)
    university = _current_university()
    if not university or milestone.project.university_id != university.id:
        flash("You do not have access to this milestone.", "danger")
        return redirect(url_for("university.overview"))
    new_status = request.form.get("status")
    comment = request.form.get("comment")
    project_service.update_milestone_status(milestone, new_status, comment=comment, actor=get_current_user())
    flash("Milestone updated.", "success")
    return redirect(url_for("university.project_workspace", project_id=milestone.project_id, tab="milestones"))


@university_bp.route("/tasks/<int:task_id>/review", methods=["POST"])
@role_required(*UNI_ROLES)
def review_task(task_id):
    task = Task.query.get_or_404(task_id)
    university = _current_university()
    if not university or task.project.university_id != university.id:
        flash("You do not have access to this task.", "danger")
        return redirect(url_for("university.overview"))
    try:
        scores = {key: max(0, min(5, int(request.form.get(key, 0))))
                  for key in ("quality", "relevance", "completeness", "evidence")}
    except ValueError:
        flash("Review scores must be between 0 and 5.", "warning")
        return redirect(url_for("university.project_workspace", project_id=task.project_id, tab="tasks"))
    decision = request.form.get("decision")
    if decision not in ("APPROVED", "CHANGES_REQUESTED"):
        flash("Choose an approval decision.", "warning")
    else:
        project_service.review_task(task, get_current_user(), scores,
                                    request.form.get("remarks", "").strip(), decision)
        flash("Task review saved and the student was notified.", "success")
    return redirect(url_for("university.project_workspace", project_id=task.project_id, tab="tasks"))


@university_bp.route("/students")
@role_required(*UNI_ROLES)
def students():
    university = _current_university()
    student_list = StudentProfile.query.filter_by(institution_id=university.id).all() if university else []
    return render_template("university/students.html", students=student_list)


@university_bp.route("/faculty")
@role_required(*UNI_ROLES)
def faculty():
    university = _current_university()
    faculty_list = Faculty.query.filter_by(university_id=university.id).all() if university else []
    return render_template("university/faculty.html", faculty_list=faculty_list)


@university_bp.route("/analytics")
@role_required(*UNI_ROLES)
def analytics():
    university = _current_university()
    projects = Project.query.filter_by(university_id=university.id).all() if university else []
    return render_template("university/analytics.html", projects=projects)
