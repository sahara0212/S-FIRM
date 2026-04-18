"""
Railway 배포 시 초기 데이터 시드.
DB가 비어있을 때(= 최초 배포 or 재배포) 기본 client/session/DutyStructure 를 생성한다.
이미 존재하면 아무것도 하지 않는다.
"""
from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import Client, AnalysisSession, DutyStructure

# ── 하드코딩된 기본 데이터 (프론트엔드 ACTIVE_CLIENT_ID / SESSION_ID 와 동일) ──
_CLIENT_ID  = "2c3c2685-63ff-48a6-a0d4-58e507d1485d"
_SESSION_ID = "0290acaa-133d-4f32-a473-0fcecb3d4bc3"

_EXECUTIVES = [
    {"role": "이사회의장", "role_code": "BOARD_CHAIR", "std_code": "BOARD_CHAIR", "level": 4,
     "name": None, "parent_role": None,
     "duties": [
         {"code": None, "description": "이사회 운영의 절차 준수에 대한 책임"},
         {"code": None, "description": "이사회 소집 및 심의·의결 등에 관한 절차 준수"},
         {"code": None, "description": "내부통제 관련 이사회 안건 심의·의결 최종 책임"},
     ]},
    {"role": "대표이사", "role_code": "CEO", "std_code": "CEO", "level": 3,
     "name": None, "parent_role": "BOARD_CHAIR",
     "duties": [
         {"code": None, "description": "내부통제 등 전반적 집행·운영에 대한 최종적인 책임"},
         {"code": None, "description": "임원 자격요건 적합여부 감독 책임"},
         {"code": None, "description": "전사 임원의 책무 배분 및 책무구조도 관리·감독 책임"},
         {"code": None, "description": "AI 거버넌스 위원회 설치·운영 최종 책임 (AI기본법 제30조)"},
         {"code": None, "description": "고위험 AI 시스템 지정 및 관리 감독 (AI기본법 제10조)"},
         {"code": None, "description": "소비자보호혁신TF 운영 총괄"},
     ]},
    {"role": "감사총괄", "role_code": "CHIEF_AUDIT", "std_code": "CHIEF_AUDIT", "level": 2,
     "name": None, "parent_role": "BOARD_CHAIR",
     "duties": [
         {"code": None, "description": "내부감사체제를 구축하고 운영·관리할 책임"},
         {"code": None, "description": "감사업무 수행 및 감사업무 후속조치에 대한 책임"},
         {"code": None, "description": "소관조직 내부통제정책 등 운영 및 이행여부 관리·감독 책임"},
         {"code": None, "description": "AI 시스템 준법 감사 책임 (금융회사지배구조법 제25조)"},
     ]},
    {"role": "준법추진본부장", "role_code": "CCO", "std_code": "CCO", "level": 2,
     "name": None, "parent_role": "CEO",
     "duties": [
         {"code": None, "description": "법령 준수 여부 점검 및 이사회 보고 책임"},
         {"code": None, "description": "AI 시스템의 법령 준수 여부 정기 감사 책임 (지배구조법 제25조)"},
         {"code": None, "description": "내부통제기준 AI 조항 포함 의무 관리 (지배구조법 제3조 제1항)"},
         {"code": None, "description": "준법추진파트 업무 총괄"},
         {"code": None, "description": "임직원 준법 교육 및 모니터링"},
     ]},
    {"role": "계리/리스크관리본부장", "role_code": "CRO", "std_code": "CRO", "level": 2,
     "name": None, "parent_role": "CEO",
     "duties": [
         {"code": None, "description": "신용위험·시장위험·운영위험 관리 총괄"},
         {"code": None, "description": "위험관리위원회 AI 위험 포함 심의 책임 (지배구조법 제26조제2항)"},
         {"code": None, "description": "계리지원Unit, 리스크관리파트, 계리운영파트, 가치평가파트 총괄"},
         {"code": None, "description": "AI 알고리즘 위험 및 데이터 위험 관리 체계 수립"},
     ]},
    {"role": "테크본부장 (CISO 겸직)", "role_code": "CISO", "std_code": "CISO", "level": 2,
     "name": None, "parent_role": "CEO",
     "duties": [
         {"code": None, "description": "정보보호 관련 업무 총괄 (정보통신망법 제45조제3항)"},
         {"code": None, "description": "AI 보안 위협 대응 체계 수립 및 운영 책임"},
         {"code": None, "description": "생성형 AI 서비스 도입 시 추가 보안 검토 총괄 (전자금융감독규정 제14조제3항)"},
         {"code": None, "description": "IT기획운영파트, IT개발파트, AI추진파트, 정보보호파트 총괄"},
         {"code": None, "description": "고위험 AI 위험성 평가 절차 수립 (AI기본법 제15조)"},
     ]},
    {"role": "고객경험혁신본부장", "role_code": "CPO", "std_code": "CPO", "level": 2,
     "name": None, "parent_role": "CEO",
     "duties": [
         {"code": None, "description": "개인정보 수집·이용·제공 관리 총괄 책임 (개인정보보호법 제15조)"},
         {"code": None, "description": "AI 자동화 결정 별도 동의 프로세스 관리"},
         {"code": None, "description": "가명처리 알고리즘 투명성 보장 의무 (개인정보보호법 제28조제2항)"},
         {"code": None, "description": "자동화 결정 설명 요구권 대응 체계 구축 (개인정보보호법 제35조)"},
         {"code": None, "description": "고객컨택파트, 계약관리파트, 보험금파트, 신계약업무파트 총괄"},
     ]},
    {"role": "자산운용본부장", "role_code": "CDO", "std_code": "CDO", "level": 2,
     "name": None, "parent_role": "CEO",
     "duties": [
         {"code": None, "description": "마이데이터 표준 API 의무화 대응 총괄 (신용정보법 제32조)"},
         {"code": None, "description": "AI 신용평가 핵심 판단근거 제공 체계 구축 (신용정보법 제17조제2항)"},
         {"code": None, "description": "자산심사Unit, 자산운용기획파트, 자산운용관리파트, 변액비즈파트 총괄"},
         {"code": None, "description": "특별계정연금운용팀 리스크 관리"},
     ]},
    {"role": "소비자보호본부장", "role_code": "CSO", "std_code": "CSO", "level": 2,
     "name": None, "parent_role": "CEO",
     "duties": [
         {"code": None, "description": "소비자보호파트 총괄 및 금융소비자 권익 보호 책임"},
         {"code": None, "description": "AI 기반 보험심사 결과 이의신청 절차 운영 (AI기본법 관련)"},
         {"code": None, "description": "소비자보호혁신TF 연계 운영"},
         {"code": None, "description": "금융소비자보호법 준수 총괄"},
     ]},
    {"role": "영업부문장", "role_code": "SALES_HEAD", "std_code": "SALES_HEAD", "level": 2,
     "name": None, "parent_role": "CEO",
     "duties": [
         {"code": None, "description": "영업채널(GA, BA, DM, 교차) 전략수립 및 운영 책임"},
         {"code": None, "description": "영업추진파트, GA1~6사업단, BA본부, 지방권GA본부, LP본부 총괄"},
         {"code": None, "description": "영업채널 시책비 집행 및 프로모션 수립·관리"},
         {"code": None, "description": "AI 기반 영업 시스템 도입 시 보안검토 요청 의무"},
     ]},
]


