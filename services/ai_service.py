"""
YugKrit - AI Service.

If AI_API_KEY is configured in the environment, this module could be
extended to call an external LLM. For the first working version we use a
transparent, rule-based "mock AI" engine so the platform works out of the
box with no external dependency. Every recommendation is clearly labeled
and government/university users can always override it.
"""

import json
import os
from database.models import Challenge, University

CATEGORY_PROFILES = {
    "Agriculture & Food Technology": {"phrases": ("farm", "farmer", "crop", "irrigation", "soil", "agriculture", "livestock"), "subcategory": ("smart irrigation", "crop monitoring", "soil health", "precision agriculture"), "skills": ("Agricultural Engineering", "IoT", "Data Analytics"), "technologies": ("Soil Moisture Sensors", "IoT", "Remote Sensing"), "departments": ("Agricultural Engineering", "Computer Science", "Electronics")},
    "Water Quality & Conservation": {"phrases": ("water", "drinking water", "leak", "groundwater", "rainwater", "wastewater", "drainage"), "subcategory": ("water quality", "water leakage", "water conservation", "groundwater monitoring"), "skills": ("Environmental Engineering", "Civil Engineering", "IoT"), "technologies": ("Water Quality Sensors", "IoT", "Data Analytics"), "departments": ("Civil Engineering", "Environmental Engineering", "Computer Science")},
    "Climate & Sustainability": {"phrases": ("climate", "waste", "garbage", "recycling", "compost", "pollution", "carbon", "air quality"), "subcategory": ("waste segregation", "recycling", "air-quality monitoring", "carbon reduction"), "skills": ("Environmental Science", "Data Analytics", "Product Design"), "technologies": ("Sensors", "GIS", "Data Analytics"), "departments": ("Environmental Engineering", "Computer Science", "Mechanical Engineering")},
    "Health Technology": {"phrases": ("health", "healthcare", "medicine", "clinic", "diagnostic", "telemedicine", "patient"), "subcategory": ("rural healthcare", "telemedicine", "diagnostics", "health monitoring"), "skills": ("Public Health", "Data Analytics", "Software Development"), "technologies": ("Mobile App", "Cloud", "Data Analytics"), "departments": ("Computer Science", "Biomedical Engineering", "Public Health")},
    "Education Technology": {"phrases": ("school", "student", "teacher", "learning", "education", "classroom", "digital learning"), "subcategory": ("digital learning", "student engagement", "assessment", "teacher support"), "skills": ("EdTech", "UX Design", "Software Development"), "technologies": ("Web Application", "Mobile App", "Analytics"), "departments": ("Computer Science", "Education", "Information Technology")},
    "Mobility & Safety Technology": {"phrases": ("traffic", "congestion", "transport", "road safety", "parking", "pedestrian", "mobility"), "subcategory": ("traffic management", "public transport", "road safety", "mobility access"), "skills": ("GIS", "Data Analytics", "IoT"), "technologies": ("GPS", "Sensors", "GIS"), "departments": ("Civil Engineering", "Computer Science", "Electronics")},
    "Disaster Resilience Technology": {"phrases": ("flood", "flooding", "disaster", "earthquake", "heatwave", "early warning", "emergency"), "subcategory": ("flood early warning", "emergency resource mapping", "resilient infrastructure data"), "skills": ("Civil Engineering", "GIS", "Data Analytics"), "technologies": ("GIS", "Sensors", "Early Warning Systems"), "departments": ("Civil Engineering", "Computer Science", "Geography")},
    "Digital Public Services": {"phrases": ("online service", "digital service", "document", "citizen access", "government portal"), "subcategory": ("service discovery", "document workflow", "multilingual interfaces"), "skills": ("Software Development", "UX Design", "Product Management"), "technologies": ("Web Application", "Cloud", "NLP"), "departments": ("Computer Science", "Information Technology", "Design")},
    "Clean Energy & Energy Access": {"phrases": ("solar", "energy", "electricity", "power", "battery", "renewable", "clean cooking"), "subcategory": ("solar performance monitoring", "energy efficiency", "battery and storage"), "skills": ("Electrical Engineering", "IoT", "Data Analytics"), "technologies": ("Sensors", "IoT", "Renewable Energy Systems"), "departments": ("Electrical Engineering", "Electronics", "Computer Science")},
    "Accessibility & Assistive Technology": {"phrases": ("disability", "accessible", "assistive", "blind", "wheelchair", "inclusive"), "subcategory": ("accessible navigation", "assistive communication", "inclusive design"), "skills": ("Accessibility Design", "UX Design", "Software Development"), "technologies": ("Mobile App", "Computer Vision", "Assistive Devices"), "departments": ("Computer Science", "Design", "Biomedical Engineering")},
}

