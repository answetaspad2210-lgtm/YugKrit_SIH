"""YugKrit - Challenge lifecycle service."""

import json
from datetime import datetime

from database.database import db
from database.models import (
    Challenge, ChallengeLocation, ChallengeCategory, ChallengeAssignment,
    AIAnalysis, University, Organization
)
from utils.helpers import generate_code
from services import ai_service
from services.audit_service import log_action
from services.notification_service import notify


def create_challenge(submitter, data, submitter_type="ORG"):
    """`submitter` is an Organization when submitter_type='ORG' (ULB/NGO), or
    a CitizenProfile when submitter_type='CITIZEN'."""
    category = ChallengeCategory.query.filter_by(name=data.get("category")).first()
    if not category:
        category = ChallengeCategory(name=data.get("category") or "General")
        db.session.add(category)
        db.session.flush()

    challenge = Challenge(
        challenge_code=generate_code("YK"),
        title=data["title"],
        description=data.get("description"),
        category_id=category.id,
        subcategory=data.get("subcategory"),
        submitted_by_org_id=submitter.id if submitter_type == "ORG" else None,
        submitted_by_citizen_id=submitter.id if submitter_type == "CITIZEN" else None,
        affected_population=int(data.get("affected_population") or 0),
        urgency=data.get("urgency", "MEDIUM"),
        current_situation=data.get("current_situation"),
        supporting_info=data.get("supporting_info"),
        status="SUBMITTED",
    )
    db.session.add(challenge)
    db.session.flush()

    location = ChallengeLocation(
        challenge_id=challenge.id,
        address=data.get("address"),
        district=data.get("district"),
        state=data.get("state"),
        latitude=float(data["latitude"]) if data.get("latitude") else None,
        longitude=float(data["longitude"]) if data.get("longitude") else None,
    )
    db.session.add(location)
    db.session.commit()

    run_ai_analysis(challenge)
    return challenge


def run_ai_analysis(challenge):
    result = ai_service.analyze_challenge(challenge)
    analysis = challenge.ai_analysis or AIAnalysis(challenge_id=challenge.id)
    analysis.suggested_category = result["suggested_category"]
    analysis.category_candidates = json.dumps(result.get("category_candidates", []))
    analysis.secondary_categories = json.dumps(result.get("secondary_categories", []))
    analysis.subcategory = result.get("subcategory")
    analysis.domains = json.dumps(result.get("domains", []))
    analysis.affected_users = json.dumps(result.get("affected_users", []))
    analysis.root_causes = json.dumps(result.get("root_causes", []))
    analysis.matched_evidence = json.dumps(result.get("matched_evidence", []))
    analysis.priority_score = result["priority_score"]
    analysis.suggested_skills = result["suggested_skills"]
    analysis.required_technologies = json.dumps(result.get("required_technologies", []))
    analysis.solution_areas = json.dumps(result.get("solution_areas", []))
    analysis.complexity = result.get("complexity")
    analysis.recommended_departments = json.dumps(result.get("recommended_departments", []))
    analysis.industry_capabilities = json.dumps(result.get("industry_capabilities", []))
    analysis.recommended_roles = json.dumps(result.get("recommended_roles", []))
    analysis.explanation = result.get("explanation")
    analysis.confidence_score = result.get("confidence_score", 0.0)
    analysis.source = result.get("source", "rule-based-engine")
    analysis.university_matches = result["university_matches"]
    analysis.similar_challenge_ids = result["similar_challenge_ids"]
    analysis.human_review_required = result["human_review_required"]
    challenge.priority_score = result["priority_score"]
    challenge.required_skills = result["suggested_skills"]
    db.session.add(analysis)
    db.session.commit()
    return analysis


def correct_challenge_category(challenge, gov_user, category_id, reason):
    category = db.session.get(ChallengeCategory, int(category_id))
    if not category:
        raise ValueError("The selected category does not exist.")
    if not reason or not reason.strip():
        raise ValueError("A correction reason is required.")
    previous = challenge.category.name if challenge.category else None
    challenge.category_id = category.id
    analysis = challenge.ai_analysis or AIAnalysis(challenge_id=challenge.id)
    analysis.corrected_category_id = category.id
    analysis.corrected_by_id = gov_user.id
    analysis.overridden_by_id = gov_user.id
    analysis.corrected_at = datetime.utcnow()
    analysis.correction_reason = reason.strip()
    db.session.add(analysis)
    db.session.commit()
    log_action(gov_user, "AI_CATEGORY_CORRECTION", "Challenge", challenge.id,
               previous, category.name, reason.strip())
    return challenge


def verify_challenge(challenge, gov_user, approve=True, reason=None):
    run_ai_analysis(challenge)
    previous = challenge.status
    challenge.status = "VERIFIED" if approve else "REJECTED"
    db.session.commit()
    log_action(gov_user, "CHALLENGE_VERIFY" if approve else "CHALLENGE_REJECT",
               "Challenge", challenge.id, previous, challenge.status, reason)
    if challenge.submitted_by_org:
        for user in challenge.submitted_by_org.users:
            notify(user, "Challenge review completed",
                   f'Your challenge "{challenge.title}" was {"verified" if approve else "rejected"}.',
                   link=f"/dashboard/ulb/challenges/{challenge.id}")
    if challenge.submitted_by_citizen and challenge.submitted_by_citizen.user:
        notify(challenge.submitted_by_citizen.user, "Problem review completed",
               f'Your problem "{challenge.title}" was {"verified" if approve else "rejected"}.',
               link=f"/dashboard/citizen/problems/{challenge.id}")
    return challenge


def assign_challenge(challenge, gov_user, university_id=None, problem_owner_org_id=None):
    if problem_owner_org_id:
        challenge.problem_owner_org_id = problem_owner_org_id
        db.session.add(ChallengeAssignment(challenge_id=challenge.id, assigned_to_type="PROBLEM_OWNER",
                                            assigned_to_org_id=problem_owner_org_id, assigned_by_id=gov_user.id))
    if university_id:
        challenge.assigned_university_id = university_id
        challenge.status = "ASSIGNED"
        db.session.add(ChallengeAssignment(challenge_id=challenge.id, assigned_to_type="UNIVERSITY",
                                            assigned_to_org_id=None, assigned_by_id=gov_user.id))
        uni = db.session.get(University, university_id)
        if uni:
            for u in uni.organization.users:
                notify(u, "Government-verified problem assigned",
                       f'"{challenge.title}" has been assigned to your university for student solution development.',
                       link=f"/dashboard/university/challenges/{challenge.id}")
    db.session.commit()
    log_action(gov_user, "CHALLENGE_ASSIGN", "Challenge", challenge.id, None,
               f"university_id={university_id}, problem_owner_org_id={problem_owner_org_id}")
    if challenge.submitted_by_org:
        for user in challenge.submitted_by_org.users:
            notify(user, "Challenge assigned", f'"{challenge.title}" has been assigned for solution development.',
                   link=f"/dashboard/ulb/challenges/{challenge.id}")
    return challenge
