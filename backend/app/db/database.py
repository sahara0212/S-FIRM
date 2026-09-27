import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# DB 파일은 프로젝트 루트의 data/ 폴더에 저장
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DB_PATH  = os.path.join(_BASE_DIR, "data", "sfirm.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

# 테스트·운영 환경에서 DB를 분리할 수 있도록 환경변수를 우선한다.
DATABASE_URL = os.getenv("SFIRM_DATABASE_URL", f"sqlite:///{_DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.db import models  # noqa: F401 — 모델 import로 테이블 등록
    Base.metadata.create_all(bind=engine)