def seed_initial_data() -> None:
    db = SessionLocal()
    try:
        # 1. Client
        if not db.get(Client, _CLIENT_ID):
            db.add(Client(
                id=_CLIENT_ID,
                name="테스트은행",
                industry="은행",
                note="기본 테스트 고객사",
                created_at=datetime(2026, 4, 17, 0, 56, 3),
                updated_at=datetime(2026, 4, 17, 0, 56, 3),
            ))
            db.commit()

        # 2. AnalysisSession
        if not db.get(AnalysisSession, _SESSION_ID):
            db.add(AnalysisSession(
                id=_SESSION_ID,
                client_id=_CLIENT_ID,
                label="2026-04 정기 검토",
                status="draft",
                created_at=datetime(2026, 4, 17, 0, 56, 3),
            ))
            db.commit()

        # 3. DutyStructure (active 없을 때만)
        existing_ds = (
            db.query(DutyStructure)
            .filter(DutyStructure.client_id == _CLIENT_ID, DutyStructure.is_active == True)
            .first()
        )
        if not existing_ds:
            db.add(DutyStructure(
                client_id=_CLIENT_ID,
                executives=_EXECUTIVES,
                is_active=True,
                parsed_at=datetime(2026, 4, 17, 23, 32, 34),
            ))
            db.commit()

    finally:
        db.close()
