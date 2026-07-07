import json
import logging

from pydantic import ValidationError

from backend.models import Opportunity

log = logging.getLogger("extract")

VOCAB = {
    "job",
    "internship",
    "fellowship",
    "grant",
    "event",
    "course",
    "reading-group",
    "other",
}

SYSTEM_PROMPT = (
    "You extract AI-safety opportunities from chat messages. "
    "Return ONLY a JSON object with these keys: "
    "is_opportunity (bool), title, org, type, deadline, link, location (strings or null), "
    "remote (bool), categories (array), description (string or null). "
    "description: 2-3 sentences describing the opportunity using the message's own "
    "wording where possible — what it is, who it's for, and what's offered; null if "
    "the message adds nothing beyond the title. "
    "Set is_opportunity false for chatter, questions, reactions, or anything without a "
    "concrete opening, deadline, or application path. "
    f"type must be one of: {', '.join(sorted(VOCAB))}. "
    "categories: one or more of \"tech\" (technical/research/engineering), "
    "\"gov\" (policy, governance, government), \"other\" — multiple allowed when a role "
    "spans both. "
    "deadline must be an ISO date (YYYY-MM-DD) or null; if the message gives a date "
    "without a year, assume the next future occurrence. "
    "link must be the official application/info URL, or null. "
    "PRIVACY: never include an individual's personal contact details. Replace any personal "
    "email, phone number, or 'DM me'/handle with the official application link or email; if "
    "there is no official link, set link to null."
)


class ExtractionError(Exception):
    pass


class Extractor:
    def __init__(self, client, model: str, today_fn=None):
        self.client = client
        self.model = model
        if today_fn is None:
            from datetime import date

            today_fn = lambda: date.today().isoformat()  # noqa: E731
        self.today_fn = today_fn

    def _call(self, content: str) -> str:
        # The model has no clock: without today's date it resolves year-less
        # deadlines ("July 22nd") into the past (live bug).
        system = f"Today's date is {self.today_fn()}. " + SYSTEM_PROMPT
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return resp.choices[0].message.content

    def extract(self, content: str) -> Opportunity | None:
        last_err: Exception | None = None
        for _ in range(2):
            try:
                opp = Opportunity.model_validate_json(self._call(content))
                if not opp.is_opportunity:
                    return None
                if opp.type not in VOCAB:
                    opp.type = "other"
                return opp
            except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as err:
                # Malformed model OUTPUT only — transport/provider errors are
                # not caught here and propagate (the worker retries those).
                last_err = err
        # Deterministic malformed output is a poison pill: at temperature 0 the
        # next retry fails identically, forever, burning the spend cap. Treat
        # it as not-an-opportunity and move on.
        log.warning("persistently malformed extraction output; skipping (%s)", last_err)
        return None
