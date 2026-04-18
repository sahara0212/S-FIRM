"""
3단계: 법령 변경 × 책무구조 교차 분석 → 금지행위 추출 + 책임자 매핑
"""
import json
import os
import re

import anthropic

_SYSTEM = """당신은 금융 컴플라이언스 전문가입니다.
변경된 법령 조문과 회사의 책무구조를 교차 분석해
금지행위 목록과 담당 임원 매핑을 JSON으로 반환하세요.
반드시 유효한 JSON 배열만 출력하고, 설명 텍스트는 포함하지 마세요."""

_PROMPT_TMPL = """## 변경된 법령 조문

{law_text}

---

## 회사 책무구조 (임원-책무 매핑)

{duty_text}

---

## 지시사항

위 법령 변경 내용을 분석하여 각 조문에서 발생하는 **금지행위**를 추출하고,
회사의 책무구조에서 가장 적합한 1차·2차·3차 책임 임원을 매핑하세요.

출력 형식 — JSON 배열을 엄격히 준수하세요:
[
  {{
    "law_id":            "법령 ID (pipa/cipa/aiba/efsr/itna/fgsl 등)",
    "law_name":          "법령명",
    "article":           "조문번호 (예: 제15조 제1항)",
    "name":              "금지행위명 (간결하고 명확하게)",
    "description":       "금지행위 상세 설명 (2~3문장)",
    "subject":           "행위 주체 (누가 지켜야 하는가)",
    "target":            "금지 대상 행위",
    "trigger_condition": "이 금지가 발동되는 조건",
    "exception":         "예외 사항 (없으면 '없음')",
    "priority":          "HIGH 또는 MEDIUM 또는 LOW",
    "first_duty":        "1차 책임 임원 role_code (CCO/CRO/CISO/CPO/CDO/CSO/CEO 중)",
    "second_duty":       "2차 책임 임원 role_code",
    "third_duty":        "3차 책임 임원 role_code (보통 CEO)",
    "mapping_reason":    "이 임원에게 매핑한 이유 (책무 연계 근거)"
  }}
]

매핑 기준:
- CPO: 개인정보·AI 자동화 결정·데이터 처리 관련
- CISO: 정보보호·AI 보안·전자금융 관련
- CCO: 법령준수·내부통제·준법감시 관련
- CRO: 위험관리·리스크 평가 관련
- CDO: 마이데이터·신용정보·데이터 거버넌스 관련
- CSO: 소비자보호·이의신청 관련
- CEO: 전사 거버넌스·AI 위원회·최종 책임

법령 조문 1개에서 여러 금지행위가 도출될 수 있습니다."""


def _build_law_text(law_diffs: list[dict]) -> str:
    """법령 diff 데이터 → 프롬프트용 텍스트"""
    parts = []
    for item in law_diffs:
        parts.append(
            f"### {item['law_name']} {item['article']}"
            + (f" ({item.get('change_type', '개정')})" )
            + f"\n**변경 전:** {item['before'][:500]}"
            + f"\n**변경 후:** {item['after'][:500]}"
        )
    return "\n\n".join(parts)


def _build_duty_text(executives: list[dict]) -> str:
    """임원 책무 데이터 → 프롬프트용 텍스트"""
    parts = []
    for e in executives:
        duties = e.get("duties") or []
        duty_lines = []
        for d in duties:
            if isinstance(d, dict):
                duty_lines.append(f"  - {d.get('description', '')}")
            else:
                duty_lines.append(f"  - {d}")
        parts.append(
            f"**{e['role']} ({e['role_code']})**\n" + "\n".join(duty_lines)
        )
    return "\n\n".join(parts)


def _parse_json_response(raw: str) -> list:
    """Claude 응답에서 JSON 배열 추출 + 잘린 경우 복구"""
    # ① ```json ... ``` 블록 추출 시도
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    if match:
        json_str = match.group(1).strip()
    else:
        arr_match = re.search(r"(\[[\s\S]+\])", raw)
        json_str = arr_match.group(1).strip() if arr_match else raw

    try:
        result = json.loads(json_str)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        last = json_str.rfind("},")
        if last > 0:
            recovered = json_str[:last + 1] + "\n]"
            try:
                result = json.loads(recovered)
                return result if isinstance(result, list) else []
            except json.JSONDecodeError:
                pass
        raise ValueError(f"JSON 파싱 실패\n원문:\n{raw[:400]}")


def _extract_for_law(
    client: anthropic.Anthropic,
    law_diffs: list[dict],
    duty_text: str,
) -> list[dict]:
    """단일 법령(또는 소수 조문) → Claude 호출 → 금지행위 리스트"""
    law_text = _build_law_text(law_diffs)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": _PROMPT_TMPL.format(law_text=law_text, duty_text=duty_text)
        }],
    )
    raw = message.content[0].text.strip()
    return _parse_json_response(raw)


def extract_prohibitions(law_diffs: list[dict], executives: list[dict]) -> list[dict]:
    """
    law_diffs: [{ law_id, law_name, article, change_type, before, after }, ...]
    executives: DutyStructure.executives 리스트
    → [{ law_id, law_name, article, name, description, subject, target,
          trigger_condition, exception, priority,
          first_duty, second_duty, third_duty, mapping_reason }, ...]

    법령별로 분리 호출해 max_tokens 초과를 방지합니다.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=api_key)
    duty_text = _build_duty_text(executives)

    # 법령 ID 기준으로 그룹핑
    from collections import defaultdict
    groups: dict[str, list[dict]] = defaultdict(list)
    for d in law_diffs:
        groups[d["law_id"]].append(d)

    all_results: list[dict] = []
    for law_id, diffs in groups.items():
        # 조문이 많으면 최대 8개씩 분할 (토큰 초과 방지)
        CHUNK = 8
        for i in range(0, len(diffs), CHUNK):
            chunk = diffs[i:i + CHUNK]
            try:
                items = _extract_for_law(client, chunk, duty_text)
                all_results.extend(items)
            except Exception as e:
                # 일부 실패해도 나머지는 계속
                print(f"[prohibition_extractor] {law_id} chunk {i//CHUNK} 실패: {e}")
                continue

    return all_results
