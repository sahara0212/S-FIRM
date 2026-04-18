"""
Railway 배포 시 초기 데이터 시드.
pre-computed 금지행위 + 업무규칙을 포함하여 탭 진입 즉시 데이터 표시.
"""
from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import Client, AnalysisSession, DutyStructure, ProhibitedAct, DutyMapping, BusinessRule

_CLIENT_ID  = '2c3c2685-63ff-48a6-a0d4-58e507d1485d'
_SESSION_ID = '0290acaa-133d-4f32-a473-0fcecb3d4bc3'

_EXECUTIVES = [{'role': '이사회의장', 'role_code': 'BOARD_CHAIR', 'std_code': 'BOARD_CHAIR', 'level': 4, 'name': None, 'parent_role': None, 'duties': [{'code': None, 'description': '이사회 운영의 절차 준수에 대한 책임'}, {'code': None, 'description': '이사회 소집 및 심의·의결 등에 관한 절차 준수'}, {'code': None, 'description': '내부통제 관련 이사회 안건 심의·의결 최종 책임'}]}, {'role': '대표이사', 'role_code': 'CEO', 'std_code': 'CEO', 'level': 3, 'name': None, 'parent_role': 'BOARD_CHAIR', 'duties': [{'code': None, 'description': '내부통제 등 전반적 집행·운영에 대한 최종적인 책임'}, {'code': None, 'description': 'AI 거버넌스 위원회 설치·운영 최종 책임'}, {'code': None, 'description': '고위험 AI 시스템 지정 및 관리 감독'}]}, {'role': '감사총괄', 'role_code': 'CHIEF_AUDIT', 'std_code': 'CHIEF_AUDIT', 'level': 2, 'name': None, 'parent_role': 'BOARD_CHAIR', 'duties': [{'code': None, 'description': '내부감사체제를 구축하고 운영·관리할 책임'}, {'code': None, 'description': 'AI 시스템 준법 감사 책임'}]}, {'role': '준법추진본부장', 'role_code': 'CCO', 'std_code': 'CCO', 'level': 2, 'name': None, 'parent_role': 'CEO', 'duties': [{'code': None, 'description': '법령 준수 여부 점검 및 이사회 보고 책임'}, {'code': None, 'description': '내부통제기준 AI 조항 포함 의무 관리'}]}, {'role': '계리/리스크관리본부장', 'role_code': 'CRO', 'std_code': 'CRO', 'level': 2, 'name': None, 'parent_role': 'CEO', 'duties': [{'code': None, 'description': '위험관리위원회 AI 위험 포함 심의 책임'}, {'code': None, 'description': 'AI 알고리즘 위험 및 데이터 위험 관리 체계 수립'}]}, {'role': '테크본부장 (CISO 겸직)', 'role_code': 'CISO', 'std_code': 'CISO', 'level': 2, 'name': None, 'parent_role': 'CEO', 'duties': [{'code': None, 'description': 'AI 보안 위협 대응 체계 수립 및 운영 책임'}, {'code': None, 'description': '생성형 AI 서비스 도입 시 추가 보안 검토 총괄'}]}, {'role': '고객경험혁신본부장', 'role_code': 'CPO', 'std_code': 'CPO', 'level': 2, 'name': None, 'parent_role': 'CEO', 'duties': [{'code': None, 'description': '개인정보 수집·이용·제공 관리 총괄 책임'}, {'code': None, 'description': 'AI 자동화 결정 별도 동의 프로세스 관리'}]}, {'role': '자산운용본부장', 'role_code': 'CDO', 'std_code': 'CDO', 'level': 2, 'name': None, 'parent_role': 'CEO', 'duties': [{'code': None, 'description': '마이데이터 표준 API 의무화 대응 총괄'}, {'code': None, 'description': 'AI 신용평가 핵심 판단근거 제공 체계 구축'}]}, {'role': '소비자보호본부장', 'role_code': 'CSO', 'std_code': 'CSO', 'level': 2, 'name': None, 'parent_role': 'CEO', 'duties': [{'code': None, 'description': '소비자보호파트 총괄 및 금융소비자 권익 보호 책임'}, {'code': None, 'description': 'AI 기반 보험심사 결과 이의신청 절차 운영'}]}, {'role': '영업부문장', 'role_code': 'SALES_HEAD', 'std_code': 'SALES_HEAD', 'level': 2, 'name': None, 'parent_role': 'CEO', 'duties': [{'code': None, 'description': '영업채널 전략수립 및 운영 책임'}, {'code': None, 'description': 'AI 기반 영업 시스템 도입 시 보안검토 요청 의무'}]}]

