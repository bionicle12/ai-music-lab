from __future__ import annotations

import argparse
import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator

import numpy as np


def platform_default_backbone_batch(platform_name: str | None = None) -> int:
    selected = sys.platform if platform_name is None else platform_name
    return 2 if selected == "darwin" else 8


#: Segments per backbone forward pass. ``0`` restores the upstream single-batch
#: behaviour; macOS starts smaller because MPS shares memory with the system.
DEFAULT_BACKBONE_BATCH = platform_default_backbone_batch()
DEFAULT_MPS_MEMORY_FRACTION = 0.75


@dataclass(frozen=True)
class DevicePlan:
    device: str
    beat_device: str
    stage1_device: str
    stage2_device: str
    mps_memory_fraction: float | None


def select_device_plan(
    requested: str,
    cuda_available: bool,
    mps_available: bool,
) -> DevicePlan:
    selected = requested
    if selected == "auto":
        if cuda_available:
            selected = "cuda"
        elif mps_available:
            selected = "mps"
        else:
            raise RuntimeError("FST requires CUDA or MPS acceleration")
    if selected == "cuda":
        if not cuda_available:
            raise RuntimeError("CUDA is unavailable in the FST environment")
        return DevicePlan("cuda", "cuda", "cuda", "cuda", None)
    if selected == "mps":
        if not mps_available:
            raise RuntimeError("MPS is unavailable in the FST environment")
        return DevicePlan(
            "mps",
            "cpu",
            "mps",
            "mps",
            DEFAULT_MPS_MEMORY_FRACTION,
        )
    raise ValueError(f"unsupported FST device: {requested}")


def validate_batch_for_device(batch: int, plan: DevicePlan) -> None:
    if plan.device == "mps" and batch == 0:
        raise ValueError("batch 0 is not supported on MPS; choose 1, 2, 4, or 8")


class MpsMemoryTracker:
    def __init__(self, api: Any, fraction: float) -> None:
        self.api = api
        self.fraction = fraction
        self.recommended_max_bytes = 0
        self.samples: list[dict[str, int | str]] = []

    def configure(self) -> None:
        self.api.set_per_process_memory_fraction(self.fraction)
        self.recommended_max_bytes = int(self.api.recommended_max_memory())

    def sample(self, stage: str) -> None:
        self.api.synchronize()
        self.samples.append(
            {
                "stage": stage,
                "current_bytes": int(self.api.current_allocated_memory()),
                "driver_bytes": int(self.api.driver_allocated_memory()),
            }
        )

    def summary(self) -> dict[str, Any]:
        current = [int(item["current_bytes"]) for item in self.samples]
        driver = [int(item["driver_bytes"]) for item in self.samples]
        return {
            "fraction": self.fraction,
            "recommended_max_bytes": self.recommended_max_bytes,
            "allocation_ceiling_bytes": int(
                self.recommended_max_bytes * self.fraction
            ),
            "sampled_peak_current_bytes": max(current, default=0),
            "sampled_peak_driver_bytes": max(driver, default=0),
            "samples": list(self.samples),
        }


def mps_memory_fraction(value: str) -> float:
    fraction = float(value)
    if not 0 < fraction <= 1:
        raise argparse.ArgumentTypeError("MPS memory fraction must be in (0, 1]")
    return fraction


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


def build_payload(
    result: dict[str, Any],
    paths: DetectorPaths,
    plan: DevicePlan,
    device_name: str,
    backbone_batch: int,
    valid_segments: int,
    memory: dict[str, Any] | None,
) -> dict[str, Any]:
    device_plan = {
        "device": plan.device,
        "beat_device": plan.beat_device,
        "stage1_device": plan.stage1_device,
        "stage2_device": plan.stage2_device,
    }
    return {
        **result,
        "device": device_name,
        "device_plan": device_plan,
        "audio": str(paths.audio.resolve()),
        "stage1": str(paths.stage1.resolve()),
        "stage2": str(paths.stage2.resolve()),
        "telemetry": {
            "detector": "FST",
            "scalars": {
                "sample_rate": 24_000,
                "segment_duration_seconds": 10.0,
                "valid_segment_count": valid_segments,
                "padded_segment_count": 48 - valid_segments,
                "maximum_segments": 48,
                "backbone_batch": backbone_batch,
                "beat_device": plan.beat_device,
                "stage1_device": plan.stage1_device,
                "stage2_device": plan.stage2_device,
                "mps_memory_fraction": plan.mps_memory_fraction,
                "memory": memory,
                "stage1_class_mapping": "not published by upstream; both class probabilities are preserved",
            },
            "warnings": [
                "Stage-1 class indices are shown without assigning unpublished Real/Fake semantics.",
                "Fusion gate values are mixing weights, not probabilities.",
            ],
        },
    }


