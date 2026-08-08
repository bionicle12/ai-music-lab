from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LabPaths:
    root: Path
    lofcz_upstream: Path
    fst_upstream: Path
    lofcz_model: Path
    fst_stage1: Path
    fst_stage2: Path
    muscriptor_upstream: Path
    lofcz_python: Path
    fst_python: Path
    muscriptor_python: Path
    lofcz_script: Path
    lofcz_adapter: Path
    fst_adapter: Path
    muscriptor_adapter: Path
    muscriptor_cache: Path
    history_db: Path
    runs_dir: Path
    settings_path: Path
    midi_dir: Path
    sunofix_dir: Path

    @classmethod
    def from_root(cls, root: Path) -> "LabPaths":
        resolved = root.resolve()
        parent = resolved.parent
        envs_dir = Path(sys.executable).resolve().parent.parent
        lofcz_python = Path(
            os.environ.get(
                "AI_MUSIC_LOFCZ_PYTHON",
                envs_dir / "ai-music-lofcz" / "python.exe",
            )
        )
        fst_python = Path(
            os.environ.get(
                "AI_MUSIC_FST_PYTHON",
                envs_dir / "ai-music-fst" / "python.exe",
            )
        )
        muscriptor_python = Path(
            os.environ.get(
                "AI_MUSIC_MUSCRIPTOR_PYTHON",
                envs_dir / "ai-music-muscriptor" / "python.exe",
            )
        )
        return cls(
            root=resolved,
            lofcz_upstream=parent / "ai-music-detector",
            fst_upstream=parent / "FST-AI-Music-Detection",
            lofcz_model=resolved / "models" / "lofcz" / "ai_music_detector.onnx",
            fst_stage1=resolved / "models" / "fst" / "Stage-1.ckpt",
            fst_stage2=resolved / "models" / "fst" / "Stage-2.ckpt",
            muscriptor_upstream=parent / "muscriptor",
            lofcz_python=lofcz_python,
            fst_python=fst_python,
            muscriptor_python=muscriptor_python,
            lofcz_script=parent
            / "ai-music-detector"
            / "src"
            / "python"
            / "inference.py",
            lofcz_adapter=resolved / "adapters" / "lofcz_cli.py",
            fst_adapter=resolved / "adapters" / "fst_cli.py",
            muscriptor_adapter=resolved / "adapters" / "muscriptor_cli.py",
            # Handed to muscriptor as HF_HOME. The transcription weights are
            # gigabytes and reach disk through huggingface_hub, whose default
            # cache is on the system drive; keeping them here puts them beside
            # models/lofcz and models/fst where the project already looks.
            muscriptor_cache=resolved / "models" / "muscriptor-cache",
            history_db=resolved / "data" / "history.sqlite3",
            runs_dir=resolved / "data" / "runs",
            settings_path=resolved / "data" / "settings.json",
            midi_dir=resolved / "output" / "midi",
            sunofix_dir=resolved / "output" / "sunofix",
        )


def default_paths() -> LabPaths:
    return LabPaths.from_root(Path(__file__).resolve().parent.parent)
