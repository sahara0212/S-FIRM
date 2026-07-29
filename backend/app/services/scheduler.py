"""
APScheduler 기반 자동 실행 스케줄러
매일 06:00 KST (= 21:00 UTC) 전체 파이프라인 자동 실행
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.database import SessionLocal
from app.db.models import Client, AnalysisSession, DutyStructure
from app.services.pipeline_runner import run_and_save

logger = logging.getLogger(__name__)


async def _daily_pipeline():
    """모든 고객사의 최신 세션에 대해 파이프라인 자동 실행"""
    logger.info("[스케줄러] 매일 새벽 파이프라인 자동 실행 시작")
    db = SessionLocal()
    try:
        clients = db.query(Client).all()
        for client in clients:
            # 가장 최근 분석 세션
            session = (
                db.query(AnalysisSession)
                .filter(AnalysisSession.client_id == client.id)
                .order_by(AnalysisSession.created_at.desc())
                .first()
            )
            if not session:
                logger.info(f"[스케줄러] {client.name}: 세션 없음, 스킵")
                continue

            # 활성 책무구조
            ds = (
                db.query(DutyStructure)
                .filter(
                    DutyStructure.client_id == client.id,
                    DutyStructure.is_active == True,
                )
                .order_by(DutyStructure.parsed_at.desc())
                .first()
            )
            if not ds:
                logger.info(f"[스케줄러] {client.name}: 책무구조 없음, 스킵")
                continue

            try:
                result = run_and_save(client.id, session, ds, db)
                if result.get("error"):
                    logger.error(f"[스케줄러] {client.name}: {result['error']}")
                else:
                    logger.info(
                        f"[스케줄러] {client.name}: "
                        f"금지행위 {result['prohibition_count']}건 · "
                        f"업무규칙 {result['rule_count']}건 완료"
                    )
            except Exception as e:
                logger.error(f"[스케줄러] {client.name} 파이프라인 실패: {e}")
    finally:
        db.close()

    logger.info("[스케줄러] 자동 실행 완료")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _daily_pipeline,
        trigger=CronTrigger(hour=21, minute=0, timezone="UTC"),  # 06:00 KST
        id="daily_pipeline",
        name="매일 새벽 6시 자율 파이프라인",
        replace_existing=True,
        misfire_grace_time=3600,  # 1시간 내 지연 실행 허용
    )
    return scheduler
