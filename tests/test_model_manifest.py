from hashlib import sha256
from pathlib import Path

from scripts.write_model_manifest import describe_file


def test_describe_file_records_size_and_sha256(tmp_path: Path) -> None:
    model = tmp_path / "model.bin"
    model.write_bytes(b"detector-weight")

    result = describe_file(model)

    assert result == {
        "path": str(model.resolve()),
        "size_bytes": 15,
        "sha256": sha256(b"detector-weight").hexdigest(),
    }
