"""Tests for CLI configuration loader."""

from pathlib import Path
from unittest.mock import patch

from src.cli.config import Config


class TestConfigInit:
    """Tests for Config initialization."""

    def test_default_values(self):
        """Test that Config has correct default values."""
        config = Config()
        assert config.snapshot_dir == ".snapshots"
        assert config.storage_path is None
        assert config.regions == []
        assert config.resource_types == []
        assert config.aws_profile is None
        assert config.parallel_workers == 10
        assert config.auto_compress_mb == 10
        assert config.log_level == "INFO"


class TestConfigLoad:
    """Tests for Config.load method."""

    def test_load_with_no_file(self, tmp_path, monkeypatch):
        """Test loading with no config file present."""
        monkeypatch.chdir(tmp_path)
        # Clear any env vars that might interfere
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)
        monkeypatch.delenv("AWS_BASELINE_LOG_LEVEL", raising=False)
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)

        config = Config.load()

        assert config.snapshot_dir == ".snapshots"
        assert config.log_level == "INFO"

    def test_load_from_specified_file(self, tmp_path, monkeypatch):
        """Test loading from explicitly specified config file."""
        config_file = tmp_path / "custom-config.yaml"
        config_file.write_text(
            """
snapshot_dir: custom-snapshots
aws_profile: my-profile
parallel_workers: 5
"""
        )
        # Clear env vars
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)
        monkeypatch.delenv("AWS_PROFILE", raising=False)

        config = Config.load(config_file=str(config_file))

        assert config.snapshot_dir == "custom-snapshots"
        assert config.aws_profile == "my-profile"
        assert config.parallel_workers == 5

    def test_load_from_current_directory(self, tmp_path, monkeypatch):
        """Test loading from .aws-baseline.yaml in current directory."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / ".aws-baseline.yaml"
        config_file.write_text(
            """
snapshot_dir: local-snapshots
regions:
  - us-east-1
  - us-west-2
"""
        )
        # Clear env vars
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)

        config = Config.load()

        assert config.snapshot_dir == "local-snapshots"
        assert config.regions == ["us-east-1", "us-west-2"]

    def test_load_from_home_directory(self, tmp_path, monkeypatch):
        """Test loading from .aws-baseline.yaml in home directory."""
        # Create temp home directory
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        config_file = fake_home / ".aws-baseline.yaml"
        config_file.write_text(
            """
snapshot_dir: home-snapshots
auto_compress_mb: 20
"""
        )

        # Set HOME and change to a dir without config
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)

        # Patch Path.home to return our fake home
        with patch.object(Path, "home", return_value=fake_home):
            config = Config.load()

        assert config.snapshot_dir == "home-snapshots"
        assert config.auto_compress_mb == 20

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        """Test that environment variables override file settings."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
snapshot_dir: file-snapshots
log_level: DEBUG
"""
        )
        monkeypatch.setenv("AWS_BASELINE_SNAPSHOT_DIR", "env-snapshots")
        monkeypatch.setenv("AWS_BASELINE_LOG_LEVEL", "WARNING")

        config = Config.load(config_file=str(config_file))

        assert config.snapshot_dir == "env-snapshots"
        assert config.log_level == "WARNING"


class TestConfigLoadFromFile:
    """Tests for Config._load_from_file method."""

    def test_load_resource_types_as_list(self, tmp_path, monkeypatch):
        """Test loading resource_types as simple list."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
resource_types:
  - AWS::EC2::Instance
  - AWS::S3::Bucket
"""
        )
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)

        config = Config.load(config_file=str(config_file))

        assert config.resource_types == ["AWS::EC2::Instance", "AWS::S3::Bucket"]

    def test_load_resource_types_as_dict(self, tmp_path, monkeypatch):
        """Test loading resource_types as dict with include key."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
resource_types:
  include:
    - AWS::Lambda::Function
    - AWS::RDS::DBInstance
"""
        )
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)

        config = Config.load(config_file=str(config_file))

        assert config.resource_types == ["AWS::Lambda::Function", "AWS::RDS::DBInstance"]

    def test_load_empty_file(self, tmp_path, monkeypatch):
        """Test loading empty config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)

        config = Config.load(config_file=str(config_file))

        # Should use defaults
        assert config.snapshot_dir == ".snapshots"

    def test_load_invalid_yaml(self, tmp_path, monkeypatch):
        """Test loading invalid YAML file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)

        # Should not raise, just use defaults
        config = Config.load(config_file=str(config_file))

        assert config.snapshot_dir == ".snapshots"

    def test_load_all_fields(self, tmp_path, monkeypatch):
        """Test loading all configuration fields."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
