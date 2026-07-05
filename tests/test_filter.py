from backend.filter import is_candidate


def test_url_plus_keyword_is_candidate():
    assert is_candidate("Apply now: https://org.org/jobs — deadline Friday") is True


def test_keyword_without_url_is_not_candidate():
    assert is_candidate("we are hiring, DM me") is False


def test_url_without_keyword_is_not_candidate():
    assert is_candidate("cool paper https://arxiv.org/abs/1234") is False


def test_plain_chatter_is_not_candidate():
    assert is_candidate("thanks, see you there!") is False


def test_email_plus_keyword_is_candidate():
    assert is_candidate("Hiring a research assistant — email jobs@safety.org to apply") is True


def test_email_without_keyword_is_not_candidate():
    assert is_candidate("my address is bob@example.com btw") is False


def test_no_contact_vector_is_not_candidate():
    # keyword alone, with neither URL nor email, still filtered out
    assert is_candidate("we should really open applications sometime") is False
