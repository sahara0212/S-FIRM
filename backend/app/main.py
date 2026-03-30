from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.services.law_api import fetcher
from backend.app.core.analyzer import analyzer

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def read_index(): return FileResponse('frontend/index.html')

@app.get("/api/v1/updates")
def get_updates():
    # 리얼 데이터를 가져와서 세종 방법론으로 분석
    raw_laws = fetcher.fetch_real_laws()
    results = []
    for l in raw_laws:
        analysis = analyzer.analyze(l)
        results.append({**l, **analysis})
    return results

@app.post("/api/v1/upload-context")
async def upload_context(file: UploadFile = File(...)):
    contents = await file.read()
    analyzer.set_context(contents.decode('utf-8'))
    return {"status": "success"}
