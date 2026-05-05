# S-FIRM — Compliance Control Board

## 프로젝트 개요

**S-FIRM**은 법무법인(유) 세종의 내부통제 관리 방법론을 기반으로 한 금융규제 관제 플랫폼입니다.

### 핵심 사상

- **레퍼런스 구현체**: KB라이프생명의 책무구조도를 기반으로 설계된 시드 데이터와 업무규칙 체계를 기본 템플릿으로 사용
- **플랫폼 지향**: 단일 고객사 전용 툴이 아니라, **다수의 금융회사가 자사 책무구조도를 업로드하면 맞춤형 컴플라이언스 운영 서비스를 제공하는 SaaS 플랫폼**으로 진화 중
- **AI 어시스트**: Claude API를 활용한 법령 분석, 업무규칙 자동 생성, 이행점검 초안 생성
- **단방향 조회 → 양방향 운영**: 기존의 데이터 시각화 보드에서, 점검 결과 입력·개선조치 등록·보고서 관리 등 실제 운영 워크플로우로 확장

---

## 제품 전략 (Product Strategy)

### 현재 상태 (v2.0)
- KB라이프 책무구조도 기반 시드 데이터로 즉시 작동
- 법령 모니터링(실시간 법제처 API) → 금지행위 추출 → 책무 매핑 → 업무규칙 생성 파이프라인
- 단일 고객사(Client) 뷰 기반 운영

### 목표 상태 (v3.0+)
- **멀티테넌트 플랫폼**: 금융회사별 책무구조도 문서 업로드 → AI 파싱 → 맞춤형 운영 보드 자동 생성
- **이행점검 운영**: 업무규칙 목록 기반 월별 이행점검 결과 입력 및 집계
- **개선조치 관리**: 점검 결과 → 개선조치계획 → 이행 추적 → 완료 확인 사이클
- **보고서 라이프사이클**: 월별 집계 → 분기 보고서 → 경영진/이사회 보고 상태 추적
- **D-Day 대시보드**: 점검 마감일, 결재 대기 건수, 개선조치 미완료 누적 현황

### 벤치마크
- **KB라이프**: 자사 책무구조도 → 업무규칙 파이프라인 (현재 구현의 기반)
- **한화손보 책무구조도 관리시스템**: 이행점검 현황, 개선조치 관리, 분기 보고서, 대시보드 구성 (기능 보강 참조)
- 한화손보의 비즈니스 프로세스를 그대로 복제하는 것이 아니라, **한화의 운영 성숙도를 참조해 KB라이프 사상에 필요한 기능만 추가**

---

## 아키텍처

### 기술 스택
- **Backend**: FastAPI (Python 3.14), SQLAlchemy ORM, SQLite (dev) / PostgreSQL (prod)
- **Frontend**: 단일 HTML 파일 (`frontend/index.html`, ~2300줄), Tailwind CSS CDN, Vanilla JS
- **AI**: Anthropic Claude API (`claude-haiku-4-5` 기본, `claude-sonnet-4-6` 고부하 분석)
- **외부 API**: 국가법령정보센터 OpenAPI (`OPEN_API_KEY`)
- **배포**: Railway (`railway.toml`, `Procfile`, `runtime.txt`)

### 디렉토리 구조
```
S-FIRM/
├── frontend/
│   └── index.html          # 전체 프론트엔드 (탭 기반 SPA)
├── backend/
│   └── app/
│       ├── main.py         # FastAPI 앱 진입점, 라우터 등록
│       ├── api/
│       │   ├── clients.py      # 고객사 CRUD + 분석 세션
│       │   ├── documents.py    # 문서 업로드/파싱
│       │   └── analysis.py     # 금지행위·책무매핑·업무규칙 API
│       ├── core/
│       │   └── analyzer.py     # 법령 분석 코어 로직
│       ├── db/
│       │   ├── database.py     # SQLAlchemy 엔진/세션
│       │   ├── models.py       # ORM 모델 (아래 참조)
│       │   └── seed.py         # KB라이프 초기 시드 데이터
│       └── services/
│           ├── law_api.py              # 법제처 API 연동
│           ├── business_rule_generator.py  # 업무규칙 AI 생성
│           ├── duty_extractor.py       # 책무 추출
│           ├── prohibition_extractor.py # 금지행위 추출
│           └── doc_parser.py           # 문서 파싱
├── data/sfirm.db           # SQLite DB (Railway 배포용)
├── .env                    # ANTHROPIC_API_KEY, OPEN_API_KEY
└── CLAUDE.md               # 이 파일
```

### DB 모델 구조
```
Client (고객사/금융회사)
  └── ClientDocument (업로드 문서: 책무구조도, 업무기술서 등)
  └── DutyStructure (파싱된 임원-책무 매핑 JSON)
  └── AnalysisSession (분석 세션: 기간·상태 추적)
        └── ProhibitedAct (금지행위 목록)
              └── DutyMapping (책무 매핑)
                    └── BusinessRule (업무규칙)
```

