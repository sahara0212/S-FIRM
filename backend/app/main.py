import os
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.services.law_api import fetcher
from backend.app.core.analyzer import analyzer

# Resolve paths relative to this file (works regardless of cwd)
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_FRONTEND_INDEX = os.path.join(_BASE_DIR, "frontend", "index.html")

app = FastAPI(title="S-FIRM Compliance API", version="2.0")

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
def get_law_monitoring():
    """
    법제처 OpenAPI 실데이터 기반 핵심/유관 법령 모니터링.
    프론트엔드 LAW_CHANGES 형식과 동일한 구조로 반환.
    """
    try:
        core    = fetcher.fetch_monitoring_data()
        related = fetcher.fetch_related_data()
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