_SEED_PROHIBITIONS = [
    {'pid': 'f463e45c-6b34-eba9-7b55-78737e86c602', 'mid': '2b6c05e2-c682-d8b0-36bc-4e3a504294b5', 'rid': '4112b425-149e-fde6-a81b-0c7abb2e07ca', 'law_id': 'efsr', 'law_name': '전자금융감독규정', 'article': '제14조 제3항', 'name': '생성형 AI 서비스 도입 시 사전 보안성 검토 의무', 'description': '생성형 AI 서비스를 도입하기 전에 사전 보안성 검토를 실시하지 않는 행위', 'subject': '전자금융업자', 'target': '생성형 AI 서비스', 'trigger_condition': '생성형 AI 서비스 도입 시점', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CISO', 'second_duty': 'CEO', 'third_duty': 'CCO', 'rule_code': 'RULE-EFS-001', 'rule_name': '생성형 AI 서비스 도입 사전 보안성 검토', 'rule_description': '생성형 AI 서비스 도입 시 사전 보안성 검토를 의무적으로 실시', 'trigger_condition_rule': '생성형 AI 서비스 도입 검토 요청 발생 시', 'actions': ['CISO에게 보안성 검토 요청서 제출', 'CISO가 보안성 검토 실시 및 위험도 평가', '검토 결과를 CEO 및 CCO에게 보고', '승인 후 도입 진행'], 'exceptions': [], 'system_guide': '생성형 AI 서비스 도입 결재 프로세스에 사전 보안성 검토 단계 필수화'},
    {'pid': '83a95e7f-a6d1-9705-d9ab-f13af218e46b', 'mid': 'febdbeaf-8af9-66bf-1195-1b3e13e3fd38', 'rid': '44f1307c-d175-cee8-a59f-453fa6bb8cd5', 'law_id': 'itna', 'law_name': '정보통신망법', 'article': '제22조 제1항', 'name': 'AI 분석 목적 개인정보 수집 시 목적 고지 의무', 'description': 'AI 분석 목적으로 개인정보를 수집하는 경우 해당 목적을 별도로 고지하지 않는 행위', 'subject': '개인정보 수집자', 'target': '정보주체', 'trigger_condition': 'AI 분석 목적으로 개인정보 수집 시', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CPO', 'second_duty': 'CCO', 'third_duty': 'CEO', 'rule_code': 'RULE-ITN-001', 'rule_name': 'AI 분석 목적 개인정보 수집 시 목적 고지 의무', 'rule_description': 'AI 분석 목적으로 개인정보를 수집하는 경우 해당 목적을 별도로 고지하는 업무규칙', 'trigger_condition_rule': 'AI 분석을 위한 개인정보 수집 시작 시점', 'actions': ['개인정보 수집 목적을 AI 분석 용도로 명확히 문서화', '고객에게 AI 분석 목적 및 범위를 별도 고지', '개인정보처리방침에 AI 분석 항목 추가 및 공개', '수집 동의서에 AI 분석 목적 명시', 'CPO가 목적 고지 이행 여부 검증', 'CCO가 법규 준수 확인', 'CEO가 최종 승인'], 'exceptions': ['법령에서 명시적으로 개인정보 수집목적 고지를 면제하는 경우', '개인정보주체가 이미 목적을 알고 있는 경우'], 'system_guide': '개인정보 수집 시스템에 AI 분석 목적 고지 필드 필수 입력 설정, 미입력 시 수집 차단'},
    {'pid': '3d43e43e-9c84-9533-ef4d-6db301ee1f4a', 'mid': '91a1e075-0f83-6a95-3f5d-ba113c241bbe', 'rid': '6609cb63-ed9a-dd8d-8b31-9bbb4376655a', 'law_id': 'itna', 'law_name': '정보통신망법', 'article': '제45조 제3항', 'name': 'AI 시스템 보안 위협 대응 체계 미포함', 'description': '정보보호 관리체계 수립·운영 시 AI 시스템에 대한 보안 위협 대응 체계를 포함하지 않는 행위', 'subject': '정보통신서비스 제공자', 'target': '정보보호 관리체계', 'trigger_condition': '정보보호 관리체계 수립·운영', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CISO', 'second_duty': 'CRO', 'third_duty': 'CCO', 'rule_code': 'RULE-ITN-002', 'rule_name': 'AI 시스템 보안 위협 대응 체계 포함 의무', 'rule_description': '정보보호 관리체계 수립·운영 시 AI 시스템에 대한 보안 위협 대응 체계를 포함하는 업무규칙', 'trigger_condition_rule': '정보보호 관리체계 수립 또는 정기 검토 시점', 'actions': ['AI 시스템 보안 위협 식별 및 분류', 'AI 시스템별 보안 위협 대응 절차 수립', 'AI 시스템 보안 대응 체계를 정보보호 관리체계에 통합', 'AI 시스템 보안 위협 모니터링 체계 구축', 'CISO가 AI 시스템 보안 대응 체계 설계 및 검증', 'CRO가 위험 평가 및 대응 전략 승인', 'CCO가 법규 준수 확인'], 'exceptions': ['AI 시스템을 사용하지 않는 부서', '시스템 개발 초기 단계로 위협 분석 진행 중인 경우'], 'system_guide': '정보보호 관리체계 수립 문서에 AI 시스템 보안 위협 대응 섹션 필수 포함, AI 시스템 인벤토리와 연동'},
    {'pid': 'dfafb597-4568-8b2c-c796-3fb7db9d6c89', 'mid': '85a28ae6-3200-0036-6582-c021642a2b58', 'rid': 'c857a24a-9900-bf27-e9a5-d1ddeb653c85', 'law_id': 'cipa', 'law_name': '신용정보법', 'article': '32조 1항', 'name': '비표준 API를 통한 신용정보 전송 금지', 'description': '마이데이터 사업자가 표준화된 API 이외의 방식으로 신용정보를 전송하는 행위', 'subject': '마이데이터 사업자', 'target': '신용정보', 'trigger_condition': '신용정보 전송 시', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CDO', 'second_duty': 'CISO', 'third_duty': 'CCO', 'rule_code': 'RULE-CIP-001', 'rule_name': '신용정보 표준 API 전송 의무화', 'rule_description': '마이데이터 사업자의 신용정보 전송 시 금융위원회 표준화 API만 사용', 'trigger_condition_rule': '신용정보 전송 요청 발생', 'actions': ['전송 요청 시스템이 사용 API 표준 규격 확인', '비표준 API 감지 시 CISO에 즉시 보고 및 전송 차단', 'CCO 승인 후 적절한 표준 API로 재전송'], 'exceptions': [], 'system_guide': 'API 게이트웨이 수준에서 표준 규격 검증 필수, 모든 신용정보 전송 로그 기록'},
    {'pid': '0130b0b5-047a-f0bb-60c1-e77573f8297a', 'mid': '308375cc-9f57-b704-c894-5934e4a2ad37', 'rid': '8d6c6144-ea42-e335-7efc-60f79c772645', 'law_id': 'cipa', 'law_name': '신용정보법', 'article': '17조 2항', 'name': 'AI 신용평가 기준 미공시', 'description': 'AI 신용평가 시 주요 평가 기준을 신용정보주체에게 미제공하는 행위', 'subject': '신용평가 운영자', 'target': '신용정보주체', 'trigger_condition': 'AI 신용평가 실시 시', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CDO', 'second_duty': 'CPO', 'third_duty': 'CSO', 'rule_code': 'RULE-CIP-002', 'rule_name': 'AI 신용평가 기준 공시 의무화', 'rule_description': 'AI 신용평가 시행 시 주요 평가 기준을 신용정보주체에게 사전 공시', 'trigger_condition_rule': 'AI 기반 신용평가 결과 생성', 'actions': ['평가 모델 개발 단계에서 주요 기준 문서화 및 CPO 검토', '평가 결과 제공 전 신용정보주체에게 사용된 주요 기준 공시', 'CSO에서 공시 내용 적절성 및 법정 준수 최종 검증'], 'exceptions': [], 'system_guide': 'AI 평가 결과 발급 시스템에 공시 프로세스 통합, 공시 이력 DB 관리'},
    {'pid': '8ccdab6c-85a0-6156-feb0-3f85ec33e493', 'mid': '34827497-022d-621a-fd31-221351794309', 'rid': '31f31aa9-b794-7259-44e2-6b8b7575795b', 'law_id': 'pipa', 'law_name': '개인정보보호법', 'article': '제15조 제1항', 'name': 'AI 자동화 결정 명시적 동의 미획득', 'description': 'AI 자동화 결정에 활용되는 개인정보를 별도의 명시적 동의 없이 수집하는 행위', 'subject': '정보처리자', 'target': '정보주체', 'trigger_condition': '개인정보가 AI 자동화 결정에 활용되는 경우', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CPO', 'second_duty': 'CCO', 'third_duty': 'CEO', 'rule_code': 'RULE-PIP-001', 'rule_name': 'AI 자동화 결정 명시적 동의 획득', 'rule_description': 'AI 자동화 결정에 활용되는 개인정보 수집 시 사전 명시적 동의를 필수로 획득', 'trigger_condition_rule': 'AI 자동화 결정 대상 개인정보 수집 또는 처리 시작 단계', 'actions': ['CPO: 수집 대상 개인정보 목록 및 AI 활용 범위 검토', 'CCO: 명시적 동의서 양식 및 내용 승인', 'CEO: 최종 정책 시행 승인 및 공시'], 'exceptions': [], 'system_guide': '개인정보 수집 단계에서 AI 자동화 결정 활용 여부를 명시하고 별도 동의 체크박스 구현 필수'},
    {'pid': '06346b86-d240-eeda-c055-4415609ee682', 'mid': 'c4ef9f3d-ee6b-c302-434c-5957789fec27', 'rid': '468e8060-de3d-138f-1641-46e44c910739', 'law_id': 'pipa', 'law_name': '개인정보보호법', 'article': '제28조의2', 'name': '가명정보 알고리즘 투명성 미보장', 'description': '가명처리에 사용된 알고리즘의 투명성을 보장하지 않고 가명정보를 처리하는 행위', 'subject': '정보처리자', 'target': '정보주체', 'trigger_condition': '가명정보를 처리하는 경우', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CISO', 'second_duty': 'CPO', 'third_duty': 'CCO', 'rule_code': 'RULE-PIP-002', 'rule_name': '가명정보 알고리즘 투명성 보장', 'rule_description': '가명처리에 사용된 알고리즘의 투명성을 보장하고 이를 명시적으로 기록 및 관리', 'trigger_condition_rule': '가명정보 처리 또는 가명처리 알고리즘 개발·변경 시', 'actions': ['CISO: 알고리즘 보안성 및 암호화 강도 검증', 'CPO: 가명처리 방법론 및 알고리즘 명세서 작성', 'CCO: 투명성 준수 여부 및 문서화 완성도 감시'], 'exceptions': [], 'system_guide': '가명처리 알고리즘 상세 명세서 작성, 정보주체 요청 시 알고리즘 원리 설명 자료 즉시 제공 체계 구축'},
    {'pid': 'e17a3eae-3623-0388-2989-f907ec3aff36', 'mid': 'a673e26f-2ba3-223f-3aa7-2abd127d74d2', 'rid': '6b643539-e8e2-fa4e-7f3d-534f58a872e4', 'law_id': 'pipa', 'law_name': '개인정보보호법', 'article': '제35조', 'name': '자동화된 결정에 대한 설명 미제공', 'description': '정보주체가 요구할 시 자동화된 결정에 대한 설명을 제공하지 않는 행위', 'subject': '정보처리자', 'target': '정보주체', 'trigger_condition': '정보주체의 자동화된 결정 설명 요구', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CPO', 'second_duty': 'CDO', 'third_duty': 'CSO', 'rule_code': 'RULE-PIP-003', 'rule_name': '자동화된 결정에 대한 설명 제공', 'rule_description': '정보주체가 자동화된 결정에 대한 설명을 요구할 경우 합리적인 기한 내 설명 제공', 'trigger_condition_rule': '정보주체의 자동화 결정 설명 요청 접수 시', 'actions': ['CPO: 설명 요청 접수 및 해당 결정 기록 확인', 'CDO: 결정에 활용된 데이터 및 프로세스 분석 후 설명서 작성', 'CSO: 정보주체에게 설명서 전달 및 응답 기록 유지'], 'exceptions': [], 'system_guide': '요청 접수 후 30일 이내 설명 제공, 설명 요청-응답 이력 전자기록 보존, 거부 사유 있을 경우 거부 사유도 함께 통보'},
    {'pid': 'd05a5181-a960-2bdd-9d5a-ee7a678b9108', 'mid': '284394da-94ff-ca09-d04a-fe017d5ecf93', 'rid': '003076b1-fa8c-4e37-04ab-23368d3f5075', 'law_id': 'fgsl', 'law_name': '금융회사지배구조법', 'article': '제25조', 'name': 'AI 시스템 내부통제기준 미포함', 'description': 'AI 시스템 활용 사항을 내부통제기준에 포함하지 않는 행위', 'subject': '금융회사', 'target': '내부통제기준', 'trigger_condition': 'AI 시스템을 활용하면서 내부통제기준에 AI 활용 사항을 미포함', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CCO', 'second_duty': 'CEO', 'third_duty': '', 'rule_code': 'RULE-FGS-001', 'rule_name': 'AI 시스템 내부통제기준 포함', 'rule_description': 'AI 시스템 활용 사항을 내부통제기준에 포함하여 관리', 'trigger_condition_rule': '내부통제기준 수립 또는 개정 시', 'actions': ['AI 활용 현황 파악', '내부통제기준에 AI 시스템 항목 추가', 'CCO 검토 및 CEO 승인'], 'exceptions': [], 'system_guide': 'CCO가 주도하여 내부통제기준에 AI 시스템 관련 항목을 반드시 포함하고 CEO 승인을 받아야 함'},
    {'pid': '3a82ad22-6260-ebb0-7208-bc2e449a0433', 'mid': '042d7c7f-34b3-791a-c51b-901cb0fb36c1', 'rid': '13195f61-f533-702e-58f4-7b103f162b9a', 'law_id': 'fgsl', 'law_name': '금융회사지배구조법', 'article': '제25조', 'name': '준법감시인의 AI 관련 정기 감사 미실시', 'description': '준법감시인이 AI 시스템 관련 내부통제기준을 정기적으로 감사하지 않는 행위', 'subject': '준법감시인', 'target': 'AI 시스템 내부통제기준', 'trigger_condition': '정기 감사 일정을 수립하였으나 AI 관련 감사를 실시하지 않음', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CCO', 'second_duty': 'CEO', 'third_duty': '', 'rule_code': 'RULE-FGS-002', 'rule_name': 'AI 관련 정기 감사 실시', 'rule_description': '준법감시인이 AI 시스템 관련 내부통제기준을 정기적으로 감사', 'trigger_condition_rule': '연 1회 이상의 감사 주기 도래 시', 'actions': ['감사 계획 수립', 'AI 시스템 내부통제기준 감사 실행', '감사 결과 보고 및 개선안 도출'], 'exceptions': [], 'system_guide': 'CCO 소속 준법감시인이 최소 연 1회 이상 AI 시스템 관련 내부통제 감사를 실시하고 CEO에 보고'},
    {'pid': '6b455449-25e1-756d-96f6-fe65c9556260', 'mid': '64e72823-f237-336b-9240-9235d75a6bba', 'rid': 'b01cad7b-a02b-bae1-a883-965d966a953f', 'law_id': 'fgsl', 'law_name': '금융회사지배구조법', 'article': '제26조 제2항', 'name': '위험관리위원회의 AI 위험 심의 미실시', 'description': '위험관리위원회가 AI 알고리즘 및 데이터 관련 위험을 심의 안건에 포함하지 않는 행위', 'subject': '위험관리위원회', 'target': 'AI 알고리즘, 데이터 위험', 'trigger_condition': '위험관리위원회 개최 시 AI 관련 위험을 심의 안건에서 제외', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CRO', 'second_duty': 'CEO', 'third_duty': '', 'rule_code': 'RULE-FGS-003', 'rule_name': 'AI 위험 심의 실시', 'rule_description': '위험관리위원회가 AI 알고리즘 및 데이터 관련 위험을 심의 안건에 포함', 'trigger_condition_rule': '위험관리위원회 개최 시 또는 분기별 정기 회의', 'actions': ['AI 관련 위험 항목 식별', '위험관리위원회 안건에 포함', '위험 평가 및 대응 방안 심의'], 'exceptions': [], 'system_guide': 'CRO가 주도하여 AI 알고리즘, 데이터 품질, 시스템 안정성 등 관련 위험을 위험관리위원회에 정기적으로 보고하고 CEO에 경보'},
    {'pid': 'dc260c2d-7b35-b176-cff3-186202bcaa79', 'mid': 'c0a38b53-f01b-e01e-4287-947611b8e43a', 'rid': '39080035-9d66-4772-1739-4f95af558f02', 'law_id': 'fgsl', 'law_name': '금융회사지배구조법', 'article': '제3조 제1항', 'name': 'AI 활용 업무 내부통제 책임자 미지정', 'description': 'AI 활용 업무 내부통제 책임자를 지정하지 않는 행위', 'subject': '금융회사', 'target': 'AI 활용 업무 내부통제', 'trigger_condition': 'AI 활용 업무를 수행하면서 책임자 지정 미실시', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CEO', 'second_duty': 'CCO', 'third_duty': '', 'rule_code': 'RULE-FGS-004', 'rule_name': 'AI 활용 업무 내부통제 책임자 지정', 'rule_description': 'AI 활용 업무에 대한 내부통제 책임자를 명확히 지정', 'trigger_condition_rule': 'AI 활용 업무 신규 도입 시 또는 조직 개편 시', 'actions': ['AI 활용 업무 범위 정의', '책임자 지정 결정', 'CEO 승인 및 공식 공지'], 'exceptions': [], 'system_guide': 'CEO가 CCO와 협의하여 AI 활용 업무별 내부통제 책임자를 명확히 지정하고 공식화'},
    {'pid': 'cfcc99ce-49fb-82e1-c23c-8c1c6f59052c', 'mid': '7b9528de-f388-1979-dae5-d2d672559bb0', 'rid': '3c474706-a376-1a3d-1ff1-34bb1e44881a', 'law_id': 'fgsl', 'law_name': '금융회사지배구조법', 'article': '제3조 제1항', 'name': '책무구조도에 AI 활용 업무 책임자 미반영', 'description': 'AI 활용 업무 내부통제 책임자를 책무구조도에 반영하지 않는 행위', 'subject': '금융회사', 'target': '책무구조도', 'trigger_condition': '책무구조도 수립 시 AI 활용 업무 책임자를 미포함', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CEO', 'second_duty': 'CCO', 'third_duty': '', 'rule_code': 'RULE-FGS-005', 'rule_name': '책무구조도에 AI 활용 업무 책임자 반영', 'rule_description': 'AI 활용 업무 내부통제 책임자를 조직의 책무구조도에 반영', 'trigger_condition_rule': '책무구조도 수립 또는 개정 시', 'actions': ['AI 활용 업무 책임자 확인', '책무구조도 개정', 'CCO 검토 및 CEO 승인'], 'exceptions': [], 'system_guide': 'CEO가 주도하여 CCO 협의 하에 AI 활용 업무 내부통제 책임자를 공식 책무구조도에 명시'},
    {'pid': 'd080bd5c-3860-d63a-a029-5e4ec3c1c3b2', 'mid': '4202062b-5005-5994-8f62-84798245f3ec', 'rid': '1bde86c6-8a82-13f2-c8ef-54adc94f2d37', 'law_id': 'fgsl', 'law_name': '금융회사지배구조법', 'article': '제12조', 'name': 'AI 대주주 적격성 심사 이의신청 절차 미마련', 'description': 'AI 대주주 적격성 심사 결과에 대한 이의신청 절차를 마련하지 않는 행위', 'subject': '금융회사', 'target': 'AI 대주주 적격성 심사 절차', 'trigger_condition': 'AI 관련 대주주 적격성 심사 시 이의신청 절차 부재', 'exception': '없음', 'priority': 'MEDIUM', 'first_duty': 'CSO', 'second_duty': 'CEO', 'third_duty': 'CCO', 'rule_code': 'RULE-FGS-006', 'rule_name': 'AI 대주주 적격성 심사 이의신청 절차 마련', 'rule_description': 'AI 대주주 적격성 심사 결과에 대한 이의신청 절차를 수립하고 운영', 'trigger_condition_rule': '대주주 적격성 심사 관련 업무 수립 시 또는 규정 개정 시', 'actions': ['이의신청 절차 설계', '이의신청 처리 규정 수립', 'CSO 주도 검토 및 CEO, CCO 승인'], 'exceptions': [], 'system_guide': 'CSO가 주도하여 AI 대주주 적격성 심사에 대한 명확한 이의신청 절차를 마련하고 CEO, CCO 승인 획득 후 공지'},
    {'pid': 'a431f7e1-9ef9-f998-ea05-09c3c98e1303', 'mid': '5c87d914-f3d4-1657-6587-d167ff4fa437', 'rid': 'a63d3d88-70e9-3efe-3830-fc2723ef395a', 'law_id': 'aiba', 'law_name': 'AI기본법', 'article': '10조', 'name': '고위험 AI 시스템 미등록', 'description': '고위험 AI 시스템을 지정하지 않거나 관계 기관에 등록하지 않는 행위', 'subject': 'AI 시스템 개발·배포자', 'target': '고위험 AI 시스템', 'trigger_condition': '고위험 AI 시스템 개발 또는 배포 시', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CEO', 'second_duty': 'CRO', 'third_duty': 'CCO', 'rule_code': 'RULE-AIB-001', 'rule_name': '고위험 AI 시스템 등록 의무', 'rule_description': '고위험 AI 시스템을 지정하고 관계 기관에 등록하는 업무규칙', 'trigger_condition_rule': '고위험 AI 시스템 개발 또는 도입 시점', 'actions': ['CRO가 고위험 AI 시스템 여부 판단 및 지정', 'CCO가 시스템 사양서 및 위험도 평가서 준비', 'CEO 승인 후 관계 기관에 등록 신청', '등록 완료 증명서 보관 및 정기 점검'], 'exceptions': ['저위험 AI 시스템', '규제 유예 대상 시스템'], 'system_guide': 'AI 시스템 레지스트리에서 고위험 등급 확인 및 자동 알림 활성화'},
    {'pid': '716907d1-82aa-1527-47bc-e4f2da9d98ee', 'mid': 'bac26e6b-5435-6ef6-d204-5f2c2c4aec8a', 'rid': '6c6e7a18-0846-4c38-c2a8-f6dd4894cad5', 'law_id': 'aiba', 'law_name': 'AI기본법', 'article': '15조', 'name': '위험성 평가 미실시 또는 미기록', 'description': '배포 전 위험성 평가를 실시하지 않거나 그 결과를 기록·보관하지 않는 행위', 'subject': 'AI 시스템 개발·배포자', 'target': 'AI 시스템', 'trigger_condition': 'AI 시스템 배포 전', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CRO', 'second_duty': 'CISO', 'third_duty': 'CCO', 'rule_code': 'RULE-AIB-002', 'rule_name': 'AI 시스템 위험성 평가 및 기록', 'rule_description': '배포 전 위험성 평가를 실시하고 결과를 기록·보관하는 업무규칙', 'trigger_condition_rule': 'AI 시스템 배포 또는 업데이트 전', 'actions': ['CISO가 위험성 평가 체크리스트 수립', 'CRO가 위험성 평가 실시 및 문서화', 'CCO가 평가 결과 검토 및 승인', '평가 결과 기록 5년 이상 보관'], 'exceptions': ['경미한 유지보수', '버그 패치'], 'system_guide': '위험성 평가 시스템에서 배포 전 평가 완료 상태 확인 필수'},
    {'pid': 'f33799e6-7411-f7b2-f791-88aaac34149a', 'mid': 'acb6d254-c239-5353-9408-7101a0a8461e', 'rid': '1ad33b75-acb1-961c-bd76-f85f44facff5', 'law_id': 'aiba', 'law_name': 'AI기본법', 'article': '20조', 'name': '중대한 사고 미보고', 'description': '중대한 사고 발생 시 즉시 관계 기관에 보고하지 않는 행위', 'subject': 'AI 시스템 운영자', 'target': '중대한 AI 사고', 'trigger_condition': '중대한 사고 발생', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CRO', 'second_duty': 'CEO', 'third_duty': 'CCO', 'rule_code': 'RULE-AIB-003', 'rule_name': 'AI 중대 사고 즉시 보고', 'rule_description': '중대한 사고 발생 시 관계 기관에 즉시 보고하는 업무규칙', 'trigger_condition_rule': 'AI 시스템 관련 중대 사고 발생', 'actions': ['사고 감지 즉시 CRO 보고', 'CRO가 사고 상황 정리 및 CEO에 보고', 'CEO 승인 후 24시간 내 관계 기관 보고', 'CCO가 보고 내용 검증 및 기록 관리'], 'exceptions': ['가상 테스트 환경에서의 사고'], 'system_guide': '사고 보고 시스템에서 자동으로 타임스탬프 기록 및 보고 진행상황 추적'},
    {'pid': '42e200e4-5b16-02fd-01ff-ed3250c178e7', 'mid': '37b1ee97-13e7-ac5c-8b53-03ed698cc5eb', 'rid': '02775fed-ab26-a7c1-ca5b-88daadd54c95', 'law_id': 'aiba', 'law_name': 'AI기본법', 'article': '25조', 'name': 'AI 활용 미고지', 'description': '이용자에게 AI 활용 여부를 사전에 고지하지 않는 행위', 'subject': 'AI 시스템 운영자', 'target': '이용자', 'trigger_condition': 'AI 시스템 활용', 'exception': '없음', 'priority': 'MEDIUM', 'first_duty': 'CSO', 'second_duty': 'CPO', 'third_duty': 'CCO', 'rule_code': 'RULE-AIB-004', 'rule_name': 'AI 활용 사전 고지 의무', 'rule_description': '이용자에게 AI 활용 여부를 사전에 고지하는 업무규칙', 'trigger_condition_rule': 'AI 시스템을 활용한 서비스 제공 시점', 'actions': ['CSO가 AI 활용 여부 식별 및 고지 방안 결정', 'CPO가 이용자 고지 문구 작성 및 검토', 'CCO 승인 후 서비스 제공 채널에 고지', '고지 이력 기록 및 이용자 동의 관리'], 'exceptions': ['실시간 시스템 장애 상황', '긴급 보안 조치'], 'system_guide': '서비스 제공 시스템에서 AI 고지 여부 자동 확인 및 미고지 시 배포 차단'},
    {'pid': 'fa2c3353-f4a9-1d46-053b-1334f0643e2c', 'mid': '859ff0dc-ea05-49cd-c19b-533c8ae7696c', 'rid': '2d59de59-1f55-5c55-27f6-a2ea2cb92270', 'law_id': 'aiba', 'law_name': 'AI기본법', 'article': '30조', 'name': 'AI 거버넌스 위원회 미설치', 'description': 'AI 윤리 및 위험 관리를 위한 거버넌스 위원회를 설치·운영하지 않는 행위', 'subject': 'AI 시스템 개발·배포 기관', 'target': '조직 내부', 'trigger_condition': '고위험 AI 시스템 개발·배포', 'exception': '없음', 'priority': 'HIGH', 'first_duty': 'CEO', 'second_duty': 'CCO', 'third_duty': 'CRO', 'rule_code': 'RULE-AIB-005', 'rule_name': 'AI 거버넌스 위원회 설치 및 운영', 'rule_description': 'AI 윤리 및 위험 관리를 위한 거버넌스 위원회를 설치·운영하는 업무규칙', 'trigger_condition_rule': '회사의 AI 시스템 도입 또는 확대 시점', 'actions': ['CEO가 거버넌스 위원회 설치 결정 및 규정 승인', 'CCO가 위원회 구성 및 운영 방안 수립', 'CRO가 정기 회의 개최 및 위험 관리 안건 주재', '위원회 회의록 및 결의사항 기록 관리'], 'exceptions': [], 'system_guide': '거버넌스 관리 시스템에서 위원회 정기 개최 일정 관리 및 미개최 시 알림 발생'},
]


def seed_initial_data() -> None:
    db = SessionLocal()
    try:
        # 1. Client
        if not db.get(Client, _CLIENT_ID):
            db.add(Client(
                id=_CLIENT_ID, name="테스트은행", industry="은행",
                note="기본 테스트 고객사",
                created_at=datetime(2026, 4, 17, 0, 56, 3),
                updated_at=datetime(2026, 4, 17, 0, 56, 3),
            ))
            db.commit()

        # 2. AnalysisSession
        if not db.get(AnalysisSession, _SESSION_ID):
            db.add(AnalysisSession(
                id=_SESSION_ID, client_id=_CLIENT_ID,
                label="2026-04 정기 검토", status="mapping",
                created_at=datetime(2026, 4, 17, 0, 56, 3),
            ))
            db.commit()

        # 3. DutyStructure
        existing_ds = (
            db.query(DutyStructure)
            .filter(DutyStructure.client_id == _CLIENT_ID, DutyStructure.is_active == True)
            .first()
        )
        if not existing_ds:
            db.add(DutyStructure(
                client_id=_CLIENT_ID, executives=_EXECUTIVES,
                is_active=True, parsed_at=datetime(2026, 4, 17, 23, 32, 34),
            ))
            db.commit()

        # 4. Pre-computed 금지행위 + 매핑 + 업무규칙 (없을 때만)
        existing_acts = db.query(ProhibitedAct).filter(
            ProhibitedAct.session_id == _SESSION_ID
        ).count()
        if existing_acts == 0:
            for item in _SEED_PROHIBITIONS:
                act = ProhibitedAct(
                    id=item['pid'], session_id=_SESSION_ID,
                    law_id=item['law_id'], law_name=item['law_name'],
                    article=item['article'], name=item['name'],
                    description=item['description'], subject=item['subject'],
                    target=item['target'], trigger_condition=item['trigger_condition'],
                    exception=item['exception'], priority=item['priority'],
                    ai_generated=True, confirmed=False,
                )
                db.add(act)
                db.flush()

                mapping = DutyMapping(
                    id=item['mid'], prohibited_act_id=item['pid'],
                    first_duty=item['first_duty'], second_duty=item['second_duty'],
                    third_duty=item['third_duty'],
                    ai_generated=True, confirmed=False,
                )
                db.add(mapping)
                db.flush()

                if item.get('rule_name'):
                    rule = BusinessRule(
                        id=item['rid'], duty_mapping_id=item['mid'],
                        rule_code=item['rule_code'], name=item['rule_name'],
                        description=item['rule_description'],
                        trigger_condition=item['trigger_condition_rule'],
                        actions=item['actions'], exceptions=item['exceptions'],
                        system_guide=item['system_guide'], status='draft',
                    )
                    db.add(rule)

            db.commit()

    finally:
        db.close()
