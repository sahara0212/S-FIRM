"""고객사 CRUD + 분석 세션 목록"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Client, AnalysisSession

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])


# ── Pydantic 스키마 ────────────────────────────────────────────────────────────
class ClientCreate(BaseModel):
    name: str
    industry: Optional[str] = None
    note: Optional[str] = None

class ClientOut(BaseModel):
    id: str
    name: str
    industry: Optional[str]
    note: Optional[str]
    created_at: datetime
    session_count: int = 0

    class Config:
        from_attributes = True

class SessionCreate(BaseModel):
    label: str
    period_type: Optional[str] = None
    period_from: Optional[str] = None
    period_to:   Optional[str] = None
    law_snapshot: Optional[dict] = None
    note: Optional[str] = None

class SessionOut(BaseModel):
    id: str
    client_id: str
    label: str
    period_type: Optional[str]
    period_from: Optional[str]
    period_to:   Optional[str]
    status: str
    created_at: datetime
    confirmed_at: Optional[datetime]
    prohibited_act_count: int = 0

    class Config:
        from_attributes = True


# ── 고객사 CRUD ────────────────────────────────────────────────────────────────
@router.get("", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    clients = db.query(Client).order_by(Client.created_at.desc()).all()
    result = []
    for c in clients:
        out = ClientOut.model_validate(c)
        out.session_count = len(c.sessions)
        result.append(out)
    return result


@router.post("", response_model=ClientOut, status_code=201)
def create_client(body: ClientCreate, db: Session = Depends(get_db)):
    client = Client(**body.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db)):
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="고객사를 찾을 수 없습니다.")
    out = ClientOut.model_validate(c)
    out.session_count = len(c.sessions)
    return out


@router.put("/{client_id}", response_model=ClientOut)
def update_client(client_id: str, body: ClientCreate, db: Session = Depends(get_db)):
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="고객사를 찾을 수 없습니다.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return ClientOut.model_validate(c)


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: str, db: Session = Depends(get_db)):
    c = db.get(Client, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="고객사를 찾을 수 없습니다.")
    db.delete(c)
    db.commit()


# ── 분석 세션 ──────────────────────────────────────────────────────────────────
@router.get("/{client_id}/sessions", response_model=list[SessionOut])
def list_sessions(client_id: str, db: Session = Depends(get_db)):
    sessions = (
        db.query(AnalysisSession)
        .filter(AnalysisSession.client_id == client_id)
        .order_by(AnalysisSession.created_at.desc())
        .all()
    )
    result = []
    for s in sessions:
        out = SessionOut.model_validate(s)
        out.prohibited_act_count = len(s.prohibited_acts)
        result.append(out)
    return result


@router.post("/{client_id}/sessions", response_model=SessionOut, status_code=201)
def create_session(client_id: str, body: SessionCreate, db: Session = Depends(get_db)):
    if not db.get(Client, client_id):
        raise HTTPException(status_code=404, detail="고객사를 찾을 수 없습니다.")
    session = AnalysisSession(client_id=client_id, **body.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionOut.model_validate(session)


@router.get("/{client_id}/sessions/{session_id}", response_model=SessionOut)
def get_session(client_id: str, session_id: str, db: Session = Depends(get_db)):
    s = db.get(AnalysisSession, session_id)
    if not s or s.client_id != client_id:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    out = SessionOut.model_validate(s)
    out.prohibited_act_count = len(s.prohibited_acts)
    return out
