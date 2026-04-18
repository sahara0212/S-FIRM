"""
3단계: 법령 변경 × 책무구조 교차 분석 → 금지행위 추출 + 책임자 매핑
성능: haiku 모델 + 법령별 병렬 호출
"""
import json
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = """금융 컴플라이언스 전문가로서, 변경된 법령 조문에서 금지행위를 추출하고 담당 임원을 매핑하여 JSON 배열로만 반환하세요. 설명 텍스트 없이 JSON만 출력하세요."""

_PROMPT_TMPL = """## 변경 조문
{law_text}

## 임원 책무
{duty_text}

## 지시
각 조문에서 금지행위를 추출하고 담당 임원을 매핑하세요.
JSON 배열만 출력 (다른 텍스트 없음):
[{{"law_id":"","law_name":"","article":"","name":"","description":"","subject":"","target":"","trigger_condition":"","exception":"없음","priority":"HIGH|MEDIUM|LOW","first_duty":"","second_duty":"","third_duty":"","mapping_reason":""}}]

매핑 기준: CPO=개인정보·AI동의, CISO=정보보호·AI보안, CCO=준법감시·내부통제, CRO=위험관리, CDO=마이데이터·신용정보, CSO=소비자보호, CEO=전사거버넌스"""


def _build_law_text(law_diffs: list[dict]) -> str:
    parts = []
    for item in law_diffs:
        parts.append(
            f"[law_id={item['law_id']} | {item['law_name']} {item['article']}]\n"
            f"전: {item['before'][:300]}\n"
            f"후: {item['after'][:300]}"
        )
    return "\n\n".join(parts)


def _build_duty_text(executives: list[dict]) -> str:
    parts = []
    for e in executives:
        duties = e.get("duties") or []
        key_duties = []
        for d in duties[:3]:  # 핵심 책무 3개만
            desc = d.get("description", "") if isinstance(d, dict) else str(d)
            key_duties.append(desc[:80])
        parts.append(f"{e['role_code']}: " + " / ".join(key_duties))
    return "\n".join(parts)


def _parse_json_response(raw: str) -> list:
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    json_str = match.group(1).strip() if match else raw
    if not match:
        arr_match = re.search(r"(\[[\s\S]+\])", raw)
        json_str = arr_match.group(1).strip() if arr_match else raw

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


def _extract_for_law(
    client: anthropic.Anthropic,
    law_id: str,
    law_diffs: list[dict],
    duty_text: str,
) -> list[dict]:
    law_text = _build_law_text(law_diffs)
    message = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": _PROMPT_TMPL.format(law_text=law_text, duty_text=duty_text)
        }],
    )
    raw = message.content[0].text.strip()
    return _parse_json_response(raw)


def extract_prohibitions(law_diffs: list[dict], executives: list[dict]) -> list[dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=api_key)
    duty_text = _build_duty_text(executives)

    # 법령 ID별 그룹핑
    groups: dict[str, list[dict]] = defaultdict(list)
    for d in law_diffs:
        groups[d["law_id"]].append(d)

    all_results: list[dict] = []

    # 법령별 병렬 호출 (최대 6개 동시)
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(_extract_for_law, client, law_id, diffs, duty_text): (law_id, diffs)
            for law_id, diffs in groups.items()
        }
        for future in as_completed(futures):
            law_id, diffs = futures[future]
            try:
                items = future.result()
                # law_id 누락 시 보정
                law_name = diffs[0]["law_name"] if diffs else ""
                for item in items:
                    if not item.get("law_id"):
                        item["law_id"] = law_id
                    if not item.get("law_name"):
                        item["law_name"] = law_name
                all_results.extend(items)
            except Exception as e:
                print(f"[prohibition_extractor] {law_id} 실패: {e}")

    return all_results
