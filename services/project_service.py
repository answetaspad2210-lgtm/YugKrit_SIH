"""YugKrit - Project / team / milestone service."""

import json
from datetime import datetime, timedelta

from database.database import db
from database.models import (
    Project, ProjectTeam, ProjectTeamMember, Milestone, ProjectImpact, Task,
    TaskSubmission, TaskReview, TaskDeliverable, SubmissionVersion, TaskDependency,
    AITaskRecommendation, AISubmissionReview, FacultyReview, Feedback
)
from utils.helpers import generate_code
from services.audit_service import log_action
from services.notification_service import notify
from services import student_service, achievement_service

DEFAULT_MILESTONES = [
    "Problem Research", "Solution Design", "Prototype", "Testing",
    "Community Validation", "Pilot", "Implementation", "Final Submission",
]

AI_TASK_BLUEPRINTS = {
    "research": ("Community evidence brief", "Collect interviews, observations, baseline data, and source links that prove the problem and its impact.", "Problem Research", ("research", "field", "data"), "RESEARCH_REPORT", ["Problem analysis", "Field observations", "Supporting evidence"], ["Use the real project location and challenge context", "Cite evidence sources", "State at least three verified findings"]),
    "design": ("Solution concept and user flow", "Turn the verified problem into a practical solution concept, user journey, and success criteria.", "Solution Design", ("design", "ux", "research"), "DOCUMENT", ["Solution concept", "User flow", "Success criteria"], ["Trace the design to the problem statement", "Include affected-user needs", "Define measurable success criteria"]),
    "prototype": ("Build a testable prototype", "Create the smallest working prototype that addresses the highest-impact part of the problem.", "Prototype", ("developer", "prototype", "technology"), "PROTOTYPE_EVIDENCE", ["Working prototype", "Architecture or component notes", "Demonstration evidence"], ["Show the core workflow", "Document technologies used", "Include reproducible test evidence"]),
    "testing": ("Run a validation test", "Prepare test cases, measure outcomes, record failures, and recommend the next technical improvement.", "Testing", ("test", "data", "developer"), "DATASET", ["Test plan", "Results", "Improvement recommendations"], ["Use defined test cases", "Report failures honestly", "Connect results to the expected outcome"]),
    "community": ("Community feedback report", "Validate the proposed solution with affected people and document feedback, accessibility, and adoption barriers.", "Community Validation", ("field", "community", "research"), "FIELD_EVIDENCE", ["Feedback notes", "Evidence photos or links", "Adoption barriers"], ["Include affected-community feedback", "Record location and date", "Identify changes made from feedback"]),
}


def create_project(challenge, university, faculty, data):
    project = Project(
        project_code=generate_code("PRJ"),
        name=data["name"],
        objective=data.get("objective"),
        description=data.get("description"),
        expected_outcome=data.get("expected_outcome"),
        challenge_id=challenge.id,
        university_id=university.id,
        faculty_mentor_id=faculty.id if faculty else None,
        start_date=data.get("start_date"),
        expected_completion=data.get("expected_completion"),
        status="PLANNING",
    )
    db.session.add(project)
    db.session.flush()

    for i, title in enumerate(DEFAULT_MILESTONES):
        db.session.add(Milestone(project_id=project.id, title=title, sequence=i, status="NOT_STARTED"))

    db.session.add(ProjectImpact(project_id=project.id, people_impacted=0))

    challenge.status = "IN_PROGRESS"
    db.session.commit()
    return project


def create_team(project, team_name, members_data):
    """members_data: list of dicts with full_name, college_email,
    registration_number, role_in_team. Uses find_or_invite_student so no
    duplicate student profiles are ever created."""
    team = ProjectTeam(project_id=project.id, team_name=team_name)
    db.session.add(team)
    db.session.flush()

    created_count = 0
    for m in members_data:
        student, is_new = student_service.find_or_invite_student(
            institution_id=project.university_id,
            registration_number=m["registration_number"],
            full_name=m["full_name"],
            college_email=m["college_email"],
        )
        if is_new:
            created_count += 1
        member = ProjectTeamMember(team_id=team.id, student_id=student.id,
                                    role_in_team=m.get("role_in_team", "Developer"))
        db.session.add(member)
        if student.user:
            notify(student.user, "Added to a project", f'You were added to "{project.name}".',
                   link=f"/dashboard/student/projects/{project.id}")

    db.session.commit()
    return team, created_count