**추가 예정 모델 (v3.0)**:
- `InspectionCheck` — 업무규칙별 월별 이행점검 결과 (적정/개선필요/해당없음, 대면/비대면)
- `ImprovementAction` — 개선조치계획 + 이행결과 + 이월 추적
- `QuarterlyReport` — 분기 보고서 상태 관리 (작성중→완료→결재완료)

---

## 프론트엔드 탭 구조

| 탭 ID | 탭명 | 설명 |
|-------|------|------|
| `monitor` | 법령 모니터링 | 법제처 실시간 법령 변경 추적 |
| `prohibit` | 금지행위 추출 | AI 기반 금지행위 목록 생성 |
| `duty` | 채무 매핑 | 임원별 책무-금지행위 연계 |
| `rules` | 업무규칙 | RULE-XXX-NNN 코드 기반 명세서 |
| `inspection` | 이행점검 (예정) | 월별 점검 결과 입력 및 현황 |
| `improvement` | 개선조치 (예정) | 개선조치 등록·추적·이월 |

---

## 현재 구현된 핵심 API

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/law-monitoring` | 법령 변경 실시간 조회 |
| GET | `/api/v1/law-diff/{law_id}` | 법령 버전 diff |
| POST | `/api/v1/law-analyze` | Claude AI 분석 (SSE 스트리밍) |
| GET/POST | `/api/v1/clients` | 고객사 CRUD |
| GET/POST | `/api/v1/clients/{id}/sessions` | 분석 세션 관리 |
| POST | `/api/v1/documents/upload` | 문서 업로드 + AI 파싱 |
| GET | `/api/v1/analysis/business-rules` | 업무규칙 목록 |
| POST | `/api/v1/analysis/generate-rules` | 업무규칙 AI 생성 |

---

## 개발 원칙

### 플랫폼 설계 원칙
1. **모든 데이터는 client_id로 격리**: 새 고객사 추가 시 기존 데이터에 영향 없음
2. **KB라이프 시드는 기본 템플릿**: `seed.py`의 KB라이프 데이터는 삭제하지 말 것, 플랫폼의 데모/레퍼런스 역할
3. **한화 UX 패턴 참조, 비즈니스 로직은 KB 사상 유지**: 이행점검 흐름은 KB라이프 책무구조를 기준으로 구현
4. **확장성 우선**: 새 금융회사 추가 = 새 Client 레코드 + 문서 업로드 + AI 파싱, 별도 코드 불필요

### 코딩 원칙
- 프론트엔드는 `frontend/index.html` 단일 파일 유지 (SPA, Vanilla JS)
- 새 기능은 새 탭 또는 기존 탭 내 섹션으로 추가
- 새 API는 `backend/app/api/` 에 별도 라우터 파일로 분리
- 새 DB 모델은 `backend/app/db/models.py` 에 추가 후 `init_db()` 자동 반영
- AI 호출은 Haiku (빠른 생성) / Sonnet (정밀 분석) 용도 구분
- 스트리밍 응답은 SSE(Server-Sent Events) 패턴 유지

### 절대 하지 말 것
- `seed.py`의 KB라이프 시드 데이터 삭제
- `frontend/index.html`을 여러 파일로 분리 (단일 파일 배포 구조 유지)
- 기존 API 엔드포인트 경로 변경 (Railway 배포 중)
- `.env` 파일 커밋

---

## 환경 변수

| 변수명 | 설명 | 필수 |
|--------|------|------|
| `ANTHROPIC_API_KEY` | Claude API 키 | 필수 |
| `OPEN_API_KEY` | 법제처 OpenAPI 키 (`sahara0212`) | 필수 |
| `DATABASE_URL` | PostgreSQL URL (Railway 자동 주입) | 선택 |

---

## 로컬 실행

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# 또는
cd /Volumes/Workspace\ 990\ pro/Sejong/Projects/S-FIRM
source venv_sejong/bin/activate
uvicorn backend.app.main:app --reload
```

---

## 다음 구현 목표 (v3.0 Roadmap)

### Phase 1 — 대시보드 고도화
- [ ] D-Day 카운트다운 (다음 이행점검 마감까지)
- [ ] 현황 카드에 부서별/항목별 완료율 추가
- [ ] 결재대기 건수 실시간 카운터

### Phase 2 — 이행점검 탭
- [ ] `InspectionCheck` 모델 추가
- [ ] 업무규칙별 월별 점검 결과 입력 UI (적정/개선필요/해당없음)
- [ ] 점검 방식 구분 (대면/비대면/미점검)
- [ ] 부서별 완료율 차트

### Phase 3 — 개선조치 관리 탭
- [ ] `ImprovementAction` 모델 추가
- [ ] 개선필요 항목 자동 연계
- [ ] 완료/미완료/이월(carry-over) 추적

### Phase 4 — 분기 보고서
- [ ] `QuarterlyReport` 모델 추가
- [ ] 월별 집계 → 분기 롤업 통계
- [ ] 보고서 상태 관리 (작성중→완료→결재완료)

### Phase 5 — 플랫폼 완성
- [ ] 고객사 온보딩 위자드 (책무구조도 업로드 → AI 파싱 → 즉시 운영 대시보드)
- [ ] 금융회사 유형별 템플릿 (생보/손보/은행/증권)
- [ ] 멀티테넌트 접근 제어
