from backend.filter import is_candidate


def test_url_plus_keyword_is_candidate():
    assert is_candidate("Apply now: https://org.org/jobs — deadline Friday") is True


def test_keyword_without_url_is_not_candidate():
    assert is_candidate("we are hiring, DM me") is False


def test_url_without_keyword_is_not_candidate():
    assert is_candidate("cool paper https://arxiv.org/abs/1234") is False


def test_plain_chatter_is_not_candidate():
    assert is_candidate("thanks, see you there!") is False
