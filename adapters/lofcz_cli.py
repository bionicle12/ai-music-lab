from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from scipy.ndimage import minimum_filter1d


def compute_fakeprint_telemetry(
    mean_spectrum_db: np.ndarray,
    frequency_bins_hz: np.ndarray,
    *,
    freq_min: float,
    freq_max: float,
    hull_area: int,
    min_db: float,
    max_db: float,
) -> dict[str, np.ndarray]:
    mask = (frequency_bins_hz >= freq_min) & (frequency_bins_hz <= freq_max)
    frequencies = np.asarray(frequency_bins_hz[mask], dtype=np.float32)
    spectrum = np.asarray(mean_spectrum_db[mask], dtype=np.float32)
    hull = minimum_filter1d(spectrum, size=hull_area, mode="nearest")
    hull = np.clip(hull, min_db, None).astype(np.float32)
    residue = np.clip(spectrum - hull, 0, None).astype(np.float32)
    clipped = np.clip(residue, 0, max_db).astype(np.float32)
    maximum = float(np.max(clipped)) if clipped.size else 0.0
    fakeprint = clipped / (maximum + 1e-6)
    if maximum > 0:
        fakeprint[np.argmax(clipped)] = 1.0
    return {
        "frequency_hz": frequencies,
        "mean_spectrum_db": spectrum,
        "lower_hull_db": hull,
        "residue_db": residue,
        "fakeprint": fakeprint.astype(np.float32),
    }


def strongest_peaks(
    frequencies: np.ndarray,
    fakeprint: np.ndarray,
    limit: int = 12,
) -> list[dict[str, float]]:
    order = np.argsort(np.asarray(fakeprint))[::-1][:limit]
    return [
        {
            "frequency_hz": float(frequencies[index]),
            "fakeprint": float(fakeprint[index]),
        }
        for index in order
    ]


def plan_windows(
    duration_seconds: float,
    window_seconds: float,
    hop_seconds: float,
) -> list[tuple[float, float]]:
    """Sliding windows covering the track, plus a tail window flush to the end."""
    if duration_seconds <= 0:
        raise ValueError("duration must be positive")
    if window_seconds <= 0 or hop_seconds <= 0:
        raise ValueError("window and hop must be positive")
    if duration_seconds <= window_seconds:
        return [(0.0, float(duration_seconds))]

    windows: list[tuple[float, float]] = []
    start = 0.0
    while start + window_seconds <= duration_seconds + 1e-9:
        windows.append((start, start + window_seconds))
        start += hop_seconds
    if duration_seconds - windows[-1][1] > 1e-9:
        windows.append((duration_seconds - window_seconds, float(duration_seconds)))
    return windows


def frames_in_window(
    frame_times_seconds: np.ndarray,
    start_seconds: float,
    end_seconds: float,
) -> np.ndarray:
    """Indices of STFT frames inside a window; never empty for a non-empty track."""
    times = np.asarray(frame_times_seconds, dtype=np.float64)
    selected = np.nonzero((times >= start_seconds) & (times < end_seconds))[0]
    if selected.size:
        return selected
    if not times.size:
        return selected
    centre = (start_seconds + end_seconds) / 2.0
    return np.array([int(np.argmin(np.abs(times - centre)))], dtype=np.int64)


@contextmanager
def upstream_import_context(upstream: Path) -> Iterator[None]:
    python_dir = upstream.resolve() / "src" / "python"
    previous_flag = sys.dont_write_bytecode
    sys.path.insert(0, str(python_dir))
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = previous_flag
        if sys.path and sys.path[0] == str(python_dir):
            sys.path.pop(0)


