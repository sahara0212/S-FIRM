"""
시드 금지행위·업무규칙의 근거 조문 교정.

- CORRECTIONS: 조문 번호·법령이 명백히 틀린 항목을 바로잡는다(세종 금융 AI GRC 기준 표준과 같은 근거).
- NEEDS_VERIFICATION: 근거 조문이 불확실한 항목. 추측으로 바꾸지 않고 '원문 확인 필요'로 표시한다.

앱 기동 시 시드 직후 apply_citation_corrections()가 새 DB·기존 DB 모두에 반영한다.
사용자가 이미 조문을 수정한 항목(원래 조문과 다른 항목)은 건드리지 않는다.
"""
from app.db.models import ProhibitedAct

VERIFY_MARKER = "[근거 조문 원문 확인 필요]"

CORRECTIONS: dict[str, dict] = {
    # 정보통신망법의 개인정보 조항은 2020.8 개인정보 보호법으로 이관
    "83a95e7f-a6d1-9705-d9ab-f13af218e46b": {
        "old_article": "제22조 제1항",
        "law_id": "pipa", "law_name": "개인정보보호법", "article": "제15조 제1항",
    },
    "0130b0b5-047a-f0bb-60c1-e77573f8297a": {
        "old_article": "17조 2항",
        "article": "제36조의2",
        "name": "자동화평가 결과 설명 요구 대응 미흡",
        "description": "개인인 신용정보주체가 자동화평가 결과·주요 기준·기초정보의 설명을 요구하거나 이의를 제기할 때 이에 대응하지 않는 행위",
        "rule_name": "자동화평가 결과 설명·이의제기 대응",
        "rule_description": "AI 등 자동화평가 결과에 대한 신용정보주체의 설명 요구·이의제기·재평가 요구에 대응하는 절차 운영",
    },
    "8ccdab6c-85a0-6156-feb0-3f85ec33e493": {
        "old_article": "제15조 제1항",
        "article": "제37조의2",
        "name": "자동화된 결정에 대한 거부·설명 요구 대응 미흡",
        "description": "완전히 자동화된 시스템으로 개인정보를 처리해 정보주체의 권리·의무에 중대한 영향을 미치는 결정을 하면서 거부·설명 요구에 대응하지 않는 행위",
        "rule_name": "자동화된 결정 거부·설명 요구 대응",
        "rule_description": "자동화된 결정의 기준·절차를 공개하고 정보주체의 거부·설명 요구 시 인적 개입 재처리 또는 설명을 제공",
        "actions": [
            "CPO: 자동화된 결정 대상 업무와 결정 기준·절차 목록화 및 공개",
            "CCO: 거부·설명 요구 처리 절차와 인적 개입 재처리 기준 승인",
            "CEO: 정책 시행 승인",
        ],
    },
    "e17a3eae-3623-0388-2989-f907ec3aff36": {
        "old_article": "제35조",
        "article": "제37조의2",
    },
    "a431f7e1-9ef9-f998-ea05-09c3c98e1303": {
        "old_article": "10조",
        "article": "제33조",
        "name": "고영향 인공지능 해당 여부 사전 검토 미실시",
        "description": "인공지능 제품·서비스 제공 전 고영향 인공지능 해당 여부를 검토하지 않는 행위(불명확 시 과학기술정보통신부장관에게 확인 요청 가능)",
        "rule_name": "고영향 인공지능 해당 여부 사전 검토",
        "rule_description": "AI 제품·서비스 제공 전 고영향 인공지능 해당 여부를 검토하고 결과를 기록",
        "actions": [
            "CRO가 제공 용도·활용 과정·영향 기준으로 고영향 해당 여부 검토",
            "CCO가 검토 결과와 근거 확인, 불명확 시 확인 요청 여부 결정",
            "CEO 승인 후 검토서 보관 및 서비스 변경 시 재검토",
        ],
    },
    "716907d1-82aa-1527-47bc-e4f2da9d98ee": {
        "old_article": "15조",
        "article": "제34조",
        "name": "고영향 인공지능 안전성·신뢰성 확보조치 미이행",
        "description": "고영향 인공지능 제공 시 위험관리방안, 설명방안, 이용자 보호방안, 사람의 관리·감독, 조치 문서화 등을 이행하지 않는 행위",
        "rule_name": "고영향 인공지능 안전성·신뢰성 확보조치",
    },
    "42e200e4-5b16-02fd-01ff-ed3250c178e7": {
        "old_article": "25조",
        "article": "제31조 제1항",
        "description": "고영향·생성형 인공지능 기반 제품·서비스 제공 시 이용자에게 인공지능 기반이라는 사실을 사전에 고지하지 않는 행위",
    },
    # 법령상 설치 의무가 아니라 금융분야 AI 가이드라인(모범규준)의 거버넌스 원칙
    "fa2c3353-f4a9-1d46-053b-1334f0643e2c": {
        "old_article": "30조",
        "law_id": "fin_ai_guideline", "law_name": "금융분야 AI 가이드라인", "article": "거버넌스 원칙",
        "priority": "MEDIUM",
    },
}

