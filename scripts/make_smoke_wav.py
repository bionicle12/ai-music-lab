from __future__ import annotations

import argparse
import math
import struct
import wave
from pathlib import Path


def write_tone(path: Path, seconds: int = 12, sample_rate: int = 16_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for index in range(seconds * sample_rate):
        sample = int(0.2 * 32767 * math.sin(2 * math.pi * 440 * index / sample_rate))
        frames.extend(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)


def write_rhythm(path: Path, seconds: int = 32, sample_rate: int = 16_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    beat_seconds = 0.5
    eighth_seconds = beat_seconds / 2
    for index in range(seconds * sample_rate):
        time = index / sample_rate
        beat_position = time % beat_seconds
        eighth_position = time % eighth_seconds
        beat_index = int(time / beat_seconds)

        kick_envelope = math.exp(-22 * beat_position)
        kick_frequency = 48 + 72 * math.exp(-30 * beat_position)
        kick = 0.48 * kick_envelope * math.sin(
            2 * math.pi * kick_frequency * beat_position
        )

        noise = (((index * 1_103_515_245 + 12_345) & 0xFFFF) / 32_768) - 1
        snare = 0.0
        if beat_index % 4 in (1, 3):
            snare = 0.20 * math.exp(-28 * beat_position) * noise
        hi_hat = 0.06 * math.exp(-85 * eighth_position) * noise

        downbeat = 0.0
        if beat_index % 4 == 0:
            downbeat = 0.20 * math.exp(-8 * beat_position) * math.sin(
                2 * math.pi * 110 * time
            )
        pad = 0.07 * (
            math.sin(2 * math.pi * 220 * time)
            + 0.6 * math.sin(2 * math.pi * 277.18 * time)
            + 0.5 * math.sin(2 * math.pi * 329.63 * time)
        )

        sample = max(-0.95, min(0.95, kick + snare + hi_hat + downbeat + pad))
        frames.extend(struct.pack("<h", int(sample * 32767)))

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=("tone", "rhythm"), default="tone")
    parser.add_argument("--seconds", type=int)
    args = parser.parse_args()
    if args.kind == "rhythm":
        write_rhythm(args.output, seconds=args.seconds or 32)
    else:
        write_tone(args.output, seconds=args.seconds or 12)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
