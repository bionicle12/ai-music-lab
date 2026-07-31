from __future__ import annotations

import argparse
from pathlib import Path

from music_lab_ui.ui_service import AnalysisService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the complete UI analysis service without opening a browser."
    )
    parser.add_argument("audio", type=Path)
    parser.add_argument(
        "--detectors",
        nargs="+",
        default=["lofcz", "FST"],
        choices=["lofcz", "FST"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = AnalysisService()

    def progress(message: str, fraction: float) -> None:
        print(f"{fraction:.0%} {message}", flush=True)

    outcome = service.analyze(
        str(args.audio),
        args.detectors,
        "E2E UI smoke",
        progress=progress,
    )
    print(f"run_id={outcome.run.run_id}")
    for result in outcome.run.results:
        print(
            f"{result.detector}: status={result.status} "
            f"probability={result.probability} device={result.device} "
            f"error={result.error}"
        )


if __name__ == "__main__":
    main()
