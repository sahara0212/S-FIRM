"""
업권별 맞춤 템플릿 API
POST /api/v1/clients/{client_id}/apply-template  — 업권 맞춤 업무규칙 시드 적용
GET  /api/v1/templates/{industry}               — 템플릿 미리보기
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Client, AnalysisSession, ProhibitedAct, DutyMapping, BusinessRule

router = APIRouter(tags=["templates"])


# ─────────────────────────────────────────────────────────────────────────────
# 업권별 템플릿 정의
# 각 항목: rule_code, name, description, law_name, article,
#          prohibition_name, priority, first_duty, second_duty,
#          trigger_condition, actions, system_guide
# ─────────────────────────────────────────────────────────────────────────────
INDUSTRY_TEMPLATES: dict[str, list[dict]] = {

    "보험(생보)": [
        {
            "rule_code": "RULE-LIF-001", "priority": "HIGH",
            "prohibition_name": "변액보험 부당 권유 금지",
            "prohibition_desc": "투자위험을 충분히 설명하지 않고 변액보험 계약 체결 유도",
            "law_name": "보험업법", "article": "제95조의2",
            "name": "변액보험 판매 시 투자위험 고지 의무",
            "description": "변액보험 계약 체결 전 투자위험·예상 손익 등을 서면으로 설명하고 확인서 징구",
            "first_duty": "CCO", "second_duty": "CPO",
            "trigger_condition": "변액보험 신규 계약 체결 또는 추가납입 발생 시",
            "actions": ["투자위험 설명서 교부 및 서명 징구", "계약 체결 후 2영업일 내 확인 전화 실시"],
            "system_guide": "판매시스템에서 설명확인서 미서명 시 계약 진행 불가 처리",
        },
        {
            "rule_code": "RULE-LIF-002", "priority": "HIGH",
            "prohibition_name": "보험금 부당 지급 거절 금지",
            "prohibition_desc": "정당한 보험금 지급 사유 발생 시 사실과 다른 이유로 지급 거절 또는 지연",
            "law_name": "보험업법", "article": "제102조",
            "name": "보험금 지급 심사 기준 준수",
            "description": "보험금 청구 접수 후 법정 기한(3영업일/30일) 내 지급 또는 지급 거절 통보",
            "first_duty": "CRO", "second_duty": "CCO",
            "trigger_condition": "보험금 청구 접수 시마다",
            "actions": ["청구 접수일로부터 3영업일 내 서류 구비 여부 확인", "30일 내 지급/거절 결정 및 통보"],
            "system_guide": "청구관리시스템에서 기한 초과 건 자동 알림 발송",
        },
        {
            "rule_code": "RULE-LIF-003", "priority": "HIGH",
            "prohibition_name": "계약자 개인정보 무단 제3자 제공 금지",
            "prohibition_desc": "보험계약자·피보험자의 개인정보를 동의 없이 제3자에게 제공",
            "law_name": "개인정보보호법", "article": "제17조",
            "name": "보험계약자 개인정보 보호 기준",
            "description": "계약자 정보 수집·이용·제공 시 사전 동의 징구 및 보유기간 준수",
            "first_duty": "CISO", "second_duty": "CCO",
            "trigger_condition": "개인정보 수집·이용·제공 발생 시",
            "actions": ["동의서 징구 여부 확인", "제3자 제공 목록 분기별 점검"],
            "system_guide": "개인정보처리시스템에서 동의 미확인 시 정보 접근 차단",
        },
        {
            "rule_code": "RULE-LIF-004", "priority": "MEDIUM",
            "prohibition_name": "내부자 보험료 산출 기준 유용 금지",
            "prohibition_desc": "임직원이 미공개 보험료 산출 정보를 이용한 계약 체결",
            "law_name": "보험업법", "article": "제110조",
            "name": "임직원 보험 계약 사전 신고 의무",
            "description": "임직원이 자사 보험 신규 계약 체결 시 준법감시팀에 사전 신고",
            "first_duty": "CCO", "second_duty": "CRO",
            "trigger_condition": "임직원 자사 보험 계약 체결 시",
            "actions": ["사전 신고서 제출", "준법감시팀 승인 후 계약 진행"],
            "system_guide": "HR시스템과 연계하여 임직원 계약 자동 감지",
        },
        {
            "rule_code": "RULE-LIF-005", "priority": "MEDIUM",
            "prohibition_name": "보험모집 수수료 과다지급 금지",
            "prohibition_desc": "법정 한도를 초과한 모집 수수료 지급",
            "law_name": "보험업법", "article": "제92조",
            "name": "보험모집 수수료 한도 관리",
            "description": "모집수수료 지급 전 법정 한도 초과 여부 자동 검증 및 초과 시 지급 보류",
            "first_duty": "CFO", "second_duty": "CCO",
            "trigger_condition": "모집수수료 지급 처리 시",
            "actions": ["수수료 한도 자동 검증", "초과 건 준법감시팀 보고"],
            "system_guide": "수수료관리시스템에서 한도 초과 시 지급 자동 보류",
        },
        {
            "rule_code": "RULE-LIF-006", "priority": "LOW",
            "prohibition_name": "내부통제 교육 미이수 금지",
            "prohibition_desc": "연간 의무 내부통제 교육 미이수",
            "law_name": "금융회사지배구조법", "article": "제24조",
            "name": "임직원 내부통제 교육 이수 관리",
            "description": "전 임직원 연 1회 이상 내부통제 의무교육 이수 및 결과 관리",
            "first_duty": "CCO", "second_duty": "CDO",
            "trigger_condition": "매년 교육 계획 수립 시 및 분기별 이수 현황 점검",
            "actions": ["교육 계획 수립 및 공지", "미이수자 개별 독려", "이수 결과 경영진 보고"],
            "system_guide": "LMS에서 미이수자 자동 추출 및 리마인더 발송",
        },
    ],

    "보험(손보)": [
        {
            "rule_code": "RULE-PNC-001", "priority": "HIGH",
            "prohibition_name": "자동차보험 요율 부당 차별 금지",
            "prohibition_desc": "동일한 위험 수준 계약자에 대한 자동차보험료 부당 차별 적용",
            "law_name": "보험업법", "article": "제129조",
            "name": "자동차보험 요율 산출 기준 준수",
            "description": "자동차보험 요율 산출 시 금융위 신고 기준표 준수 및 역선택 방지 절차 운영",
            "first_duty": "CRO", "second_duty": "CCO",
            "trigger_condition": "자동차보험 요율 변경 또는 신상품 출시 시",
            "actions": ["요율 산출 기초 검증", "금감원 신고 전 준법감시팀 검토"],
            "system_guide": "요율산출시스템에서 기준표 대비 편차 자동 경고",
        },
        {
            "rule_code": "RULE-PNC-002", "priority": "HIGH",
            "prohibition_name": "보험사기 조장 행위 금지",
            "prohibition_desc": "임직원 또는 모집인의 보험사기 방조·공모 행위",
            "law_name": "보험사기방지특별법", "article": "제8조",
            "name": "보험사기 예방 및 적발 절차 운영",
            "description": "이상 청구 패턴 탐지, 사기 의심 건 SIU 이관, 수사기관 협조 체계 운영",
            "first_duty": "CCO", "second_duty": "CRO",
            "trigger_condition": "보험금 청구 접수 시 및 이상 징후 탐지 시",
            "actions": ["AI 사기 탐지 시스템 상시 운영", "월 1회 사기 의심 건 검토 회의"],
            "system_guide": "청구관리시스템에서 사기 스코어링 자동 산출 및 임계치 초과 시 SIU 자동 배정",
        },
        {
            "rule_code": "RULE-PNC-003", "priority": "HIGH",
            "prohibition_name": "재보험 계약 미신고 금지",
            "prohibition_desc": "의무 재보험 계약 체결 시 금감원 미신고",
            "law_name": "보험업법", "article": "제136조",
            "name": "재보험 계약 체결 및 신고 절차 준수",
            "description": "재보험 계약 체결 전 이사회 승인 및 체결 후 금감원 신고 기한 준수",
            "first_duty": "CRO", "second_duty": "CFO",
            "trigger_condition": "재보험 계약 체결·갱신·해지 시",
            "actions": ["계약 전 이사회 보고", "체결 후 15일 내 금감원 신고"],
            "system_guide": "재보험관리시스템에서 신고 기한 D-5 알림 자동 발송",
        },
        {
            "rule_code": "RULE-PNC-004", "priority": "MEDIUM",
            "prohibition_name": "장기보험 해지환급금 부당 안내 금지",
            "prohibition_desc": "장기보험 해지환급금을 실제보다 과장하여 안내",
            "law_name": "금융소비자보호법", "article": "제19조",
            "name": "장기보험 해지환급금 안내 기준 준수",
            "description": "계약 체결 시 및 유지 기간 중 해지환급금 예시 자료를 정확하게 교부",
            "first_duty": "CCO", "second_duty": "CPO",
            "trigger_condition": "장기보험 신규 계약 체결 시 및 연간 안내문 발송 시",
            "actions": ["해지환급금 예시 자료 교부 및 확인서 징구", "연 1회 안내 자료 정확성 점검"],
            "system_guide": "계약관리시스템에서 예시 자료 미교부 시 계약 진행 차단",
        },
        {
            "rule_code": "RULE-PNC-005", "priority": "MEDIUM",
            "prohibition_name": "배상책임 한도 초과 인수 금지",
            "prohibition_desc": "리스크 관리 한도를 초과한 배상책임보험 인수",
            "law_name": "보험업법", "article": "제102조의3",
            "name": "배상책임보험 인수 한도 관리",
            "description": "배상책임보험 종목별 최대 인수 한도 설정 및 초과 시 이사회 승인 절차",
            "first_duty": "CRO", "second_duty": "CFO",
            "trigger_condition": "배상책임보험 신규 인수 건 심사 시",
            "actions": ["종목별 인수 한도 확인", "한도 초과 건 CRO 승인 후 진행"],
            "system_guide": "언더라이팅시스템에서 한도 초과 시 자동 에스컬레이션",
        },
    ],

    "은행": [
        {
            "rule_code": "RULE-BNK-001", "priority": "HIGH",
            "prohibition_name": "BIS 비율 최저 기준 미달 금지",
            "prohibition_desc": "바젤III 기준 BIS 자기자본비율 최저 기준(8%) 미달 운영",
            "law_name": "은행법", "article": "제34조",
            "name": "BIS 자기자본비율 유지 및 모니터링",
            "description": "BIS 비율 일별 모니터링, 경보 수준(10%) 도달 시 경영진 즉시 보고 및 자본 확충 계획 수립",
            "first_duty": "CFO", "second_duty": "CRO",
            "trigger_condition": "매영업일 BIS 비율 산출 시",
            "actions": ["일별 BIS 비율 산출 및 보고", "경보 수준 도달 시 48시간 내 대응 계획 수립"],
            "system_guide": "리스크관리시스템에서 BIS 비율 자동 산출 및 임계치 알림",
        },
        {
            "rule_code": "RULE-BNK-002", "priority": "HIGH",
            "prohibition_name": "고객 확인 없는 고액 현금 거래 허용 금지",
            "prohibition_desc": "1,000만원 이상 현금 거래 시 고객 확인 절차 생략",
            "law_name": "특정금융거래법", "article": "제5조의2",
            "name": "고액 현금 거래 고객 확인 절차 이행",
            "description": "1,000만원 이상 현금 거래 발생 시 고객 신원 확인 및 FIU 보고 의무 이행",
            "first_duty": "CCO", "second_duty": "CISO",
            "trigger_condition": "1,000만원 이상 현금 거래 발생 시",
            "actions": ["고객 신원 확인 서류 징구", "5영업일 내 FIU 보고"],
            "system_guide": "창구시스템에서 1,000만원 이상 거래 시 CTR 보고 자동 생성",
        },
        {
            "rule_code": "RULE-BNK-003", "priority": "HIGH",
            "prohibition_name": "대출 한도 초과 여신 금지",
            "prohibition_desc": "동일인·동일 차주 여신 한도 초과 대출 실행",
            "law_name": "은행법", "article": "제35조",
            "name": "여신 한도 집중 리스크 관리",
            "description": "동일인 여신 한도(자기자본의 20%) 준수 및 대출 실행 전 한도 잔액 자동 확인",
            "first_duty": "CRO", "second_duty": "CCO",
            "trigger_condition": "여신 신규 실행 또는 한도 증액 시",
            "actions": ["여신 실행 전 동일인 잔액 확인", "한도 90% 도달 시 CRO 사전 승인"],
            "system_guide": "여신관리시스템에서 한도 초과 시 실행 자동 차단",
        },
        {
            "rule_code": "RULE-BNK-004", "priority": "MEDIUM",
            "prohibition_name": "예금자 보호 한도 초과 안내 금지",
            "prohibition_desc": "예금자보호 한도(5,000만원)를 초과하는 금액에 대해 보호된다고 안내",
            "law_name": "예금자보호법", "article": "제32조",
            "name": "예금자보호 한도 정확 안내 의무",
            "description": "신규 예금 계약 체결 시 예금자보호 한도 및 비보호 상품 여부를 명확히 안내",
            "first_duty": "CCO", "second_duty": "CPO",
            "trigger_condition": "예금 상품 신규 가입 및 만기 갱신 시",
            "actions": ["예금자보호 안내문 교부", "비보호 상품 가입 시 별도 확인서 징구"],
            "system_guide": "예금관리시스템에서 한도 초과 예금 발생 시 자동 안내",
        },
        {
            "rule_code": "RULE-BNK-005", "priority": "MEDIUM",
            "prohibition_name": "대출금리 산정 기준 미공시 금지",
            "prohibition_desc": "여신 금리 산정 근거를 차주에게 미통보",
            "law_name": "은행법", "article": "제30조의2",
            "name": "대출금리 산정 체계 공시 의무",
            "description": "대출 실행 시 기준금리·가산금리·우대금리 산정 내역을 차주에게 서면 통보",
            "first_duty": "CFO", "second_duty": "CCO",
            "trigger_condition": "대출 실행 및 금리 변경 시",
            "actions": ["금리 산정 내역서 교부", "변동금리 변경 시 사전 통보"],
            "system_guide": "여신관리시스템에서 금리 내역서 자동 생성 및 발송",
        },
        {
            "rule_code": "RULE-BNK-006", "priority": "LOW",
            "prohibition_name": "임직원 자사 대출 특혜 금지",
            "prohibition_desc": "임직원에게 일반 고객보다 유리한 조건으로 대출 제공",
            "law_name": "은행법", "article": "제35조의2",
            "name": "임직원 여신 특혜 방지 절차",
            "description": "임직원 대출 신청 시 일반 고객과 동일 기준 심사 및 준법감시팀 사전 확인",
            "first_duty": "CCO", "second_duty": "CRO",
            "trigger_condition": "임직원 대출 신청 시",
            "actions": ["준법감시팀 사전 확인", "이사회 분기별 임직원 여신 현황 보고"],
            "system_guide": "여신시스템에서 임직원 여신 자동 태깅 및 별도 심사 프로세스 적용",
        },
    ],

    "증권": [
        {
            "rule_code": "RULE-SEC-001", "priority": "HIGH",
            "prohibition_name": "미공개중요정보 이용 거래 금지",
            "prohibition_desc": "내부자 또는 정보 수령자가 미공개중요정보를 이용한 증권 거래",
            "law_name": "자본시장법", "article": "제174조",
            "name": "내부자거래 사전 신고 및 모니터링",
            "description": "임직원의 자사 및 관련 종목 거래 사전 신고, 블랙아웃 기간 운영, 이상 거래 탐지",
            "first_duty": "CCO", "second_duty": "CPO",
            "trigger_condition": "임직원 유가증권 거래 발생 시 및 블랙아웃 기간 선정 시",
            "actions": ["거래 사전 신고서 제출 및 승인", "블랙아웃 기간 전 임직원 공지"],
            "system_guide": "트레이딩시스템에서 미신고 거래 실시간 감지 및 알림",
        },
        {
            "rule_code": "RULE-SEC-002", "priority": "HIGH",
            "prohibition_name": "시세조종 행위 금지",
            "prohibition_desc": "인위적 매매를 통한 시세 조종 및 부정거래 행위",
            "law_name": "자본시장법", "article": "제176조",
            "name": "시세조종 탐지 및 이상거래 모니터링",
            "description": "알고리즘 기반 이상거래 실시간 모니터링, 의심 거래 즉시 거래소 보고",
            "first_duty": "CRO", "second_duty": "CCO",
            "trigger_condition": "매 거래일 장 마감 후 및 이상 패턴 탐지 시",
            "actions": ["이상거래 일일 리포트 검토", "의심 건 24시간 내 거래소 보고"],
            "system_guide": "시장감시시스템에서 이상거래 스코어링 자동 산출",
        },
        {
            "rule_code": "RULE-SEC-003", "priority": "HIGH",
            "prohibition_name": "투자권유 적합성 원칙 위반 금지",
            "prohibition_desc": "고객 투자성향에 부적합한 금융투자상품 권유",
            "law_name": "자본시장법", "article": "제46조",
            "name": "투자자 적합성 원칙 준수",
            "description": "투자권유 전 투자자 정보 파악, 적합성 분류 후 부적합 상품 권유 제한",
            "first_duty": "CCO", "second_duty": "CDO",
            "trigger_condition": "투자권유 발생 시마다",
            "actions": ["투자자정보확인서 징구 (1년 유효)", "부적합 상품 권유 시 확인서 징구 후 진행"],
            "system_guide": "투자권유시스템에서 적합성 미검증 시 권유 차단",
        },
        {
            "rule_code": "RULE-SEC-004", "priority": "MEDIUM",
            "prohibition_name": "자기매매·위탁매매 이해충돌 금지",
            "prohibition_desc": "자기계정 거래와 고객 위탁매매 간 이해충돌 방치",
            "law_name": "자본시장법", "article": "제71조",
            "name": "자기매매·위탁매매 이해충돌 관리",
            "description": "자기매매부서와 위탁매매부서 간 정보 차단벽(Chinese Wall) 운영 및 점검",
            "first_duty": "CCO", "second_duty": "CRO",
            "trigger_condition": "부서 간 정보 접근 요청 시 및 분기별 점검",
            "actions": ["정보 차단벽 반기 점검", "위반 사항 즉시 CCO 보고"],
            "system_guide": "IT접근통제시스템에서 부서 간 데이터 접근 기록 자동 감사",
        },
        {
            "rule_code": "RULE-SEC-005", "priority": "MEDIUM",
            "prohibition_name": "파생상품 운용 리스크 한도 초과 금지",
            "prohibition_desc": "이사회 승인 파생상품 운용 리스크 한도 초과",
            "law_name": "자본시장법", "article": "제166조",
            "name": "파생상품 리스크 한도 모니터링",
            "description": "파생상품 포지션 VaR 일별 산출, 한도 90% 도달 시 CRO 보고, 한도 초과 시 즉시 축소",
            "first_duty": "CRO", "second_duty": "CFO",
            "trigger_condition": "매 거래일 마감 후",
            "actions": ["일별 VaR 산출 및 보고", "한도 초과 시 2시간 내 포지션 축소"],
            "system_guide": "리스크관리시스템에서 VaR 자동 산출 및 임계치 초과 시 자동 알림",
        },
    ],

    "카드": [
        {
            "rule_code": "RULE-CRD-001", "priority": "HIGH",
            "prohibition_name": "카드 발급 심사 기준 미적용 금지",
            "prohibition_desc": "개인 신용카드 발급 시 신용평가 절차 생략",
            "law_name": "여신전문금융업법", "article": "제14조의2",
            "name": "신용카드 발급 심사 기준 준수",
            "description": "신용카드 신청 시 신용평점·소득·부채 비율 등 발급 기준 준수 및 거절 사유 통보",
            "first_duty": "CRO", "second_duty": "CCO",
            "trigger_condition": "신용카드 신규 발급 신청 시",
            "actions": ["신용평가 조회 및 기준 적용", "거절 시 사유 서면 통보"],
            "system_guide": "발급심사시스템에서 기준 미충족 시 자동 거절 처리",
        },
        {
            "rule_code": "RULE-CRD-002", "priority": "HIGH",
            "prohibition_name": "카드 부정사용 탐지 지연 금지",
            "prohibition_desc": "카드 부정사용 의심 거래 발생 시 즉시 조치 미이행",
            "law_name": "여신전문금융업법", "article": "제16조",
            "name": "카드 부정사용 실시간 탐지 및 차단",
            "description": "FDS 기반 부정사용 의심 거래 실시간 탐지, 카드 사용 일시 정지 및 회원 확인",
            "first_duty": "CISO", "second_duty": "CRO",
            "trigger_condition": "부정사용 의심 거래 탐지 시",
            "actions": ["의심 거래 즉시 일시 정지", "30분 내 회원 SMS 발송 및 확인"],
            "system_guide": "FDS에서 부정사용 스코어 임계치 초과 시 자동 차단",
        },
        {
            "rule_code": "RULE-CRD-003", "priority": "HIGH",
            "prohibition_name": "가맹점 수수료 부당 차별 금지",
            "prohibition_desc": "동일 업종 가맹점에 합리적 이유 없이 차별적 수수료 적용",
            "law_name": "여신전문금융업법", "article": "제18조의2",
            "name": "가맹점 수수료 산정 기준 준수",
            "description": "가맹점 수수료율 산정 기준 공시 및 우대수수료 대상 가맹점 자동 적용",
            "first_duty": "CFO", "second_duty": "CCO",
            "trigger_condition": "가맹점 신규 등록 및 수수료 정기 조정 시",
            "actions": ["수수료 기준 적용 여부 확인", "우대수수료 자동 적용 점검"],
            "system_guide": "가맹점관리시스템에서 업종별 수수료 기준 자동 적용",
        },
        {
            "rule_code": "RULE-CRD-004", "priority": "MEDIUM",
            "prohibition_name": "카드정보 해외 유출 금지",
            "prohibition_desc": "카드 번호·유효기간 등 결제정보의 해외 서버 저장",
            "law_name": "개인정보보호법", "article": "제24조의2",
            "name": "카드 결제정보 국내 보관 기준 준수",
            "description": "카드 결제정보 국내 서버 저장 원칙 준수 및 해외 결제 대행 시 암호화 적용",
            "first_duty": "CISO", "second_duty": "CDO",
            "trigger_condition": "결제 시스템 변경 또는 해외 PG 연동 시",
            "actions": ["결제정보 저장 위치 점검", "해외 연동 시 암호화 여부 확인"],
            "system_guide": "결제시스템에서 해외 데이터 전송 시 자동 암호화 적용",
        },
        {
            "rule_code": "RULE-CRD-005", "priority": "LOW",
            "prohibition_name": "카드 이용한도 임의 축소 금지",
            "prohibition_desc": "회원 동의 없이 신용카드 이용한도 임의 축소",
            "law_name": "여신전문금융업법", "article": "제14조의3",
            "name": "카드 이용한도 변경 사전 통보 의무",
            "description": "이용한도 축소 30일 전 회원에게 사전 통보 및 이의 제기 절차 안내",
            "first_duty": "CCO", "second_duty": "CPO",
            "trigger_condition": "신용 악화 또는 리스크 관리 목적 한도 축소 시",
            "actions": ["30일 전 서면/앱 사전 통보", "이의 제기 처리 절차 운영"],
            "system_guide": "카드관리시스템에서 한도 축소 30일 전 자동 통보 발송",
        },
    ],

    "자산운용": [
        {
            "rule_code": "RULE-AMC-001", "priority": "HIGH",
            "prohibition_name": "펀드 운용 이해충돌 금지",
            "prohibition_desc": "자기 또는 관계인 이익을 위한 펀드 자산 운용",
            "law_name": "자본시장법", "article": "제85조",
            "name": "펀드 운용 이해충돌 방지 절차",
            "description": "운용역 개인 계좌 거래와 펀드 운용 간 이해충돌 예방, 거래 사전 신고 의무화",
            "first_duty": "CCO", "second_duty": "CRO",
            "trigger_condition": "운용역 개인 유가증권 거래 시",
            "actions": ["개인 거래 사전 신고", "펀드 편입 종목과의 충돌 여부 확인"],
            "system_guide": "트레이딩시스템에서 운용역 개인 거래와 펀드 편입 종목 자동 대조",
        },
        {
            "rule_code": "RULE-AMC-002", "priority": "HIGH",
            "prohibition_name": "기준가격(NAV) 산출 오류 금지",
            "prohibition_desc": "펀드 기준가격 산출 오류 방치 또는 고의 조작",
            "law_name": "자본시장법", "article": "제238조",
            "name": "펀드 기준가격 산출 정확성 관리",
            "description": "NAV 일별 독립 검증, 전일 대비 2% 이상 편차 발생 시 즉시 원인 규명",
            "first_duty": "CFO", "second_duty": "CRO",
            "trigger_condition": "매 영업일 NAV 산출 시",
            "actions": ["독립적 NAV 검증 절차 운영", "편차 발생 시 2시간 내 원인 보고"],
            "system_guide": "펀드관리시스템에서 NAV 자동 검증 및 편차 알림",
        },
        {
            "rule_code": "RULE-AMC-003", "priority": "HIGH",
            "prohibition_name": "투자 설명서 미교부 판매 금지",
            "prohibition_desc": "공모펀드 판매 시 투자설명서 미교부",
            "law_name": "자본시장법", "article": "제124조",
            "name": "펀드 판매 시 투자설명서 교부 의무",
            "description": "펀드 가입 전 투자설명서 교부 및 주요 내용 설명, 확인서 징구",
            "first_duty": "CCO", "second_duty": "CPO",
            "trigger_condition": "공모펀드 신규 가입 시",
            "actions": ["투자설명서 교부 및 서명 징구", "핵심 투자위험 구두 설명"],
            "system_guide": "판매시스템에서 투자설명서 서명 미완료 시 가입 차단",
        },
        {
            "rule_code": "RULE-AMC-004", "priority": "MEDIUM",
            "prohibition_name": "성과보수 부당 산정 금지",
            "prohibition_desc": "약관에 정한 기준과 다른 방식으로 성과보수 산정",
            "law_name": "자본시장법", "article": "제86조",
            "name": "성과보수 산정 기준 준수",
            "description": "성과보수 산정 시 약관 기준 준수 여부 준법감시팀 사전 검토",
            "first_duty": "CCO", "second_duty": "CFO",
            "trigger_condition": "성과보수 산정 주기 도래 시",
            "actions": ["성과보수 산정 내역 준법감시팀 검토", "약관 기준 대비 편차 확인"],
            "system_guide": "보수산정시스템에서 약관 기준 자동 대조 및 편차 알림",
        },
        {
            "rule_code": "RULE-AMC-005", "priority": "MEDIUM",
            "prohibition_name": "투자 집중 리스크 한도 초과 금지",
            "prohibition_desc": "단일 종목 10% 초과 편입 등 분산투자 의무 위반",
            "law_name": "자본시장법", "article": "제81조",
            "name": "펀드 분산투자 의무 준수",
            "description": "단일 종목 편입 비율 한도(10%) 실시간 모니터링 및 초과 시 즉시 조정",
            "first_duty": "CRO", "second_duty": "CCO",
            "trigger_condition": "매 거래일 포트폴리오 리밸런싱 시",
            "actions": ["종목별 편입 비율 일별 점검", "한도 초과 시 1거래일 내 조정"],
            "system_guide": "포트폴리오관리시스템에서 편입 비율 실시간 모니터링",
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# 헬퍼: 템플릿에서 DB 레코드 생성
# ─────────────────────────────────────────────────────────────────────────────
def _create_records_from_template(db: Session, client_id: str, industry: str, session_id: str) -> list[dict]:
    items = INDUSTRY_TEMPLATES.get(industry, [])
    if not items:
        return []

    created = []
    for t in items:
        # ProhibitedAct
        pa = ProhibitedAct(
            session_id=session_id,
            law_name=t["law_name"],
            article=t["article"],
            name=t["prohibition_name"],
            description=t["prohibition_desc"],
            priority=t["priority"],
            ai_generated=False,
            confirmed=True,
        )
        db.add(pa)
        db.flush()

        # DutyMapping
        dm = DutyMapping(
            prohibited_act_id=pa.id,
            first_duty=t["first_duty"],
            second_duty=t.get("second_duty"),
            ai_generated=False,
            confirmed=True,
            confirmed_at=datetime.utcnow(),
        )
        db.add(dm)
        db.flush()

        # BusinessRule
        br = BusinessRule(
            duty_mapping_id=dm.id,
            rule_code=t["rule_code"],
            name=t["name"],
            description=t["description"],
            trigger_condition=t.get("trigger_condition"),
            actions=t.get("actions", []),
            system_guide=t.get("system_guide"),
            status="completed",
        )
        db.add(br)
        created.append({"rule_code": t["rule_code"], "name": t["name"]})

    db.commit()
    return created


# ─────────────────────────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────────────────────────
router = APIRouter(tags=["templates"])


@router.get("/api/v1/templates/{industry}")
def preview_template(industry: str):
    """업권별 템플릿 미리보기 (적용 전 확인용)"""
    items = INDUSTRY_TEMPLATES.get(industry)
    if items is None:
        raise HTTPException(404, f"'{industry}' 업권 템플릿이 없습니다. 사용 가능: {list(INDUSTRY_TEMPLATES.keys())}")
    return {
        "industry": industry,
        "rule_count": len(items),
        "rules": [{"rule_code": t["rule_code"], "name": t["name"], "priority": t["priority"], "law_name": t["law_name"]} for t in items],
    }


@router.get("/api/v1/templates")
def list_templates():
    """사용 가능한 업권 목록"""
    return [
        {"industry": ind, "rule_count": len(rules)}
        for ind, rules in INDUSTRY_TEMPLATES.items()
    ]


@router.post("/api/v1/clients/{client_id}/apply-template")
def apply_template(client_id: str, body: dict, db: Session = Depends(get_db)):
    """
    고객사에 업권 맞춤 템플릿 적용.
    body: { "industry": "은행" }
    - 신규 AnalysisSession 생성
    - 업권별 ProhibitedAct + DutyMapping + BusinessRule 시드 삽입
    """
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "고객사를 찾을 수 없습니다.")

    industry = body.get("industry") or client.industry or ""
    if industry not in INDUSTRY_TEMPLATES:
        raise HTTPException(400, f"'{industry}' 업권 템플릿이 없습니다. 가능: {list(INDUSTRY_TEMPLATES.keys())}")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    session = AnalysisSession(
        client_id=client_id,
        label=f"{industry} 맞춤 템플릿 세션",
        period_type="1m",
        period_from=today,
        status="confirmed",
        confirmed_at=datetime.utcnow(),
    )
    db.add(session)
    db.flush()

    created = _create_records_from_template(db, client_id, industry, session.id)

    return {
        "status": "ok",
        "session_id": session.id,
        "industry": industry,
        "rules_created": len(created),
        "rules": created,
    }