NEEDS_VERIFICATION: dict[str, str] = {
    "f463e45c-6b34-eba9-7b55-78737e86c602": "전자금융감독규정 해당 조항",
    "3d43e43e-9c84-9533-ef4d-6db301ee1f4a": "정보통신망법 해당 조항",
    "dfafb597-4568-8b2c-c796-3fb7db9d6c89": "마이데이터 표준 API 전송 근거",
    "06346b86-d240-eeda-c055-4415609ee682": "가명처리 알고리즘 투명성은 법령상 명시 의무가 아님",
    "d05a5181-a960-2bdd-9d5a-ee7a678b9108": "지배구조법 내부통제기준 조항",
    "3a82ad22-6260-ebb0-7208-bc2e449a0433": "지배구조법 준법감시인 조항",
    "6b455449-25e1-756d-96f6-fe65c9556260": "지배구조법 위험관리위원회 조항",
    "dc260c2d-7b35-b176-cff3-186202bcaa79": "지배구조법 책무구조도·관리의무 조항",
    "cfcc99ce-49fb-82e1-c23c-8c1c6f59052c": "지배구조법 책무구조도 조항",
    "d080bd5c-3860-d63a-a029-5e4ec3c1c3b2": "대주주 적격성 심사 관련성",
    "f33799e6-7411-f7b2-f791-88aaac34149a": "AI 기본법에는 일반적 중대사고 보고 의무가 없음(전자금융 사고보고 등 적용 근거 확인)",
}

_ACT_FIELDS = ("law_id", "law_name", "article", "name", "description", "priority")


def apply_citation_corrections(db) -> int:
    """기존 DB용: 원래 조문 그대로인 시드 항목만 교정한다. 교정 건수를 반환."""
    changed = 0
    for pid, fix in CORRECTIONS.items():
        act = db.get(ProhibitedAct, pid)
        if act is None or act.article != fix["old_article"]:
            continue
        for field in _ACT_FIELDS:
            if field in fix:
                setattr(act, field, fix[field])
        rule = act.duty_mapping.business_rule if act.duty_mapping else None
        if rule is not None:
            if "rule_name" in fix:
                rule.name = fix["rule_name"]
            if "rule_description" in fix:
                rule.description = fix["rule_description"]
            if "actions" in fix:
                rule.actions = fix["actions"]
        changed += 1
    for pid, note in NEEDS_VERIFICATION.items():
        act = db.get(ProhibitedAct, pid)
        if act is not None and act.description and VERIFY_MARKER not in act.description:
            act.description = f"{act.description} {VERIFY_MARKER} {note}"
            changed += 1
    if changed:
        db.commit()
    return changed
