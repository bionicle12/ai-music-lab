from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np


def platform_default_backbone_batch(platform_name: str | None = None) -> int:
    selected = sys.platform if platform_name is None else platform_name
    return 2 if selected == "darwin" else 8


#: Segments per backbone forward pass. ``0`` restores the upstream single-batch
#: behaviour; macOS starts smaller because MPS shares memory with the system.
DEFAULT_BACKBONE_BATCH = platform_default_backbone_batch()


@dataclass(frozen=True)
class DetectorPaths:
    upstream: Path
    stage1: Path
    stage2: Path
    audio: Path


def validate_paths(paths: DetectorPaths) -> None:
    required = (
        paths.upstream / "model.py",
        paths.upstream / "inference.py",
        paths.upstream / "preprocess.py",
        paths.stage1,
        paths.stage2,
        paths.audio,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing required files: " + ", ".join(missing))


def validate_segments(padding_mask: Any) -> None:
    if padding_mask.numel() == 0 or bool(padding_mask.all().item()):
        raise RuntimeError(
            "FST preprocessing found no beat-aligned segments; "
            "use audio with detectable rhythmic/downbeat content"
        )


def stage1_class_probabilities(logits: np.ndarray) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    shifted = values - np.max(values, axis=-1, keepdims=True)
    exponentials = np.exp(shifted)
    return (exponentials / exponentials.sum(axis=-1, keepdims=True)).astype(
        np.float32
    )


def self_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    values = np.asarray(embeddings, dtype=np.float32)
    differences = values[:, np.newaxis, :] - values[np.newaxis, :, :]
    distances = np.mean(np.square(differences), axis=-1)
    return np.exp(-distances).astype(np.float32)


def mean_fusion_gate(
    gate_values: np.ndarray,
    valid_segments: int,
) -> np.ndarray:
    values = np.asarray(gate_values, dtype=np.float32)
    if values.ndim != 3 or values.shape[0] != 1:
        raise ValueError("fusion gate must have shape (1, segments, features)")
    return values[0, :valid_segments].mean(axis=-1).astype(np.float32)


@contextmanager
def upstream_import_context(upstream: Path) -> Iterator[None]:
    resolved = str(upstream.resolve())
    previous_flag = sys.dont_write_bytecode
    sys.path.insert(0, resolved)
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = previous_flag
        if sys.path and sys.path[0] == resolved:
            sys.path.pop(0)


def analyze(
    paths: DetectorPaths,
    backbone_batch: int = DEFAULT_BACKBONE_BATCH,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    validate_paths(paths)
    with upstream_import_context(paths.upstream):
        import torch
        import torchaudio
        from inference import run_inference
        from model import MERT_AudioCAT, MusicAudioClassifier
        from preprocess import get_segments_from_wav, find_optimal_segment_length

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable in the ai-music-fst environment")
        device = "cuda"
        sample_rate = 24_000
        fixed_samples = 240_000
        beats, downbeats = get_segments_from_wav(str(paths.audio))
        _, cleaned_downbeats = find_optimal_segment_length(downbeats)
        waveform, source_sample_rate = torchaudio.load(str(paths.audio))
        waveform = waveform.to(torch.float32)
        if source_sample_rate != sample_rate:
            waveform = torchaudio.transforms.Resample(
                source_sample_rate,
                sample_rate,
            )(waveform)
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        if waveform.shape[1] <= fixed_samples:
            waveform = torch.cat(
                [
                    waveform,
                    torch.zeros(1, fixed_samples, dtype=torch.float32),
                ],
                dim=1,
            )
        segment_items = []
        segment_starts = []
        for start_time in cleaned_downbeats:
            start_sample = int(float(start_time) * sample_rate)
            end_sample = start_sample + fixed_samples
            if end_sample > waveform.shape[1]:
                continue
            segment_items.append(waveform[:, start_sample:end_sample])
            segment_starts.append(float(start_time))
            if len(segment_items) >= 48:
                break
        if segment_items:
            segments = torch.stack(segment_items)
            valid_segments = len(segment_items)
            padding_mask = torch.zeros(48, dtype=torch.bool)
            if valid_segments < 48:
                padding = torch.zeros(
                    (48 - valid_segments, 1, fixed_samples),
                    dtype=torch.float32,
                )
                segments = torch.cat([segments, padding], dim=0)
                padding_mask[valid_segments:] = True
        else:
            segments = torch.zeros((1, 1, fixed_samples), dtype=torch.float32)
            padding_mask = torch.ones(1, dtype=torch.bool)
        validate_segments(padding_mask)
        backbone = MERT_AudioCAT.load_from_checkpoint(
            str(paths.stage1),
            map_location=device,
        ).to(device)
        backbone.eval()
        segments = segments.to(device=device, dtype=torch.float32)
        padding_mask = padding_mask.to(device).unsqueeze(0)
        # The segments are independent here — they are only mixed later, by the
        # Stage-2 classifier — so the backbone can be fed in slices. Upstream
        # sends all 48 at once, which peaks at 16 GB of VRAM and puts FST out of
        # reach of every card below 24 GB. In slices of 8 the same run peaks at
        # 4.8 GB and takes the same time; the GPU was never the bottleneck.
        #
        # Measured on three tracks: two produced byte-identical output, the
        # third moved the raw logit by one float16 ulp (6.0546875 -> 6.05859375)
        # while prediction and every reported probability stayed the same. Each
        # batch size is repeatable on its own — three runs, same value — so this
        # is a reduction-order artifact, not a coin toss. It does mean a saved
        # score is tied to the batch size that produced it, like every other
        # part of the run.
        with torch.no_grad():
            flat = segments.squeeze(1)
            step = backbone_batch if backbone_batch > 0 else flat.shape[0]
            logit_slices = []
            embedding_slices = []
            for start in range(0, flat.shape[0], step):
                part_logits, part_embedding = backbone(flat[start : start + step])
                logit_slices.append(part_logits)
                embedding_slices.append(part_embedding)
            stage1_logits = torch.cat(logit_slices, dim=0)
            embedding = torch.cat(embedding_slices, dim=0)
        classifier = MusicAudioClassifier.load_from_checkpoint(
            checkpoint_path=str(paths.stage2),
            map_location=device,
            input_dim=768,
            backbone="fusion_segment_transformer",
            is_emb=True,
        )
        captured_gates: list[np.ndarray] = []

        def capture_gate(_module, _inputs, output):
            captured_gates.append(output.detach().float().cpu().numpy())

        handle = classifier.model.fusion_layers[0].fusion_gate.register_forward_hook(
            capture_gate
        )
        try:
            result = run_inference(classifier, embedding, padding_mask, device)
        finally:
            handle.remove()
        valid_segments = int((~padding_mask.squeeze(0)).sum().item())
        logits_array = (
            stage1_logits[:valid_segments].detach().float().cpu().numpy()
        )
        embeddings_array = (
            embedding[:valid_segments].detach().float().cpu().numpy()
        )
        arrays = {
            "beats_seconds": np.asarray(beats, dtype=np.float32),
            "downbeats_seconds": np.asarray(downbeats, dtype=np.float32),
            "segment_start_seconds": np.asarray(
                segment_starts[:valid_segments],
                dtype=np.float32,
            ),
            "stage1_logits": logits_array.astype(np.float32),
            "stage1_class_probabilities": stage1_class_probabilities(
                logits_array
            ),
            "mert_embeddings": embeddings_array.astype(np.float32),
            "self_similarity": self_similarity_matrix(embeddings_array),
            "fusion_content_gate": mean_fusion_gate(
                captured_gates[-1],
                valid_segments,
            ),
        }
        payload = {
            **result,
            "device": torch.cuda.get_device_name(0),
            "audio": str(paths.audio.resolve()),
            "stage1": str(paths.stage1.resolve()),
            "stage2": str(paths.stage2.resolve()),
            "telemetry": {
                "detector": "FST",
                "scalars": {
                    "sample_rate": sample_rate,
                    "segment_duration_seconds": fixed_samples / sample_rate,
                    "valid_segment_count": valid_segments,
                    "padded_segment_count": 48 - valid_segments,
                    "maximum_segments": 48,
                    # Recorded because it can move the raw logit by one float16
                    # ulp: a saved score has to be able to say which batch size
                    # produced it.
                    "backbone_batch": step,
                    "stage1_class_mapping": "not published by upstream; both class probabilities are preserved",
                },
                "warnings": [
                    "Stage-1 class indices are shown without assigning unpublished Real/Fake semantics.",
                    "Fusion gate values are mixing weights, not probabilities.",
                ],
            },
        }
        return payload, arrays


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="External CLI for pristine Mippia FST")
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--stage2", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--npz-output", type=Path)
    parser.add_argument(
        "--backbone-batch",
        type=int,
        default=DEFAULT_BACKBONE_BATCH,
        help=(
            "how many segments go through the backbone at once; "
            "0 means all 48, as upstream does it, at 16 GB of VRAM"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result, arrays = analyze(
        DetectorPaths(args.upstream, args.stage1, args.stage2, args.audio),
        backbone_batch=args.backbone_batch,
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    if args.npz_output:
        args.npz_output.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.npz_output, **arrays)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