def analyze(
    upstream: Path,
    model: Path,
    audio_path: Path,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    with upstream_import_context(upstream):
        import torch
        from inference import AIDetector

        detector = AIDetector(model_path=str(model))
        audio = detector.load_audio(str(audio_path)).to(detector.device)
        if audio.shape[0] > 1:
            audio = audio.mean(dim=0, keepdim=True)
        with torch.no_grad():
            spectrum = detector.stft(audio)
        spectrum_db = 10 * torch.log10(torch.clamp(spectrum, min=1e-10, max=1e6))
        mean_spectrum = spectrum_db.mean(dim=(0, 2)).cpu().numpy()
        arrays = compute_fakeprint_telemetry(
            mean_spectrum,
            detector.freq_bins,
            freq_min=detector.freq_min,
            freq_max=detector.freq_max,
            hull_area=detector.hull_area,
            min_db=detector.min_db,
            max_db=detector.max_db,
        )
        fakeprint = arrays["fakeprint"]
        if fakeprint.size != detector.expected_features:
            old_axis = np.linspace(0, 1, fakeprint.size)
            new_axis = np.linspace(0, 1, detector.expected_features)
            fakeprint = np.interp(new_axis, old_axis, fakeprint).astype(np.float32)
            arrays["frequency_hz"] = np.interp(
                new_axis,
                old_axis,
                arrays["frequency_hz"],
            ).astype(np.float32)
            for name in (
                "mean_spectrum_db",
                "lower_hull_db",
                "residue_db",
            ):
                arrays[name] = np.interp(
                    new_axis,
                    old_axis,
                    arrays[name],
                ).astype(np.float32)
            arrays["fakeprint"] = fakeprint
        probability = float(
            detector.session.run(
                None,
                {detector.input_name: fakeprint.reshape(1, -1)},
            )[0][0, 0]
        )
        is_ai = probability >= 0.5
        payload = {
            "probability": probability,
            "is_ai": is_ai,
            "label": "AI-Generated" if is_ai else "Real Music",
            "confidence": abs(probability - 0.5) * 2,
            "telemetry": {
                "detector": "lofcz",
                "scalars": {
                    "sample_rate": detector.sample_rate,
                    "n_fft": detector.n_fft,
                    "max_duration_seconds": detector.max_duration,
                    "analyzed_duration_seconds": audio.shape[-1]
                    / detector.sample_rate,
                    "frequency_min_hz": detector.freq_min,
                    "frequency_max_hz": detector.freq_max,
                    "feature_count": detector.expected_features,
                    "hull_area_bins": detector.hull_area,
                    "residue_clip_db": detector.max_db,
                    "minimum_hull_db": detector.min_db,
                    "strongest_peaks": strongest_peaks(
                        arrays["frequency_hz"],
                        arrays["fakeprint"],
                    ),
                },
                "warnings": [
                    "The lofcz fakeprint is averaged across time and is not a temporal localization."
                ],
            },
        }
        return payload, arrays


def analyze_timeline(
    upstream: Path,
    model: Path,
    audio_path: Path,
    *,
    window_seconds: float,
    hop_seconds: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Score the fakeprint in sliding windows to localize it along the track.

    The upstream feature is a full-track time average and cannot localize on its
    own. Averaging a shorter span keeps the same feature definition but gives a
    noisier estimate off the model's training distribution, so the curve is a
    relative map inside one track — not a calibrated per-second probability.
    """
    with upstream_import_context(upstream):
        import torch
        from inference import AIDetector

        detector = AIDetector(model_path=str(model))
        audio = detector.load_audio(str(audio_path)).to(detector.device)
        if audio.shape[0] > 1:
            audio = audio.mean(dim=0, keepdim=True)
        duration = audio.shape[-1] / detector.sample_rate
        with torch.no_grad():
            spectrum = detector.stft(audio)
        spectrum_db = 10 * torch.log10(torch.clamp(spectrum, min=1e-10, max=1e6))
        # Collapse channels only; the time axis is what we slice.
        frames_db = spectrum_db.mean(dim=0).cpu().numpy()
        stft_hop = int(getattr(detector.stft, "hop_length", detector.n_fft // 2))
        frame_times = np.arange(frames_db.shape[-1]) * stft_hop / detector.sample_rate

        windows = plan_windows(duration, window_seconds, hop_seconds)
        starts: list[float] = []
        ends: list[float] = []
        probabilities: list[float] = []
        mean_residue: list[float] = []
        fakeprints: list[np.ndarray] = []
        frame_counts: list[int] = []

        for start, end in windows:
            indices = frames_in_window(frame_times, start, end)
            mean_spectrum = frames_db[:, indices].mean(axis=1)
            arrays = compute_fakeprint_telemetry(
                mean_spectrum,
                detector.freq_bins,
                freq_min=detector.freq_min,
                freq_max=detector.freq_max,
                hull_area=detector.hull_area,
                min_db=detector.min_db,
                max_db=detector.max_db,
            )
            fakeprint = arrays["fakeprint"]
            if fakeprint.size != detector.expected_features:
                old_axis = np.linspace(0, 1, fakeprint.size)
                new_axis = np.linspace(0, 1, detector.expected_features)
                fakeprint = np.interp(new_axis, old_axis, fakeprint).astype(np.float32)
            probability = float(
                detector.session.run(
                    None,
                    {detector.input_name: fakeprint.reshape(1, -1)},
                )[0][0, 0]
            )
            starts.append(float(start))
            ends.append(float(end))
            probabilities.append(probability)
            mean_residue.append(float(np.mean(arrays["residue_db"])))
            fakeprints.append(fakeprint)
            frame_counts.append(int(indices.size))

        probability_array = np.asarray(probabilities, dtype=np.float32)
        timeline_arrays = {
            "window_start_seconds": np.asarray(starts, dtype=np.float32),
            "window_end_seconds": np.asarray(ends, dtype=np.float32),
            "window_center_seconds": (
                (np.asarray(starts, dtype=np.float32) + np.asarray(ends, dtype=np.float32))
                / 2.0
            ).astype(np.float32),
            "probability": probability_array,
            "mean_residue_db": np.asarray(mean_residue, dtype=np.float32),
            "stft_frames_per_window": np.asarray(frame_counts, dtype=np.int32),
            "fakeprint_by_window": np.asarray(fakeprints, dtype=np.float32),
        }

        hottest = np.argsort(probability_array)[::-1][:5] if probability_array.size else []
        payload = {
            "mode": "timeline",
            "window_count": len(windows),
            "probability_min": float(probability_array.min()) if probability_array.size else None,
            "probability_max": float(probability_array.max()) if probability_array.size else None,
            "probability_mean": float(probability_array.mean()) if probability_array.size else None,
            "windows_above_half": int((probability_array >= 0.5).sum()),
            "hottest_windows": [
                {
                    "start_seconds": starts[int(index)],
                    "end_seconds": ends[int(index)],
                    "probability": float(probability_array[int(index)]),
                }
                for index in hottest
            ],
            "telemetry": {
                "detector": "lofcz-timeline",
                "scalars": {
                    "sample_rate": detector.sample_rate,
                    "n_fft": detector.n_fft,
                    "stft_hop_samples": stft_hop,
                    "analyzed_duration_seconds": duration,
                    "max_duration_seconds": detector.max_duration,
                    "window_seconds": window_seconds,
                    "hop_seconds": hop_seconds,
                    "frequency_min_hz": detector.freq_min,
                    "frequency_max_hz": detector.freq_max,
                    "feature_count": detector.expected_features,
                },
                "warnings": [
                    "Windowed scores are a relative map inside one track, not calibrated "
                    "per-second probabilities: the model was trained on full-track averages.",
                    "Shorter windows average fewer STFT frames and therefore vary more.",
                ],
            },
        }
        return payload, timeline_arrays


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Telemetry adapter for pristine lofcz")
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--npz-output", type=Path, required=True)
    parser.add_argument("--mode", choices=("full", "timeline"), default="full")
    parser.add_argument("--window-seconds", type=float, default=15.0)
    parser.add_argument("--hop-seconds", type=float, default=5.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.mode == "timeline":
        payload, arrays = analyze_timeline(
            args.upstream,
            args.model,
            args.audio,
            window_seconds=args.window_seconds,
            hop_seconds=args.hop_seconds,
        )
    else:
        payload, arrays = analyze(args.upstream, args.model, args.audio)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.npz_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    np.savez_compressed(args.npz_output, **arrays)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
