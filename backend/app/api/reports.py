"""분기 보고서 API — 이행점검·개선조치 집계 + 결재 워크플로우"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import QuarterlyReport, InspectionCheck, ImprovementAction, BusinessRule

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

VALID_STATUSES = ["작성중", "검토완료", "결재완료"]

# quarter → (from, to) 헬퍼
def _quarter_range(quarter: str) -> tuple[str, str]:
    """'2026-Q2' → ('2026-04', '2026-06')"""
    year, q = quarter.split("-Q")
    q = int(q)
    month_from = (q - 1) * 3 + 1
    month_to   = q * 3
    return (f"{year}-{month_from:02d}", f"{year}-{month_to:02d}")


def _aggregate_inspection(db: Session, client_id: str, period_from: str, period_to: str) -> dict:
    """기간 내 이행점검 집계"""
    checks = db.query(InspectionCheck).filter(
        InspectionCheck.client_id == client_id,
        InspectionCheck.period >= period_from,
        InspectionCheck.period <= period_to,
    ).all()

    total   = len(checks)
    ok      = sum(1 for c in checks if c.result == "적정")
    needs   = sum(1 for c in checks if c.result == "개선필요")
    na      = sum(1 for c in checks if c.result == "해당없음")
    not_chk = sum(1 for c in checks if c.result == "미점검")
    rate    = round(ok / total * 100) if total > 0 else 0

    return {
        "total": total, "ok": ok, "needs_improvement": needs,
        "not_applicable": na, "not_checked": not_chk, "completion_rate": rate,
    }


def _aggregate_improvement(db: Session, client_id: str, period_from: str, period_to: str) -> dict:
    """기간 내 개선조치 집계"""
    actions = db.query(ImprovementAction).filter(
        ImprovementAction.client_id == client_id,
        ImprovementAction.origin_period >= period_from,
        ImprovementAction.origin_period <= period_to,
    ).all()

    total   = len(actions)
    done    = sum(1 for a in actions if a.status == "완료")
    ongoing = sum(1 for a in actions if a.status == "진행중")
    pending = sum(1 for a in actions if a.status == "미완료")
    carried = sum(1 for a in actions if a.carryover_count > 0)
    rate    = round(done / total * 100) if total > 0 else 0

    return {
        "total": total, "done": done, "ongoing": ongoing,
        "pending": pending, "carryover": carried, "completion_rate": rate,
    }


# ── 목록 조회 ──────────────────────────────────────────────────────────────────
@router.get("/{client_id}")
def list_reports(client_id: str, db: Session = Depends(get_db)):
    reports = db.query(QuarterlyReport).filter(
        QuarterlyReport.client_id == client_id
    ).order_by(QuarterlyReport.quarter.desc()).all()

    return [
        {
            "id": r.id, "quarter": r.quarter, "status": r.status,
            "period_from": r.period_from, "period_to": r.period_to,
            "inspection_summary":  r.inspection_summary,
            "improvement_summary": r.improvement_summary,
            "note": r.note,
            "reviewer": r.reviewer, "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "approver": r.approver, "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
        }
        for r in reports
    ]


# ── 단일 조회 (없으면 실시간 집계 반환) ──────────────────────────────────────
@router.get("/{client_id}/{quarter}")
def get_report(client_id: str, quarter: str, db: Session = Depends(get_db)):
    r = db.query(QuarterlyReport).filter(
        QuarterlyReport.client_id == client_id,
        QuarterlyReport.quarter   == quarter,
    ).first()

    period_from, period_to = _quarter_range(quarter)
    insp = _aggregate_inspection(db, client_id, period_from, period_to)
    impr = _aggregate_improvement(db, client_id, period_from, period_to)

    if not r:
        return {
            "id": None, "quarter": quarter, "status": "작성중",
            "period_from": period_from, "period_to": period_to,
            "inspection_summary": insp, "improvement_summary": impr,
            "note": None, "reviewer": None, "reviewed_at": None,
            "approver": None, "approved_at": None,
            "live": True,   # DB 레코드 없음 = 실시간 집계
        }

    return {
        "id": r.id, "quarter": r.quarter, "status": r.status,
        "period_from": r.period_from, "period_to": r.period_to,
        # 저장된 스냅샷 우선, 없으면 실시간 집계
        "inspection_summary":  r.inspection_summary or insp,
        "improvement_summary": r.improvement_summary or impr,
        "note": r.note,
        "reviewer": r.reviewer, "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "approver": r.approver, "approved_at": r.approved_at.isoformat() if r.approved_at else None,
        "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
        "live": False,
    }


# ── 생성 또는 업데이트 (upsert) ───────────────────────────────────────────────
class ReportUpsert(BaseModel):
    client_id: str
    quarter:   str
    note:      Optional[str] = None

@router.post("")
def upsert_report(body: ReportUpsert, db: Session = Depends(get_db)):
    period_from, period_to = _quarter_range(body.quarter)
    r = db.query(QuarterlyReport).filter(
        QuarterlyReport.client_id == body.client_id,
        QuarterlyReport.quarter   == body.quarter,
    ).first()

    insp = _aggregate_inspection(db, body.client_id, period_from, period_to)
    impr = _aggregate_improvement(db, body.client_id, period_from, period_to)

    if not r:
        r = QuarterlyReport(
            client_id=body.client_id, quarter=body.quarter,
            period_from=period_from, period_to=period_to,
            inspection_summary=insp, improvement_summary=impr,
            note=body.note,
        )
        db.add(r)
    else:
        r.inspection_summary  = insp
        r.improvement_summary = impr
        if body.note is not None:
            r.note = body.note
        r.updated_at = datetime.utcnow()

    db.commit(); db.refresh(r)
    return {"status": "ok", "id": r.id, "quarter": r.quarter}


# ── 상태 변경 (검토완료 / 결재완료) ──────────────────────────────────────────
class StatusUpdate(BaseModel):
    status:   str
    actor:    Optional[str] = None   # 검토자 or 결재자 이름

@router.patch("/{report_id}/status")
def update_status(report_id: str, body: StatusUpdate, db: Session = Depends(get_db)):
    r = db.get(QuarterlyReport, report_id)
    if not r:
        raise HTTPException(404, "보고서를 찾을 수 없습니다.")
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"status는 {VALID_STATUSES} 중 하나여야 합니다.")

    now = datetime.utcnow()
    r.status = body.status
    if body.status == "검토완료":
        r.reviewer = body.actor; r.reviewed_at = now
    elif body.status == "결재완료":
        r.approver = body.actor; r.approved_at = now
    r.updated_at = now
    db.commit(); db.refresh(r)
    return {"status": "ok", "id": r.id, "new_status": r.status}


# ── 메모 업데이트 ─────────────────────────────────────────────────────────────
class NoteUpdate(BaseModel):
    note: str

@router.patch("/{report_id}/note")
def update_note(report_id: str, body: NoteUpdate, db: Session = Depends(get_db)):
    r = db.get(QuarterlyReport, report_id)
    if not r:
        raise HTTPException(404, "보고서를 찾을 수 없습니다.")
    r.note = body.note
    r.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "ok"}
