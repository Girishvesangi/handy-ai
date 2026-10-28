"""Run evals and write the results the web app's /evals page shows.

    python -m evals retrieval
    python -m evals steps --proxy 40
    python -m evals stats
    python -m evals all --proxy 40     # everything, then publish to the web app
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

RESULTS = Path(__file__).parent / "results"
WEB_PUBLIC = Path(__file__).resolve().parents[2] / "web" / "public" / "eval-results.json"


def save(name: str, data: dict) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(data, indent=2))
    print(json.dumps(data, indent=2))


def publish() -> None:
    combined = {"generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
    for name in ("retrieval", "steps", "stats"):
        path = RESULTS / f"{name}.json"
        if path.exists():
            combined[name] = json.loads(path.read_text())
    WEB_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    WEB_PUBLIC.write_text(json.dumps(combined, indent=2))
    print(f"Published results to {WEB_PUBLIC}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("which", choices=["retrieval", "steps", "stats", "all", "publish"])
    parser.add_argument("--proxy", type=int, default=0, help="number of proxy step-check cases to build")
    args = parser.parse_args()
    load_dotenv()

    if args.which in ("retrieval", "all"):
        from . import retrieval

        save("retrieval", retrieval.run())
    if args.which in ("steps", "all"):
        from . import step_check

        save("steps", step_check.run(proxy=args.proxy))
    if args.which in ("stats", "all"):
        from . import stats

        save("stats", stats.run())
    if args.which in ("all", "publish"):
        publish()


if __name__ == "__main__":
    main()
