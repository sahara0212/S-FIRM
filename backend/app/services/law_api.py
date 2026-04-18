"""
법제처 OpenAPI + 금융위원회 법규 연동
- 법제처: https://www.law.go.kr/DRF  (법령 검색 · 전문 · 신구조문 비교)
- 금융위: https://law.fsc.go.kr      (행정규칙 · 감독규정 변경이력)
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta


class LawMonitoringFetcher:
    API_KEY  = "sahara0212"
    LAW_BASE = "https://www.law.go.kr/DRF"

    # 모니터링 대상 핵심 법령
    TARGET_LAWS = [
        {"id": "pipa", "query": "개인정보 보호법",                               "emoji": "🔒", "name": "개인정보보호법"},
        {"id": "cipa", "query": "신용정보의 이용 및 보호에 관한 법률",             "emoji": "💳", "name": "신용정보법"},
        {"id": "aiba", "query": "인공지능 발전과 신뢰 기반 조성 등에 관한 기본법", "emoji": "🤖", "name": "AI기본법"},
        {"id": "efsr", "query": "전자금융감독규정",                               "emoji": "💰", "name": "전자금융감독규정", "target": "admrul"},
        {"id": "itna", "query": "정보통신망 이용촉진 및 정보보호 등에 관한 법률",  "emoji": "🌐", "name": "정보통신망법"},
        {"id": "fgsl", "query": "금융회사의 지배구조에 관한 법률",                 "emoji": "🏛️", "name": "금융회사지배구조법"},
    ]

    # 유관 법령
    RELATED_LAWS = [
        {"id": "esla", "query": "전자서명법",                                          "name": "전자서명법"},
        {"id": "cmal", "query": "자본시장과 금융투자업에 관한 법률",                    "name": "자본시장법"},
        {"id": "spfl", "query": "특정 금융거래정보의 보고 및 이용 등에 관한 법률",      "name": "특정금융정보법"},
        {"id": "insa", "query": "보험업법",                                            "name": "보험업법"},
    ]

    # ── 내부 HTTP 헬퍼 ─────────────────────────────────────────────────────
    def _get_xml(self, endpoint, params: dict):
        try:
            resp = requests.get(
                f"{self.LAW_BASE}/{endpoint}",
                params={**params, "OC": self.API_KEY, "type": "XML"},
                timeout=8,
            )
            if resp.status_code == 200:
                return ET.fromstring(resp.content)
        except Exception as e:
            print(f"[LawAPI] {endpoint} 오류: {e}")
        return None

    # ── 법제처: 법령 검색 ──────────────────────────────────────────────────
    def search_law(self, query: str, display: int = 5, target: str = "law") -> list[dict]:
        root = self._get_xml("lawSearch.do", {
            "target": target, "query": query, "display": display, "sort": "efdate",
        })
        if root is None:
            return []
        items = []
        # 행정규칙(admrul)은 태그명이 다름
        tag = "admrul" if target == "admrul" else "law"
        for law in root.findall(f".//{tag}"):
            serial = (law.findtext("행정규칙일련번호") or law.findtext("법령일련번호") or "").strip()
            name   = (law.findtext("행정규칙명") or law.findtext("법령명_한글") or law.findtext("법령명한글") or "").strip()
            items.append({
                "serial":            serial,
                "name":              name,
                "revision_type":     (law.findtext("제개정구분명") or law.findtext("법령구분명") or "").strip(),
                "promulgation_date": (law.findtext("발령일자") or law.findtext("공포일자") or "").strip(),
                "effective_date":    (law.findtext("시행일자") or "").strip(),
                "ministry":          (law.findtext("소관부처명") or "").strip(),
            })
        return items

    # ── 법제처: 신구조문 대비표 ────────────────────────────────────────────
    def get_law_diff(self, serial: str) -> list[dict]:
        root = self._get_xml("lawService.do", {"target": "lawDiff", "MST": serial})
        if root is None:
            return []
        diffs = []
        for node in root.findall(".//신구조문비교") + root.findall(".//조문비교"):
            art    = (node.findtext("조문번호") or "").strip()
            before = (node.findtext("현행") or node.findtext("구조문") or "").strip()
            after  = (node.findtext("개정") or node.findtext("신조문") or "").strip()
            if before or after:
                diffs.append({"article": art, "before": before[:400], "after": after[:400]})
        return diffs

    # ── 법령 XML 루트 로드 (MST 파라미터) ────────────────────────────────
    def _get_law_root(self, serial: str, target: str = "law"):
        return self._get_xml("lawService.do", {"target": target, "MST": serial})

    @staticmethod
    def _extract_articles(root) -> dict[str, str]:
        """조문단위 → {조문번호: 조문내용} 딕셔너리 (법령 전문 구조 기준)"""
        arts: dict[str, str] = {}
        for jo in root.findall(".//조문단위"):
            no      = (jo.findtext("조문번호") or "").strip()
            content = (jo.findtext("조문내용") or "").strip()
            # 조문번호가 있고 내용이 실제 조문(제N조 형식)인 것만 포함
            if no and content and f"제{no}조" in content[:20]:
                arts[no] = content
        return arts

    # ── 법제처: 법령 전문(조문 내용) ──────────────────────────────────────
    def get_law_articles(self, serial: str) -> list[dict]:
        root = self._get_law_root(serial)
        if root is None:
            return []
        articles = []
        for jo in root.findall(".//조문단위")[:12]:
            no      = (jo.findtext("조문번호") or "").strip()
            content = (jo.findtext("조문내용") or "").strip()
            if no and content and f"제{no}조" in content[:20]:
                # 조문 제목 파싱: 제N조(제목) 형식
                title = ""
                if "(" in content and ")" in content:
                    s, e = content.find("("), content.find(")")
                    if 0 < e - s < 40:
                        title = content[s+1:e]
                articles.append({"no": no, "title": title, "content": content[:350]})
        return articles[:8]

    # ── 두 버전 비교: 변경 조문 추출 ─────────────────────────────────────
    def compute_version_diff(
        self, curr_serial: str, prev_serial: str, target: str = "law"
    ) -> list[dict]:
        curr_root = self._get_law_root(curr_serial, target)
        prev_root = self._get_law_root(prev_serial, target)
        if curr_root is None:
            return []

        curr_arts = self._extract_articles(curr_root)
        prev_arts = self._extract_articles(prev_root) if prev_root else {}

        # 변경 조문 번호 수집 (조문변경여부=Y 우선, 없으면 텍스트 비교)
        changed_nos: set[str] = set()
        for jo in curr_root.findall(".//조문단위"):
            if jo.findtext("조문변경여부") == "Y":
                no = (jo.findtext("조문번호") or "").strip()
                if no:
                    changed_nos.add(no)

        if not changed_nos:
            # 신구조문변경여부 없으면 텍스트 직접 비교
            changed_nos = {
                no for no in set(curr_arts) | set(prev_arts)
                if curr_arts.get(no, "") != prev_arts.get(no, "")
            }

        def _sort_key(no: str) -> int:
            return int(no) if no.isdigit() else 9999

        diffs = []
        for no in sorted(changed_nos, key=_sort_key):
            c_text = curr_arts.get(no, "")
            p_text = prev_arts.get(no, "")
            if c_text == p_text:
                continue
            change_type = "신설" if not p_text else ("삭제" if not c_text else "개정")
            # 조문 제목 파싱
            title = ""
            ref = c_text or p_text
            if "(" in ref and ")" in ref:
                s, e = ref.find("("), ref.find(")")
                if 0 < e - s < 40:
                    title = ref[s+1:e]
            diffs.append({
                "article":     f"제{no}조",
                "title":       title,
                "change_type": change_type,
                "before":      p_text[:800] if p_text else "(신설)",
                "after":       c_text[:800] if c_text else "(삭제)",
            })
        return diffs

    # ── 법령 버전 diff 전체 데이터 (엔드포인트용) ─────────────────────────
    def get_version_diff_data(self, law_id: str) -> dict:
        all_laws = self.TARGET_LAWS + [
            {**l, "emoji": "📋"} for l in self.RELATED_LAWS
        ]
        law_def = next((l for l in all_laws if l["id"] == law_id), None)
        if not law_def:
            return {"error": "법령을 찾을 수 없습니다."}

        target  = law_def.get("target", "law")
        history = self.search_law(law_def["query"], display=10, target=target)

        if not history:
            return {"error": "법제처 데이터를 가져올 수 없습니다."}

        # 시행일자 기준 내림차순 정렬 (API가 오름차순 반환할 수 있음)
        def _date_key(h: dict) -> str:
            return h["effective_date"] or h["promulgation_date"] or "00000000"
        history.sort(key=_date_key, reverse=True)

        if len(history) < 2:
            return {"error": "비교할 이전 버전이 없습니다.", "law_id": law_id}

        curr, prev = history[0], history[1]
        diffs = self.compute_version_diff(curr["serial"], prev["serial"], target)

        return {
            "law_id":       law_id,
            "name":         curr["name"] or law_def["name"],
            "emoji":        law_def["emoji"],
            "curr_date":    self._fmt_date(curr["effective_date"] or curr["promulgation_date"]),
            "prev_date":    self._fmt_date(prev["effective_date"] or prev["promulgation_date"]),
            "revision_type": curr["revision_type"],
            "ministry":     curr["ministry"],
            "diffs":        diffs,
        }

    # ── 유틸 ──────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt_date(raw: str) -> str:
        """'20240115' → '2024.01.15'"""
        if raw and len(raw) == 8 and raw.isdigit():
            return f"{raw[:4]}.{raw[4:6]}.{raw[6:]}"
        return raw or ""

    @staticmethod
    def _priority(revision_type: str, text: str) -> str:
        if revision_type in ("전부개정", "제정"):
            return "HIGH"
        if any(w in text for w in ("금지", "의무", "처벌", "과태료", "금지행위", "위반")):
            return "HIGH"
        if any(w in text for w in ("강화", "신설", "추가", "확대")):
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _tags(text: str) -> list[str]:
        tags = []
        if any(w in text for w in ("책임", "임원", "준법감시", "내부통제", "이사회", "대표이사", "감사")):
            tags.append("책무구조도 영향")
        if any(w in text for w in ("시스템", "API", "전산", "기간계", "클라우드", "서비스", "망")):
            tags.append("기간계 수정 필요")
        if any(w in text for w in ("인공지능", "AI", "알고리즘", "자동화", "학습", "모델")):
            tags.append("AI 거버넌스")
        if any(w in text for w in ("신설", "제정", "신규")):
            tags.append("신규 법령")
        return tags

    # ── 핵심 법령 모니터링 데이터 수집 ────────────────────────────────────
    def fetch_monitoring_data(
        self,
        days: int = 7,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        # 날짜 범위 결정
        if from_date and to_date:
            try:
                cutoff_start = datetime.strptime(from_date, "%Y-%m-%d")
                cutoff_end   = datetime.strptime(to_date,   "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59
                )
            except ValueError:
                cutoff_end   = datetime.now()
                cutoff_start = cutoff_end - timedelta(days=days)
        else:
            cutoff_end   = datetime.now()
            cutoff_start = cutoff_end - timedelta(days=days)

        # 기간이 길수록 더 많은 연혁 조회
        display = min(max(5, days // 7 + 4), 25)

        result = {}
        for law_def in self.TARGET_LAWS:
            law_id   = law_def["id"]
            history  = self.search_law(law_def["query"], display=display, target=law_def.get("target", "law"))
            # 날짜 내림차순 정렬 (최신 → 과거), route ②에서 이전 버전 탐색에 필요
            history.sort(key=lambda h: h["effective_date"] or h["promulgation_date"] or "0", reverse=True)
            changes  = []

            # 기간 내 개정 이력만 추출
            in_range = []
            for h in history:
                raw = h["effective_date"] or h["promulgation_date"]
                if len(raw) == 8 and raw.isdigit():
                    try:
                        if cutoff_start <= datetime.strptime(raw, "%Y%m%d") <= cutoff_end:
                            in_range.append(h)
                    except ValueError:
                        pass

            for latest in in_range[:3]:
                display_name = latest["name"] or law_def["name"]
                eff_date = self._fmt_date(
                    latest["effective_date"] or latest["promulgation_date"]
                )
                rev_changes: list[dict] = []

                # ① 신구조문 대비표 우선 시도
                diffs = self.get_law_diff(latest["serial"]) if latest["serial"] else []
                if diffs:
                    for diff in diffs[:4]:
                        art_label = f"제{diff['article']}조" if diff["article"] else "전문"
                        rev_changes.append({
                            "article":  art_label,
                            "title":    f"{display_name} {art_label} 개정",
                            "date":     eff_date,
                            "priority": self._priority(latest["revision_type"], diff["after"]),
                            "before":   diff["before"] or "(신설)",
                            "after":    diff["after"],
                            "impact":   f"{latest['revision_type']} ({eff_date} 시행) — {latest['ministry']} 소관",
                            "tags":     self._tags(diff["before"] + diff["after"]),
                        })

                # ② 신구조문 없으면 이전 버전과 직접 비교
                if not rev_changes:
                    # history에서 latest의 바로 이전 버전 찾기
                    try:
                        curr_idx = next(
                            i for i, h in enumerate(history) if h["serial"] == latest["serial"]
                        )
                        prev_entry = history[curr_idx + 1] if curr_idx + 1 < len(history) else None
                    except StopIteration:
                        prev_entry = None

                    if prev_entry and prev_entry["serial"]:
                        target_type = law_def.get("target", "law")
                        diffs = self.compute_version_diff(
                            latest["serial"], prev_entry["serial"], target_type
                        )
                        for diff in diffs[:4]:
                            rev_changes.append({
                                "article":  diff["article"],
                                "title":    diff["title"] or f"{display_name} {diff['article']} 개정",
                                "date":     eff_date,
                                "priority": self._priority(latest["revision_type"], diff["after"]),
                                "before":   diff["before"],
                                "after":    diff["after"],
                                "impact":   f"{latest['revision_type']} ({eff_date} 시행) — {latest['ministry']} 소관",
                                "tags":     self._tags(diff["before"] + diff["after"]),
                            })

                    # 비교 결과도 없으면 현행 조문만이라도 표시
                    if not rev_changes:
                        articles = self.get_law_articles(latest["serial"]) if latest["serial"] else []
                        for art in articles[:3]:
                            art_label = f"제{art['no']}조" if art["no"] else "전문"
                            rev_changes.append({
                                "article":  art_label,
                                "title":    art["title"] or f"{display_name} {art_label}",
                                "date":     eff_date,
                                "priority": self._priority(latest["revision_type"], art["content"]),
                                "before":   "(이전 버전 정보 없음)",
                                "after":    art["content"],
                                "impact":   f"{latest['revision_type']} ({eff_date} 시행) — {latest['ministry']} 소관",
                                "tags":     self._tags(art["content"]),
                            })

                # ③ 조문도 없으면 법령 레벨 1건
                if not rev_changes:
                    rev_changes.append({
                        "article":  "전문",
                        "title":    f"{display_name} {latest['revision_type']}",
                        "date":     eff_date,
                        "priority": "MEDIUM",
                        "before":   "(이전 법령)",
                        "after":    f"{display_name} {latest['revision_type']} — {eff_date} 시행",
                        "impact":   f"{latest['ministry']} 소관 — 담당 부서 검토 필요",
                        "tags":     [],
                    })

                changes.extend(rev_changes)

            result[law_id] = {
                "id":           law_id,
                "name":         history[0]["name"] if history else law_def["name"],
                "emoji":        law_def["emoji"],
                "changes":      changes,
                "source":       "live" if history else "fallback",
                "last_fetched": datetime.now().strftime("%Y.%m.%d %H:%M"),
            }

        return result

    # ── 유관 법령 최근 변경 건수 ──────────────────────────────────────────
    def fetch_related_data(
        self,
        days: int = 30,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        if from_date and to_date:
            try:
                cutoff_start = datetime.strptime(from_date, "%Y-%m-%d")
                cutoff_end   = datetime.strptime(to_date,   "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59
                )
            except ValueError:
                cutoff_end   = datetime.now()
                cutoff_start = cutoff_end - timedelta(days=days)
        else:
            cutoff_end   = datetime.now()
            cutoff_start = cutoff_end - timedelta(days=days)

        result = []
        for law_def in self.RELATED_LAWS:
            history = self.search_law(law_def["query"], display=min(max(10, days // 5), 30))
            count = 0
            for h in history:
                raw = h["effective_date"] or h["promulgation_date"]
                if len(raw) == 8 and raw.isdigit():
                    try:
                        d = datetime.strptime(raw, "%Y%m%d")
                        if cutoff_start <= d <= cutoff_end:
                            count += 1
                    except ValueError:
                        pass
            result.append({"id": law_def["id"], "name": law_def["name"], "changes": count})
        return result


fetcher = LawMonitoringFetcher()
