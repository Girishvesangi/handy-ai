"""Client for the public iFixit API v2.0 (https://www.ifixit.com/api/2.0).

We use two endpoints:
  GET /search/{query}?filter=guide  -> find guide ids
  GET /guides/{guideid}             -> full guide with steps and images

The parsing is kept separate from the HTTP calls so it can be tested
against saved JSON.
"""

from __future__ import annotations

import re
import time
import urllib.parse

import requests

from .guides import Guide, Step

API = "https://www.ifixit.com/api/2.0"
USER_AGENT = "handy-ai (portfolio project; https://github.com/Girishvesangi/handy-ai)"

# Image sizes iFixit returns per media item, from smallest to largest.
_PREFERRED_SIZES = ("large", "medium", "standard", "original")

_TAGS = re.compile(r"<[^>]+>")
_MARKUP = re.compile(r"\[(?:link|guide_link)\|[^|\]]*\|([^\]]*)\]")


def clean_text(raw: str | None) -> str:
    """Strip iFixit wiki markup and HTML so the text reads well when spoken."""
    if not raw:
        return ""
    text = _MARKUP.sub(r"\1", raw)  # [link|url|label] -> label
    text = _TAGS.sub("", text)
    text = text.replace("[*]", "").replace("[/*]", "")
    text = re.sub(r"\[/?[a-z_]+\]", "", text)  # [b], [/b], [icon_caution] ...
    text = text.replace("'''", "").replace("''", "")  # wiki bold / italic
    return re.sub(r"\s+", " ", text).strip()


def _image_url(media_item: dict) -> str | None:
    for size in _PREFERRED_SIZES:
        if media_item.get(size):
            return media_item[size]
    return None


def parse_guide(data: dict) -> Guide:
    steps: list[Step] = []
    for i, raw_step in enumerate(data.get("steps", []), start=1):
        lines = [clean_text(line.get("text_raw")) for line in raw_step.get("lines", [])]
        media = raw_step.get("media") or {}
        images: list[str] = []
        if media.get("type") == "image":
            images = [u for u in (_image_url(m) for m in media.get("data", [])) if u]
        steps.append(
            Step(
                number=i,
                title=clean_text(raw_step.get("title")),
                lines=[line for line in lines if line],
                image_urls=images,
            )
        )

    tools = [clean_text(t.get("text")) for t in data.get("tools", []) if t.get("text")]
    return Guide(
        id=int(data["guideid"]),
        title=clean_text(data.get("title")),
        device=clean_text(data.get("category") or data.get("subject") or ""),
        url=data.get("url", f"https://www.ifixit.com/Guide/_/{data['guideid']}"),
        difficulty=data.get("difficulty") or "",
        time_required=data.get("time_required") or "",
        introduction=clean_text(data.get("introduction_raw")),
        tools=tools,
        steps=steps,
    )


def parse_search_results(data: dict) -> list[int]:
    return [
        int(r["guideid"])
        for r in data.get("results", [])
        if r.get("dataType") == "guide" and r.get("guideid")
    ]


class IFixitClient:
    def __init__(self, delay_s: float = 0.5, timeout_s: float = 15) -> None:
        self._http = requests.Session()
        self._http.headers["User-Agent"] = USER_AGENT
        self._delay_s = delay_s  # be polite: one request at a time, with a pause
        self._timeout_s = timeout_s

    def _get(self, path: str, **params) -> dict:
        resp = self._http.get(f"{API}{path}", params=params, timeout=self._timeout_s)
        resp.raise_for_status()
        time.sleep(self._delay_s)
        return resp.json()

    def search_guide_ids(self, query: str, limit: int = 20) -> list[int]:
        q = urllib.parse.quote(query)
        return parse_search_results(self._get(f"/search/{q}", filter="guide", limit=limit))

    def get_guide(self, guide_id: int) -> Guide:
        return parse_guide(self._get(f"/guides/{guide_id}"))
