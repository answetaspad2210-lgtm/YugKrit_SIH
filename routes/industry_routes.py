"""Industry / organization collaboration portal."""

import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import or_

from database.database import db
from database.database import CHALLENGE_CATEGORIES, STUDENT_SOLVABLE_SUBCATEGORIES
from database.models import (
    Challenge, IndustryProfile, IndustryMentor, IndustryCollaborationRequest,
    IndustryCollaboration, IndustryFunding, IndustryResourceOffer, Project,
    University, PilotProject, User, Role,
    ChallengeCategory, ChallengeEvidence,
)
from services import challenge_service
from services.audit_service import log_action
from services.notification_service import notify
from utils.helpers import save_uploaded_file
from utils.decorators import role_required, get_current_user

industry_bp = Blueprint("industry", __name__, template_folder="../templates/industry")

INDUSTRY_ROLES = ("INDUSTRY",)
ORGANIZATION_TYPES = ("Industry", "Startup", "MSME", "CSR Organization", "Research Institution",
                      "Innovation Hub", "Technology Provider", "Other")
SECTOR_SUBSECTORS = {
    "Information Technology": ("Software Development", "Cloud Computing", "Cybersecurity", "Web Development", "Mobile Applications", "Data Engineering", "IT Services", "Enterprise Software", "SaaS"),
    "Artificial Intelligence": ("Machine Learning", "Natural Language Processing", "Computer Vision", "Generative AI", "Predictive Analytics"),
    "Electronics": ("Embedded Systems", "PCB Design", "Sensors", "Consumer Electronics", "Industrial Electronics"),
    "Electrical": ("Power Systems", "Electrical Design", "Smart Grid", "Control Systems", "Energy Storage"),
    "Mechanical": ("Manufacturing", "Machine Design", "Automation", "CAD/CAM", "Industrial Equipment", "Robotics", "Thermal Engineering", "Production Engineering"),
    "Civil & Infrastructure": ("Structural Engineering", "Urban Infrastructure", "Water Infrastructure", "Construction Technology", "Geotechnical Engineering"),
    "Aerospace": ("Aerospace Engineering", "Unmanned Aerial Systems", "Avionics", "Propulsion", "Satellite Systems"),
    "Automotive": ("Electric Vehicles", "Vehicle Systems", "Autonomous Vehicles", "Automotive Manufacturing", "Mobility Services"),
    "Manufacturing": ("Industrial Automation", "Lean Manufacturing", "Quality Engineering", "Supply Chain", "Factory Digitization"),
    "Agriculture Technology": ("Precision Agriculture", "Smart Irrigation", "Agricultural IoT", "Farm Automation", "Crop Monitoring", "Soil Monitoring", "Agri Supply Chain", "Agricultural Drones"),
    "Healthcare Technology": ("Medical Devices", "Health Informatics", "Telemedicine", "Diagnostics", "Medical AI", "Digital Health", "Biomedical Engineering"),
    "Biotechnology": ("Bioinformatics", "Bioprocessing", "Medical Biotechnology", "Agricultural Biotechnology"),
    "Renewable Energy": ("Solar Energy", "Wind Energy", "Biomass", "Energy Storage", "Microgrids"),
    "Energy": ("Power Generation", "Energy Efficiency", "Grid Management", "Energy Storage", "Utilities"),
    "Water Management": ("Water Quality", "Water Treatment", "Smart Water Networks", "Irrigation", "Groundwater Management"),
    "Waste Management": ("Recycling", "Waste Processing", "Composting", "Waste-to-Energy", "Circular Economy"),
    "Environmental Technology": ("Pollution Control", "Climate Technology", "Environmental Monitoring", "Conservation", "Carbon Management"),
    "Construction": ("Project Management", "Building Technology", "Construction Materials", "Safety Systems", "Infrastructure Delivery"),
    "Transportation": ("Public Transport", "Traffic Management", "Logistics", "Intelligent Transport", "Last-mile Mobility"),
    "Telecommunications": ("Network Infrastructure", "5G", "Broadband", "Satellite Communication", "Network Security"),
    "Robotics": ("Industrial Robotics", "Service Robotics", "Autonomous Systems", "Robotic Vision", "Human-Robot Collaboration"),
    "IoT": ("Industrial IoT", "Smart Cities", "Connected Devices", "IoT Platforms", "Remote Monitoring"),
    "FinTech": ("Digital Payments", "Financial Inclusion", "InsurTech", "RegTech", "Lending Technology"),
    "EdTech": ("Digital Learning", "Learning Analytics", "Education Platforms", "Assistive Learning"),
    "Food Technology": ("Food Processing", "Food Safety", "Cold Chain", "Agri Food Systems"),
    "Defence Technology": ("Security Systems", "Surveillance", "Defence Electronics", "Unmanned Systems"),
    "Rural Development": ("Rural Livelihoods", "Community Infrastructure", "Digital Inclusion", "Rural Health", "Rural Education"),
    "Smart City Technology": ("Urban Mobility", "Smart Utilities", "Public Safety", "Urban Analytics", "Civic Technology"),
    "Other": ("Other",),
}
SECTORS = tuple(SECTOR_SUBSECTORS)
CAPABILITY_OPTIONS = {
    "expertise": ("Product Development", "Engineering Design", "Research & Development", "Artificial Intelligence", "Machine Learning", "Data Analytics", "Software Development", "Hardware Development", "Embedded Systems", "IoT", "Robotics", "Automation", "Manufacturing", "Civil Infrastructure", "Environmental Engineering", "Renewable Energy", "Healthcare Technology", "Agricultural Technology", "Project Management", "Business Development", "Supply Chain", "Testing & Quality", "Field Implementation", "Community Development", "Innovation & R&D"),
    "technologies": ("Artificial Intelligence", "Machine Learning", "Computer Vision", "Data Analytics", "Cloud Computing", "IoT", "Sensors", "Embedded Systems", "Robotics", "Automation", "GIS", "GPS", "Blockchain", "Mobile Development", "Web Development", "CAD/CAM", "3D Printing", "Drones", "Digital Twins", "Renewable Energy Systems", "Smart Grid", "Remote Sensing", "Cybersecurity", "Big Data", "Edge Computing"),
    "services": ("Technical Mentoring", "Research Collaboration", "Product Development", "Prototype Development", "Testing", "Manufacturing", "Software Development", "Hardware Development", "Engineering Consultation", "Design Support", "Data Support", "Laboratory Access", "Field Testing", "Pilot Implementation", "Technology Transfer", "Training", "Internship", "Employment Opportunities", "Project Management", "Deployment Support", "Maintenance Support"),
    "csr_focus_areas": ("Education", "Healthcare", "Rural Development", "Women Empowerment", "Skill Development", "Agriculture", "Water & Sanitation", "Environment", "Renewable Energy", "Disaster Management", "Accessibility", "Digital Inclusion", "Livelihood", "Community Infrastructure", "Public Safety", "Child Development", "Elderly Welfare", "Tribal Development", "Poverty Reduction", "Sustainable Development"),
    "available_resources": ("Technical Experts", "Industry Mentors", "Engineers", "Software Developers", "Hardware", "Sensors", "Laboratory", "Testing Facility", "Manufacturing Facility", "Prototyping Facility", "3D Printing", "Cloud Resources", "Computing Resources", "Software Licenses", "Data Resources", "Research Facilities", "Funding", "CSR Funding", "Field Deployment Support", "Pilot Sites", "Equipment", "Training Facilities", "Internship Opportunities"),
}
SUPPORT_TYPES = ("Technical Mentorship", "Funding", "CSR Support", "Hardware", "Software",
                 "Prototype Development", "Testing", "Data/Technology", "Pilot Implementation",
                 "Internship", "Employment", "Technology Transfer")


