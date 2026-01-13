"""Protection rules configuration loader.

Loads protection rules from YAML config files and CLI options.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import yaml

from src.models.protection_rule import ProtectionRule, RuleType

logger = logging.getLogger(__name__)

# Default config file locations (checked in order)
CONFIG_LOCATIONS = [
    ".awsinv-restore.yaml",  # Project-local
    ".awsinv-restore.yml",
    os.path.expanduser("~/.awsinv/restore.yaml"),  # User-level
    os.path.expanduser("~/.awsinv/restore.yml"),
]


def find_config_file() -> Optional[Path]:
    """Find the first available config file.

    Searches in order:
    1. .awsinv-restore.yaml (current directory)
    2. .awsinv-restore.yml (current directory)
    3. ~/.awsinv/restore.yaml (user home)
    4. ~/.awsinv/restore.yml (user home)

    Returns:
        Path to config file if found, None otherwise
    """
    for location in CONFIG_LOCATIONS:
        path = Path(location)
        if path.exists():
            logger.debug(f"Found config file: {path}")
            return path
    return None


def load_config_file(config_path: Optional[str] = None) -> dict:
    """Load configuration from YAML file.

    Args:
        config_path: Explicit path to config file (optional).
                    If not provided, searches default locations.

    Returns:
        Configuration dictionary, empty dict if no config found
    """
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
    else:
        path = find_config_file()
        if not path:
            logger.debug("No config file found, using defaults")
            return {}

    logger.info(f"Loading config from: {path}")

    with open(path) as f:
        config = yaml.safe_load(f) or {}

    return config


def parse_protect_tag(tag_string: str) -> tuple[str, str]:
    """Parse a protect-tag CLI argument.

    Args:
        tag_string: Tag in format "key=value"

    Returns:
        Tuple of (key, value)

    Raises:
        ValueError: If format is invalid
    """
    if "=" not in tag_string:
        raise ValueError(f"Invalid tag format: '{tag_string}'. Expected 'key=value'")

    parts = tag_string.split("=", 1)
    key = parts[0].strip()
    value = parts[1].strip()

    if not key:
        raise ValueError(f"Empty tag key in: '{tag_string}'")

    return key, value


def build_protection_rules(
    config: dict,
    cli_protect_tags: Optional[list[str]] = None,
) -> list[ProtectionRule]:
    """Build protection rules from config and CLI options.

    CLI options are merged with config file rules. CLI rules have
    higher priority (lower priority number = checked first).

    Args:
        config: Configuration dictionary from YAML file
        cli_protect_tags: List of "key=value" tag strings from CLI

    Returns:
        List of ProtectionRule objects, sorted by priority
    """
    rules = []
    rule_counter = 0

    # 1. CLI protect-tags (highest priority: 1-10)
    if cli_protect_tags:
        for tag_string in cli_protect_tags:
            try:
                key, value = parse_protect_tag(tag_string)
                rule_counter += 1
                rule = ProtectionRule(
                    rule_id=f"cli-tag-{rule_counter}",
                    rule_type=RuleType.TAG,
                    enabled=True,
                    priority=rule_counter,  # CLI rules get priority 1, 2, 3...
                    patterns={"tag_key": key, "tag_values": [value]},
                    description=f"CLI protection: {key}={value}",
                )
                rules.append(rule)
                logger.debug(f"Added CLI protection rule: {key}={value}")
            except ValueError as e:
                logger.warning(f"Skipping invalid protect-tag: {e}")

    # 2. Config file global tag rules (priority 11-50)
    protection_config = config.get("protection", {})
    global_rules = protection_config.get("global", [])

    for i, rule_config in enumerate(global_rules):
        rule_counter += 1
        priority = 10 + rule_counter

        if isinstance(rule_config, dict):
            # Complex rule with property/value/type
            prop = rule_config.get("property", "")
            value = rule_config.get("value", "")

            # Handle tag:Name format
            if prop.startswith("tag:"):
                tag_key = prop[4:]  # Remove "tag:" prefix
                rule = ProtectionRule(
                    rule_id=f"config-global-{i + 1}",
                    rule_type=RuleType.TAG,
                    enabled=True,
                    priority=priority,
                    patterns={"tag_key": tag_key, "tag_values": [value]},
                    description=f"Config global: {tag_key}={value}",
                )
                rules.append(rule)
        elif isinstance(rule_config, str):
            # Simple string format "key=value"
            try:
                key, value = parse_protect_tag(rule_config)
                rule = ProtectionRule(
                    rule_id=f"config-global-{i + 1}",
                    rule_type=RuleType.TAG,
                    enabled=True,
                    priority=priority,
                    patterns={"tag_key": key, "tag_values": [value]},
                    description=f"Config global: {key}={value}",
                )
                rules.append(rule)
            except ValueError:
                logger.warning(f"Skipping invalid global rule: {rule_config}")

    # 3. Excluded types (priority 51-100) - these are TYPE rules
    excluded_types = protection_config.get("excluded_types", [])
    if excluded_types:
        rule = ProtectionRule(
            rule_id="config-excluded-types",
            rule_type=RuleType.TYPE,
            enabled=True,
            priority=51,
            patterns={"resource_types": excluded_types},
            description=f"Excluded types: {', '.join(excluded_types)}",
        )
        rules.append(rule)

    # Sort by priority
    rules.sort(key=lambda r: r.priority)

    logger.info(f"Built {len(rules)} protection rules")
    return rules


def get_skip_aws_managed(config: dict) -> bool:
    """Get skip_aws_managed setting from config.

    Args:
        config: Configuration dictionary

    Returns:
        True if AWS-managed resources should be skipped (default: True)
    """
    return config.get("skip_aws_managed", True)
