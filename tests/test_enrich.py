from backend.enrich import enrich_deadline, page_text


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


def test_page_text_strips_html_and_scripts():
    html = "<html><script>var x=1;</script><body><h1>Apply now</h1><p>Deadline: July 22, 2026</p></body></html>"
    text = page_text("https://x.org", get=lambda url, **kw: FakeResponse(html))
    assert "Apply now" in text
    assert "Deadline: July 22, 2026" in text
    assert "var x=1" not in text


def test_page_text_returns_none_on_error():
    def get(url, **kw):
        raise OSError("down")

    assert page_text("https://x.org", get=get) is None


def test_enrich_deadline_returns_iso_date():
    deadline = enrich_deadline(
        "https://x.org/apply",
        page_text_fn=lambda url: "Applications close July 22, 2026",
        find_fn=lambda text: "2026-07-22",
    )
    assert deadline == "2026-07-22"


def test_enrich_deadline_rejects_non_iso():
    deadline = enrich_deadline(
        "https://x.org/apply",
        page_text_fn=lambda url: "whenever",
        find_fn=lambda text: "sometime in July",
    )
    assert deadline is None


def test_enrich_deadline_none_when_page_unreachable():
    assert enrich_deadline(
        "https://x.org", page_text_fn=lambda url: None, find_fn=lambda text: "2026-07-22",
    ) is None


def test_enrich_respects_spend_guard():
    calls = []

    class NoBudget:
        def try_acquire(self):
            return False

    deadline = enrich_deadline(
        "https://x.org",
        page_text_fn=lambda url: "text",
        find_fn=lambda text: calls.append(1) or "2026-07-22",
        spend_guard=NoBudget(),
    )
    assert deadline is None
    assert calls == []  # no LLM call once the cap is spent
