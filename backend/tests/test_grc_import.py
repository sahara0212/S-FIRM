from fastapi.testclient import TestClient

from app.main import app

# 시드 레퍼런스 고객사·세션
CLIENT_ID = "2c3c2685-63ff-48a6-a0d4-58e507d1485d"
SESSION_ID = "0290acaa-133d-4f32-a473-0fcecb3d4bc3"
URL = f"/api/v1/clients/{CLIENT_ID}/sessions/{SESSION_ID}/grc-import"

client = TestClient(app)


def rule(**overrides):
    base = {
        "rule_code": "RULE-AI-001",
        "name": "AI 거버넌스 체계와 경영진 역할 분담",
        "description": "경영진의 AI 개발·활용 역할과 책임을 분담한다.",
        "trigger_condition": "AI 도입·변경 건이 GRC-01에 해당하는 경우",
        "actions": ["AI 거버넌스 규정 작성·보관"],
        "exceptions": [],
        "system_guide": "해당 없음",
        "priority": "HIGH",
        "classification": "사규필수반영",
        "law_name": "금융분야 AI 가이드라인",
        "grc_control_id": "GOV-01",
        "first_duty": "CEO",
        "second_duty": None,
        "third_duty": None,
    }
    base.update(overrides)
    return base


def rules_by_code():
    items = client.get(f"/api/v1/clients/{CLIENT_ID}/sessions/{SESSION_ID}/rules").json()["items"]
    return {item["rule_code"]: item for item in items}


def test_import_creates_draft_rules_with_duty_chain():
    response = client.post(
        URL,
        json={
            "standard_version": "0.1.0",
            "assessment_title": "상담 추천 AI",
            "rules": [rule(), rule(rule_code="RULE-AI-002", grc_control_id="SEC-01", first_duty="CISO", second_duty="CRO", third_duty="CEO")],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "success", "created": 2, "updated": 0, "total": 2}

    imported = rules_by_code()
    sec = imported["RULE-AI-002"]
    assert sec["status"] == "draft"
    assert sec["prohibition"]["article"] == "SEC-01"
    assert sec["duty"] == {"first_duty": "CISO", "second_duty": "CRO", "third_duty": "CEO"}


def test_reimport_updates_existing_rule_version():
    client.post(URL, json={"standard_version": "0.1.0", "rules": [rule(rule_code="RULE-AI-010")]})
    again = client.post(URL, json={"standard_version": "0.1.1", "rules": [rule(rule_code="RULE-AI-010", name="변경된 규칙명")]})
    assert again.json()["updated"] == 1 and again.json()["created"] == 0
    item = rules_by_code()["RULE-AI-010"]
    assert item["name"] == "변경된 규칙명"
    assert item["version"] == 2


def test_import_rejects_unknown_duty_and_session():
    bad_duty = client.post(URL, json={"standard_version": "0.1.0", "rules": [rule(rule_code="RULE-AI-020", first_duty="NOPE")]})
    assert bad_duty.status_code == 422
    wrong_session = client.post(
        f"/api/v1/clients/{CLIENT_ID}/sessions/unknown/grc-import",
        json={"standard_version": "0.1.0", "rules": [rule()]},
    )
    assert wrong_session.status_code == 404
