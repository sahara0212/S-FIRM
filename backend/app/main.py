import os
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import anthropic
from app.services.law_api import fetcher
from app.core.analyzer import analyzer
from app.db.database import init_db
from app.db.seed import seed_initial_data
from app.api import clients as clients_router
from app.api import documents as documents_router
from app.api import analysis as analysis_router

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")), override=True)

# Resolve paths relative to this file (works regardless of cwd)
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_FRONTEND_INDEX = os.path.join(_BASE_DIR, "frontend", "index.html")

app = FastAPI(title="S-FIRM Compliance API", version="2.0")

# DB 테이블 생성 + 초기 데이터 시드 (앱 시작 시 1회)
init_db()
seed_initial_data()

# 라우터 등록
app.include_router(clients_router.router)
app.include_router(documents_router.router)
app.include_router(analysis_router.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_index():
    return FileResponse(_FRONTEND_INDEX)


@app.get("/api/v1/law-monitoring")
def get_law_monitoring(
    days: int = Query(default=7, ge=1, le=365),
    from_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    to_date:   Optional[str] = Query(default=None, description="YYYY-MM-DD"),
):
    """
    법제처 OpenAPI 실데이터 기반 핵심/유관 법령 모니터링.
    - days: 최근 N일 (기본 7)
    - from_date / to_date: 직접 기간 지정 (YYYY-MM-DD), 입력 시 days 무시
    """
    try:
        core    = fetcher.fetch_monitoring_data(days=days, from_date=from_date, to_date=to_date)
        related = fetcher.fetch_related_data(days=days, from_date=from_date, to_date=to_date)
        return JSONResponse({
            "status":  "live",
            "core":    core,
            "related": related,
            "fetched_at": core[next(iter(core))]["last_fetched"] if core else "",
        })
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500,
        )


# ── 법령 버전 diff ────────────────────────────────────────────────────────
@app.get("/api/v1/law-diff/{law_id}")
def get_law_diff(law_id: str):
    """현행 ↔ 직전 버전 조문 비교"""
    try:
        data = fetcher.get_version_diff_data(law_id)
        if "error" in data:
            return JSONResponse(data, status_code=404)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── Claude AI 분석 (SSE 스트리밍) ────────────────────────────────────────
@app.post("/api/v1/law-analyze")
async def analyze_law(body: dict):
    """
    법령 변경 내용을 Claude로 분석. SSE 스트리밍으로 응답.
    body: { law_name, revision_type, curr_date, prev_date, diffs: [...] }
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse({"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."}, status_code=503)

    law_name     = body.get("law_name", "")
    revision_type = body.get("revision_type", "")
    curr_date    = body.get("curr_date", "")
    prev_date    = body.get("prev_date", "")
    diffs        = body.get("diffs", [])

    diff_text = "\n\n".join(
        f"[{d['article']} — {d.get('change_type','개정')}]\n"
        f"■ 이전:\n{d['before'][:600]}\n\n"
        f"■ 변경 후:\n{d['after'][:600]}"
        for d in diffs[:10]
    ) or "(변경 내용 없음)"

    prompt = f"""당신은 금융 컴플라이언스 전문가입니다.
아래는 '{law_name}'의 {revision_type} 내용입니다 ({prev_date} → {curr_date} 시행).

{diff_text}

다음 항목을 **한국어**로 분석해주세요:

## 1. 핵심 변경 요약
주요 개정 내용을 3~5개 불릿으로 간결하게 정리하세요.

## 2. 금융회사 영향도
이 개정이 금융회사(특히 준법감시 부서)에 미치는 영향을 서술하세요.

## 3. 즉시 조치 사항
담당 임원/부서가 지금 당장 해야 할 행동을 우선순위 순으로 나열하세요.

## 4. 위험 등급
HIGH / MEDIUM / LOW 중 하나를 선택하고 이유를 한 줄로 설명하세요."""

    client = anthropic.Anthropic(api_key=api_key)

    def stream():
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        ) as s:
            for text in s.text_stream:
                yield f"data: {text}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── 기존 엔드포인트 유지 (하위호환) ──────────────────────────────────────
@app.get("/api/v1/updates")
def get_updates():
    raw_laws = fetcher.fetch_monitoring_data()
    results = []
    for k, v in raw_laws.items():
        analysis = analyzer.analyze({"title": v["name"], "type": "개정"})
        results.append({**v, **analysis})
    return results


@app.post("/api/v1/upload-context")
async def upload_context(file: UploadFile = File(...)):
    contents = await file.read()
    analyzer.set_context(contents.decode("utf-8"))
    return {"status": "success"}