KEYWORD_CATEGORY_MAP = {phrase: category for category, profile in CATEGORY_PROFILES.items() for phrase in profile["phrases"]}

KEYWORD_SKILL_MAP = {
    "irrigation": ["IoT", "Embedded Systems", "Data Analysis", "Environmental Science"],
    "farm": ["Agricultural Technology", "IoT", "Data Analysis", "Embedded Systems"],
    "crop": ["Agricultural Technology", "Remote Sensing", "Data Analysis"],
    "sensor": ["IoT", "Embedded Systems", "Data Analysis"],
    "iot": ["IoT", "Embedded Systems", "Cloud Computing", "Data Analysis"],
    "water": ["Civil Engineering", "Environmental Science", "IoT"],
    "park": ["Civil Engineering", "IoT", "GIS"],
    "waste": ["Environmental Science", "Mechanical Engineering", "Data Analysis"],
    "traffic": ["IoT", "Data Analysis", "GIS"],
    "health": ["Public Health", "Data Analysis", "Mobile App Development"],
    "school": ["EdTech", "UI/UX Design", "Web Development"],
    "power": ["Electrical Engineering", "IoT", "Renewable Energy"],
    "safety": ["IoT", "Mobile App Development", "Data Analysis"],
}

AI_ENABLED_EXTERNALLY = bool(os.environ.get("AI_API_KEY"))


def categorize_challenge(title, description):
    return analyze_text(title, description)["suggested_category"]


def calculate_priority(affected_population, urgency):
    urgency_weight = {"LOW": 20, "MEDIUM": 45, "HIGH": 70, "CRITICAL": 90}.get(urgency, 45)
    population_weight = min(affected_population / 100, 30) if affected_population else 0
    score = int(min(urgency_weight + population_weight, 100))
    return max(score, 1)


def recommend_skills(title, description):
    return analyze_text(title, description)["required_skills"]


def analyze_text(title, description, extra_text=""):
    text = f"{title} {description} {extra_text}".lower()
    ranked = []
    for category, profile in CATEGORY_PROFILES.items():
        evidence = [phrase for phrase in profile["phrases"] if phrase in text]
        if evidence:
            score = sum(3 if len(item.split()) > 1 else 2 for item in evidence)
            ranked.append((score, category, evidence, profile))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    if not ranked:
        return {"suggested_category": "General Innovation Challenge", "category_candidates": [{"category": "General Innovation Challenge", "confidence": 0.25, "evidence": []}], "confidence_score": 0.25, "subcategory": "Prototype and pilot", "required_skills": ["Research", "Data Analysis"], "required_technologies": ["Data Collection Tools"], "recommended_departments": ["Computer Science", "Project Management"], "explanation": "The submitted description does not contain enough domain-specific evidence for a stronger category recommendation. Human review is required.", "secondary_categories": []}
    total = sum(item[0] for item in ranked)
    candidates = [{"category": category, "confidence": round(min(0.98, score / max(total, 1) + 0.35), 2), "evidence": evidence} for score, category, evidence, _ in ranked[:3]]
    primary = ranked[0]
    profile = primary[3]
    subcategory = next((value for value in profile["subcategory"] if value in text), profile["subcategory"][0])
    return {"suggested_category": primary[1], "category_candidates": candidates, "confidence_score": candidates[0]["confidence"], "subcategory": subcategory, "required_skills": list(profile["skills"]), "required_technologies": list(profile["technologies"]), "recommended_departments": list(profile["departments"]), "secondary_categories": [item[1] for item in ranked[1:3]], "explanation": f"The analysis matched {', '.join(primary[2])} in the submitted problem context, indicating {primary[1]} as the strongest domain.", "matched_evidence": primary[2]}


