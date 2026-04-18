"""
4단계: 금지행위 + 책임자 매핑 → 구체적 내부 업무규칙 생성
"""
import json
import os
import re
from collections import defaultdict

import anthropic

_SYSTEM = """당신은 금융회사 내부통제 전문가입니다.
금지행위와 책임자 매핑을 입력받아 실무에서 바로 사용할 수 있는 내부 업무규칙을 JSON으로 생성하세요.
반드시 유효한 JSON 배열만 출력하고, 설명 텍스트는 포함하지 마세요."""

_PROMPT_TMPL = """## 금지행위 목록 (책임자 매핑 포함)

{prohibition_text}

---

## 지시사항

각 금지행위에 대해 금융회사 내부 업무규칙을 생성하세요.
업무규칙은 준법감시팀이 실제로 사용할 수 있도록 구체적으로 작성하세요.

출력 형식 — JSON 배열을 엄격히 준수하세요:
[
  {{
    "prohibition_id":    "입력받은 금지행위 ID (그대로 복사)",
    "rule_code":         "규칙 코드 (예: RULE-PIP-001, RULE-AIB-001 등 법령별 접두어 사용)",
    "name":              "업무규칙명 (동사형 명사구, 예: '개인정보 수집 동의 점검 절차')",
    "description":       "이 업무규칙이 왜 필요한지, 무엇을 달성하는지 2~3문장",
    "trigger_condition": "이 규칙이 발동되는 구체적 조건 (예: '신규 서비스 출시 전', '분기 1회')",
    "actions":           [
      "구체적 실행 단계 1 (담당자·기한·방법 포함)",
      "구체적 실행 단계 2",
      "구체적 실행 단계 3"
    ],
    "exceptions":        ["예외 조건 1 (없으면 빈 배열 []로)"],
    "system_guide":      "기간계/IT 시스템 구현 가이드 (어떤 시스템을 어떻게 수정·점검해야 하는지 1~2문장)"
  }}
]

법령 접두어 규칙:
- 개인정보보호법 → RULE-PIP
- 인공지능 기본법 → RULE-AIB
- 금융지배구조법/시행령 → RULE-FGS
- 전자금융거래법 → RULE-EFS
- 신용정보법 → RULE-CIP
- 정보통신망법 → RULE-ITN

규칙 번호는 001부터 순서대로 부여하되, 같은 법령 내 다른 규칙과 겹치지 않도록 {start_seq}부터 시작하세요."""

_LAW_PREFIX = {
    "pipa": "PIP", "aiba": "AIB", "fgsl": "FGS",
    "efsr": "EFS", "cipa": "CIP", "itna": "ITN",
}


def _build_prohibition_text(items: list[dict]) -> str:
    parts = []
    for p in items:
        m = p.get("mapping") or {}
        parts.append(
            f"### [ID: {p['id']}] {p.get('law_name','')} {p.get('article','')}\n"
            f"**금지행위명:** {p['name']}\n"
            f"**설명:** {p.get('description','')}\n"
            f"**행위 주체:** {p.get('subject','')}\n"
            f"**금지 대상:** {p.get('target','')}\n"
            f"**발동 조건:** {p.get('trigger_condition','')}\n"
            f"**예외:** {p.get('exception','없음')}\n"
            f"**우선순위:** {p.get('priority','MEDIUM')}\n"
            f"**1차 책임:** {m.get('first_duty','')} / "
            f"**2차 책임:** {m.get('second_duty','')} / "
            f"**3차 책임:** {m.get('third_duty','')}"
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
        raise ValueError(f"JSON 파싱 실패\n원문:\n{raw[:400]}")


def generate_rules(prohibitions: list[dict]) -> list[dict]:
    """
    prohibitions: _prohibition_to_out() 형태의 dict 리스트
      (id, law_id, law_name, article, name, description, subject, target,
       trigger_condition, exception, priority, mapping{first/second/third_duty})
    → [{prohibition_id, rule_code, name, description, trigger_condition,
        actions, exceptions, system_guide}, ...]
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=api_key)

    # 법령별 그룹핑 후 순서 번호 관리
    groups: dict[str, list[dict]] = defaultdict(list)
    for p in prohibitions:
        groups[p.get("law_id", "etc")].append(p)

    all_results: list[dict] = []
    CHUNK = 4  # 한 번 호출당 최대 4개 (토큰 초과 방지)

    for law_id, items in groups.items():
        prefix = _LAW_PREFIX.get(law_id, "RULE")
        for chunk_idx, i in enumerate(range(0, len(items), CHUNK)):
            chunk = items[i:i + CHUNK]
            start_seq = i + 1

            prompt = _PROMPT_TMPL.format(
                prohibition_text=_build_prohibition_text(chunk),
                start_seq=str(start_seq).zfill(3),
            )
            try:
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8192,
                    system=_SYSTEM,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = msg.content[0].text.strip()
                items_out = _parse_json(raw)
                all_results.extend(items_out)
            except Exception as e:
                print(f"[rule_generator] {law_id} chunk {chunk_idx} 실패: {e}")
                continue

    return all_results
