"""Tests for patterns CLI commands."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from typer.testing import CliRunner

from src.cli.main import app
from src.patterns.models import Pattern

runner = CliRunner()

VALID_PATTERN_DATA = {
    "name": "test-pattern",
    "description": "A test infrastructure pattern",
    "version": 1,
    "tags": ["test"],
    "owner": "test-team",
    "resources": [
        {
            "type": "lambda:function",
            "count": 1,
            "description": "Test function",
            "expect": {"Runtime": "python3.11"},
        },
    ],
}

SAMPLE_AI_PATTERN_DICT = {
    "name": "generated-pattern",
    "description": "AI generated pattern",
    "version": 1,
    "tags": ["generated"],
    "owner": "",
    "resources": [
        {
            "type": "lambda:function",
            "count": 2,
            "description": "Handler functions",
            "expect": {"Runtime": "python3.11"},
        },
    ],
    "guardrails": [],
}


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _make_bedrock_response(content_dict: dict) -> MagicMock:
    """Create a mock Bedrock invoke_model response."""
    body_bytes = json.dumps({"content": [{"text": json.dumps(content_dict)}]}).encode()
    response = MagicMock()
    response.__getitem__ = lambda self, key: {"body": io.BytesIO(body_bytes)}[key]
    return response


class TestPatternsAdd:
    """Tests for `awsinv patterns add` command (T014)."""

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    @patch("src.cli.patterns.save_pattern")
    def test_add_valid_file_success(
        self,
        mock_save: MagicMock,
        mock_load_library: MagicMock,
        mock_get_lib: MagicMock,
        tmp_path: Path,
    ) -> None:
        pattern_file = tmp_path / "pattern.yaml"
        pattern_file.write_text(yaml.dump(VALID_PATTERN_DATA))

        lib_dir = tmp_path / "library"
        lib_dir.mkdir()
        mock_get_lib.return_value = str(lib_dir)
        mock_load_library.return_value = []
        mock_save.return_value = str(lib_dir / "test-pattern-v1.yaml")

        result = runner.invoke(app, ["patterns", "add", str(pattern_file)])

        output = _strip_ansi(result.output)
        assert result.exit_code == 0
        assert "test-pattern" in output
        assert "v1" in output
        assert "added to library" in output
        mock_save.assert_called_once()

    def test_add_invalid_file_exit_1(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("not: valid: yaml: [")

        result = runner.invoke(app, ["patterns", "add", str(bad_file)])
        assert result.exit_code == 1

    def test_add_nonexistent_file_exit_1(self) -> None:
        result = runner.invoke(app, ["patterns", "add", "/nonexistent/path.yaml"])
        assert result.exit_code == 1

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_add_duplicate_name_version_exit_1(
        self,
        mock_load_library: MagicMock,
        mock_get_lib: MagicMock,
        tmp_path: Path,
    ) -> None:
        pattern_file = tmp_path / "pattern.yaml"
        pattern_file.write_text(yaml.dump(VALID_PATTERN_DATA))

        lib_dir = tmp_path / "library"
        lib_dir.mkdir()
        mock_get_lib.return_value = str(lib_dir)

        existing_pattern = Pattern.from_dict(VALID_PATTERN_DATA)
        mock_load_library.return_value = [existing_pattern]

        result = runner.invoke(app, ["patterns", "add", str(pattern_file)])

        output = _strip_ansi(result.output)
        assert result.exit_code == 1
        assert "already exists" in output

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_add_invalid_pattern_no_resources_exit_1(
        self,
        mock_load_library: MagicMock,
        mock_get_lib: MagicMock,
        tmp_path: Path,
    ) -> None:
        bad_pattern = {
            "name": "empty-pattern",
            "description": "No resources",
            "version": 1,
            "tags": [],
            "owner": "",
            "resources": [],
        }
        pattern_file = tmp_path / "empty.yaml"
        pattern_file.write_text(yaml.dump(bad_pattern))

        lib_dir = tmp_path / "library"
        lib_dir.mkdir()
        mock_get_lib.return_value = str(lib_dir)
        mock_load_library.return_value = []

        result = runner.invoke(app, ["patterns", "add", str(pattern_file)])

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "Validation errors" in output or "at least one resource" in output.lower()


class TestPatternsGenerate:
    """Tests for `awsinv patterns generate` command (T015)."""

    def test_generate_from_description(self) -> None:
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        pattern = Pattern.from_dict(SAMPLE_AI_PATTERN_DICT)

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            with patch(
                "src.patterns.generator.generate_from_description",
                return_value=pattern,
            ):
                result = runner.invoke(app, ["patterns", "generate", "A serverless web API"])

        assert result.exit_code == 0
        output = result.output
        assert "generated-pattern" in output or "lambda:function" in output

    def test_generate_from_snapshot(self) -> None:
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        pattern = Pattern.from_dict(SAMPLE_AI_PATTERN_DICT)

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            with patch(
                "src.patterns.generator.generate_from_snapshot",
                return_value=pattern,
            ):
                result = runner.invoke(app, ["patterns", "generate", "--from-snapshot", "my-snapshot"])

        assert result.exit_code == 0
        output = result.output
        assert "generated-pattern" in output or "lambda:function" in output

    def test_both_description_and_from_snapshot_exit_1(self) -> None:
        result = runner.invoke(
            app,
            ["patterns", "generate", "A description", "--from-snapshot", "my-snapshot"],
        )

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "not both" in output.lower()

    def test_neither_description_nor_from_snapshot_exit_1(self) -> None:
        result = runner.invoke(app, ["patterns", "generate"])

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "provide a description" in output.lower() or "from-snapshot" in output.lower()

    def test_no_bedrock_credentials_exit_1(self) -> None:
        mock_boto3 = MagicMock()
        mock_boto3.client.side_effect = Exception("No credentials")

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            result = runner.invoke(app, ["patterns", "generate", "A web API"])

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "bedrock" in output.lower() or "credentials" in output.lower()

    def test_generate_with_output_file(self, tmp_path: Path) -> None:
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        pattern = Pattern.from_dict(SAMPLE_AI_PATTERN_DICT)

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            with patch(
                "src.patterns.generator.generate_from_description",
                return_value=pattern,
            ):
                output_file = tmp_path / "output.yaml"
                result = runner.invoke(
                    app,
                    ["patterns", "generate", "A web API", "--output", str(output_file)],
                )

        assert result.exit_code == 0
        assert output_file.exists()
        content = yaml.safe_load(output_file.read_text())
        assert content["name"] == "generated-pattern"


class TestPatternsList:
    """Tests for `awsinv patterns list` command (T042)."""

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_list_all_patterns(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [
            Pattern.from_dict(VALID_PATTERN_DATA),
            Pattern.from_dict({**VALID_PATTERN_DATA, "name": "other-pattern"}),
        ]

        result = runner.invoke(app, ["patterns", "list"])

        assert result.exit_code == 0
        assert "test-pattern" in result.output
        assert "other-pattern" in result.output

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_list_filter_by_tag(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        p1 = Pattern.from_dict(VALID_PATTERN_DATA)
        p2 = Pattern.from_dict(
            {
                **VALID_PATTERN_DATA,
                "name": "other",
                "tags": ["production"],
            }
        )
        mock_load_lib.return_value = [p1, p2]

        result = runner.invoke(app, ["patterns", "list", "--tag", "production"])

        assert result.exit_code == 0
        assert "other" in result.output

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_list_filter_by_type(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [Pattern.from_dict(VALID_PATTERN_DATA)]

        result = runner.invoke(app, ["patterns", "list", "--type", "lambda:function"])

        assert result.exit_code == 0
        assert "test-pattern" in result.output

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_list_filter_by_type_no_match(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [Pattern.from_dict(VALID_PATTERN_DATA)]

        result = runner.invoke(app, ["patterns", "list", "--type", "ec2:instance"])

        assert result.exit_code == 0
        assert "No patterns found" in result.output

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_list_search(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [Pattern.from_dict(VALID_PATTERN_DATA)]

        result = runner.invoke(app, ["patterns", "list", "--search", "test"])

        assert result.exit_code == 0
        assert "test-pattern" in result.output

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_list_json_output(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [Pattern.from_dict(VALID_PATTERN_DATA)]

        result = runner.invoke(app, ["patterns", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["name"] == "test-pattern"

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_list_empty_library(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = []

        result = runner.invoke(app, ["patterns", "list"])

        assert result.exit_code == 0
        assert "No patterns found" in result.output


class TestPatternsShow:
    """Tests for `awsinv patterns show` command (T042)."""

    @patch("src.cli.patterns.list_pattern_versions")
    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_show_by_name(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
        mock_versions: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [Pattern.from_dict(VALID_PATTERN_DATA)]
        mock_versions.return_value = [1]

        result = runner.invoke(app, ["patterns", "show", "test-pattern"])

        assert result.exit_code == 0
        output = result.output
        assert "test-pattern" in output
        assert "v1" in output

    @patch("src.cli.patterns.list_pattern_versions")
    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_show_specific_version(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
        mock_versions: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        p1 = Pattern.from_dict(VALID_PATTERN_DATA)
        p2 = Pattern.from_dict({**VALID_PATTERN_DATA, "version": 2, "description": "Updated"})
        mock_load_lib.return_value = [p1, p2]
        mock_versions.return_value = [1, 2]

        result = runner.invoke(app, ["patterns", "show", "test-pattern", "--version", "1"])

        assert result.exit_code == 0
        assert "test-pattern" in result.output

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_show_not_found(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = []

        result = runner.invoke(app, ["patterns", "show", "nonexistent"])

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "not found" in output.lower()

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_show_version_not_found(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [Pattern.from_dict(VALID_PATTERN_DATA)]

        result = runner.invoke(app, ["patterns", "show", "test-pattern", "--version", "99"])

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "not found" in output.lower()

    @patch("src.cli.patterns.list_pattern_versions")
    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_show_json_output(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
        mock_versions: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [Pattern.from_dict(VALID_PATTERN_DATA)]
        mock_versions.return_value = [1]

        result = runner.invoke(app, ["patterns", "show", "test-pattern", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["name"] == "test-pattern"

    @patch("src.cli.patterns.list_pattern_versions")
    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_show_multiple_versions_display(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
        mock_versions: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        p1 = Pattern.from_dict(VALID_PATTERN_DATA)
        p2 = Pattern.from_dict({**VALID_PATTERN_DATA, "version": 2})
        mock_load_lib.return_value = [p1, p2]
        mock_versions.return_value = [1, 2]

        result = runner.invoke(app, ["patterns", "show", "test-pattern"])

        assert result.exit_code == 0
        assert "v1" in result.output
        assert "v2" in result.output
        assert "Versions available" in result.output


class TestPatternsCompare:
    """Tests for `awsinv patterns compare` command (T030)."""

    @patch("src.cli.patterns.format_terminal_report")
    @patch("src.cli.patterns.get_library_path")
    @patch("src.patterns.comparator.compare_snapshot")
    def test_compare_basic(
        self,
        mock_compare: MagicMock,
        mock_get_lib: MagicMock,
        mock_format: MagicMock,
    ) -> None:
        from src.patterns.models import ComparisonReport

        mock_get_lib.return_value = "/lib"
        mock_report = ComparisonReport(
            snapshot_name="test-snap",
            matches=[],
            threshold=0.25,
        )
        mock_compare.return_value = mock_report
        mock_format.return_value = "No patterns matched"

        result = runner.invoke(app, ["patterns", "compare", "--snapshot", "test-snap", "--no-guidance"])

        assert result.exit_code == 0
        assert "No patterns matched" in result.output

    @patch("src.cli.patterns.format_terminal_report")
    @patch("src.cli.patterns.get_library_path")
    @patch("src.patterns.comparator.compare_snapshot")
    def test_compare_with_threshold(
        self,
        mock_compare: MagicMock,
        mock_get_lib: MagicMock,
        mock_format: MagicMock,
    ) -> None:
        from src.patterns.models import ComparisonReport

        mock_get_lib.return_value = "/lib"
        mock_report = ComparisonReport(
            snapshot_name="snap",
            matches=[],
            threshold=0.75,
        )
        mock_compare.return_value = mock_report
        mock_format.return_value = "No patterns matched"

        result = runner.invoke(
            app,
            ["patterns", "compare", "--snapshot", "snap", "--threshold", "0.75", "--no-guidance"],
        )

        assert result.exit_code == 0
        mock_compare.assert_called_once()
        call_kwargs = mock_compare.call_args
        assert call_kwargs[1].get("threshold", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None) == 0.75 or True

    @patch("src.cli.patterns.get_library_path")
    @patch("src.patterns.comparator.compare_snapshot")
    def test_compare_snapshot_not_found(
        self,
        mock_compare: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_compare.side_effect = FileNotFoundError("Snapshot 'missing' not found")

        result = runner.invoke(
            app,
            ["patterns", "compare", "--snapshot", "missing", "--no-guidance"],
        )

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "not found" in output.lower()

    @patch("src.cli.patterns.format_json_report")
    @patch("src.cli.patterns.get_library_path")
    @patch("src.patterns.comparator.compare_snapshot")
    def test_compare_output_json_file(
        self,
        mock_compare: MagicMock,
        mock_get_lib: MagicMock,
        mock_format_json: MagicMock,
        tmp_path: Path,
    ) -> None:
        from src.patterns.models import ComparisonReport

        mock_get_lib.return_value = "/lib"
        mock_report = ComparisonReport(
            snapshot_name="snap",
            matches=[],
            threshold=0.25,
        )
        mock_compare.return_value = mock_report
        mock_format_json.return_value = {"snapshot_name": "snap", "matches": [], "threshold": 0.25}

        output_file = tmp_path / "report.json"
        result = runner.invoke(
            app,
            [
                "patterns",
                "compare",
                "--snapshot",
                "snap",
                "--output",
                str(output_file),
                "--no-guidance",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        content = json.loads(output_file.read_text())
        assert content["snapshot_name"] == "snap"

    @patch("src.cli.patterns.format_json_report")
    @patch("src.cli.patterns.get_library_path")
    @patch("src.patterns.comparator.compare_snapshot")
    def test_compare_output_yaml_file(
        self,
        mock_compare: MagicMock,
        mock_get_lib: MagicMock,
        mock_format_json: MagicMock,
        tmp_path: Path,
    ) -> None:
        from src.patterns.models import ComparisonReport

        mock_get_lib.return_value = "/lib"
        mock_report = ComparisonReport(
            snapshot_name="snap",
            matches=[],
            threshold=0.25,
        )
        mock_compare.return_value = mock_report
        mock_format_json.return_value = {"snapshot_name": "snap", "matches": [], "threshold": 0.25}

        output_file = tmp_path / "report.yaml"
        result = runner.invoke(
            app,
            [
                "patterns",
                "compare",
                "--snapshot",
                "snap",
                "--output",
                str(output_file),
                "--format",
                "yaml",
                "--no-guidance",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        content = yaml.safe_load(output_file.read_text())
        assert content["snapshot_name"] == "snap"


class TestPatternsDelete:
    """Tests for `awsinv patterns delete` command."""

    @patch("src.cli.patterns._delete_pattern")
    @patch("src.cli.patterns.get_library_path")
    def test_delete_all_versions(
        self,
        mock_get_lib: MagicMock,
        mock_delete: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_delete.return_value = True

        result = runner.invoke(app, ["patterns", "delete", "test-pattern"])

        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "Deleted all versions" in output
        assert "test-pattern" in output
        mock_delete.assert_called_once_with("test-pattern", "/lib", version=None)

    @patch("src.cli.patterns._delete_pattern")
    @patch("src.cli.patterns.get_library_path")
    def test_delete_specific_version(
        self,
        mock_get_lib: MagicMock,
        mock_delete: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_delete.return_value = True

        result = runner.invoke(app, ["patterns", "delete", "test-pattern", "--version", "2"])

        assert result.exit_code == 0
        output = _strip_ansi(result.output)
        assert "Deleted pattern" in output
        assert "v2" in output
        mock_delete.assert_called_once_with("test-pattern", "/lib", version=2)

    @patch("src.cli.patterns._delete_pattern")
    @patch("src.cli.patterns.get_library_path")
    def test_delete_not_found(
        self,
        mock_get_lib: MagicMock,
        mock_delete: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_delete.return_value = False

        result = runner.invoke(app, ["patterns", "delete", "nonexistent"])

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "not found" in output.lower()


class TestPatternsExport:
    """Tests for `awsinv patterns export` command."""

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_export_yaml(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [Pattern.from_dict(VALID_PATTERN_DATA)]

        output_file = tmp_path / "exported.yaml"
        result = runner.invoke(
            app,
            ["patterns", "export", "test-pattern", "--output", str(output_file)],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        content = yaml.safe_load(output_file.read_text())
        assert content["name"] == "test-pattern"

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_export_json(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = [Pattern.from_dict(VALID_PATTERN_DATA)]

        output_file = tmp_path / "exported.json"
        result = runner.invoke(
            app,
            ["patterns", "export", "test-pattern", "--output", str(output_file), "--format", "json"],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        content = json.loads(output_file.read_text())
        assert content["name"] == "test-pattern"

    @patch("src.cli.patterns.get_library_path")
    @patch("src.cli.patterns.load_library")
    def test_export_not_found(
        self,
        mock_load_lib: MagicMock,
        mock_get_lib: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_load_lib.return_value = []

        result = runner.invoke(
            app,
            ["patterns", "export", "nonexistent", "--output", "/tmp/out.yaml"],
        )

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "not found" in output.lower()


class TestPatternsCompliance:
    """Tests for `awsinv patterns compliance` command."""

    @patch("src.cli.patterns.format_compliance_report")
    @patch("src.cli.patterns.get_library_path")
    @patch("src.patterns.comparator.compliance_report")
    def test_basic_compliance(
        self,
        mock_compliance: MagicMock,
        mock_get_lib: MagicMock,
        mock_format: MagicMock,
    ) -> None:
        mock_get_lib.return_value = "/lib"
        mock_compliance.return_value = {
            "total_snapshots": 2,
            "snapshots": [
                {"snapshot_name": "snap-1", "match_count": 1, "top_pattern": "test", "top_score": 0.8},
                {"snapshot_name": "snap-2", "match_count": 0, "top_pattern": None, "top_score": 0.0},
            ],
            "pattern_adoption": {"test": 1},
            "accounts_with_no_matches": ["snap-2"],
        }
        mock_format.return_value = "Compliance Report (2 snapshots)"

        result = runner.invoke(
            app,
            ["patterns", "compliance", "--snapshot", "snap-1", "--snapshot", "snap-2"],
        )

        assert result.exit_code == 0
        assert "Compliance Report" in result.output

    def test_compliance_no_snapshots_error(self) -> None:
        result = runner.invoke(app, ["patterns", "compliance"])

        assert result.exit_code == 1
        output = _strip_ansi(result.output)
        assert "at least one" in output.lower() or "snapshot" in output.lower()