def find_similar_challenges(title, description, exclude_id=None, limit=5):
    text_words = set(f"{title} {description}".lower().split())
    candidates = Challenge.query.filter(Challenge.id != exclude_id).all() if exclude_id else Challenge.query.all()
    scored = []
    for c in candidates:
        c_words = set(f"{c.title} {c.description or ''}".lower().split())
        overlap = len(text_words.intersection(c_words))
        if overlap > 1:
            scored.append((overlap, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]


def recommend_universities(required_skills, district=None, limit=3):
    """Rule-based scoring: departments matching required skills score higher."""
    universities = University.query.join(University.organization).filter_by(status="VERIFIED").all()
    scored = []
    for uni in universities:
        dept_names = " ".join([d.name.lower() for d in uni.departments]) if uni.departments else ""
        score = 60  # base score
        for skill in required_skills:
            if skill.lower().split()[0] in dept_names:
                score += 10
        if district and uni.organization and uni.organization.district == district:
            score += 15
        score = min(score, 99)
        scored.append({"university_id": uni.id, "name": uni.organization.name, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def analyze_challenge(challenge):
    """Analyze all submitted challenge context with an explainable local engine."""
    location_text = " ".join(filter(None, [
        challenge.location.address if challenge.location else "",
        challenge.location.district if challenge.location else "",
        challenge.location.state if challenge.location else "",
    ]))
    context = " ".join(filter(None, [challenge.current_situation, challenge.supporting_info,
                                     challenge.subcategory, location_text]))
    semantic = analyze_text(challenge.title, challenge.description or "", context)
    category = semantic["suggested_category"]
    priority = calculate_priority(challenge.affected_population or 0, challenge.urgency)
    skills = semantic["required_skills"]
    district = challenge.location.district if challenge.location else None
    universities = recommend_universities(skills, district)
    similar = find_similar_challenges(challenge.title, challenge.description or "", exclude_id=challenge.id)
    affected_users = ["Residents and community members"]
    if any(word in context.lower() for word in ("student", "school", "teacher")):
        affected_users = ["Students", "Teachers", "Families"]
    elif any(word in context.lower() for word in ("farmer", "farm", "crop")):
        affected_users = ["Farmers", "Rural households", "Agricultural workers"]
    root_causes = [f"Signals found in submitted text: {', '.join(semantic.get('matched_evidence', [])) or 'insufficient evidence'}"]
    complexity = "HIGH" if len(context) > 500 or priority >= 80 else "MEDIUM" if len(context) > 180 else "LOW"

    return {
        "suggested_category": category,
        "secondary_categories": semantic.get("secondary_categories", []),
        "subcategory": semantic.get("subcategory"),
        "category_candidates": semantic.get("category_candidates", []),
        "domains": semantic["recommended_departments"],
        "affected_users": affected_users,
        "root_causes": root_causes,
        "priority_score": priority,
        "suggested_skills": ", ".join(skills),
        "required_skills": skills,
        "required_technologies": semantic["required_technologies"],
        "solution_areas": ["Research and evidence collection", "Prototype development", "Field validation"],
        "complexity": complexity,
        "recommended_departments": semantic["recommended_departments"],
        "industry_capabilities": ["Technical Mentoring", "Prototype Development", "Testing", "Data Support"],
        "recommended_roles": ["Problem Researcher", "Technical Builder", "Data Analyst", "Field Validator"],
        "explanation": semantic["explanation"],
        "confidence_score": semantic["confidence_score"],
        "university_matches": json.dumps(universities),
        "similar_challenge_ids": ",".join(str(c.id) for c in similar),
        "human_review_required": True,
        "source": "rule-based-semantic-engine",
    }