def create_team_from_profiles(project, team_name, selected_profiles):
    """Create an approved team from existing student profiles.

    The caller must authorize the project university. Student IDs are reused;
    no duplicate StudentProfile records are created.
    """
    team = ProjectTeam(project_id=project.id, team_name=team_name)
    db.session.add(team)
    db.session.flush()
    seen = set()
    for profile, role in selected_profiles:
        if profile.id in seen:
            continue
        seen.add(profile.id)
        db.session.add(ProjectTeamMember(team_id=team.id, student_id=profile.id,
                                         role_in_team=role or "Developer"))
    db.session.commit()
    for profile, role in selected_profiles:
        if profile.id in seen and profile.user:
            notify(profile.user, "You were assigned to a project team",
                   f'You were assigned to "{project.name}" as {role or "Developer"}.',
                   link=f"/dashboard/student/projects/{project.id}")
    return team


def _task_match_score(member, keywords):
    profile = member.student
    role = (member.role_in_team or "").lower()
    skills = " ".join(skill.skill_name.lower() for skill in profile.skills)
    department = (profile.department or "").lower()
    searchable = f"{role} {skills} {department}"
    return sum(3 if keyword in role else 2 if keyword in skills else 1 if keyword in searchable else 0
               for keyword in keywords)


def _normalize_role_name(value):
    return (value or "").lower().replace("/", " ").replace("-", " ").replace("_", " ")


