from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def describe_file(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("models", type=Path, nargs="+")
    args = parser.parse_args()
    missing = [str(path) for path in args.models if not path.is_file()]
    if missing:
        parser.error("missing model files: " + ", ".join(missing))
    payload = {"models": [describe_file(path) for path in args.models]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
