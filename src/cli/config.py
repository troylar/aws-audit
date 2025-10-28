"""Configuration loader for CLI."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class Config:
    """Application configuration manager."""

    def __init__(self):
        """Initialize configuration with defaults."""
        self.snapshot_dir = ".snapshots"
        self.regions = []  # Empty means all enabled regions
        self.resource_types = []  # Empty means all supported types
        self.aws_profile = None
        self.parallel_workers = 10
        self.auto_compress_mb = 10
        self.log_level = "INFO"

    @classmethod
    def load(cls, config_file: Optional[str] = None) -> "Config":
        """Load configuration from file and environment variables.

        Priority (highest to lowest):
        1. Environment variables
        2. Config file
        3. Defaults

        Args:
            config_file: Path to config file (optional)

        Returns:
            Config instance
        """
        config = cls()

        # Try to load from config file
        config_path = None
        if config_file:
            config_path = Path(config_file)
        else:
            # Try current directory first
            config_path = Path(".aws-baseline.yaml")
            if not config_path.exists():
                # Try home directory
                config_path = Path.home() / ".aws-baseline.yaml"

        if config_path and config_path.exists():
            config._load_from_file(config_path)

        # Override with environment variables
        config._load_from_env()

        return config

    def _load_from_file(self, config_path: Path) -> None:
        """Load configuration from YAML file.

        Args:
            config_path: Path to config file
        """
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)

            if not data:
                return

            self.snapshot_dir = data.get("snapshot_dir", self.snapshot_dir)
            self.regions = data.get("regions", self.regions)
            self.aws_profile = data.get("aws_profile", self.aws_profile)
            self.parallel_workers = data.get("parallel_workers", self.parallel_workers)
            self.auto_compress_mb = data.get("auto_compress_mb", self.auto_compress_mb)

            # Handle resource_types (include/exclude)
            resource_types_config = data.get("resource_types", {})
            if isinstance(resource_types_config, dict):
                self.resource_types = resource_types_config.get("include", [])
            elif isinstance(resource_types_config, list):
                self.resource_types = resource_types_config

            logger.info(f"Loaded configuration from {config_path}")

        except Exception as e:
            logger.warning(f"Could not load config file {config_path}: {e}")

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        # AWS_BASELINE_SNAPSHOT_DIR
        if os.getenv("AWS_BASELINE_SNAPSHOT_DIR"):
            self.snapshot_dir = os.getenv("AWS_BASELINE_SNAPSHOT_DIR")

        # AWS_BASELINE_LOG_LEVEL
        if os.getenv("AWS_BASELINE_LOG_LEVEL"):
            self.log_level = os.getenv("AWS_BASELINE_LOG_LEVEL")

        # AWS_PROFILE
        if os.getenv("AWS_PROFILE"):
            self.aws_profile = os.getenv("AWS_PROFILE")

        # AWS_REGION (single region from env)
        if os.getenv("AWS_REGION"):
            self.regions = [os.getenv("AWS_REGION")]

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Configuration as dictionary
        """
        return {
            "snapshot_dir": self.snapshot_dir,
            "regions": self.regions,
            "resource_types": self.resource_types,
            "aws_profile": self.aws_profile,
            "parallel_workers": self.parallel_workers,
            "auto_compress_mb": self.auto_compress_mb,
            "log_level": self.log_level,
        }
