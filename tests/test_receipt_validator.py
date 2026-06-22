from src.receipt_validator import ScriptedReceiptValidator

v = ScriptedReceiptValidator()


def test_eric_wilson_approved_reply1():
    r = v.validate("ERIC WILSON", reply_count=1)
    assert r.approved is True
    assert r.failed_items == []


def test_todd_bahr_approved_reply1():
    r = v.validate("TODD BAHR", reply_count=1)
    assert r.approved is True
    assert r.failed_items == []


def test_kim_watroba_partial_fail_reply1():
    r = v.validate("KIM WATROBA", reply_count=1)
    assert r.approved is False
    assert "SCREAMING FROG LTD" in r.failed_items
    assert "EPN*EXPERIAN BIZCREDIT" in r.failed_items
    assert len(r.failed_items) == 2


def test_kim_watroba_approved_reply2():
    r = v.validate("KIM WATROBA", reply_count=2)
    assert r.approved is True


def test_cory_bach_partial_fail_reply1():
    r = v.validate("CORY BACH", reply_count=1)
    assert r.approved is False
    assert len(r.failed_items) == 6
    assert "AVIS RENT-A-CAR" in r.failed_items
    assert "FAST PARK CLEVELAND FPR" in r.failed_items


def test_cory_bach_partial_fail_reply2():
    """Cory fails on reply 2 too — deadline set by coordinator at this step."""
    r = v.validate("CORY BACH", reply_count=2)
    assert r.approved is False
    assert len(r.failed_items) == 6


def test_cory_bach_approved_reply3():
    """Cory approved on reply 3 — coordinator checks deadline before calling."""
    r = v.validate("CORY BACH", reply_count=3)
    assert r.approved is True


def test_unknown_employee_approved():
    r = v.validate("JANE DOE", reply_count=1)
    assert r.approved is True