def _industry():
    user = get_current_user()
    return IndustryProfile.query.filter_by(organization_id=user.organization_id).first() if user else None


def _tags(value):
    if not value:
        return set()
    try:
        values = json.loads(value) if value.strip().startswith("[") else value.replace(";", ",").split(",")
    except (TypeError, json.JSONDecodeError):
        values = value.replace(";", ",").split(",")
    return {str(tag).strip().lower() for tag in values if str(tag).strip()}


def _json_tags(form, field):
    selected = list(dict.fromkeys(form.getlist(field)))
    if len(selected) == 1 and "," in selected[0]:
        selected = [value.strip() for value in selected[0].split(",") if value.strip()]
    invalid = set(selected) - set(CAPABILITY_OPTIONS[field])
    if invalid:
        raise ValueError(f"Invalid {field.replace('_', ' ')} selection.")
    return json.dumps(selected)


def _recommendation(challenge, profile):
    profile_sector = _tags(profile.sector)
    profile_subsector = _tags(profile.sub_sector)
    expertise = _tags(profile.expertise)
    technologies = _tags(profile.technologies)
    csr = _tags(profile.csr_focus_areas)
    challenge_category = _tags(challenge.category.name if challenge.category else "")
    challenge_subcategory = _tags(challenge.subcategory)
    required_skills = _tags(challenge.required_skills)
    technical_matches = (expertise | technologies) & required_skills
    category_match = bool(profile_sector & challenge_category or csr & challenge_category)
    subcategory_match = bool(profile_subsector & challenge_subcategory)
    technology_match = bool(technologies & required_skills)
    location_match = bool(challenge.location and profile.organization.state and
                          challenge.location.state and
                          challenge.location.state.lower() == profile.organization.state.lower())
    breakdown = {
        "category": 20 if category_match else 0,
        "subsector": 15 if subcategory_match else 0,
        "technical_skills": min(25, len(technical_matches) * 8),
        "technology": 20 if technology_match else 0,
        "expertise": min(10, len(expertise & required_skills) * 5),
        "location": 5 if location_match else 0,
        "impact": 5 if csr & challenge_category else 0,
    }
    score = min(100, sum(breakdown.values()))
    reasons = []
    if technical_matches:
        reasons.append(f"matches {', '.join(sorted(technical_matches))}")
    if category_match:
        reasons.append("matches the challenge domain")
    if location_match:
        reasons.append("is in your organization's state")
    if not reasons:
        reasons.append("is eligible to review this verified challenge")
    return score, "Recommended because the organization " + " and ".join(reasons) + ".", breakdown


