"""
Claude를 사용해 업로드 문서에서 임원-책무 구조 추출
입력: 파싱된 텍스트 (pptx/docx/xlsx 혼합 가능)
출력: {executives: [...], org_tree: {...}}

전략:
  - 문서가 80K자 이하이면 전체를 단일 호출로 처리
  - 80K자 초과이면 청크별 추출 후 병합 호출
"""
import json
import os
import re

import anthropic

# Claude Sonnet 4.6 컨텍스트: ~200K 토큰 ≈ 한글 기준 약 80K자 안전 사용
_SINGLE_PASS_LIMIT = 80_000
_CHUNK_SIZE        = 30_000   # 청크 분할 시 각 청크 크기

_SYSTEM = """당신은 금융회사 책무구조도 분석 전문가입니다.
업로드된 문서 텍스트에서 임원별 책무 구조를 추출해 JSON으로 반환하세요.
반드시 유효한 JSON만 출력하고, 설명 텍스트·주석은 포함하지 마세요."""

_PROMPT_FULL = """아래는 금융회사의 책무구조 관련 문서 전체 내용입니다.
(책무기술서·책무체계도·책무현황표 등이 혼합되어 있을 수 있습니다)

---
{text}
---

## 추출 지침

1. **임원(직책) 식별**
   - 직책명(대표이사, 준법감시인, CRO, CPO 등)과 성명을 최대한 추출
   - 문서가 A/B/C/D 같은 내부 코드 체계를 사용하는 경우, 코드와 함께 실제 직책명도 매핑
   - 지배구조법상 지정 책임자(A레벨), 금융영업 담당(B레벨), 경영관리 담당(C레벨), 공통(D레벨) 구조를 인식

2. **책무 코드 해석**
   - A1, A2 … / B1, B2 … / C1, C2 … 같은 코드가 있으면 각 코드의 실제 내용(책무명)을 함께 기재
   - 책무 설명은 문서에 나온 원문 그대로 사용

3. **출력 형식** — 아래 JSON 스키마를 엄격히 준수
{{
  "company_name": "회사명 또는 null",
  "duty_code_system": "ABC" | "standard" | "mixed",
  "executives": [
    {{
      "role":      "직책명 (예: 대표이사, 준법감시인, A레벨 지정책임자)",
      "role_code": "문서 내 코드 또는 표준 영문코드 (예: A, B, CEO, CCO)",
      "std_code":  "표준 영문코드로 매핑 가능하면 기재 (CEO/CCO/CRO/CPO/CISO/CDO/CFO), 불가 시 null",
      "level":     3,
      "name":      "성명 또는 null",
      "duties": [
        {{"code": "A1", "description": "책무 원문 내용"}},
        {{"code": "A2", "description": "책무 원문 내용"}}
      ],
      "parent_role": "상위 role_code 또는 null"
    }}
  ],
  "org_tree": {{
    "A": ["B", "C"],
    "B": ["D"]
  }},
  "summary": "책무구조 전체 요약 2~3문장"
}}

executives 배열은 레벨 높은 순(3→1)으로 정렬하세요.
실제 문서에 있는 임원/직책만 포함하고, 없는 직책은 추가하지 마세요."""


_PROMPT_CHUNK = """아래는 금융회사 책무 문서의 일부(청크 {idx}/{total})입니다.

---
{text}
---

이 청크에서 **임원 직책, 성명, 책무 코드, 책무 내용**만 추출해 JSON 배열로 반환하세요.
없으면 빈 배열 []을 반환하세요.

[
  {{
    "role": "직책명",
    "role_code": "코드",
    "name": "성명 또는 null",
    "duties": [{{"code": "A1", "description": "책무 내용"}}]
  }}
]"""


_PROMPT_MERGE = """아래는 여러 청크에서 추출한 임원-책무 데이터입니다.

{chunks_json}

중복을 제거하고 동일 직책을 합쳐 아래 최종 JSON을 완성해주세요.

{{
  "company_name": "회사명 또는 null",
  "duty_code_system": "ABC" | "standard" | "mixed",
  "executives": [
    {{
      "role": "직책명",
      "role_code": "문서 코드",
      "std_code": "표준 영문코드 또는 null",
      "level": 3,
      "name": "성명 또는 null",
      "duties": [{{"code": "코드", "description": "책무 내용"}}],
      "parent_role": "상위 role_code 또는 null"
    }}
  ],
  "org_tree": {{}},
  "summary": "책무구조 전체 요약 2~3문장"
}}"""


def _call_claude(client: anthropic.Anthropic, prompt: str, max_tokens: int = 4096) -> str:
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _parse_json(raw: str) -> dict | list:
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
    json_str = match.group(1).strip() if match else raw
    return json.loads(json_str)


def extract_duty_structure(text: str) -> dict:
    """문서 텍스트 → 임원-책무 구조 JSON"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=api_key)

    if len(text) <= _SINGLE_PASS_LIMIT:
        # ── 단일 호출 (전체 문서를 한 번에) ─────────────────────────────
        raw = _call_claude(client, _PROMPT_FULL.format(text=text), max_tokens=4096)
        try:
            return _parse_json(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 파싱 실패: {e}\n원문:\n{raw[:400]}")

    else:
        # ── 청크 분할 → 병합 (문서가 80K자 초과인 경우) ──────────────────
        chunks = [text[i:i + _CHUNK_SIZE] for i in range(0, len(text), _CHUNK_SIZE)]
        total  = len(chunks)
        extracted = []

        for idx, chunk in enumerate(chunks, 1):
            raw = _call_claude(
                client,
                _PROMPT_CHUNK.format(idx=idx, total=total, text=chunk),
                max_tokens=2048,
            )
            try:
                parsed = _parse_json(raw)
                if isinstance(parsed, list):
                    extracted.extend(parsed)
            except json.JSONDecodeError:
                pass  # 해당 청크에서 추출 실패 시 스킵

        # 병합 호출
        chunks_json = json.dumps(extracted, ensure_ascii=False, indent=2)
        raw_merged  = _call_claude(
            client,
            _PROMPT_MERGE.format(chunks_json=chunks_json),
            max_tokens=4096,
        )
        try:
            return _parse_json(raw_merged)
        except json.JSONDecodeError as e:
            raise ValueError(f"병합 JSON 파싱 실패: {e}\n원문:\n{raw_merged[:400]}")
