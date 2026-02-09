"""Unit tests for guardrails file parser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.guardrails.file_parser import detect_format, parse_rules_file


class TestDetectFormat:
    """Tests for detect_format()."""

    def test_txt_extension(self) -> None:
        assert detect_format("rules.txt") == "txt"

    def test_json_extension(self) -> None:
        assert detect_format("rules.json") == "json"

    def test_csv_extension(self) -> None:
        assert detect_format("rules.csv") == "csv"

    def test_unknown_extension_raises(self) -> None:
        with pytest.raises(ValueError, match="Unrecognized file extension"):
            detect_format("rules.xml")

    def test_case_insensitive(self) -> None:
        assert detect_format("rules.TXT") == "txt"
        assert detect_format("rules.JSON") == "json"
        assert detect_format("rules.CSV") == "csv"


class TestParseTxt:
    """Tests for TXT format parsing."""

    def test_basic(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.txt"
        f.write_text("S3 must be encrypted\nRDS must have backups\n")
        result = parse_rules_file(str(f))
        assert result == ["S3 must be encrypted", "RDS must have backups"]

    def test_blank_lines_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.txt"
        f.write_text("rule one\n\n\nrule two\n")
        result = parse_rules_file(str(f))
        assert result == ["rule one", "rule two"]

    def test_comments_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.txt"
        f.write_text("# This is a comment\nrule one\n# Another comment\nrule two\n")
        result = parse_rules_file(str(f))
        assert result == ["rule one", "rule two"]

    def test_whitespace_stripped(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.txt"
        f.write_text("  rule one  \n\trule two\t\n")
        result = parse_rules_file(str(f))
        assert result == ["rule one", "rule two"]

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.txt"
        f.write_text("")
        result = parse_rules_file(str(f))
        assert result == []


class TestParseJson:
    """Tests for JSON format parsing."""

    def test_list_of_strings(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.json"
        f.write_text(json.dumps(["rule one", "rule two"]))
        result = parse_rules_file(str(f))
        assert result == ["rule one", "rule two"]

    def test_list_of_objects(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.json"
        data = [{"rule": "rule one"}, {"description": "rule two"}, {"requirement": "rule three"}]
        f.write_text(json.dumps(data))
        result = parse_rules_file(str(f))
        assert result == ["rule one", "rule two", "rule three"]

    def test_dict_with_rules_key(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.json"
        f.write_text(json.dumps({"rules": ["rule one", "rule two"]}))
        result = parse_rules_file(str(f))
        assert result == ["rule one", "rule two"]

    def test_invalid_structure_no_rules_key(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.json"
        f.write_text(json.dumps({"policies": ["rule one"]}))
        with pytest.raises(ValueError, match="must contain a 'rules' key"):
            parse_rules_file(str(f))

    def test_not_list_or_dict(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.json"
        f.write_text('"just a string"')
        with pytest.raises(ValueError, match="must be a list"):
            parse_rules_file(str(f))

    def test_blank_strings_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.json"
        f.write_text(json.dumps(["rule one", "", "  ", "rule two"]))
        result = parse_rules_file(str(f))
        assert result == ["rule one", "rule two"]


class TestParseCsv:
    """Tests for CSV format parsing."""

    def test_rule_column(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.csv"
        f.write_text("id,rule\n1,S3 encryption\n2,RDS backups\n")
        result = parse_rules_file(str(f))
        assert result == ["S3 encryption", "RDS backups"]

    def test_description_column(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.csv"
        f.write_text("id,description\n1,S3 encryption\n2,RDS backups\n")
        result = parse_rules_file(str(f))
        assert result == ["S3 encryption", "RDS backups"]

    def test_requirement_column(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.csv"
        f.write_text("id,requirement\n1,S3 encryption\n2,RDS backups\n")
        result = parse_rules_file(str(f))
        assert result == ["S3 encryption", "RDS backups"]

    def test_first_column_fallback(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.csv"
        f.write_text("policy,severity\nS3 encryption,HIGH\nRDS backups,MEDIUM\n")
        result = parse_rules_file(str(f))
        assert result == ["S3 encryption", "RDS backups"]

    def test_empty_rows_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.csv"
        f.write_text("rule\nS3 encryption\n\nRDS backups\n")
        result = parse_rules_file(str(f))
        assert result == ["S3 encryption", "RDS backups"]

    def test_empty_csv(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.csv"
        f.write_text("")
        result = parse_rules_file(str(f))
        assert result == []


class TestFormatOverride:
    """Tests for format_override parameter."""

    def test_override_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.dat"
        f.write_text("rule one\nrule two\n")
        result = parse_rules_file(str(f), format_override="txt")
        assert result == ["rule one", "rule two"]

    def test_override_json_on_txt_file(self, tmp_path: Path) -> None:
        f = tmp_path / "rules.txt"
        f.write_text(json.dumps(["rule one"]))
        result = parse_rules_file(str(f), format_override="json")
        assert result == ["rule one"]


class TestFileNotFound:
    """Tests for missing files."""

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="File not found"):
            parse_rules_file("/nonexistent/path/rules.txt")