@industry_bp.route("/register", methods=["GET", "POST"])
def register():
    from services import auth_service, otp_service
    from routes.auth_routes import _start_signup_verification
    from utils.validators import validate_passwords_match, validate_phone_required, ValidationError
    from database.models import Organization

    if request.method == "POST":
        f = request.form
        try:
            validate_passwords_match(f.get("password", ""), f.get("confirm_password", ""))
            phone = validate_phone_required(f.get("phone", ""))
            if f.get("organization_type") not in ORGANIZATION_TYPES or f.get("sector") not in SECTORS:
                raise ValidationError("Select a valid organization type and industry sector.", code="INVALID_PROFILE")
            if f.get("sub_sector") not in SECTOR_SUBSECTORS[f.get("sector")]:
                raise ValidationError("Select a valid sub-sector for the chosen sector.", code="INVALID_PROFILE")
            organization = Organization(
                name=f["organization_name"], org_type="INDUSTRY", official_email=f["official_email"],
                phone=phone, website=f.get("website"), address=f.get("location"),
                district=f.get("district"), state=f.get("state"), status="PENDING",
            )
            db.session.add(organization)
            db.session.flush()
            profile = IndustryProfile(
                organization_id=organization.id, organization_type=f["organization_type"],
                sector=f["sector"], sub_sector=f.get("sub_sector"), organization_size=f.get("organization_size"),
                description=f.get("description"), expertise=_json_tags(f, "expertise"),
                technologies=_json_tags(f, "technologies"), services=_json_tags(f, "services"),
                csr_focus_areas=_json_tags(f, "csr_focus_areas"), available_resources=_json_tags(f, "available_resources"),
                contact_person=f["contact_person"],
            )
            db.session.add(profile)
            db.session.commit()
            user = auth_service.create_user(f["contact_person"], f["official_email"], f["password"],
                                            "INDUSTRY", organization_id=organization.id, phone=phone)
            return _start_signup_verification(user)
        except (ValidationError, KeyError) as exc:
            db.session.rollback()
            flash(getattr(exc, "message", "Please complete all required fields."), "danger")
        except Exception:
            db.session.rollback()
            flash("Registration failed. Please check the form and try again.", "danger")
    return render_template("industry/register.html", organization_types=ORGANIZATION_TYPES, sectors=SECTORS,
                           sector_subsectors=SECTOR_SUBSECTORS, capability_options=CAPABILITY_OPTIONS)


@industry_bp.route("/login")
def login():
    return redirect(url_for("auth.login", next=url_for("industry.dashboard")))


@industry_bp.route("/")
@industry_bp.route("/dashboard")
@role_required(*INDUSTRY_ROLES)
def dashboard():
    profile = _industry()
    requests = IndustryCollaborationRequest.query.filter_by(industry_id=profile.id).order_by(
        IndustryCollaborationRequest.created_at.desc()).all() if profile else []
    collaborations = IndustryCollaboration.query.filter_by(industry_id=profile.id).order_by(
        IndustryCollaboration.created_at.desc()).all() if profile else []
    recommendations = _recommended_challenges(profile, 6) if profile else []
    submitted_challenges = Challenge.query.filter_by(submitted_by_org_id=profile.organization_id).count() if profile else 0
    stats = {
        "submitted_challenges": submitted_challenges,
        "relevant_challenges": len(recommendations),
        "active_collaborations": len([c for c in collaborations if c.status == "ACTIVE"]),
        "pending_requests": len([r for r in requests if r.status in ("REQUESTED", "UNDER_REVIEW")]),
        "active_mentorships": len([c for c in collaborations if c.status == "ACTIVE" and "mentorship" in c.role.lower()]),
        "funded_projects": IndustryFunding.query.filter_by(industry_id=profile.id, status="RELEASED").count() if profile else 0,
        "pilot_projects": PilotProject.query.filter_by(industry_id=profile.id).count() if profile else 0,
        "completed_collaborations": len([c for c in collaborations if c.status == "COMPLETED"]),
    }
    return render_template("industry/dashboard.html", profile=profile, stats=stats,
                           recommendations=recommendations, requests=requests[:8], collaborations=collaborations)


