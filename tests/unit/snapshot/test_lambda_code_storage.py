"""Unit tests for LambdaCodeStorage."""

import base64
import hashlib
from pathlib import Path

import pytest

from src.snapshot.lambda_code_storage import LambdaCodeStorage


@pytest.fixture
def storage(tmp_path: Path) -> LambdaCodeStorage:
    """Create a LambdaCodeStorage with tmp_path base."""
    return LambdaCodeStorage(base_path=str(tmp_path))


class TestInit:
    """Tests for __init__."""

    def test_custom_base_path(self, tmp_path: Path) -> None:
        s = LambdaCodeStorage(base_path=str(tmp_path / "custom"))
        assert s.base_path == tmp_path / "custom"

    def test_default_base_path(self) -> None:
        s = LambdaCodeStorage()
        assert s.base_path == Path.home() / ".snapshots" / "lambda-code"


class TestGetSnapshotCodeDir:
    """Tests for get_snapshot_code_dir."""

    def test_returns_correct_path(self, storage: LambdaCodeStorage) -> None:
        result = storage.get_snapshot_code_dir("my-snapshot")
        assert result == storage.base_path / "my-snapshot"


class TestStoreCode:
    """Tests for store_code."""

    def test_stores_file_and_returns_path_and_hash(self, storage: LambdaCodeStorage) -> None:
        code = b"fake zip content"
        file_path, code_hash = storage.store_code("snap1", "my-function", code)

        assert Path(file_path).exists()
        assert Path(file_path).read_bytes() == code
        assert code_hash == hashlib.sha256(code).hexdigest()

    def test_creates_directory_structure(self, storage: LambdaCodeStorage) -> None:
        storage.store_code("snap1", "my-function", b"data")
        assert (storage.base_path / "snap1").is_dir()

    def test_sanitizes_filename(self, storage: LambdaCodeStorage) -> None:
        file_path, _ = storage.store_code("snap1", "my/function:name", b"data")
        assert "my_function_name.zip" in file_path


class TestLoadCode:
    """Tests for load_code."""

    def test_loads_stored_bytes(self, storage: LambdaCodeStorage) -> None:
        code = b"test bytes"
        file_path, _ = storage.store_code("snap1", "func", code)
        loaded = storage.load_code(file_path)
        assert loaded == code

    def test_returns_none_for_missing(self, storage: LambdaCodeStorage) -> None:
        result = storage.load_code("/nonexistent/path.zip")
        assert result is None


class TestLoadCodeBase64:
    """Tests for load_code_base64."""

    def test_returns_base64_string(self, storage: LambdaCodeStorage) -> None:
        code = b"test bytes"
        file_path, _ = storage.store_code("snap1", "func", code)
        result = storage.load_code_base64(file_path)
        assert result == base64.b64encode(code).decode("utf-8")

    def test_returns_none_for_missing(self, storage: LambdaCodeStorage) -> None:
        result = storage.load_code_base64("/nonexistent/path.zip")
        assert result is None


class TestDeleteSnapshotCode:
    """Tests for delete_snapshot_code."""

    def test_deletes_existing_directory(self, storage: LambdaCodeStorage) -> None:
        storage.store_code("snap1", "func", b"data")
        assert storage.delete_snapshot_code("snap1") is True
        assert not (storage.base_path / "snap1").exists()

    def test_returns_false_for_nonexistent(self, storage: LambdaCodeStorage) -> None:
        assert storage.delete_snapshot_code("nonexistent") is False


class TestGetCodeSize:
    """Tests for get_code_size."""

    def test_returns_correct_size(self, storage: LambdaCodeStorage) -> None:
        code = b"twelve bytes"
        file_path, _ = storage.store_code("snap1", "func", code)
        assert storage.get_code_size(file_path) == len(code)

    def test_returns_none_for_missing(self, storage: LambdaCodeStorage) -> None:
        assert storage.get_code_size("/nonexistent/path.zip") is None


class TestListSnapshotCodeFiles:
    """Tests for list_snapshot_code_files."""

    def test_lists_zip_files(self, storage: LambdaCodeStorage) -> None:
        storage.store_code("snap1", "func1", b"data1")
        storage.store_code("snap1", "func2", b"data2")
        files = storage.list_snapshot_code_files("snap1")
        assert len(files) == 2
        assert all(f.endswith(".zip") for f in files)

    def test_empty_for_nonexistent_snapshot(self, storage: LambdaCodeStorage) -> None:
        assert storage.list_snapshot_code_files("nonexistent") == []


class TestSanitizeFilename:
    """Tests for _sanitize_filename."""

    def test_replaces_special_characters(self, storage: LambdaCodeStorage) -> None:
        result = storage._sanitize_filename('a/b\\c:d<e>f|g*h?i"j')
        assert "/" not in result
        assert "\\" not in result
        assert ":" not in result
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result
        assert "*" not in result
        assert "?" not in result
        assert '"' not in result
        assert result == "a_b_c_d_e_f_g_h_i_j"

    def test_normal_name_unchanged(self, storage: LambdaCodeStorage) -> None:
        assert storage._sanitize_filename("my-function") == "my-function"
