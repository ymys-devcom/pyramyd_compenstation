from src.excel_parser import parse_transactions

FIXTURE = "tests/fixtures/sample_transactions.xlsx"


def test_returns_three_cardholders():
    result = parse_transactions(FIXTURE)
    assert len(result) == 3


def test_cardholder_names():
    names = {ch.name for ch in parse_transactions(FIXTURE)}
    assert names == {"CORY BACH", "TODD BAHR", "ARIEL BENEWIAT"}


def test_each_has_email_field():
    for ch in parse_transactions(FIXTURE):
        assert isinstance(ch.email, str)


def test_cory_has_three_transactions():
    cardholders = {ch.name: ch for ch in parse_transactions(FIXTURE)}
    assert len(cardholders["CORY BACH"].transactions) == 3


def test_amounts_are_floats():
    for ch in parse_transactions(FIXTURE):
        for tx in ch.transactions:
            assert isinstance(tx.amount, float)


def test_merchant_names_non_empty():
    for ch in parse_transactions(FIXTURE):
        for tx in ch.transactions:
            assert tx.merchant_name.strip() != ""
