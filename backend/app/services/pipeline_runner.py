"""
파이프라인 실행 + DB 저장 통합 함수
API 엔드포인트와 스케줄러 모두 이 모듈을 사용
"""
import logging
from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisSession, DutyStructure,
    ProhibitedAct, DutyMapping, BusinessRule,
)
from app.services.pipeline import pipeline

logger = logging.getLogger(__name__)

_DEFAULT_LAW_IDS = ["pipa", "cipa", "aiba", "efsr", "itna", "fgsl"]


def run_and_save(
    client_id: str,
    session: AnalysisSession,
    ds: DutyStructure,
    db: Session,
    law_ids: list[str] | None = None,
) -> dict:
    """
    파이프라인 실행 후 DB 저장까지 수행.
    반환: { law_diff_count, prohibition_count, rule_count, log, error }
    """
    initial_state = {
        "client_id":    client_id,
        "session_id":   session.id,
        "law_ids":      law_ids or _DEFAULT_LAW_IDS,
        "executives":   ds.executives or [],
        "law_diffs":    [],
        "prohibitions": [],
        "rules":        [],
        "error":        None,
        "log":          [],
    }
    config = {"configurable": {"thread_id": f"{client_id}:{session.id}"}}

    session.status = "running"
    db.commit()

    result = pipeline.invoke(initial_state, config=config)

    if result.get("error"):
        session.status = "draft"
        db.commit()
        return {"error": result["error"], "log": result.get("log", [])}

    # ── 기존 결과 초기화 ───────────────────────────────────────────────────────
    for p in db.query(ProhibitedAct).filter(ProhibitedAct.session_id == session.id).all():
        db.delete(p)
    db.commit()

    # ── 금지행위 + 매핑 저장 ───────────────────────────────────────────────────
    act_map: dict[str, ProhibitedAct] = {}
    for item in result["prohibitions"]:
        act = ProhibitedAct(
            session_id=session.id,
            law_id=item.get("law_id"),
            law_name=item.get("law_name"),
            article=item.get("article"),
            name=item.get("name", ""),
            description=item.get("description"),
            subject=item.get("subject"),
            target=item.get("target"),
            trigger_condition=item.get("trigger_condition"),
            exception=item.get("exception"),
            priority=item.get("priority", "MEDIUM"),
            ai_generated=True,
            confirmed=False,
        )
        db.add(act)
        db.flush()

        m = item.get("mapping") or {}
        if m.get("first_duty"):
            db.add(DutyMapping(
                prohibited_act_id=act.id,
                first_duty=m.get("first_duty"),
                second_duty=m.get("second_duty"),
                third_duty=m.get("third_duty"),
                mapping_note=item.get("mapping_reason"),
                ai_generated=True,
                confirmed=False,
            ))

        act_map[item.get("id", "")] = act
    db.commit()

    # ── 업무규칙 저장 ──────────────────────────────────────────────────────────
    saved_rules = 0
    for rule_item in result["rules"]:
        act = act_map.get(rule_item.get("prohibition_id", ""))
        if not act or not act.duty_mapping:
            continue
        r = BusinessRule(duty_mapping_id=act.duty_mapping.id)
        db.add(r)
        r.rule_code         = rule_item.get("rule_code", "")
        r.name              = rule_item.get("name", "")
        r.description       = rule_item.get("description")
        r.trigger_condition = rule_item.get("trigger_condition")
        r.actions           = rule_item.get("actions") or []
        r.exceptions        = rule_item.get("exceptions") or []
        r.system_guide      = rule_item.get("system_guide")
        r.status            = "draft"
        saved_rules += 1

    session.status = "completed"
    db.commit()

    return {
        "law_diff_count":    len(result["law_diffs"]),
        "prohibition_count": len(result["prohibitions"]),
        "rule_count":        saved_rules,
        "log":               result["log"],
        "error":             None,
    }
