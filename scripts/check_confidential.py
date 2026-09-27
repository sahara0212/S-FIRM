#!/usr/bin/env python3
"""저장소에 기밀자료·비밀정보가 커밋되지 않았는지 검사한다.

CI와 로컬 pre-commit에서 실행한다. 위반이 있으면 종료코드 1.
정책: CLAUDE.md '절대 하지 말 것'
"""

from __future__ import annotations

import re
import subprocess
import sys

# 고객 산출물·원본 문서가 들어가는 경로
FORBIDDEN_PREFIXES = ("data/", "uploads/", "confidential/")
# 저장소에 두지 않는 문서 형식(고객 원본·산출물일 가능성이 높음)
FORBIDDEN_SUFFIXES = (".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pdf", ".hwp", ".hwpx", ".msg", ".eml")
ALLOWED_FILES = {"outputs/README.md", "templates/proposal/README.md"}
FORBIDDEN_NAMES = (".env",)

SECRET_PATTERNS = {
    "OpenAI/Anthropic API key": re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
CONFIDENTIAL_MARKERS = ("Privileged & Confidential", "Attorney Work Product")
TEXT_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".txt", ".csv", ".yaml", ".yml", ".html", ".css", ".sh")
SELF = "scripts/check_confidential.py"


def tracked_files() -> list[str]:
    output = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True).stdout
    return [path for path in output.decode("utf-8").split("\0") if path]


def main() -> int:
    violations: list[str] = []
    for path in tracked_files():
        if path in ALLOWED_FILES:
            continue
        lower = path.lower()
        name = lower.rsplit("/", 1)[-1]
        if lower.startswith(FORBIDDEN_PREFIXES):
            violations.append(f"{path}: 기밀자료 경로")
            continue
        if lower.endswith(FORBIDDEN_SUFFIXES):
            violations.append(f"{path}: 저장소에 두지 않는 문서 형식")
            continue
        if name in FORBIDDEN_NAMES:
            violations.append(f"{path}: 환경 파일")
            continue
        if path == SELF or not lower.endswith(TEXT_SUFFIXES):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError):
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                violations.append(f"{path}: {label} 의심 문자열")
        for marker in CONFIDENTIAL_MARKERS:
            if marker in text:
                violations.append(f"{path}: 기밀 표시 문구 '{marker}'")

    if violations:
        print("기밀자료·비밀정보 검사 실패:")
        for violation in violations:
            print(f"  - {violation}")
        print("정책: CLAUDE.md '절대 하지 말 것'")
        return 1
    print("기밀자료·비밀정보 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
