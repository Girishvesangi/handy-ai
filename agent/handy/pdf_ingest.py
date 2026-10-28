"""Turn a PDF service manual into Handy guides.

Many laptops have an official service manual (Dell, Lenovo and HP publish
them) with removal procedures that iFixit doesn't cover. This reads the PDF
with Gemini, pulls out each procedure as a step-by-step guide, and adds them
to data/guides.json next to the iFixit guides.

Usage (from the agent/ folder):
    python -m handy.pdf_ingest manual.pdf --device "Dell Latitude 5490"
    python -m handy.pdf_ingest manual.pdf --device "ThinkPad T14" --url https://...manual.pdf --embed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .guides import Guide, Step, load_guides, save_guides

PDF_MODEL = os.getenv("PDF_MODEL") or os.getenv("CHECKER_MODEL") or "gemini-3.8-flash"

PROMPT = """This is a laptop service manual for: {device}.

Extract every removal, replacement, or installation procedure as a guide.
For each guide give:
- title: e.g. "{device} Battery Replacement"
- tools: tools the procedure needs (empty list if none are named)
- steps: in order. Each step has a short title and its instruction lines,
  rewritten as short, clear sentences a beginner could follow out loud.
  Keep every warning (ESD, battery, disconnect power) as its own line.
- page: the page number where the procedure starts.

Skip specifications, part lists, diagnostics, and BIOS sections.
Only use what the manual says; don't invent steps."""

SCHEMA = {
    "type": "object",
    "properties": {
        "guides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "page": {"type": "integer"},
                    "tools": {"type": "array", "items": {"type": "string"}},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "lines": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["title", "lines"],
                        },
                    },
                },
                "required": ["title", "steps"],
            },
        }
    },
    "required": ["guides"],
}


def stable_id(device: str, title: str) -> int:
    """Negative ids keep manual guides from ever clashing with iFixit's positive ids."""
    digest = hashlib.sha1(f"{device}|{title}".encode()).hexdigest()
    return -int(digest[:12], 16)


def to_guides(data: dict, device: str, url: str) -> list[Guide]:
    guides = []
    for g in data.get("guides", []):
        steps = [
            Step(number=i, title=s.get("title", ""), lines=[line for line in s.get("lines", []) if line])
            for i, s in enumerate(g.get("steps", []), start=1)
        ]
        if len(steps) < 2:
            continue
        page = g.get("page")
        guides.append(
            Guide(
                id=stable_id(device, g["title"]),
                title=g["title"],
                device=device,
                url=f"{url}#page={page}" if url and page else url,
                difficulty="",
                time_required="",
                introduction=f"From the {device} service manual" + (f", page {page}." if page else "."),
                tools=g.get("tools", []),
                steps=steps,
            )
        )
    return guides


def extract(pdf: Path, device: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client()
    uploaded = client.files.upload(file=str(pdf), config={"mime_type": "application/pdf"})
    resp = client.models.generate_content(
        model=PDF_MODEL,
        contents=[uploaded, PROMPT.format(device=device)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
            temperature=0.0,
        ),
    )
    return json.loads(resp.text or "{}")


def merge(existing: list[Guide], new: list[Guide]) -> list[Guide]:
    """Replace guides with the same id, keep everything else."""
    new_ids = {g.id for g in new}
    return [g for g in existing if g.id not in new_ids] + new


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--device", required=True, help='laptop model, e.g. "Dell Latitude 5490"')
    parser.add_argument("--url", default="", help="public link to the manual, shown in the app")
    parser.add_argument("--embed", action="store_true", help="embed the new guides for hybrid search")
    args = parser.parse_args(argv)

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger("pdf_ingest")

    log.info("Reading %s with %s (this can take a minute for long manuals)...", args.pdf, PDF_MODEL)
    new = to_guides(extract(args.pdf, args.device), args.device, args.url)
    if not new:
        log.error("No procedures found in the manual.")
        return 1

    guides = merge(load_guides(), new)
    if args.embed or any(g.embedding for g in guides):
        # Hybrid search needs every guide embedded, so embed whatever is missing.
        from .embeddings import Embedder

        missing = [g for g in guides if not g.embedding]
        vectors = Embedder().embed_documents([g.search_text() for g in missing])
        for g, v in zip(missing, vectors):
            g.embedding = list(v)

    save_guides(guides)
    for g in new:
        log.info("  + %s (%d steps)", g.title, len(g.steps))
    log.info("Added %d guides from the manual. %d guides total.", len(new), len(guides))
    return 0


if __name__ == "__main__":
    sys.exit(main())