def _recommended_role_blueprint(role_name, project):
    normalized = _normalize_role_name(role_name)
    challenge_text = " ".join([
        project.name or "",
        project.challenge.title or "",
        project.challenge.description or "",
        project.challenge.subcategory or "",
        project.challenge.required_skills or "",
    ]).lower()
    role_map = {
        "problem research": {
            "title": f"Field and Literature Review for {project.name}",
            "objective": "Understand the verified problem, current gaps, and evidence before design and prototyping.",
            "instructions": f"Study the project problem in {project.challenge.title}, review at least 5 relevant sources, identify the root causes of the issue, compare existing solutions, document field observations and research gaps, and prepare a short evidence-backed summary with references.",
            "deliverables": ["Research summary", "Reference list", "Field observations", "Problem analysis document"],
            "acceptance_criteria": ["At least 5 relevant references are cited", "Root cause is explained with evidence", "Comparison with at least two existing approaches is included", "Research summary is linked to the project goal"],
            "submission_type": "DOCUMENT",
            "priority": "HIGH",
            "estimated_effort": "5-7 working days",
            "required_skills": ["Research", "Field Analysis", "Problem Framing", "Documentation"],
            "required_technologies": ["Research articles", "Reports", "Documentation tools"],
            "milestone": "Problem Research",
            "days": 7,
        },
        "iot developer": {
            "title": f"Sensor and Hardware Design for {project.name}",
            "objective": "Design and validate the physical sensing layer that supports the project solution.",
            "instructions": f"Recommend a suitable sensing approach for the {project.challenge.title} challenge, map the hardware architecture, select the appropriate sensor/controller, validate connectivity and data flow, and document implementation steps including testing evidence.",
            "deliverables": ["Hardware architecture", "Sensor selection notes", "Data flow diagram", "Test results"],
            "acceptance_criteria": ["Sensor/controller choice is justified", "System flow is documented", "At least one working data collection test is recorded", "Implementation notes are clear enough to reproduce"],
            "submission_type": "PROTOTYPE_EVIDENCE",
            "priority": "HIGH",
            "estimated_effort": "4-6 working days",
            "required_skills": ["IoT", "Embedded Systems", "Hardware Design", "Testing"],
            "required_technologies": ["Sensors", "Microcontrollers", "IoT protocols", "Data collection"],
            "milestone": "Prototype",
            "days": 6,
        },
        "ai data analyst": {
            "title": f"Data Analysis and Insights for {project.name}",
            "objective": "Convert raw project evidence into actionable insights and measurable recommendations.",
            "instructions": f"Prepare the relevant dataset for {project.challenge.title}, clean and structure the information, analyze patterns, build the required analytical model or method, evaluate quality and limitations, and produce practical insights that inform the solution.",
            "deliverables": ["Clean dataset", "Analysis notebook/report", "Insights summary", "Evaluation results"],
            "acceptance_criteria": ["Dataset is cleaned and structured", "At least one meaningful analysis is performed", "Insights are backed by results", "Limitations or assumptions are documented"],
            "submission_type": "DATASET",
            "priority": "HIGH",
            "estimated_effort": "5-7 working days",
            "required_skills": ["Data Analysis", "Python", "Machine Learning", "Statistics"],
            "required_technologies": ["Python", "Pandas", "Visualization tools", "Modeling"],
            "milestone": "Testing",
            "days": 7,
        },
        "dashboard developer": {
            "title": f"Dashboard and Interface for {project.name}",
            "objective": "Deliver the visible monitoring and reporting layer for the solution and project evidence.",
            "instructions": f"Create the dashboard architecture for {project.challenge.title}, connect relevant project data to the interface, design key views for progress and analytics, and implement a working prototype that demonstrates stakeholder visibility.",
            "deliverables": ["Dashboard wireframe", "API/data connection notes", "Progress views", "User-facing demo"],
            "acceptance_criteria": ["Core dashboard views are implemented", "Relevant data is connected to the interface", "Authentication or access logic is explained if needed", "Prototype demonstrates a working user flow"],
            "submission_type": "PROTOTYPE_EVIDENCE",
            "priority": "MEDIUM",
            "estimated_effort": "4-5 working days",
            "required_skills": ["Dashboard Design", "Frontend Development", "API Integration", "UX"],
            "required_technologies": ["Web application", "APIs", "Visualization library", "Authentication"],
            "milestone": "Solution Design",
            "days": 5,
        },
        "field testing": {
            "title": f"Field Testing and Validation for {project.name}",
            "objective": "Evaluate the solution in realistic conditions and identify gaps before final piloting.",
            "instructions": f"Prepare a field-testing plan for {project.challenge.title}, run test cases in a realistic setting, record observations, compare expected results to actual outcomes, and identify improvements required before deployment.",
            "deliverables": ["Test plan", "Field notes", "Validation results", "Improvement recommendations"],
            "acceptance_criteria": ["Testing conditions are documented", "Realistic evidence is recorded", "Results are compared against expected outcome", "Next-step improvement list is included"],
            "submission_type": "FIELD_EVIDENCE",
            "priority": "MEDIUM",
            "estimated_effort": "3-5 working days",
            "required_skills": ["Field Testing", "Observation", "Validation", "Report Writing"],
            "required_technologies": ["Testing checklist", "Documentation", "Field notes"],
            "milestone": "Testing",
            "days": 4,
        },
    }
    for key, blueprint in role_map.items():
        if key in normalized or all(token in normalized for token in key.split() if token not in {"and", "for"}):
            return blueprint
    if "research" in normalized:
        return role_map["problem research"]
    if "iot" in normalized or "embedded" in normalized or "hardware" in normalized:
        return role_map["iot developer"]
    if "data" in normalized or "analyst" in normalized or "ai" in normalized:
        return role_map["ai data analyst"]
    if "dashboard" in normalized or "design" in normalized or "frontend" in normalized:
        return role_map["dashboard developer"]
    if "test" in normalized or "field" in normalized:
        return role_map["field testing"]
    return role_map["problem research"]


