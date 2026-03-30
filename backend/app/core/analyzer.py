class SejongAnalyzer:
    def __init__(self):
        self.client_context = ""

    def analyze(self, law):
        title = law['title']
        l_type = law['type']
        
        # 금융법령 여부 판별 
        is_fin = any(kw in title for kw in ["금융", "은행", "보험", "증권", "가상자산", "신용"])
        
        # [방법론 147-151] Gap 분석 기반 신구 데이터 생성
        # 실제 운영 시에는 lawService API의 <조문내용> 태그를 파싱하여 매핑합니다.
        diff_data = {
            "old_text": f"현행 『{title}』 기준: 내부통제 관리의무 및 책임 소재가 포괄적으로 규정되어 실효적 운영에 한계가 있음 [cite: 7, 9]",
            "new_text": f"개정 『{title}』 반영: 지배구조법 제24조의2에 따른 관리의무 구체화 및 책무구조도 내 담당 임원(A) 명시 필수 [cite: 312, 184]"
        }

        # [방법론 136, 177] 우선순위 및 RACI 자동 할당
        target_exec = "준법감시인"
        if "가상자산" in title: target_exec = "CISO/준법감시인"
        elif "지배구조" in title: target_exec = "대표이사/준법감시인"

        return {
            "is_finance": is_fin,
            "priority": "High" if is_fin else "Low",
            "exec_level": target_exec,
            "exec_action": f"{title} 관련 내부통제기준 개정 및 이사회 승인 [cite: 190]",
            "risk_level": "High (즉시 대응)" if is_fin else "Mid (상시 모니터링)",
            "sejong_insight": f"본 {l_type}안은 세종 방법론의 Framework 2(사규 변경관리)에 따라 RFC 등록이 필요한 사안입니다 [cite: 279, 303]",
            "diff": diff_data,
            "checklist": [
                "책무구조도 v2.0 반영 및 버전 관리 [cite: 233]",
                "RACI Matrix 기반 업무 분장 적정성 검토 [cite: 177]",
                "3-Tier 실효성 점검 지표 설정 [cite: 306]"
            ]
        }

analyzer = SejongAnalyzer()