@industry_bp.route("/submit-challenge", methods=["GET", "POST"])
@role_required(*INDUSTRY_ROLES)
def submit_challenge():
    profile = _industry()
    if not profile:
        flash("Complete your organization profile before submitting a challenge.", "warning")
        return redirect(url_for("industry.profile"))
    if request.method == "POST":
        form = request.form
        try:
            category = form.get("category")
            subcategory = form.get("subcategory", "").strip()
            if category not in CHALLENGE_CATEGORIES:
                raise ValueError("Select a valid challenge category.")
            if subcategory not in STUDENT_SOLVABLE_SUBCATEGORIES.get(category, []):
                raise ValueError("Choose a student-solvable innovation subcategory.")
            challenge = challenge_service.create_challenge(profile.organization, {
                "title": form["title"].strip(), "description": form.get("description", "").strip(),
                "category": category, "subcategory": subcategory,
                "affected_population": form.get("affected_population", 0),
                "urgency": form.get("urgency", "MEDIUM"),
                "current_situation": form.get("current_situation"),
                "supporting_info": form.get("expected_outcome"),
                "address": form.get("location"), "district": form.get("district"), "state": form.get("state"),
                "latitude": form.get("latitude"), "longitude": form.get("longitude"),
            })
            for uploaded in request.files.getlist("evidence"):
                if uploaded and uploaded.filename:
                    name, path, _ = save_uploaded_file(uploaded, subfolder="challenges")
                    extension = name.rsplit(".", 1)[-1].lower() if name else ""
                    evidence_type = "PHOTO" if extension in ("jpg", "jpeg", "png") else "VIDEO" if extension == "mp4" else "DOCUMENT"
                    db.session.add(ChallengeEvidence(challenge_id=challenge.id, evidence_type=evidence_type,
                                                      file_name=name, file_path=path))
            db.session.commit()
            government_users = User.query.join(User.role).filter(
                Role.name.in_(("GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "GOVT_IT_CELL_ADMIN")),
                User.is_active.is_(True),
            ).all()
            for government_user in government_users:
                notify(government_user, "New industry challenge submitted",
                       f"{profile.organization.name} submitted '{challenge.title}' for verification.",
                       link=f"/dashboard/government/challenges/{challenge.id}")
            flash("Challenge submitted for Government and IT Cell verification.", "success")
            return redirect(url_for("industry.dashboard"))
        except (KeyError, ValueError) as exc:
            db.session.rollback()
            flash(str(exc) or "Complete the required challenge fields.", "danger")
    return render_template("industry/submit_challenge.html", categories=CHALLENGE_CATEGORIES,
                           subcategories=STUDENT_SOLVABLE_SUBCATEGORIES)


def _recommended_challenges(profile, limit=None):
    challenges = Challenge.query.filter(Challenge.status.in_(["VERIFIED", "ASSIGNED", "IN_PROGRESS"])).all()
    values = []
    for challenge in challenges:
        score, reason, breakdown = _recommendation(challenge, profile)
        values.append({"challenge": challenge, "score": score, "reason": reason, "breakdown": breakdown})
    values.sort(key=lambda item: (item["score"], item["challenge"].priority_score), reverse=True)
    return values[:limit] if limit else values


@industry_bp.route("/challenges")
@role_required(*INDUSTRY_ROLES)
def recommendations():
    profile = _industry()
    return render_template("industry/challenges.html", profile=profile,
                           recommendations=_recommended_challenges(profile) if profile else [])


@industry_bp.route("/projects")
@role_required(*INDUSTRY_ROLES)
def projects():
    profile = _industry()
    project_list = Project.query.join(IndustryCollaboration).filter(
        IndustryCollaboration.industry_id == profile.id).all() if profile else []
    return render_template("industry/projects.html", projects=project_list)


@industry_bp.route("/challenges/<int:challenge_id>/collaborate", methods=["GET", "POST"])
@role_required(*INDUSTRY_ROLES)
def collaborate(challenge_id):
    profile = _industry()
    challenge = Challenge.query.get_or_404(challenge_id)
    project_id = request.args.get("project_id", type=int) or request.form.get("project_id", type=int)
    project = db.session.get(Project, project_id) if project_id else None
    if request.method == "POST":
        support_types = request.form.getlist("support_types")
        if not support_types or not request.form.get("description", "").strip():
            flash("Select at least one support type and describe your proposal.", "warning")
            return render_template("industry/collaborate.html", challenge=challenge, project=project,
                                   support_types=SUPPORT_TYPES)
        if IndustryCollaborationRequest.query.filter_by(industry_id=profile.id, challenge_id=challenge.id,
                                                        project_id=project_id).filter(
                                                            IndustryCollaborationRequest.status.in_(["REQUESTED", "UNDER_REVIEW", "APPROVED", "ACTIVE"])
                                                        ).first():
            flash("A collaboration proposal already exists for this problem.", "info")
            return redirect(url_for("industry.dashboard"))
        proposal = IndustryCollaborationRequest(
            industry_id=profile.id, challenge_id=challenge.id, project_id=project_id,
            university_id=project.university_id if project else challenge.assigned_university_id,
            proposal_type=request.form.get("proposal_type", "Industry collaboration"),
            support_types=", ".join(support_types), description=request.form["description"],
            estimated_contribution=request.form.get("estimated_contribution"),
            expected_duration=request.form.get("expected_duration"), experts=request.form.get("experts"),
            budget=request.form.get("budget") or None,
        )
        db.session.add(proposal)
        db.session.commit()
        if proposal.university:
            for user in proposal.university.organization.users:
                notify(user, "Industry collaboration request", f"{profile.organization.name} proposed support for {challenge.title}.",
                       link=f"/dashboard/university/collaboration-requests/{proposal.id}")
        log_action(get_current_user(), "COLLABORATION_REQUEST", "IndustryCollaborationRequest", proposal.id,
                   None, "REQUESTED")
        flash("Collaboration proposal submitted for university review.", "success")
        return redirect(url_for("industry.dashboard"))
    return render_template("industry/collaborate.html", challenge=challenge, project=project,
                           support_types=SUPPORT_TYPES)


@industry_bp.route("/profile", methods=["GET", "POST"])
@role_required(*INDUSTRY_ROLES)
def profile():
    industry = _industry()
    if request.method == "POST":
        f = request.form
        industry.sub_sector = f.get("sub_sector")
        for field in CAPABILITY_OPTIONS:
            setattr(industry, field, _json_tags(f, field))
        industry.description = f.get("description")
        db.session.commit()
        flash("Organization capability profile updated.", "success")
        return redirect(url_for("industry.profile"))
    return render_template("industry/profile.html", industry=industry, capability_options=CAPABILITY_OPTIONS,
                           sector_subsectors=SECTOR_SUBSECTORS)


@industry_bp.route("/mentors", methods=["GET", "POST"])
@role_required(*INDUSTRY_ROLES)
def mentors():
    industry = _industry()
    if request.method == "POST":
        mentor = IndustryMentor(industry_id=industry.id, name=request.form["name"],
                                designation=request.form.get("designation"), expertise=request.form.get("expertise"),
                                experience=request.form.get("experience"), skills=request.form.get("skills"),
                                contact=request.form.get("contact"))
        db.session.add(mentor)
        db.session.commit()
        log_action(get_current_user(), "INDUSTRY_MENTOR_ADDED", "IndustryMentor", mentor.id, None, "ACTIVE")
        flash("Industry mentor added.", "success")
        return redirect(url_for("industry.mentors"))
    return render_template("industry/mentors.html", industry=industry)


@industry_bp.route("/funding", methods=["GET", "POST"])
@role_required(*INDUSTRY_ROLES)
def funding():
    industry = _industry()
    projects = Project.query.join(IndustryCollaboration).filter(IndustryCollaboration.industry_id == industry.id).all()
    if request.method == "POST":
        proposal = IndustryFunding(industry_id=industry.id, project_id=int(request.form["project_id"]),
                                   amount=request.form.get("amount") or None, purpose=request.form["purpose"],
                                   expected_outcome=request.form.get("expected_outcome"),
                                   duration=request.form.get("duration"), terms=request.form.get("terms"))
        db.session.add(proposal)
        db.session.commit()
        flash("Funding proposal submitted for review.", "success")
        return redirect(url_for("industry.funding"))
    proposals = IndustryFunding.query.filter_by(industry_id=industry.id).order_by(IndustryFunding.created_at.desc()).all()
    return render_template("industry/funding.html", projects=projects, proposals=proposals)
