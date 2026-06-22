from src.whitelist import is_whitelisted


def test_amazon_variant_matched():
    assert is_whitelisted("AMAZON MKTPL*NQ10Q3GX2") is True


def test_amazon_exact_matched():
    assert is_whitelisted("AMAZON") is True


def test_unrelated_merchant_not_matched():
    assert is_whitelisted("LOWES #01023*") is False


def test_harbor_freight_not_matched():
    assert is_whitelisted("HARBOR FREIGHT TOOLS3249") is False


def test_case_insensitive():
    assert is_whitelisted("amazon marketplace") is True


def test_partial_word_match():
    # "amazon" is contained in "amazonian"
    assert is_whitelisted("AMAZONIAN SUPPLIES") is True