snapshot_dir: all-fields-snapshots
regions:
  - eu-west-1
  - eu-central-1
aws_profile: production
parallel_workers: 20
auto_compress_mb: 50
"""
        )
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)

        config = Config.load(config_file=str(config_file))

        assert config.snapshot_dir == "all-fields-snapshots"
        assert config.regions == ["eu-west-1", "eu-central-1"]
        assert config.aws_profile == "production"
        assert config.parallel_workers == 20
        assert config.auto_compress_mb == 50


class TestConfigLoadFromEnv:
    """Tests for Config._load_from_env method."""

    def test_aws_baseline_snapshot_dir(self, monkeypatch):
        """Test AWS_BASELINE_SNAPSHOT_DIR environment variable."""
        monkeypatch.setenv("AWS_BASELINE_SNAPSHOT_DIR", "/custom/path")
        monkeypatch.delenv("AWS_BASELINE_LOG_LEVEL", raising=False)
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)

        config = Config()
        config._load_from_env()

        assert config.snapshot_dir == "/custom/path"

    def test_aws_baseline_log_level(self, monkeypatch):
        """Test AWS_BASELINE_LOG_LEVEL environment variable."""
        monkeypatch.setenv("AWS_BASELINE_LOG_LEVEL", "DEBUG")
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)

        config = Config()
        config._load_from_env()

        assert config.log_level == "DEBUG"

    def test_aws_profile(self, monkeypatch):
        """Test AWS_PROFILE environment variable."""
        monkeypatch.setenv("AWS_PROFILE", "dev-profile")
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)
        monkeypatch.delenv("AWS_BASELINE_LOG_LEVEL", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)

        config = Config()
        config._load_from_env()

        assert config.aws_profile == "dev-profile"

    def test_aws_region(self, monkeypatch):
        """Test AWS_REGION environment variable."""
        monkeypatch.setenv("AWS_REGION", "ap-southeast-1")
        monkeypatch.delenv("AWS_BASELINE_SNAPSHOT_DIR", raising=False)
        monkeypatch.delenv("AWS_BASELINE_LOG_LEVEL", raising=False)
        monkeypatch.delenv("AWS_PROFILE", raising=False)

        config = Config()
        config._load_from_env()

        assert config.regions == ["ap-southeast-1"]

    def test_multiple_env_vars(self, monkeypatch):
        """Test multiple environment variables at once."""
        monkeypatch.setenv("AWS_BASELINE_SNAPSHOT_DIR", "/snapshots")
        monkeypatch.setenv("AWS_BASELINE_LOG_LEVEL", "ERROR")
        monkeypatch.setenv("AWS_PROFILE", "test-profile")
        monkeypatch.setenv("AWS_REGION", "us-west-2")

        config = Config()
        config._load_from_env()

        assert config.snapshot_dir == "/snapshots"
        assert config.log_level == "ERROR"
        assert config.aws_profile == "test-profile"
        assert config.regions == ["us-west-2"]


class TestConfigToDict:
    """Tests for Config.to_dict method."""

    def test_to_dict_defaults(self):
        """Test to_dict with default values."""
        config = Config()
        result = config.to_dict()

        assert result["snapshot_dir"] == ".snapshots"
        assert result["regions"] == []
        assert result["resource_types"] == []
        assert result["aws_profile"] is None
        assert result["parallel_workers"] == 10
        assert result["auto_compress_mb"] == 10
        assert result["log_level"] == "INFO"

    def test_to_dict_custom_values(self):
        """Test to_dict with custom values."""
        config = Config()
        config.snapshot_dir = "custom-dir"
        config.regions = ["us-east-1"]
        config.resource_types = ["AWS::EC2::Instance"]
        config.aws_profile = "my-profile"
        config.parallel_workers = 20
        config.auto_compress_mb = 50
        config.log_level = "DEBUG"

        result = config.to_dict()

        assert result["snapshot_dir"] == "custom-dir"
        assert result["regions"] == ["us-east-1"]
        assert result["resource_types"] == ["AWS::EC2::Instance"]
        assert result["aws_profile"] == "my-profile"
        assert result["parallel_workers"] == 20
        assert result["auto_compress_mb"] == 50
        assert result["log_level"] == "DEBUG"

    def test_to_dict_returns_new_dict(self):
        """Test that to_dict returns a new dictionary each time."""
        config = Config()
        dict1 = config.to_dict()
        dict2 = config.to_dict()

        assert dict1 is not dict2
        assert dict1 == dict2
