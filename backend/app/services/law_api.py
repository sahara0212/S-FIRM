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
        {"id": "efsr", "query": "전자금융감독규정",                               "emoji": "💰", "name": "전자금융감독규정"},
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
    def search_law(self, query: str, display: int = 5) -> list[dict]:
        root = self._get_xml("lawSearch.do", {
            "target": "law", "query": query, "display": display, "sort": "efdate",
        })
        if root is None:
            return []
        items = []
        for law in root.findall(".//law"):
            serial = law.findtext("법령일련번호") or ""
            name   = (law.findtext("법령명_한글") or law.findtext("법령명한글") or "").strip()
            items.append({
                "serial":            serial,
                "name":              name,
                "revision_type":     (law.findtext("법령구분명") or "").strip(),
                "promulgation_date": (law.findtext("공포일자") or "").strip(),
                "effective_date":    (law.findtext("시행일자") or "").strip(),
                "ministry":          (law.findtext("소관부처명") or "").strip(),
            })
        return items

    # ── 법제처: 신구조문 대비표 ────────────────────────────────────────────
    def get_law_diff(self, serial: str) -> list[dict]:
        root = self._get_xml("lawService.do", {"target": "lawDiff", "ID": serial})
        if root is None:
            return []
        diffs = []
        # 태그명은 버전에 따라 다를 수 있어 여러 경로 시도
        for node in root.findall(".//신구조문비교") + root.findall(".//조문비교"):
            art    = (node.findtext("조문번호") or "").strip()
            before = (node.findtext("현행") or node.findtext("구조문") or "").strip()
            after  = (node.findtext("개정") or node.findtext("신조문") or "").strip()
            if before or after:
                diffs.append({"article": art, "before": before[:400], "after": after[:400]})
        return diffs

    # ── 법제처: 법령 전문(조문 내용) ──────────────────────────────────────
    def get_law_articles(self, serial: str) -> list[dict]:
        root = self._get_xml("lawService.do", {"target": "law", "ID": serial})
        if root is None:
            return []
        articles = []
        for jo in root.findall(".//조문단위"):
            no    = (jo.findtext("조번호") or jo.findtext("조문번호") or "").strip()
            title = (jo.findtext("조문제목") or "").strip()
            # 항 내용 결합
            hang_texts = [
                h.findtext("항내용") or ""
                for h in jo.findall(".//항")
                if h.findtext("항내용")
            ]
            content = " ".join(hang_texts[:3])[:350]
            if content or title:
                articles.append({"no": no, "title": title, "content": content})
        return articles[:8]

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
    def fetch_monitoring_data(self) -> dict:
        result = {}

        for law_def in self.TARGET_LAWS:
            law_id = law_def["id"]
            history = self.search_law(law_def["query"], display=5)
            changes = []

            if history:
                latest = history[0]
                display_name = latest["name"] or law_def["name"]
                eff_date = self._fmt_date(
                    latest["effective_date"] or latest["promulgation_date"]
                )

                # ① 신구조문 대비표 우선 시도
                diffs = self.get_law_diff(latest["serial"]) if latest["serial"] else []
                if diffs:
                    for diff in diffs[:4]:
                        art_label = f"제{diff['article']}조" if diff["article"] else "전문"
                        changes.append({
                            "article": art_label,
                            "title":   f"{display_name} {art_label} 개정",
                            "date":    eff_date,
                            "priority": self._priority(latest["revision_type"], diff["after"]),
                            "before":  diff["before"] or "(신설)",
                            "after":   diff["after"],
                            "impact":  f"{latest['revision_type']} ({eff_date} 시행) — {latest['ministry']} 소관",
                            "tags":    self._tags(diff["before"] + diff["after"]),
                        })

                # ② 신구조문 없으면 법령 전문에서 조문 추출
                if not changes:
                    articles = self.get_law_articles(latest["serial"]) if latest["serial"] else []
                    for art in articles[:3]:
                        art_label = f"제{art['no']}조" if art["no"] else "전문"
                        changes.append({
                            "article": art_label,
                            "title":   art["title"] or f"{display_name} {art_label}",
                            "date":    eff_date,
                            "priority": self._priority(latest["revision_type"], art["content"]),
                            "before":  "(이전 버전 — 법제처 연혁 법령 참조)",
                            "after":   art["content"],
                            "impact":  f"{latest['revision_type']} ({eff_date} 시행) — {latest['ministry']} 소관",
                            "tags":    self._tags(art["content"]),
                        })

                # ③ 조문도 없으면 법령 레벨 1건
                if not changes:
                    changes.append({
                        "article": "전문",
                        "title":   f"{display_name} {latest['revision_type']}",
                        "date":    eff_date,
                        "priority": "MEDIUM",
                        "before":  "(이전 법령)",
                        "after":   f"{display_name} {latest['revision_type']} — {eff_date} 시행",
                        "impact":  f"{latest['ministry']} 소관 — 담당 부서 검토 필요",
                        "tags":    [],
                    })

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
    def fetch_related_data(self) -> list[dict]:
        cutoff = datetime.now() - timedelta(days=30)
        result = []
        for law_def in self.RELATED_LAWS:
            history = self.search_law(law_def["query"], display=10)
            count = 0
            for h in history:
                raw = h["effective_date"] or h["promulgation_date"]
                if len(raw) == 8:
                    try:
                        if datetime.strptime(raw, "%Y%m%d") >= cutoff:
                            count += 1
                    except ValueError:
                        pass
            result.append({"id": law_def["id"], "name": law_def["name"], "changes": count})
        return result


fetcher = LawMonitoringFetcher()