def format_accelerator_error(
    error: RuntimeError,
    stage: str,
    plan: DevicePlan,
    backbone_batch: int,
    memory: dict[str, Any] | None,
) -> str:
    original = str(error)
    prefix = f"FST {plan.device} failed during {stage}"
    if "out of memory" not in original.lower():
        return f"{prefix}: {original}"
    details = memory or {}
    message = (
        f"{prefix}: {original}; batch={backbone_batch}; "
        f"fraction={details.get('fraction', plan.mps_memory_fraction)}; "
        f"ceiling={details.get('allocation_ceiling_bytes')}; "
        f"last_sample={(details.get('samples') or [None])[-1]}"
    )
    next_batch = {2: 1, 4: 2, 8: 4}.get(backbone_batch)
    if next_batch is not None:
        message += f"; try --backbone-batch {next_batch}"
    return message


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
    requested_device: str = "auto",
    mps_memory_fraction_value: float = DEFAULT_MPS_MEMORY_FRACTION,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    validate_paths(paths)
    stage = "device_selection"
    plan: DevicePlan | None = None
    tracker: MpsMemoryTracker | None = None
    try:
        with upstream_import_context(paths.upstream):
            import torch
            import torchaudio
            from inference import run_inference
            from model import MERT_AudioCAT, MusicAudioClassifier
            from preprocess import find_optimal_segment_length, get_segments_from_wav

            plan = select_device_plan(
                requested_device,
                cuda_available=torch.cuda.is_available(),
                mps_available=bool(
                    torch.backends.mps.is_built()
                    and torch.backends.mps.is_available()
                ),
            )
            if plan.device == "mps":
                if not 0 < mps_memory_fraction_value <= 1:
                    raise ValueError("MPS memory fraction must be in (0, 1]")
                plan = replace(
                    plan,
                    mps_memory_fraction=mps_memory_fraction_value,
                )
            validate_batch_for_device(backbone_batch, plan)

            if plan.device == "mps":
                tracker = MpsMemoryTracker(
                    torch.mps,
                    fraction=mps_memory_fraction_value,
                )
                tracker.configure()
                tracker.sample("initialized")

            sample_rate = 24_000
            fixed_samples = 240_000
            stage = "beat_preprocessing"
            beats, downbeats = get_segments_from_wav(
                str(paths.audio),
                device=plan.beat_device,
            )
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
                segments = torch.zeros(
                    (1, 1, fixed_samples),
                    dtype=torch.float32,
                )
                padding_mask = torch.ones(1, dtype=torch.bool)
            validate_segments(padding_mask)
            del waveform, segment_items

            stage = "stage1_checkpoint_load"
            backbone = MERT_AudioCAT.load_from_checkpoint(
                str(paths.stage1),
                map_location="cpu",
            ).to(plan.stage1_device)
            backbone.eval()
            if tracker is not None:
                tracker.sample("stage1_checkpoint_loaded")

            flat_segments = segments.squeeze(1)
            step = (
                backbone_batch
                if backbone_batch > 0
                else int(flat_segments.shape[0])
            )
            logit_slices = []
            embedding_slices = []
            with torch.no_grad():
                for batch_index, start_index in enumerate(
                    range(0, int(flat_segments.shape[0]), step),
                    start=1,
                ):
                    stage = f"stage1_batch_{batch_index}"
                    input_slice = flat_segments[
                        start_index : start_index + step
                    ].to(device=plan.stage1_device, dtype=torch.float32)
                    part_logits, part_embedding = backbone(input_slice)
                    logit_slices.append(
                        part_logits.detach().float().cpu()
                    )
                    embedding_slices.append(
                        part_embedding.detach().float().cpu()
                    )
                    if tracker is not None:
                        tracker.sample(stage)
                    del input_slice, part_logits, part_embedding

            stage1_logits_cpu = torch.cat(logit_slices, dim=0)
            embedding_cpu = torch.cat(embedding_slices, dim=0)
            if tracker is not None:
                tracker.sample("stage1_outputs_copied")

            stage = "stage1_release"
            del (
                backbone,
                segments,
                flat_segments,
                logit_slices,
                embedding_slices,
            )
            if tracker is not None:
                torch.mps.empty_cache()
                tracker.sample("stage1_released")

            stage = "stage2_checkpoint_load"
            classifier = MusicAudioClassifier.load_from_checkpoint(
                checkpoint_path=str(paths.stage2),
                map_location="cpu",
                input_dim=768,
                backbone="fusion_segment_transformer",
                is_emb=True,
            ).to(plan.stage2_device)
            classifier.eval()
            embedding_device = embedding_cpu.to(
                device=plan.stage2_device,
                dtype=torch.float16,
            )
            padding_mask_device = padding_mask.unsqueeze(0).to(
                plan.stage2_device
            )
            if tracker is not None:
                tracker.sample("stage2_checkpoint_loaded")

            captured_gates: list[np.ndarray] = []

            def capture_gate(_module, _inputs, output):
                captured_gates.append(
                    output.detach().float().cpu().numpy()
                )

            handle = (
                classifier.model.fusion_layers[0]
                .fusion_gate.register_forward_hook(capture_gate)
            )
            stage = "stage2_inference"
            try:
                result = run_inference(
                    classifier,
                    embedding_device,
                    padding_mask_device,
                    plan.stage2_device,
                )
            finally:
                handle.remove()
            if tracker is not None:
                tracker.sample("stage2_inference_completed")

            logits_array = (
                stage1_logits_cpu[:valid_segments].numpy().astype(np.float32)
            )
            embeddings_array = (
                embedding_cpu[:valid_segments].numpy().astype(np.float32)
            )
            arrays = {
                "beats_seconds": np.asarray(beats, dtype=np.float32),
                "downbeats_seconds": np.asarray(downbeats, dtype=np.float32),
                "segment_start_seconds": np.asarray(
                    segment_starts[:valid_segments],
                    dtype=np.float32,
                ),
                "stage1_logits": logits_array,
                "stage1_class_probabilities": stage1_class_probabilities(
                    logits_array
                ),
                "mert_embeddings": embeddings_array,
                "self_similarity": self_similarity_matrix(embeddings_array),
                "fusion_content_gate": mean_fusion_gate(
                    captured_gates[-1],
                    valid_segments,
                ),
            }

            stage = "final_cleanup"
            del classifier, embedding_device, padding_mask_device
            if tracker is not None:
                torch.mps.empty_cache()
                tracker.sample("final_cleanup")
            memory = tracker.summary() if tracker is not None else None
            device_name = (
                torch.cuda.get_device_name(0)
                if plan.device == "cuda"
                else "mps"
            )
            payload = build_payload(
                result=result,
                paths=paths,
                plan=plan,
                device_name=device_name,
                backbone_batch=step,
                valid_segments=valid_segments,
                memory=memory,
            )
            return payload, arrays
    except RuntimeError as error:
        if plan is None:
            raise
        memory = tracker.summary() if tracker is not None else None
        raise RuntimeError(
            format_accelerator_error(
                error,
                stage=stage,
                plan=plan,
                backbone_batch=backbone_batch,
                memory=memory,
            )
        ) from error

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="External CLI for pristine Mippia FST")
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--stage2", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--npz-output", type=Path)
    parser.add_argument(
        "--device",
        choices=("auto", "cuda", "mps"),
        default="auto",
    )
    parser.add_argument(
        "--mps-memory-fraction",
        type=mps_memory_fraction,
        default=DEFAULT_MPS_MEMORY_FRACTION,
    )
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
        requested_device=args.device,
        mps_memory_fraction_value=args.mps_memory_fraction,
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
