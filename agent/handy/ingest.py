"""Download laptop repair guides from iFixit into data/guides.json.

Usage (from the agent/ folder):
    python -m handy.ingest                 # fetch guides, keyword search only
    python -m handy.ingest --embed         # also compute Gemini embeddings (needs GOOGLE_API_KEY)
    python -m handy.ingest --max 200       # fetch more guides

Guides come from iFixit under CC BY-NC-SA. Credit iFixit wherever you show them.
"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

from .guides import DEFAULT_GUIDES_PATH, Guide, load_guides, save_guides
from .ifixit import IFixitClient

# Searches that cover the most common laptop repairs on popular models.
QUERIES = [
    "MacBook Air battery replacement",
    "MacBook Pro battery replacement",
    "MacBook Pro SSD replacement",
    "MacBook Air trackpad replacement",
    "MacBook keyboard replacement",
    "MacBook fan replacement",
    "Lenovo ThinkPad battery replacement",
    "Lenovo ThinkPad RAM replacement",
    "Lenovo ThinkPad SSD replacement",
    "ThinkPad keyboard replacement",
    "Dell XPS battery replacement",
    "Dell XPS SSD replacement",
    "Dell Inspiron RAM replacement",
    "Dell Latitude battery replacement",
    "HP Pavilion battery replacement",
    "HP laptop RAM replacement",
    "HP EliteBook SSD replacement",
    "Acer Aspire hard drive replacement",
    "Acer laptop RAM upgrade",
    "ASUS ZenBook battery replacement",
    "ASUS laptop SSD replacement",
    "laptop fan cleaning",
    "laptop thermal paste replacement",
    "laptop CMOS battery replacement",
    "laptop screen replacement",
    "laptop DC jack replacement",
    "laptop bottom cover removal",
    "Microsoft Surface Laptop battery replacement",
    "Chromebook battery replacement",
    "laptop wifi card replacement",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max", type=int, default=120, help="maximum number of guides to keep")
    parser.add_argument("--per-query", type=int, default=8, help="guides to take from each search")
    parser.add_argument("--embed", action="store_true", help="compute embeddings with Gemini")
    parser.add_argument("--embed-only", action="store_true", help="skip fetching; embed the existing file")
    args = parser.parse_args(argv)

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger("ingest")

    if args.embed_only:
        guides = load_guides()
        if not guides:
            log.error("No guides at %s. Run without --embed-only first.", DEFAULT_GUIDES_PATH)
            return 1
    else:
        guides = fetch(args.max, args.per_query, log)

    if args.embed or args.embed_only:
        from .embeddings import Embedder

        log.info("Embedding %d guides with Gemini...", len(guides))
        vectors = Embedder().embed_documents([g.search_text() for g in guides])
        for g, v in zip(guides, vectors):
            g.embedding = list(v)

    save_guides(guides)
    total_steps = sum(len(g.steps) for g in guides)
    log.info("Saved %d guides (%d steps) to %s", len(guides), total_steps, DEFAULT_GUIDES_PATH)
    return 0


def fetch(max_guides: int, per_query: int, log: logging.Logger) -> list[Guide]:
    client = IFixitClient()
    seen: set[int] = set()
    guides: list[Guide] = []
    for query in QUERIES:
        if len(guides) >= max_guides:
            break
        try:
            ids = client.search_guide_ids(query, limit=per_query * 2)
        except Exception as e:  # keep going if one search fails
            log.warning("search failed for %r: %s", query, e)
            continue
        taken = 0
        for gid in ids:
            if gid in seen or taken >= per_query or len(guides) >= max_guides:
                continue
            seen.add(gid)
            try:
                guide = client.get_guide(gid)
            except Exception as e:
                log.warning("  could not fetch guide %s: %s", gid, e)
                continue
            if len(guide.steps) < 2:
                continue  # skip stubs
            guides.append(guide)
            taken += 1
            log.info("  [%d] %s (%d steps)", len(guides), guide.title, len(guide.steps))
    return guides


if __name__ == "__main__":
    sys.exit(main())
