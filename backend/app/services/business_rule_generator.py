"""
4단계: 금지행위 + 책임자 매핑 → 구체적 내부 업무규칙 생성
성능: haiku 모델 + 법령별 병렬 호출
"""
import json
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = """금융회사 내부통제 전문가로서, 금지행위와 책임자 매핑을 기반으로 내부 업무규칙을 JSON 배열로만 생성하세요. 설명 텍스트 없이 JSON만 출력하세요."""

_PROMPT_TMPL = """## 금지행위 목록
{prohibition_text}

## 지시
각 금지행위에 대해 업무규칙을 생성하세요. JSON 배열만 출력:
[{{"prohibition_id":"","rule_code":"RULE-{prefix}-{start_seq}","name":"","description":"","trigger_condition":"","actions":["단계1","단계2","단계3"],"exceptions":[],"system_guide":""}}]

rule_code: RULE-{prefix}-001 형식, {start_seq}부터 순번"""

_LAW_PREFIX = {
    "pipa": "PIP", "aiba": "AIB", "fgsl": "FGS",
    "efsr": "EFS", "cipa": "CIP", "itna": "ITN",
}


def _build_prohibition_text(items: list[dict]) -> str:
    parts = []
    for p in items:
        m = p.get("mapping") or {}
        parts.append(
            f"[ID:{p['id']}] {p.get('law_name','')} {p.get('article','')}\n"
            f"금지행위: {p['name']}\n"
            f"설명: {p.get('description','')[:200]}\n"
            f"책임: {m.get('first_duty','')}>{m.get('second_duty','')}>{m.get('third_duty','')}"
        )
    return "\n\n".join(parts)


def _parse_json(raw: str) -> list:
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    json_str = match.group(1).strip() if match else raw
    if not match:
        arr = re.search(r"(\[[\s\S]+\])", raw)
        json_str = arr.group(1).strip() if arr else raw
    try:
        result = json.loads(json_str)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        last = json_str.rfind("},")
        if last > 0:
            try:
                result = json.loads(json_str[:last + 1] + "\n]")
                return result if isinstance(result, list) else []
            except json.JSONDecodeError:
                pass
        raise ValueError(f"JSON 파싱 실패: {raw[:300]}")


def _generate_for_group(
    client: anthropic.Anthropic,
    law_id: str,
    items: list[dict],
) -> list[dict]:
    prefix = _LAW_PREFIX.get(law_id, "RULE")
    prompt = _PROMPT_TMPL.format(
        prohibition_text=_build_prohibition_text(items),
        prefix=prefix,
        start_seq="001",
    )
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(msg.content[0].text.strip())


def generate_rules(prohibitions: list[dict]) -> list[dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=api_key)

    groups: dict[str, list[dict]] = defaultdict(list)
    for p in prohibitions:
        groups[p.get("law_id", "etc")].append(p)

    all_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_generate_for_group, client, law_id, items): law_id
            for law_id, items in groups.items()
        }
        for future in as_completed(futures):
            law_id = futures[future]
            try:
                all_results.extend(future.result())
            except Exception as e:
                print(f"[rule_generator] {law_id} 실패: {e}")

    return all_results
