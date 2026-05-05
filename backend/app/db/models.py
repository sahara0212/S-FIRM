"""
S-FIRM ORM 모델
고객사 → 문서 → 분석세션 → 금지행위 → 책무매핑 → 업무규칙
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, Boolean, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> datetime:
    return datetime.utcnow()


# ── 고객사 ────────────────────────────────────────────────────────────────────
class Client(Base):
    __tablename__ = "clients"

    id:         Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    name:       Mapped[str]           = mapped_column(String(100), nullable=False)
    industry:   Mapped[Optional[str]] = mapped_column(String(50))   # 은행, 보험, 증권, 카드 …
    note:       Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime]      = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime]      = mapped_column(DateTime, default=_now, onupdate=_now)

    documents:       Mapped[list["ClientDocument"]]  = relationship(back_populates="client", cascade="all, delete-orphan")
    duty_structures: Mapped[list["DutyStructure"]]   = relationship(back_populates="client", cascade="all, delete-orphan")
    sessions:        Mapped[list["AnalysisSession"]] = relationship(back_populates="client", cascade="all, delete-orphan")


# ── 업로드 문서 ───────────────────────────────────────────────────────────────
class ClientDocument(Base):
    __tablename__ = "client_documents"

    id:           Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    client_id:    Mapped[str]           = mapped_column(ForeignKey("clients.id"), nullable=False)
    doc_type:     Mapped[str]           = mapped_column(String(30))  # duty_structure | duty_description | duty_status | other
    filename:     Mapped[str]           = mapped_column(String(255))
    content_text: Mapped[Optional[str]] = mapped_column(Text)        # 추출된 원문 텍스트
    uploaded_at:  Mapped[datetime]      = mapped_column(DateTime, default=_now)

    client: Mapped["Client"] = relationship(back_populates="documents")


# ── 파싱된 책무 구조 (임원-책무 매핑) ─────────────────────────────────────────
class DutyStructure(Base):
    __tablename__ = "duty_structures"

    id:         Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    client_id:  Mapped[str]           = mapped_column(ForeignKey("clients.id"), nullable=False)
    source_doc: Mapped[Optional[str]] = mapped_column(ForeignKey("client_documents.id"))
    # executives: [{role, name, level, duties:[str], parent_role}]
    executives: Mapped[Optional[dict]] = mapped_column(JSON)
    # org_tree: 시각화용 계층 구조
    org_tree:   Mapped[Optional[dict]] = mapped_column(JSON)
    parsed_at:  Mapped[datetime]       = mapped_column(DateTime, default=_now)
    is_active:  Mapped[bool]           = mapped_column(Boolean, default=True)

    client: Mapped["Client"] = relationship(back_populates="duty_structures")


# ── 분석 세션 ─────────────────────────────────────────────────────────────────
class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id:           Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    client_id:    Mapped[str]           = mapped_column(ForeignKey("clients.id"), nullable=False)
    label:        Mapped[str]           = mapped_column(String(100))  # "2026-04 정기 검토"
    period_type:  Mapped[Optional[str]] = mapped_column(String(20))   # 7d | 1m | 3m | custom
    period_from:  Mapped[Optional[str]] = mapped_column(String(10))   # YYYY-MM-DD
    period_to:    Mapped[Optional[str]] = mapped_column(String(10))
    # 분석 시점의 법령 데이터 스냅샷 (법령명/조문/before/after)
    law_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)
    status:       Mapped[str]            = mapped_column(String(20), default="draft")
    # draft → extracting → mapping → generating → in_review → confirmed
    note:         Mapped[Optional[str]]  = mapped_column(Text)
    created_at:   Mapped[datetime]       = mapped_column(DateTime, default=_now)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    client:          Mapped["Client"]           = relationship(back_populates="sessions")
    prohibited_acts: Mapped[list["ProhibitedAct"]] = relationship(back_populates="session", cascade="all, delete-orphan")


# ── 금지행위 ──────────────────────────────────────────────────────────────────
class ProhibitedAct(Base):
    __tablename__ = "prohibited_acts"

    id:                Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id:        Mapped[str]           = mapped_column(ForeignKey("analysis_sessions.id"), nullable=False)
    law_id:            Mapped[Optional[str]] = mapped_column(String(20))
    law_name:          Mapped[Optional[str]] = mapped_column(String(100))
    article:           Mapped[Optional[str]] = mapped_column(String(50))
    name:              Mapped[str]           = mapped_column(String(200))
    description:       Mapped[Optional[str]] = mapped_column(Text)
    subject:           Mapped[Optional[str]] = mapped_column(String(100))  # 행위 주체
    target:            Mapped[Optional[str]] = mapped_column(String(100))  # 금지 대상
    trigger_condition: Mapped[Optional[str]] = mapped_column(Text)
    exception:         Mapped[Optional[str]] = mapped_column(Text)
    priority:          Mapped[str]           = mapped_column(String(10), default="MEDIUM")  # HIGH|MEDIUM|LOW
    ai_generated:      Mapped[bool]          = mapped_column(Boolean, default=True)
    confirmed:         Mapped[bool]          = mapped_column(Boolean, default=False)
    created_at:        Mapped[datetime]      = mapped_column(DateTime, default=_now)

    session:      Mapped["AnalysisSession"] = relationship(back_populates="prohibited_acts")
    duty_mapping: Mapped[Optional["DutyMapping"]] = relationship(back_populates="prohibited_act", uselist=False, cascade="all, delete-orphan")


# ── 책무 매핑 ─────────────────────────────────────────────────────────────────
class DutyMapping(Base):
    __tablename__ = "duty_mappings"

    id:                Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    prohibited_act_id: Mapped[str]           = mapped_column(ForeignKey("prohibited_acts.id"), nullable=False, unique=True)
    first_duty:        Mapped[Optional[str]] = mapped_column(String(20))   # CPO, CISO …
    second_duty:       Mapped[Optional[str]] = mapped_column(String(20))
    third_duty:        Mapped[Optional[str]] = mapped_column(String(20))
    mapping_note:      Mapped[Optional[str]] = mapped_column(Text)
    ai_generated:      Mapped[bool]          = mapped_column(Boolean, default=True)
    confirmed:         Mapped[bool]          = mapped_column(Boolean, default=False)
    confirmed_at:      Mapped[Optional[datetime]] = mapped_column(DateTime)

    prohibited_act: Mapped["ProhibitedAct"] = relationship(back_populates="duty_mapping")
    business_rule:  Mapped[Optional["BusinessRule"]] = relationship(back_populates="duty_mapping", uselist=False, cascade="all, delete-orphan")


# ── 업무규칙 ──────────────────────────────────────────────────────────────────
class BusinessRule(Base):
    __tablename__ = "business_rules"

    id:               Mapped[str]            = mapped_column(String(36), primary_key=True, default=_uuid)
    duty_mapping_id:  Mapped[str]            = mapped_column(ForeignKey("duty_mappings.id"), nullable=False, unique=True)
    rule_code:        Mapped[Optional[str]]  = mapped_column(String(30))   # RULE-PIP-001
    name:             Mapped[str]            = mapped_column(String(200))
    description:      Mapped[Optional[str]]  = mapped_column(Text)
    trigger_condition:Mapped[Optional[str]]  = mapped_column(Text)
    actions:          Mapped[Optional[list]] = mapped_column(JSON)         # [str, ...]
    exceptions:       Mapped[Optional[list]] = mapped_column(JSON)
    system_guide:     Mapped[Optional[str]]  = mapped_column(Text)
    status:           Mapped[str]            = mapped_column(String(20), default="draft")
    # draft | reviewing | completed
    version:          Mapped[int]            = mapped_column(Integer, default=1)
    created_at:       Mapped[datetime]       = mapped_column(DateTime, default=_now)
    updated_at:       Mapped[datetime]       = mapped_column(DateTime, default=_now, onupdate=_now)

    duty_mapping: Mapped["DutyMapping"] = relationship(back_populates="business_rule")
    inspection_checks: Mapped[list["InspectionCheck"]] = relationship(back_populates="rule", cascade="all, delete-orphan")


# ── 이행점검 결과 ─────────────────────────────────────────────────────────────
class InspectionCheck(Base):
    __tablename__ = "inspection_checks"

    id:         Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    client_id:  Mapped[str]           = mapped_column(ForeignKey("clients.id"), nullable=False)
    rule_id:    Mapped[str]           = mapped_column(ForeignKey("business_rules.id"), nullable=False)
    period:     Mapped[str]           = mapped_column(String(7))    # YYYY-MM
    # 점검 결과: 적정 | 개선필요 | 해당없음 | 미점검
    result:     Mapped[Optional[str]] = mapped_column(String(20), default="미점검")
    # 점검 방식: 대면 | 비대면 | 해당없음
    method:     Mapped[Optional[str]] = mapped_column(String(20), default="대면")
    note:       Mapped[Optional[str]] = mapped_column(Text)
    checked_by: Mapped[Optional[str]] = mapped_column(String(100))
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime]      = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime]      = mapped_column(DateTime, default=_now, onupdate=_now)

    rule: Mapped["BusinessRule"] = relationship(back_populates="inspection_checks")


# ── 개선조치 ──────────────────────────────────────────────────────────────────
class ImprovementAction(Base):
    __tablename__ = "improvement_actions"

    id:             Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    client_id:      Mapped[str]           = mapped_column(ForeignKey("clients.id"), nullable=False)
    # 연계 출처: 이행점검에서 '개선필요' 발생 시 자동 생성, 또는 수동 등록
    check_id:       Mapped[Optional[str]] = mapped_column(ForeignKey("inspection_checks.id"))
    rule_id:        Mapped[Optional[str]] = mapped_column(ForeignKey("business_rules.id"))
    origin_period:  Mapped[str]           = mapped_column(String(7))   # 최초 발생 기간 YYYY-MM
    # 조치 내용
    title:          Mapped[str]           = mapped_column(String(200))
    cause:          Mapped[Optional[str]] = mapped_column(Text)         # 발생 원인
    action_plan:    Mapped[Optional[str]] = mapped_column(Text)         # 개선 계획
    action_result:  Mapped[Optional[str]] = mapped_column(Text)         # 조치 결과
    action_type:    Mapped[str]           = mapped_column(String(20), default="이행점검조치")
    # 이행점검조치 | 자율개선조치
    # 상태: 미완료 → 진행중 → 완료
    status:         Mapped[str]           = mapped_column(String(20), default="미완료")
    due_date:       Mapped[Optional[str]] = mapped_column(String(10))   # YYYY-MM-DD
    completed_at:   Mapped[Optional[datetime]] = mapped_column(DateTime)
    # 이월 추적: 완료 못 하고 다음 기간으로 넘어간 횟수
    carryover_count: Mapped[int]          = mapped_column(Integer, default=0)
    last_period:    Mapped[Optional[str]] = mapped_column(String(7))    # 마지막 이월 기간
    created_at:     Mapped[datetime]      = mapped_column(DateTime, default=_now)
    updated_at:     Mapped[datetime]      = mapped_column(DateTime, default=_now, onupdate=_now)


# ── 분기 보고서 ───────────────────────────────────────────────────────────────
class QuarterlyReport(Base):
    __tablename__ = "quarterly_reports"

    id:           Mapped[str]            = mapped_column(String(36), primary_key=True, default=_uuid)
    client_id:    Mapped[str]            = mapped_column(ForeignKey("clients.id"), nullable=False)
    quarter:      Mapped[str]            = mapped_column(String(7))    # 2026-Q1
    period_from:  Mapped[str]            = mapped_column(String(7))    # 2026-01
    period_to:    Mapped[str]            = mapped_column(String(7))    # 2026-03
    # 상태: 작성중 → 검토완료 → 결재완료
    status:       Mapped[str]            = mapped_column(String(20), default="작성중")
    # 집계 스냅샷 (확정 시점의 수치 보존)
    inspection_summary: Mapped[Optional[dict]] = mapped_column(JSON)
    improvement_summary: Mapped[Optional[dict]] = mapped_column(JSON)
    # 보고서 본문 메모
    note:         Mapped[Optional[str]]  = mapped_column(Text)
    # 검토/결재 이력
    reviewer:     Mapped[Optional[str]]  = mapped_column(String(100))
    reviewed_at:  Mapped[Optional[datetime]] = mapped_column(DateTime)
    approver:     Mapped[Optional[str]]  = mapped_column(String(100))
    approved_at:  Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at:   Mapped[datetime]       = mapped_column(DateTime, default=_now)
    updated_at:   Mapped[datetime]       = mapped_column(DateTime, default=_now, onupdate=_now)
