from app.generators.editorial_style import SEPIA_TELEGRAM_EDITORIAL_PASS


def test_editorial_pass_preserves_fact_boundary():
    assert "меняет только подачу" in SEPIA_TELEGRAM_EDITORIAL_PASS
    assert "Не добавляй новые цифры" in SEPIA_TELEGRAM_EDITORIAL_PASS


def test_editorial_pass_targets_telegram_readability():
    assert "Telegram-канала" in SEPIA_TELEGRAM_EDITORIAL_PASS
    assert "одинаковым" in SEPIA_TELEGRAM_EDITORIAL_PASS
