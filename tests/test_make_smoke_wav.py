import wave
from pathlib import Path

from scripts.make_smoke_wav import write_rhythm


def test_write_rhythm_creates_expected_pcm_wav(tmp_path: Path) -> None:
    output = tmp_path / "rhythm.wav"

    write_rhythm(output, seconds=4, sample_rate=16_000)

    with wave.open(str(output), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 16_000
        assert wav_file.getnframes() == 64_000
        assert any(wav_file.readframes(64_000))
