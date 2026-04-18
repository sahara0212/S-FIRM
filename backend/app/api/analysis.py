"""
분석 파이프라인 API
3단계: POST /extract   → 금지행위 추출 + 책임자 매핑
       GET  /prohibitions → 추출 결과 조회
       PUT  /prohibitions/{pid} → 수정/확정
4단계: POST /generate-rules → 업무규칙 생성
       GET  /rules          → 업무규칙 조회
       PUT  /rules/{rid}    → 업무규칙 수정/상태 변경
"""
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import (
    AnalysisSession, DutyStructure,
    ProhibitedAct, DutyMapping, BusinessRule
)
from app.services.law_api import fetcher
from app.services.prohibition_extractor import extract_prohibitions
from app.services.business_rule_generator import generate_rules

router = APIRouter(prefix="/api/v1/clients/{client_id}/sessions/{session_id}", tags=["analysis"])


# ── Pydantic 스키마 ────────────────────────────────────────────────────────────
class ProhibitionOut(BaseModel):
    id: str
    law_id: Optional[str]
    law_name: Optional[str]
    article: Optional[str]
    name: str
    description: Optional[str]
    subject: Optional[str]
    target: Optional[str]
    trigger_condition: Optional[str]
    exception: Optional[str]
    priority: str
    ai_generated: bool
    confirmed: bool
    mapping: Optional[dict] = None

    class Config:
        from_attributes = True

class ProhibitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    target: Optional[str] = None
    trigger_condition: Optional[str] = None
    exception: Optional[str] = None
    priority: Optional[str] = None
    confirmed: Optional[bool] = None
    first_duty: Optional[str] = None
    second_duty: Optional[str] = None
    third_duty: Optional[str] = None


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────
def _get_session(client_id: str, session_id: str, db: Session) -> AnalysisSession:
    s = db.get(AnalysisSession, session_id)
    if not s or s.client_id != client_id:
        raise HTTPException(404, "분석 세션을 찾을 수 없습니다.")
    return s

def _prohibition_to_out(p: ProhibitedAct) -> dict:
    mapping = None
    if p.duty_mapping:
        mapping = {
            "first_duty":    p.duty_mapping.first_duty,
            "second_duty":   p.duty_mapping.second_duty,
            "third_duty":    p.duty_mapping.third_duty,
            "mapping_note":  p.duty_mapping.mapping_note,
            "confirmed":     p.duty_mapping.confirmed,
        }
    return {
        "id": p.id, "law_id": p.law_id, "law_name": p.law_name,
        "article": p.article, "name": p.name, "description": p.description,
        "subject": p.subject, "target": p.target,
        "trigger_condition": p.trigger_condition, "exception": p.exception,
        "priority": p.priority, "ai_generated": p.ai_generated,
        "confirmed": p.confirmed, "mapping": mapping,
    }


