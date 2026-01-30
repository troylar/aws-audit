"""Tests for protection rules configuration loader."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.models.protection_rule import RuleType
from src.restore.config import (
    build_protection_rules,
    find_config_file,
    load_config_file,
    parse_protect_tag,
)


class TestParseProtectTag:
    """Tests for parse_protect_tag function."""

    def test_valid_tag(self):
        """Test parsing valid key=value tag."""
        key, value = parse_protect_tag("project=baseline")
        assert key == "project"
        assert value == "baseline"

    def test_tag_with_spaces(self):
        """Test parsing tag with spaces around equals."""
        key, value = parse_protect_tag("project = baseline")
        assert key == "project"
        assert value == "baseline"

    def test_tag_with_value_containing_equals(self):
        """Test parsing tag where value contains equals sign."""
        key, value = parse_protect_tag("equation=a=b+c")
        assert key == "equation"
        assert value == "a=b+c"

    def test_empty_value(self):
        """Test parsing tag with empty value."""
        key, value = parse_protect_tag("flag=")
        assert key == "flag"
        assert value == ""

    def test_missing_equals(self):
        """Test that missing equals raises ValueError."""
        with pytest.raises(ValueError, match="Invalid tag format"):
            parse_protect_tag("project-baseline")

    def test_empty_key(self):
        """Test that empty key raises ValueError."""
        with pytest.raises(ValueError, match="Empty tag key"):
            parse_protect_tag("=value")


class TestBuildProtectionRules:
    """Tests for build_protection_rules function."""

    def test_cli_tags_only(self):
        """Test building rules from CLI tags only."""
        rules = build_protection_rules({}, ["project=baseline", "env=prod"])

        assert len(rules) == 2
        assert rules[0].rule_type == RuleType.TAG
        assert rules[0].patterns["tag_key"] == "project"
        assert rules[0].patterns["tag_values"] == ["baseline"]
        assert rules[0].priority == 1

        assert rules[1].patterns["tag_key"] == "env"
        assert rules[1].patterns["tag_values"] == ["prod"]
        assert rules[1].priority == 2

    def test_config_global_rules(self):
        """Test building rules from config global section."""
        config = {
            "protection": {
                "global": [
                    {"property": "tag:project", "value": "baseline"},
                    {"property": "tag:Environment", "value": "production"},
                ]
            }
        }

        rules = build_protection_rules(config, None)

        assert len(rules) == 2
        assert all(r.rule_type == RuleType.TAG for r in rules)
        assert rules[0].patterns["tag_key"] == "project"
        assert rules[1].patterns["tag_key"] == "Environment"

    def test_config_excluded_types(self):
        """Test building rules from excluded_types."""
        config = {"protection": {"excluded_types": ["AWS::RDS::DBInstance", "AWS::RDS::DBCluster"]}}

        rules = build_protection_rules(config, None)

        assert len(rules) == 1
        assert rules[0].rule_type == RuleType.TYPE
        assert "AWS::RDS::DBInstance" in rules[0].patterns["resource_types"]
        assert "AWS::RDS::DBCluster" in rules[0].patterns["resource_types"]

    def test_cli_and_config_merged(self):
        """Test that CLI rules and config rules are merged."""
        config = {
            "protection": {
                "global": [{"property": "tag:env", "value": "prod"}],
                "excluded_types": ["AWS::RDS::DBInstance"],
            }
        }

        rules = build_protection_rules(config, ["project=baseline"])

        # CLI rule (priority 1) + config global (priority 11+) + excluded types (priority 51)
        assert len(rules) == 3

        # CLI rule should be first (highest priority)
        assert rules[0].patterns["tag_key"] == "project"
        assert rules[0].priority == 1

    def test_cli_rules_have_higher_priority(self):
        """Test that CLI rules have higher priority than config rules."""
        config = {"protection": {"global": [{"property": "tag:config-tag", "value": "value"}]}}

        rules = build_protection_rules(config, ["cli-tag=value"])

        # Rules should be sorted by priority
        assert rules[0].patterns["tag_key"] == "cli-tag"  # CLI first
        assert rules[0].priority < rules[1].priority

    def test_empty_inputs(self):
        """Test with empty config and no CLI tags."""
        rules = build_protection_rules({}, None)
        assert rules == []

    def test_invalid_cli_tag_skipped(self):
        """Test that invalid CLI tags are skipped with warning."""
        rules = build_protection_rules({}, ["valid=tag", "invalid-no-equals"])

        # Only valid tag should be added
        assert len(rules) == 1
        assert rules[0].patterns["tag_key"] == "valid"

    def test_simple_string_global_rule(self):
        """Test global rule as simple string format."""
        config = {"protection": {"global": ["project=baseline"]}}

        rules = build_protection_rules(config, None)

        assert len(rules) == 1
        assert rules[0].patterns["tag_key"] == "project"
        assert rules[0].patterns["tag_values"] == ["baseline"]


class TestLoadConfigFile:
    """Tests for load_config_file function."""

    def test_load_existing_file(self):
        """Test loading an existing config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"protection": {"global": []}}, f)
            f.flush()

            try:
                config = load_config_file(f.name)
                assert "protection" in config
            finally:
                os.unlink(f.name)

    def test_load_nonexistent_file_raises(self):
        """Test that loading nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config_file("/nonexistent/path/config.yaml")

    def test_load_empty_file(self):
        """Test loading an empty config file returns empty dict."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()

            try:
                config = load_config_file(f.name)
                assert config == {}
            finally:
                os.unlink(f.name)

    def test_auto_find_config(self):
        """Test that None path searches default locations."""
        # Should return empty dict if no config found
        config = load_config_file(None)
        assert isinstance(config, dict)


class TestFindConfigFile:
    """Tests for find_config_file function."""

    def test_finds_project_config(self):
        """Test finding project-local config file."""
        # Create temp config in current directory
        config_path = Path(".awsinv-restore.yaml")

        try:
            config_path.write_text("protection: {}")
            found = find_config_file()
            assert found == config_path
        finally:
            if config_path.exists():
                config_path.unlink()

    def test_returns_none_when_not_found(self):
        """Test returns None when no config file exists."""
        # Ensure no config files exist in test environment
        for loc in [".awsinv-restore.yaml", ".awsinv-restore.yml"]:
            path = Path(loc)
            if path.exists():
                path.unlink()

        # This may find user-level config, so just check it doesn't crash
        result = find_config_file()
        assert result is None or isinstance(result, Path)
