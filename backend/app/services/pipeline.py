"""
S-FIRM 자율 분석 파이프라인 — LangGraph
법령수집 → 금지행위추출 → 업무규칙생성

그래프 구조:
  START → fetch_laws → extract → generate → END
                 ↘ error → END  (각 단계에서 오류 시 즉시 중단)
"""
import operator
from typing import TypedDict, Optional, Annotated

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.law_api import fetcher
from app.services.prohibition_extractor import extract_prohibitions
from app.services.business_rule_generator import generate_rules


# ── 파이프라인 상태 ──────────────────────────────────────────────────────────

class PipelineState(TypedDict):
    client_id: str
    session_id: str
    law_ids: list[str]
    executives: list[dict]
    # 각 단계 결과
    law_diffs: list[dict]
    prohibitions: list[dict]
    rules: list[dict]
    # 제어
    error: Optional[str]
    log: Annotated[list[str], operator.add]   # 각 노드가 append


# ── 노드 함수 ────────────────────────────────────────────────────────────────

def node_fetch_laws(state: PipelineState) -> dict:
    """법제처 API → 법령별 현행/직전 조문 diff 수집"""
    law_diffs: list[dict] = []

    for law_id in state["law_ids"]:
        try:
            data = fetcher.get_version_diff_data(law_id)
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

    if not law_diffs:
        return {
            "law_diffs": [],
            "error": "분석할 법령 변경 데이터가 없습니다.",
            "log": ["[법령수집] 변경 데이터 없음 — 파이프라인 중단"],
        }

    return {
        "law_diffs": law_diffs,
        "log": [f"[법령수집] {len(law_diffs)}개 조문 수집 완료"],
    }


def node_extract(state: PipelineState) -> dict:
    """Claude → 금지행위 추출 + 책임자 매핑"""
    try:
        raw = extract_prohibitions(state["law_diffs"], state["executives"])
    except Exception as e:
        return {"error": f"금지행위 추출 실패: {e}"}

    # generate_rules 가 기대하는 형식으로 정규화
    # (first/second/third_duty → mapping 딕셔너리 중첩)
    normalized: list[dict] = []
    for i, p in enumerate(raw):
        normalized.append({
            **p,
            "id": p.get("id") or f"p-{i}",
            "mapping": {
                "first_duty":  p.get("first_duty", ""),
                "second_duty": p.get("second_duty", ""),
                "third_duty":  p.get("third_duty", ""),
            },
        })

    return {
        "prohibitions": normalized,
        "log": [f"[금지행위추출] {len(normalized)}개 추출 완료"],
    }


def node_generate(state: PipelineState) -> dict:
    """Claude → 금지행위별 내부 업무규칙 생성"""
    try:
        rules = generate_rules(state["prohibitions"])
    except Exception as e:
        return {"error": f"업무규칙 생성 실패: {e}"}

    return {
        "rules": rules,
        "log": [f"[업무규칙생성] {len(rules)}개 생성 완료"],
    }


# ── 라우팅 ───────────────────────────────────────────────────────────────────

def _route(state: PipelineState) -> str:
    return END if state.get("error") else "continue"


# ── 그래프 빌드 ──────────────────────────────────────────────────────────────

def build_pipeline():
    g = StateGraph(PipelineState)

    g.add_node("fetch_laws", node_fetch_laws)
    g.add_node("extract",    node_extract)
    g.add_node("generate",   node_generate)

    g.set_entry_point("fetch_laws")
    g.add_conditional_edges("fetch_laws", _route, {"continue": "extract", END: END})
    g.add_conditional_edges("extract",    _route, {"continue": "generate", END: END})
    g.add_edge("generate", END)

    return g.compile(checkpointer=MemorySaver())


pipeline = build_pipeline()
