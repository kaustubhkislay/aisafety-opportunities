import json

from pydantic import ValidationError

from backend.models import Opportunity

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
    "remote (bool). "
    "Set is_opportunity false for chatter, questions, reactions, or anything without a "
    "concrete opening, deadline, or application path. "
    f"type must be one of: {', '.join(sorted(VOCAB))}. "
    "deadline must be an ISO date (YYYY-MM-DD) or null. "
    "link must be the official application/info URL, or null. "
    "PRIVACY: never include an individual's personal contact details. Replace any personal "
    "email, phone number, or 'DM me'/handle with the official application link or email; if "
    "there is no official link, set link to null."
)


class ExtractionError(Exception):
    pass


class Extractor:
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def _call(self, content: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
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
            except (ValidationError, ValueError, json.JSONDecodeError) as err:
                last_err = err
        raise ExtractionError(f"extraction failed after retry: {last_err}")