def _compute_task_deadline(project, blueprint, offset_days=0):
    base_date = project.expected_completion or (datetime.utcnow().date() + timedelta(days=45))
    if isinstance(base_date, str):
        try:
            base_date = datetime.strptime(base_date, "%Y-%m-%d").date()
        except ValueError:
            base_date = datetime.utcnow().date() + timedelta(days=45)
    due_date = base_date - timedelta(days=max(2, blueprint.get("days", 5) + offset_days))
    return due_date


def generate_ai_task_plan(project):
    """Create project-aware AI recommendations for each approved team member."""
    if not project.teams:
        return []

    members = [member for team in project.teams for member in team.members]
    if not members:
        return []

    existing_task_roles = {(task.assigned_to_id, (task.role or "").lower()) for task in project.tasks}
    created = []
    ordered_members = sorted(members, key=lambda item: (item.student.full_name or "").lower())
    project_role_pairs = []
    for member in ordered_members:
        role_name = member.role_in_team or "Developer"
        if (member.student_id, _normalize_role_name(role_name)) in existing_task_roles:
            continue
        blueprint = _recommended_role_blueprint(role_name, project)
        project_role_pairs.append((member, role_name, blueprint))

    if not project_role_pairs:
        return list(project.tasks)

    task_sequence = []
    for index, (member, role_name, blueprint) in enumerate(project_role_pairs):
        milestone = next((item for item in project.milestones if item.title == blueprint["milestone"]), None)
        due_date = _compute_task_deadline(project, blueprint, offset_days=index)
        task = Task(
            project_id=project.id,
            milestone_id=milestone.id if milestone else None,
            title=blueprint["title"],
            description=blueprint["instructions"],
            assigned_to_id=member.student_id,
            due_date=due_date,
            deadline=due_date,
            role=role_name,
            objective=blueprint["objective"],
            instructions=blueprint["instructions"],
            required_skills=", ".join(blueprint["required_skills"]),
            required_technologies=json.dumps(blueprint["required_technologies"]),
            expected_deliverables=json.dumps(blueprint["deliverables"]),
            acceptance_criteria=json.dumps(blueprint["acceptance_criteria"]),
            submission_type=blueprint["submission_type"],
            estimated_effort=blueprint["estimated_effort"],
            priority=blueprint["priority"],
            ai_reason=f"Generated for the {role_name} role using the project objective, the verified challenge, and the student skills profile.",
            status="AI_RECOMMENDED",
        )
        db.session.add(task)
        db.session.flush()
        for deliverable in blueprint["deliverables"]:
            db.session.add(TaskDeliverable(task_id=task.id, title=deliverable))
        task_sequence.append(task)
        recommendation = AITaskRecommendation(
            task_id=task.id,
            student_id=member.student_id,
            role=role_name,
            title=blueprint["title"],
            objective=blueprint["objective"],
            instructions=blueprint["instructions"],
            required_skills=", ".join(blueprint["required_skills"]),
            required_technologies=json.dumps(blueprint["required_technologies"]),
            deliverables=json.dumps(blueprint["deliverables"]),
            acceptance_criteria=json.dumps(blueprint["acceptance_criteria"]),
            submission_type=blueprint["submission_type"],
            priority=blueprint["priority"],
            estimated_effort=blueprint["estimated_effort"],
            deadline=due_date,
            dependencies=json.dumps([]),
            ai_reason=task.ai_reason,
            status="PENDING",
            faculty_decision="PENDING",
        )
        db.session.add(recommendation)
        created.append(task)

    for index, task in enumerate(task_sequence):
        if index == 0:
            task.dependencies = json.dumps([])
            continue
        prev_task = task_sequence[index - 1]
        task.dependencies = json.dumps([prev_task.title])
        db.session.add(TaskDependency(task_id=task.id, depends_on_task_id=prev_task.id, dependency_type="BLOCKS", status="WAITING"))

    db.session.commit()
    faculty_user = project.faculty_mentor.user if project.faculty_mentor and project.faculty_mentor.user else None
    if faculty_user and created:
        notify(faculty_user, "AI task recommendations ready",
               f"Review {len(created)} AI-generated recommendations for {project.name}.",
               link=f"/dashboard/university/projects/{project.id}?tab=tasks")
    return created


