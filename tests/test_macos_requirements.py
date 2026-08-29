from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def requirement_text(name: str) -> str:
    return (ROOT / "environments" / name).read_text(encoding="utf-8-sig")


def test_macos_ui_snapshot_has_no_windows_or_cuda_packages() -> None:
    text = requirement_text("ai-music-ui-macos.txt")
    assert "gradio==6.20.0" in text
    assert "pytest==9.1.1" in text
    assert "pyreadline3" not in text
    assert "+cu128" not in text


def test_macos_lofcz_snapshot_uses_native_runtime_packages() -> None:
    text = requirement_text("ai-music-lofcz-macos.txt")
    assert "onnxruntime==" in text
    assert "onnxruntime-gpu" not in text
    assert "torch==2.8.0" in text
    assert "torchaudio==2.8.0" in text
    assert "pyreadline3" not in text
    assert "+cu128" not in text
