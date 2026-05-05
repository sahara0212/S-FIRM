"""이행점검 API — 업무규칙별 월별 점검 결과 등록/조회"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import BusinessRule, DutyMapping, ProhibitedAct, InspectionCheck

router = APIRouter(prefix="/api/v1/inspection", tags=["inspection"])

VALID_RESULTS = {"적정", "개선필요", "해당없음", "미점검"}
VALID_METHODS = {"대면", "비대면", "해당없음"}


# ── Pydantic 스키마 ────────────────────────────────────────────────────────────
class CheckUpsert(BaseModel):
    client_id: str
    rule_id:   str
    period:    str           # YYYY-MM
    result:    str = "미점검"
    method:    str = "대면"
    note:      Optional[str] = None
    checked_by: Optional[str] = None

class CheckOut(BaseModel):
    id: str
    client_id: str
    rule_id: str
    period: str
    result: str
    method: str
    note: Optional[str]
    checked_by: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


# ── 기간별 점검 현황 조회 ───────────────────────────────────────────────────────
@router.get("/{client_id}/{period}")
def get_inspection_period(client_id: str, period: str, db: Session = Depends(get_db)):
    """
    특정 고객사의 특정 기간(YYYY-MM) 이행점검 목록.
    업무규칙 전체 목록 + 각 규칙의 점검 결과를 JOIN해서 반환.
    """
    # 해당 고객사의 업무규칙 전체
    rules = (
        db.query(BusinessRule)
        .join(DutyMapping, BusinessRule.duty_mapping_id == DutyMapping.id)
        .join(ProhibitedAct, DutyMapping.prohibited_act_id == ProhibitedAct.id)
        .filter(ProhibitedAct.session_id.in_(
            db.query(ProhibitedAct.session_id)
            .join(DutyMapping, ProhibitedAct.id == DutyMapping.prohibited_act_id)
            .join(BusinessRule, DutyMapping.id == BusinessRule.duty_mapping_id)
        ))
        .all()
    )

    # 해당 기간 점검 결과 맵핑
    checks = db.query(InspectionCheck).filter(
        InspectionCheck.client_id == client_id,
        InspectionCheck.period == period,
    ).all()
    check_map = {c.rule_id: c for c in checks}

    items = []
    for r in rules:
        c = check_map.get(r.id)
        dm = r.duty_mapping
        pa = dm.prohibited_act if dm else None
        items.append({
            "rule_id":    r.id,
            "rule_code":  r.rule_code or "-",
            "name":       r.name,
            "law_name":   pa.law_name if pa else "",
            "article":    pa.article if pa else "",
            "priority":   pa.priority if pa else "LOW",
            "first_duty": dm.first_duty if dm else "",
            "result":     c.result if c else "미점검",
            "method":     c.method if c else "대면",
            "note":       c.note if c else "",
            "checked_by": c.checked_by if c else "",
            "checked_at": c.checked_at.isoformat() if (c and c.checked_at) else None,
            "check_id":   c.id if c else None,
        })

    # 요약 통계
    total  = len(items)
    done   = sum(1 for i in items if i["result"] in ("적정", "해당없음"))
    needs  = sum(1 for i in items if i["result"] == "개선필요")
    未점검 = sum(1 for i in items if i["result"] == "미점검")

    return {
        "period":  period,
        "client_id": client_id,
        "summary": {"total": total, "done": done, "needs_improvement": needs, "not_checked": 未점검},
        "items":   items,
    }


# ── 점검 결과 등록/수정 (upsert) ───────────────────────────────────────────────
@router.post("/upsert")
def upsert_check(body: CheckUpsert, db: Session = Depends(get_db)):
    if body.result not in VALID_RESULTS:
        raise HTTPException(400, f"result는 {VALID_RESULTS} 중 하나여야 합니다.")
    if body.method not in VALID_METHODS:
        raise HTTPException(400, f"method는 {VALID_METHODS} 중 하나여야 합니다.")

    existing = db.query(InspectionCheck).filter(
        InspectionCheck.client_id == body.client_id,
        InspectionCheck.rule_id   == body.rule_id,
        InspectionCheck.period    == body.period,
    ).first()

    now = datetime.utcnow()
    if existing:
        existing.result     = body.result
        existing.method     = body.method
        existing.note       = body.note
        existing.checked_by = body.checked_by
        existing.checked_at = now
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return {"status": "updated", "id": existing.id}
    else:
        check = InspectionCheck(
            client_id  = body.client_id,
            rule_id    = body.rule_id,
            period     = body.period,
            result     = body.result,
            method     = body.method,
            note       = body.note,
            checked_by = body.checked_by,
            checked_at = now,
        )
        db.add(check)
        db.commit()
        db.refresh(check)
        return {"status": "created", "id": check.id}


# ── 기간별 요약 (대시보드용) ────────────────────────────────────────────────────
@router.get("/summary/{client_id}/{period}")
def get_summary(client_id: str, period: str, db: Session = Depends(get_db)):
    checks = db.query(InspectionCheck).filter(
        InspectionCheck.client_id == client_id,
        InspectionCheck.period    == period,
    ).all()
    counts = {"적정": 0, "개선필요": 0, "해당없음": 0, "미점검": 0}
    methods = {"대면": 0, "비대면": 0, "해당없음": 0}
    for c in checks:
        if c.result in counts: counts[c.result] += 1
        if c.method in methods: methods[c.method] += 1
    return {"period": period, "results": counts, "methods": methods, "total_checked": len(checks)}