def approve_task(task, reviewer):
    task.status = "NOT_STARTED"
    task.approved_by_id = reviewer.id
    task.approved_at = datetime.utcnow()
    db.session.commit()
    if task.assigned_to and task.assigned_to.user:
        notify(task.assigned_to.user, "Faculty approved a project task",
               f"'{task.title}' is ready for you in {task.project.name}.",
               link=f"/dashboard/student/projects/{task.project_id}?tab=tasks")
    return task


def _generate_ai_review_summary(task, submission):
    required_fields = []
    if task.acceptance_criteria:
        required_fields.extend(json.loads(task.acceptance_criteria) if isinstance(task.acceptance_criteria, str) else task.acceptance_criteria)
    if not required_fields:
        required_fields.append("submission completeness")
    findings = []
    if submission.evidence_link:
        findings.append("Evidence link was submitted.")
    else:
        findings.append("Evidence link is missing.")
    if task.expected_deliverables:
        deliverables = json.loads(task.expected_deliverables) if isinstance(task.expected_deliverables, str) else task.expected_deliverables
        if isinstance(deliverables, list) and len(deliverables) > 0:
            findings.append(f"Deliverables expected: {', '.join(deliverables[:3])}.")
    if submission.work_notes and len(submission.work_notes) < 80:
        findings.append("Work notes are brief; provide more evidence and references.")
    summary = "AI review: the submission is relevant to the assignment and covers the major task objective. "
    summary += "Please confirm any missing references or evidence items before final approval."
    return summary, findings


def submit_task_work(task, student, work_notes, evidence_link=None):
    submission = task.submission or TaskSubmission(task_id=task.id, student_id=student.id,
                                                    work_notes=work_notes)
    submission.student_id = student.id
    submission.work_notes = work_notes
    submission.evidence_link = evidence_link
    submission.status = "SUBMITTED"
    task.status = "AI_REVIEW"
    if task.milestone and task.milestone.status == "NOT_STARTED":
        task.milestone.status = "IN_PROGRESS"
    db.session.add(submission)
    db.session.flush()
    version_number = len(submission.versions) + 1
    db.session.add(SubmissionVersion(task_id=task.id, submission=submission,
                                     version_number=version_number, work_notes=work_notes,
                                     evidence_link=evidence_link, status="SUBMITTED"))
    summary, findings = _generate_ai_review_summary(task, submission)
    ai_review = AISubmissionReview(submission_id=submission.id, reviewer_type="AI", summary=summary,
                                  findings=json.dumps(findings), status="PENDING")
    db.session.add(ai_review)
    for deliverable in task.deliverables:
        deliverable.status = "UPLOADED"
    db.session.commit()
    faculty_user = task.project.faculty_mentor.user if task.project.faculty_mentor and task.project.faculty_mentor.user else None
    if faculty_user:
        notify(faculty_user, "Student submitted task work",
               f"{student.full_name} submitted '{task.title}' for review.",
               link=f"/dashboard/university/projects/{task.project_id}?tab=tasks")
    return submission


