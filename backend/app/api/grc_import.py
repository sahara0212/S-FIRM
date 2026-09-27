"""
GRC 판정 가져오기 API
Digital Lawyer Platform(세종 금융 AI GRC 기준 표준)의 판정 결과를 S-FIRM 파이프라인에 적재한다.

GRC 통제항목 1건 → 금지행위(ProhibitedAct) + 책무매핑(DutyMapping) + 업무규칙(BusinessRule, draft)
적재된 규칙은 기존 이행점검·개선조치·분기보고 흐름을 그대로 탄다.
같은 세션에 같은 rule_code가 있으면 새로 만들지 않고 갱신한다(버전 +1).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import AnalysisSession, BusinessRule, DutyMapping, ProhibitedAct

router = APIRouter(prefix="/api/v1/clients/{client_id}/sessions/{session_id}", tags=["grc-import"])

DUTY_CODES = {"CEO", "CCO", "CRO", "CISO", "CPO", "CDO", "CFO", "CSO", "CIO", "BIZ_HEAD", "CHIEF_AUDIT", "BOARD_CHAIR"}


class GrcRule(BaseModel):
    rule_code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    trigger_condition: Optional[str] = None
    actions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    system_guide: Optional[str] = None
    priority: str = Field(default="MEDIUM", pattern="^(HIGH|MEDIUM|LOW)$")
    classification: Optional[str] = None
    law_name: Optional[str] = Field(default=None, max_length=100)
    grc_control_id: str = Field(min_length=1, max_length=50)
    first_duty: str
    second_duty: Optional[str] = None
    third_duty: Optional[str] = None


class GrcImportBody(BaseModel):
    source: str = "digital-lawyer-platform"
    standard_version: str
    assessment_title: Optional[str] = None
    rules: list[GrcRule] = Field(min_length=1)


def _check_duty(code: Optional[str]) -> Optional[str]:
    if code in (None, ""):
        return None
    if code not in DUTY_CODES:
        raise HTTPException(422, f"알 수 없는 책임자 코드: {code}")
    return code


@router.post("/grc-import")
def import_grc_rules(client_id: str, session_id: str, body: GrcImportBody, db: Session = Depends(get_db)):
    session = db.get(AnalysisSession, session_id)
    if session is None or session.client_id != client_id:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    existing = {
        act.duty_mapping.business_rule.rule_code: act
        for act in db.query(ProhibitedAct).filter(ProhibitedAct.session_id == session_id).all()
        if act.duty_mapping and act.duty_mapping.business_rule
    }

    created = updated = 0
    for rule in body.rules:
        first, second, third = (_check_duty(rule.first_duty), _check_duty(rule.second_duty), _check_duty(rule.third_duty))
        if first is None:
            raise HTTPException(422, f"{rule.rule_code}: 1차 책임자가 필요합니다.")

        act = existing.get(rule.rule_code)
        if act is None:
            act = ProhibitedAct(session_id=session_id, name=rule.name, ai_generated=False, confirmed=False)
            mapping = DutyMapping(ai_generated=False, confirmed=False)
            business_rule = BusinessRule(name=rule.name, version=1)
            act.duty_mapping = mapping
            mapping.business_rule = business_rule
            db.add(act)
            created += 1
        else:
            mapping = act.duty_mapping
            business_rule = mapping.business_rule
            business_rule.version += 1
            updated += 1

        act.law_id = "grc"
        act.law_name = rule.law_name or "세종 금융 AI GRC 기준 표준"
        act.article = rule.grc_control_id
        act.name = rule.name
        act.description = rule.description
        act.subject = "금융회사"
        act.target = "AI 시스템"
        act.trigger_condition = rule.trigger_condition
        act.priority = rule.priority

        mapping.first_duty, mapping.second_duty, mapping.third_duty = first, second, third
        mapping.mapping_note = (
            f"GRC 기준 표준 {body.standard_version} · {rule.grc_control_id}"
            + (f" · {rule.classification}" if rule.classification else "")
            + (f" · {body.assessment_title}" if body.assessment_title else "")
        )

        business_rule.rule_code = rule.rule_code
        business_rule.name = rule.name
        business_rule.description = rule.description
        business_rule.trigger_condition = rule.trigger_condition
        business_rule.actions = rule.actions
        business_rule.exceptions = rule.exceptions
        business_rule.system_guide = rule.system_guide
        # 변호사 검토 전 초안으로 들어온다.
        business_rule.status = "draft"

    db.commit()
    return {"status": "success", "created": created, "updated": updated, "total": len(body.rules)}
