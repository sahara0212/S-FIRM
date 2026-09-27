from app.db.citation_corrections import CORRECTIONS, NEEDS_VERIFICATION, VERIFY_MARKER, apply_citation_corrections
from app.db.database import SessionLocal
from app.db.models import ProhibitedAct
from app.db.seed import _SEED_PROHIBITIONS
from app.main import app  # noqa: F401  (import 시 DB 생성·시드·교정)


def test_every_correction_targets_a_seed_item_with_its_original_article():
    seed = {item["pid"]: item for item in _SEED_PROHIBITIONS}
    for pid, fix in CORRECTIONS.items():
        assert seed[pid]["article"] == fix["old_article"]
    assert set(NEEDS_VERIFICATION) <= set(seed)
    assert not set(CORRECTIONS) & set(NEEDS_VERIFICATION)


def test_seeded_database_carries_corrected_citations():
    db = SessionLocal()
    try:
        high = db.get(ProhibitedAct, "a431f7e1-9ef9-f998-ea05-09c3c98e1303")
        assert (high.law_name, high.article) == ("AI기본법", "제33조")
        assert high.duty_mapping.business_rule.name == "고영향 인공지능 해당 여부 사전 검토"
        itna = db.get(ProhibitedAct, "83a95e7f-a6d1-9705-d9ab-f13af218e46b")
        assert (itna.law_name, itna.article) == ("개인정보보호법", "제15조 제1항")
        flagged = db.get(ProhibitedAct, "f33799e6-7411-f7b2-f791-88aaac34149a")
        assert flagged.description.count(VERIFY_MARKER) == 1
        # 다시 실행해도 중복 교정·중복 표시가 없다
        assert apply_citation_corrections(db) == 0
    finally:
        db.close()


def test_user_edited_citation_is_left_alone():
    db = SessionLocal()
    try:
        act = db.get(ProhibitedAct, "716907d1-82aa-1527-47bc-e4f2da9d98ee")
        act.article = "제34조 제1항(담당자 수정)"
        db.commit()
        apply_citation_corrections(db)
        db.refresh(act)
        assert act.article == "제34조 제1항(담당자 수정)"
    finally:
        db.close()
