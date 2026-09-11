"""Phase 1 AI problem-analysis regression tests."""

from services.ai_service import analyze_text


def test_irrigation_problem_gets_relevant_ranked_analysis():
    result = analyze_text(
        "Farm irrigation water wastage",
        "Farmers are wasting water because irrigation is manually controlled.",
        "Rural district; soil moisture sensors could improve scheduling.",
    )
    assert result["suggested_category"] == "Agriculture & Food Technology"
    assert "Water Quality & Conservation" in result["secondary_categories"]
    assert result["subcategory"] == "smart irrigation"
    assert result["confidence_score"] > 0.5
    assert result["category_candidates"][0]["evidence"]
    assert "irrigation" in result["explanation"]


def test_required_examples_do_not_fall_back_to_generic_category():
    examples = [
        ("Rural digital learning", "Students in rural schools do not have access to digital learning resources.", "Education Technology"),
        ("Residential waste", "Garbage is not being separated in residential areas.", "Climate & Sustainability"),
        ("Village healthcare", "Village residents cannot easily access basic healthcare.", "Health Technology"),
        ("Intersection congestion", "Traffic congestion is severe near a city intersection.", "Mobility & Safety Technology"),
        ("Village flooding", "Repeated flooding damages village roads and drainage.", "Disaster Resilience Technology"),
    ]
    for title, description, expected in examples:
        result = analyze_text(title, description)
        assert result["suggested_category"] == expected
        assert result["suggested_category"] != "General Societal Challenge"
        assert result["explanation"]


def test_unknown_problem_requires_human_review_with_low_confidence():
    result = analyze_text("A local concern", "People need help with an unclear issue.")
    assert result["suggested_category"] == "General Innovation Challenge"
    assert result["confidence_score"] < 0.5
    assert "Human review" in result["explanation"]
