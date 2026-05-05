"""개선조치 API — 이행점검 '개선필요' 연계 + 이월 추적"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ImprovementAction, InspectionCheck, BusinessRule, DutyMapping, ProhibitedAct

router = APIRouter(prefix="/api/v1/improvement", tags=["improvement"])

VALID_STATUSES = {"미완료", "진행중", "완료"}
VALID_TYPES    = {"이행점검조치", "자율개선조치"}


# ── Pydantic 스키마 ────────────────────────────────────────────────────────────
class ActionCreate(BaseModel):
    client_id:     str
    origin_period: str
    title:         str
    cause:         Optional[str] = None
    action_plan:   Optional[str] = None
    due_date:      Optional[str] = None
    action_type:   str = "이행점검조치"
    check_id:      Optional[str] = None
    rule_id:       Optional[str] = None

class ActionUpdate(BaseModel):
    status:        Optional[str] = None
    action_result: Optional[str] = None
    action_plan:   Optional[str] = None
    due_date:      Optional[str] = None
    completed_at:  Optional[str] = None  # ISO 문자열

class ActionOut(BaseModel):
    id: str
    client_id: str
    check_id: Optional[str]
    rule_id: Optional[str]
    origin_period: str
    title: str
    cause: Optional[str]
    action_plan: Optional[str]
    action_result: Optional[str]
    action_type: str
    status: str
    due_date: Optional[str]
    carryover_count: int
    last_period: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── 목록 조회 ──────────────────────────────────────────────────────────────────
@router.get("/{client_id}")
def list_actions(
    client_id: str,
    period: Optional[str] = None,        # 특정 기간 필터 (origin_period)
    status:  Optional[str] = None,        # 미완료|진행중|완료
    action_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(ImprovementAction).filter(ImprovementAction.client_id == client_id)
    if period:      q = q.filter(ImprovementAction.origin_period == period)
    if status:      q = q.filter(ImprovementAction.status == status)
    if action_type: q = q.filter(ImprovementAction.action_type == action_type)
    actions = q.order_by(ImprovementAction.created_at.desc()).all()

    # rule 정보 보강
    result = []
    for a in actions:
        row = {
            "id":            a.id,
            "client_id":     a.client_id,
            "check_id":      a.check_id,
            "rule_id":       a.rule_id,
            "origin_period": a.origin_period,
            "title":         a.title,
            "cause":         a.cause,
            "action_plan":   a.action_plan,
            "action_result": a.action_result,
            "action_type":   a.action_type,
            "status":        a.status,
            "due_date":      a.due_date,
            "carryover_count": a.carryover_count,
            "last_period":   a.last_period,
            "created_at":    a.created_at.isoformat(),
            "updated_at":    a.updated_at.isoformat(),
            "rule_code":     None,
            "rule_name":     None,
            "law_name":      None,
        }
        if a.rule_id:
            rule = db.get(BusinessRule, a.rule_id)
            if rule:
                row["rule_code"] = rule.rule_code
                row["rule_name"] = rule.name
                dm = rule.duty_mapping
                if dm and dm.prohibited_act:
                    row["law_name"] = dm.prohibited_act.law_name
        result.append(row)
    return result


# ── 요약 통계 (대시보드용) ────────────────────────────────────────────────────
@router.get("/summary/{client_id}/{period}")
def get_summary(client_id: str, period: str, db: Session = Depends(get_db)):
    """해당 기간 발생 + 이월 미완료 건수 통계"""
    # 해당 기간 발생
    current = db.query(ImprovementAction).filter(
        ImprovementAction.client_id    == client_id,
        ImprovementAction.origin_period == period,
    ).all()

    # 이전 기간에서 이월된 미완료
    carried = db.query(ImprovementAction).filter(
        ImprovementAction.client_id    == client_id,
        ImprovementAction.origin_period != period,
        ImprovementAction.status.in_(["미완료", "진행중"]),
        ImprovementAction.carryover_count > 0,
    ).all()

    def counts(items):
        return {
            "total":   len(items),
            "미완료":  sum(1 for i in items if i.status == "미완료"),
            "진행중":  sum(1 for i in items if i.status == "진행중"),
            "완료":    sum(1 for i in items if i.status == "완료"),
        }

    return {
        "period":  period,
        "current": counts(current),
        "carried": {"total": len(carried), "items": [i.id for i in carried]},
        "all_incomplete": counts(current)["미완료"] + counts(current)["진행중"] + len(carried),
    }


# ── 생성 ───────────────────────────────────────────────────────────────────────
@router.post("")
def create_action(body: ActionCreate, db: Session = Depends(get_db)):
    if body.action_type not in VALID_TYPES:
        raise HTTPException(400, f"action_type은 {VALID_TYPES} 중 하나여야 합니다.")
    action = ImprovementAction(
        client_id     = body.client_id,
        origin_period = body.origin_period,
        title         = body.title,
        cause         = body.cause,
        action_plan   = body.action_plan,
        due_date      = body.due_date,
        action_type   = body.action_type,
        check_id      = body.check_id,
        rule_id       = body.rule_id,
    )
    db.add(action); db.commit(); db.refresh(action)
    return {"status": "created", "id": action.id}


# ── 수정 ───────────────────────────────────────────────────────────────────────
@router.patch("/{action_id}")
def update_action(action_id: str, body: ActionUpdate, db: Session = Depends(get_db)):
    action = db.get(ImprovementAction, action_id)
    if not action:
        raise HTTPException(404, "개선조치 항목을 찾을 수 없습니다.")

    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(400, f"status는 {VALID_STATUSES} 중 하나여야 합니다.")
        action.status = body.status
        if body.status == "완료":
            action.completed_at = datetime.utcnow()
    if body.action_result is not None: action.action_result = body.action_result
    if body.action_plan   is not None: action.action_plan   = body.action_plan
    if body.due_date      is not None: action.due_date      = body.due_date

    action.updated_at = datetime.utcnow()
    db.commit(); db.refresh(action)
    return {"status": "updated", "id": action.id}


# ── 이월 처리 (월말 마감 시 미완료 항목을 다음 달로 이월) ────────────────────
@router.post("/carryover/{client_id}/{from_period}/{to_period}")
def carryover(client_id: str, from_period: str, to_period: str, db: Session = Depends(get_db)):
    """
    from_period의 미완료/진행중 항목을 to_period 로 이월 표시.
    실제로 새 레코드를 만들지 않고 carryover_count + last_period를 업데이트.
    """
    incomplete = db.query(ImprovementAction).filter(
        ImprovementAction.client_id    == client_id,
        ImprovementAction.origin_period == from_period,
        ImprovementAction.status.in_(["미완료", "진행중"]),
    ).all()

    for a in incomplete:
        a.carryover_count += 1
        a.last_period      = to_period
        a.updated_at       = datetime.utcnow()

    db.commit()
    return {"status": "ok", "carried_count": len(incomplete)}


# ── 이행점검 '개선필요' 결과에서 자동 생성 ──────────────────────────────────
@router.post("/auto-create-from-inspection")
def auto_create(body: dict, db: Session = Depends(get_db)):
    """
    check_ids 목록의 점검 결과가 '개선필요'인 항목들을 개선조치로 자동 등록.
    이미 동일 check_id로 등록된 것은 건너뜀.
    """
    client_id  = body.get("client_id")
    period     = body.get("period")
    check_ids  = body.get("check_ids", [])

    existing = {
        a.check_id for a in
        db.query(ImprovementAction.check_id).filter(
            ImprovementAction.client_id == client_id,
            ImprovementAction.check_id.in_(check_ids),
        ).all()
    }

    created = 0
    for cid in check_ids:
        if cid in existing:
            continue
        chk = db.get(InspectionCheck, cid)
        if not chk or chk.result != "개선필요":
            continue
        rule = db.get(BusinessRule, chk.rule_id) if chk.rule_id else None
        title = f"[{period}] {rule.name if rule else '업무규칙'} — 개선필요 조치"
        action = ImprovementAction(
            client_id     = client_id,
            check_id      = cid,
            rule_id       = chk.rule_id,
            origin_period = period,
            title         = title,
            action_type   = "이행점검조치",
        )
        db.add(action)
        created += 1

    db.commit()
    return {"status": "ok", "created": created, "skipped": len(check_ids) - created}
