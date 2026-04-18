"""
문서 업로드 → 텍스트 추출 → Claude 책무구조 파싱 → DB 저장
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import asyncio
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Client, ClientDocument, DutyStructure
from app.services.doc_parser import extract_text
from app.services.duty_extractor import extract_duty_structure

router = APIRouter(prefix="/api/v1/clients/{client_id}", tags=["documents"])

ALLOWED_EXT = {".pptx", ".docx", ".xlsx", ".xls", ".txt", ".pdf"}
MAX_SIZE_MB = 10


# ── 문서 업로드 ───────────────────────────────────────────────────────────────
@router.post("/documents")
async def upload_document(
    client_id: str,
    file: UploadFile = File(...),
    doc_type: str = Form(default="other"),
    # doc_type: duty_structure | duty_description | duty_status | other
    db: Session = Depends(get_db),
):
    if not db.get(Client, client_id):
        raise HTTPException(404, "고객사를 찾을 수 없습니다.")

    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"지원하지 않는 파일 형식입니다: {ext}")

    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"파일 크기가 {MAX_SIZE_MB}MB를 초과합니다.")

    # 텍스트 추출
    try:
        text = extract_text(filename, content)
    except Exception as e:
        raise HTTPException(422, f"파일 파싱 실패: {e}")

    doc = ClientDocument(
        client_id=client_id,
        doc_type=doc_type,
        filename=filename,
        content_text=text,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "id":          doc.id,
        "filename":    doc.filename,
        "doc_type":    doc.doc_type,
        "char_count":  len(text),
        "uploaded_at": doc.uploaded_at,
        "preview":     text[:300] + ("…" if len(text) > 300 else ""),
    }


# ── 문서 목록 ─────────────────────────────────────────────────────────────────
@router.get("/documents")
def list_documents(client_id: str, db: Session = Depends(get_db)):
    if not db.get(Client, client_id):
        raise HTTPException(404, "고객사를 찾을 수 없습니다.")
    docs = (
        db.query(ClientDocument)
        .filter(ClientDocument.client_id == client_id)
        .order_by(ClientDocument.uploaded_at.desc())
        .all()
    )
    return [
        {
            "id":          d.id,
            "filename":    d.filename,
            "doc_type":    d.doc_type,
            "char_count":  len(d.content_text or ""),
            "uploaded_at": d.uploaded_at,
        }
        for d in docs
    ]


# ── 책무구조 추출 (Claude) ────────────────────────────────────────────────────
@router.post("/duty-structure")
async def parse_duty_structure(
    client_id: str,
    body: dict,
    db: Session = Depends(get_db),
):
    """
    body: { "doc_ids": ["uuid1", "uuid2", ...] }
    여러 문서를 합쳐서 Claude로 책무구조 추출
    """
    if not db.get(Client, client_id):
        raise HTTPException(404, "고객사를 찾을 수 없습니다.")

    doc_ids = body.get("doc_ids", [])
    if not doc_ids:
        raise HTTPException(400, "분석할 문서 ID를 하나 이상 지정하세요.")

    # 문서 텍스트 병합
    combined = []
    for doc_id in doc_ids:
        doc = db.get(ClientDocument, doc_id)
        if not doc or doc.client_id != client_id:
            raise HTTPException(404, f"문서를 찾을 수 없습니다: {doc_id}")
        if doc.content_text:
            combined.append(f"=== {doc.filename} ({doc.doc_type}) ===\n{doc.content_text}")

    if not combined:
        raise HTTPException(422, "추출된 텍스트가 없습니다.")

    merged_text = "\n\n".join(combined)

    # Claude로 책무구조 추출 (동기 함수를 스레드풀에서 실행해 이벤트루프 블로킹 방지)
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, extract_duty_structure, merged_text
        )
    except Exception as e:
        raise HTTPException(500, f"책무구조 추출 실패: {e}")

    # 기존 active 구조 비활성화
    db.query(DutyStructure).filter(
        DutyStructure.client_id == client_id,
        DutyStructure.is_active == True,
    ).update({"is_active": False})

    # 새 구조 저장
    ds = DutyStructure(
        client_id=client_id,
        source_doc=doc_ids[0],
        executives=result.get("executives", []),
        org_tree=result.get("org_tree", {}),
        is_active=True,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    return {
        "id":            ds.id,
        "company_name":  result.get("company_name"),
        "summary":       result.get("summary"),
        "executive_count": len(ds.executives or []),
        "executives":    ds.executives,
        "org_tree":      ds.org_tree,
        "parsed_at":     ds.parsed_at,
    }


# ── 현재 책무구조 조회 ────────────────────────────────────────────────────────
@router.get("/duty-structure")
def get_duty_structure(client_id: str, db: Session = Depends(get_db)):
    if not db.get(Client, client_id):
        raise HTTPException(404, "고객사를 찾을 수 없습니다.")
    ds = (
        db.query(DutyStructure)
        .filter(DutyStructure.client_id == client_id, DutyStructure.is_active == True)
        .order_by(DutyStructure.parsed_at.desc())
        .first()
    )
    if not ds:
        raise HTTPException(404, "파싱된 책무구조가 없습니다. 문서를 먼저 업로드하세요.")
    return {
        "id":              ds.id,
        "executive_count": len(ds.executives or []),
        "executives":      ds.executives,
        "org_tree":        ds.org_tree,
        "parsed_at":       ds.parsed_at,
    }