# ── 금지행위 추출 실행 ─────────────────────────────────────────────────────────
@router.post("/extract")
async def run_extraction(
    client_id: str,
    session_id: str,
    body: dict = {},
    db: Session = Depends(get_db),
):
    """
    법령 모니터링 데이터 + 책무구조 → Claude로 금지행위 추출 + 책임자 매핑

    모드:
      - 기간 기준(기본): body에 law_diffs 직접 전달 (모니터링 기간 필터 적용 조문)
      - 확장(full_diff): body에 law_ids 전달 → 법제처 현행 vs 직전 전체 diff 사용

    body:
      { "law_diffs": [...] }              # 기간 기준 모드
      { "law_ids": ["pipa","aiba",...] }  # 확장 모드
    """
    session = _get_session(client_id, session_id, db)

    # 활성 책무구조 로드
    ds = (
        db.query(DutyStructure)
        .filter(DutyStructure.client_id == client_id, DutyStructure.is_active == True)
        .order_by(DutyStructure.parsed_at.desc())
        .first()
    )
    if not ds:
        raise HTTPException(400, "책무구조가 없습니다. 먼저 문서를 업로드하고 책무구조를 추출하세요.")

    # ── 모드 분기 ──────────────────────────────────────────────────────────────
    if body.get("law_diffs"):
        # 기간 기준 모드: 프론트에서 모니터링 변경 조문 직접 전달
        law_diffs = body["law_diffs"]
        extract_mode = "period"
    else:
        # 확장 모드: 법제처 API로 현행 vs 직전 전체 diff 수집
        law_ids = body.get("law_ids") or ["pipa", "cipa", "aiba", "efsr", "itna", "fgsl"]
        law_diffs = []
        for law_id in law_ids:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, fetcher.get_version_diff_data, law_id
                )
                if data.get("error") or not data.get("diffs"):
                    continue
                for d in data["diffs"]:
                    law_diffs.append({
                        "law_id":      law_id,
                        "law_name":    data["name"],
                        "article":     d["article"],
                        "change_type": d.get("change_type", "개정"),
                        "before":      d["before"],
                        "after":       d["after"],
                    })
            except Exception:
                continue
        extract_mode = "full_diff"

    if not law_diffs:
        raise HTTPException(422, "분석할 법령 변경 데이터가 없습니다.")

    # 세션 상태 업데이트
    session.status = "extracting"
    session.law_snapshot = {
        "diffs": law_diffs,
        "mode": extract_mode,
        "fetched_at": str(datetime.utcnow()),
    }
    db.commit()

    # Claude 금지행위 추출
    try:
        prohibitions = await asyncio.get_event_loop().run_in_executor(
            None, extract_prohibitions, law_diffs, ds.executives
        )
    except Exception as e:
        session.status = "draft"
        db.commit()
        raise HTTPException(500, f"금지행위 추출 실패: {e}")

    # 기존 결과 삭제 후 재저장 (재실행 가능하도록)
    existing = db.query(ProhibitedAct).filter(ProhibitedAct.session_id == session_id).all()
    for p in existing:
        db.delete(p)
    db.commit()

    # 결과 저장
    saved = []
    for item in prohibitions:
        act = ProhibitedAct(
            session_id=session_id,
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
        db.flush()  # id 생성

        # 책임자 매핑 저장
        if item.get("first_duty"):
            mapping = DutyMapping(
                prohibited_act_id=act.id,
                first_duty=item.get("first_duty"),
                second_duty=item.get("second_duty"),
                third_duty=item.get("third_duty"),
                mapping_note=item.get("mapping_reason"),
                ai_generated=True,
                confirmed=False,
            )
            db.add(mapping)

        saved.append(act)

    session.status = "mapping"
    db.commit()

    # 결과 반환
    db.refresh(session)
    for act in saved:
        db.refresh(act)

    return {
        "status":           "success",
        "session_status":   session.status,
        "law_diff_count":   len(law_diffs),
        "prohibition_count": len(saved),
        "prohibitions":     [_prohibition_to_out(a) for a in saved],
    }


# ── 금지행위 목록 조회 ────────────────────────────────────────────────────────
@router.get("/prohibitions")
def list_prohibitions(
    client_id: str,
    session_id: str,
    db: Session = Depends(get_db),
):
    _get_session(client_id, session_id, db)
    acts = (
        db.query(ProhibitedAct)
        .filter(ProhibitedAct.session_id == session_id)
        .order_by(ProhibitedAct.priority, ProhibitedAct.law_name)
        .all()
    )

    # 요약 통계
    total   = len(acts)
    high    = sum(1 for a in acts if a.priority == "HIGH")
    medium  = sum(1 for a in acts if a.priority == "MEDIUM")
    low     = sum(1 for a in acts if a.priority == "LOW")
    mapped  = sum(1 for a in acts if a.duty_mapping is not None)
    confirmed = sum(1 for a in acts if a.confirmed)

    return {
        "summary": {
            "total": total, "high": high, "medium": medium, "low": low,
            "mapped": mapped, "confirmed": confirmed,
        },
        "items": [_prohibition_to_out(a) for a in acts],
    }


# ── 금지행위 개별 수정/확정 ────────────────────────────────────────────────────
@router.put("/prohibitions/{prohibition_id}")
def update_prohibition(
    client_id: str,
    session_id: str,
    prohibition_id: str,
    body: ProhibitionUpdate,
    db: Session = Depends(get_db),
):
    _get_session(client_id, session_id, db)
    act = db.get(ProhibitedAct, prohibition_id)
    if not act or act.session_id != session_id:
        raise HTTPException(404, "금지행위를 찾을 수 없습니다.")

    # 기본 필드 업데이트
    for field in ["name","description","subject","target",
                  "trigger_condition","exception","priority","confirmed"]:
        val = getattr(body, field)
        if val is not None:
            setattr(act, field, val)

    # 매핑 업데이트
    if any(v is not None for v in [body.first_duty, body.second_duty, body.third_duty]):
        if act.duty_mapping:
            m = act.duty_mapping
        else:
            m = DutyMapping(prohibited_act_id=act.id, ai_generated=False)
            db.add(m)
        if body.first_duty:  m.first_duty  = body.first_duty
        if body.second_duty: m.second_duty = body.second_duty
        if body.third_duty:  m.third_duty  = body.third_duty
        if body.confirmed:
            m.confirmed    = True
            m.confirmed_at = datetime.utcnow()

    db.commit()
    db.refresh(act)
    return _prohibition_to_out(act)


# ══════════════════════════════════════════════════════════════════════════════
# 4단계: 업무규칙 생성
# ══════════════════════════════════════════════════════════════════════════════

class RuleUpdate(BaseModel):
    name:              Optional[str] = None
    description:       Optional[str] = None
    trigger_condition: Optional[str] = None
    actions:           Optional[list] = None
    exceptions:        Optional[list] = None
    system_guide:      Optional[str] = None
    status:            Optional[str] = None  # draft | reviewing | completed


def _rule_to_out(r: BusinessRule) -> dict:
    dm = r.duty_mapping
    act = dm.prohibited_act if dm else None
    return {
        "id":               r.id,
        "rule_code":        r.rule_code,
        "name":             r.name,
        "description":      r.description,
        "trigger_condition":r.trigger_condition,
        "actions":          r.actions or [],
        "exceptions":       r.exceptions or [],
        "system_guide":     r.system_guide,
        "status":           r.status,
        "version":          r.version,
        "created_at":       r.created_at.isoformat() if r.created_at else None,
        "prohibition": {
            "id":       act.id       if act else None,
            "law_name": act.law_name if act else None,
            "article":  act.article  if act else None,
            "name":     act.name     if act else None,
            "priority": act.priority if act else None,
        } if act else None,
        "duty": {
            "first_duty":  dm.first_duty  if dm else None,
            "second_duty": dm.second_duty if dm else None,
            "third_duty":  dm.third_duty  if dm else None,
        } if dm else None,
    }


@router.post("/generate-rules")
async def run_rule_generation(
    client_id: str,
    session_id: str,
    body: dict = {},
    db: Session = Depends(get_db),
):
    """
    4단계: 금지행위 + 책임자 매핑 → Claude → 내부 업무규칙 생성
    body(선택): { "prohibition_ids": [...] }  # 특정 금지행위만 처리 시
    """
    _get_session(client_id, session_id, db)

    # 대상 금지행위 수집 (매핑이 있는 것만)
    q = (
        db.query(ProhibitedAct)
        .filter(ProhibitedAct.session_id == session_id)
    )
    pid_filter = body.get("prohibition_ids")
    if pid_filter:
        q = q.filter(ProhibitedAct.id.in_(pid_filter))

    acts = [a for a in q.all() if a.duty_mapping is not None]
    if not acts:
        raise HTTPException(422, "업무규칙을 생성할 금지행위(매핑 포함)가 없습니다.")

    # Claude 호출용 데이터 변환
    prohibition_data = [_prohibition_to_out(a) for a in acts]

    # 업무규칙 생성
    try:
        rules_raw = await asyncio.get_event_loop().run_in_executor(
            None, generate_rules, prohibition_data
        )
    except Exception as e:
        raise HTTPException(500, f"업무규칙 생성 실패: {e}")

    # prohibition_id → act 매핑
    act_map = {a.id: a for a in acts}

    saved: list[BusinessRule] = []
    for item in rules_raw:
        pid = item.get("prohibition_id")
        act = act_map.get(pid)
        if not act or not act.duty_mapping:
            continue

        dm = act.duty_mapping
        # 기존 규칙 있으면 덮어쓰기
        existing = dm.business_rule
        if existing:
            r = existing
            r.version += 1
        else:
            r = BusinessRule(duty_mapping_id=dm.id)
            db.add(r)

        r.rule_code        = item.get("rule_code", "")
        r.name             = item.get("name", "")
        r.description      = item.get("description")
        r.trigger_condition= item.get("trigger_condition")
        r.actions          = item.get("actions") or []
        r.exceptions       = item.get("exceptions") or []
        r.system_guide     = item.get("system_guide")
        r.status           = "draft"
        db.flush()
        saved.append(r)

    db.commit()
    for r in saved:
        db.refresh(r)

    return {
        "status":      "success",
        "rule_count":  len(saved),
        "rules":       [_rule_to_out(r) for r in saved],
    }


@router.get("/rules")
def list_rules(
    client_id: str,
    session_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """4단계 업무규칙 목록 조회"""
    _get_session(client_id, session_id, db)

    acts = (
        db.query(ProhibitedAct)
        .filter(ProhibitedAct.session_id == session_id)
        .all()
    )
    rules: list[BusinessRule] = []
    for act in acts:
        dm = act.duty_mapping
        if dm and dm.business_rule:
            r = dm.business_rule
            if status is None or r.status == status:
                rules.append(r)

    total     = len(rules)
    draft     = sum(1 for r in rules if r.status == "draft")
    reviewing = sum(1 for r in rules if r.status == "reviewing")
    completed = sum(1 for r in rules if r.status == "completed")

    return {
        "summary": {
            "total": total, "draft": draft,
            "reviewing": reviewing, "completed": completed,
        },
        "items": [_rule_to_out(r) for r in rules],
    }


@router.put("/rules/{rule_id}")
def update_rule(
    client_id: str,
    session_id: str,
    rule_id: str,
    body: RuleUpdate,
    db: Session = Depends(get_db),
):
    """업무규칙 수정 및 상태 변경"""
    _get_session(client_id, session_id, db)
    rule = db.get(BusinessRule, rule_id)
    if not rule:
        raise HTTPException(404, "업무규칙을 찾을 수 없습니다.")

    for field in ["name", "description", "trigger_condition",
                  "actions", "exceptions", "system_guide", "status"]:
        val = getattr(body, field)
        if val is not None:
            setattr(rule, field, val)

    db.commit()
    db.refresh(rule)
    return _rule_to_out(rule)