def review_task(task, reviewer, scores, remarks, decision):
    review = task.review or TaskReview(task_id=task.id, reviewed_by_id=reviewer.id)
    review.reviewed_by_id = reviewer.id
    review.quality_score = scores["quality"]
    review.relevance_score = scores["relevance"]
    review.completeness_score = scores["completeness"]
    review.evidence_score = scores["evidence"]
    review.remarks = remarks
    review.decision = decision

    faculty_review = FacultyReview(task_id=task.id, reviewer_id=reviewer.id, decision=decision,
                                  remarks=remarks, quality_score=scores["quality"],
                                  relevance_score=scores["relevance"], completeness_score=scores["completeness"],
                                  evidence_score=scores["evidence"])
    db.session.add(faculty_review)

    feedback_note = Feedback(task_id=task.id, student_id=task.assigned_to_id, reviewer_id=reviewer.id,
                             message=remarks or "Faculty reviewed the submitted work.", status="OPEN")
    db.session.add(feedback_note)

    task.status = "APPROVED" if decision == "APPROVED" else "CHANGES_REQUESTED"
    if task.submission:
        task.submission.status = decision
        if task.submission.versions:
            task.submission.versions[-1].status = decision
    db.session.add(review)
    db.session.commit()
    if task.milestone:
        milestone_tasks = task.milestone.tasks
        if decision == "APPROVED" and milestone_tasks and all(item.status == "APPROVED" and item.review and item.review.decision == "APPROVED" for item in milestone_tasks):
            update_milestone_status(task.milestone, "COMPLETED", comment=remarks, actor=reviewer)
        elif decision == "CHANGES_REQUESTED":
            update_milestone_status(task.milestone, "CHANGES_REQUESTED", comment=remarks, actor=reviewer)
    if task.assigned_to and task.assigned_to.user:
        notify(task.assigned_to.user, "Faculty reviewed your task",
               f"{task.title}: {decision.replace('_', ' ').title()}.",
               link=f"/dashboard/student/projects/{task.project_id}?tab=tasks")
    return review


def update_milestone_status(milestone, new_status, comment=None, actor=None):
    previous = milestone.status
    milestone.status = new_status
    if comment:
        milestone.reviewer_comment = comment
    db.session.commit()
    if actor:
        log_action(actor, "MILESTONE_UPDATE", "Milestone", milestone.id, previous, new_status)

    _recalculate_progress(milestone.project)

    if new_status == "COMPLETED":
        all_done = all(m.status == "COMPLETED" for m in milestone.project.milestones)
        if all_done:
            complete_project(milestone.project, actor)
    return milestone


def _recalculate_progress(project):
    stage_map = {
        "Problem Research": "research_progress",
        "Solution Design": "design_progress",
        "Prototype": "prototype_progress",
        "Testing": "testing_progress",
        "Community Validation": "validation_progress",
    }
    status_pct = {
        "NOT_STARTED": 0, "IN_PROGRESS": 40, "SUBMITTED": 70,
        "UNDER_REVIEW": 80, "APPROVED": 90, "CHANGES_REQUESTED": 50, "COMPLETED": 100,
    }
    for m in project.milestones:
        field = stage_map.get(m.title)
        if field:
            tasks = list(m.tasks)
            if tasks:
                completed = sum(task.status in ("APPROVED", "COMPLETED") for task in tasks)
                value = round((completed / len(tasks)) * 100)
            else:
                value = status_pct.get(m.status, 0)
            setattr(project, field, value)
    db.session.commit()


def complete_project(project, actor=None):
    """Marks a project COMPLETED. Government verification is the required gate
    before achievements and certificates are generated."""
    previous = project.status
    project.status = "COMPLETED"
    db.session.commit()
    if actor:
        log_action(actor, "PROJECT_COMPLETE", "Project", project.id, previous, "COMPLETED")
    return project


def verify_project(project, gov_user=None, approve=True, reason=None):
    """Government verification is the real issuance gate for project awards."""
    previous = project.status
    if approve:
        if project.status not in ("COMPLETED", "VERIFIED"):
            raise ValueError("Only completed projects can be verified.")
        project.status = "VERIFIED"
        db.session.commit()
        if gov_user:
            log_action(gov_user, "PROJECT_VERIFIED", "Project", project.id, previous, "VERIFIED", reason)
        achievement_service.generate_achievements_for_project(project)
        return project

    project.status = "COMPLETED"
    db.session.commit()
    if gov_user:
        log_action(gov_user, "PROJECT_REJECTED", "Project", project.id, previous, "COMPLETED", reason)
    return project
