"""Unit tests for ResourceNormalizer."""

from unittest.mock import MagicMock, patch

import pytest

from src.matching.config import NormalizerConfig
from src.matching.normalizer import ResourceNormalizer


@pytest.fixture
def config() -> NormalizerConfig:
    """Create a test config without AI enabled."""
    return NormalizerConfig(api_key=None)


@pytest.fixture
def normalizer(config: NormalizerConfig) -> ResourceNormalizer:
    """Create a normalizer instance."""
    return ResourceNormalizer(config)


class TestBasicNormalize:
    """Test basic string normalization."""

    def test_lowercase(self, normalizer: ResourceNormalizer) -> None:
        """Test lowercasing."""
        assert normalizer._basic_normalize("MyFunction") == "myfunction"

    def test_underscore_to_hyphen(self, normalizer: ResourceNormalizer) -> None:
        """Test replacing underscores with hyphens."""
        assert normalizer._basic_normalize("my_function_name") == "my-function-name"

    def test_spaces_to_hyphen(self, normalizer: ResourceNormalizer) -> None:
        """Test replacing spaces with hyphens."""
        assert normalizer._basic_normalize("My Function Name") == "my-function-name"

    def test_strip_hyphens(self, normalizer: ResourceNormalizer) -> None:
        """Test stripping leading/trailing hyphens."""
        assert normalizer._basic_normalize("-my-function-") == "my-function"

    def test_collapse_hyphens(self, normalizer: ResourceNormalizer) -> None:
        """Test collapsing multiple hyphens."""
        assert normalizer._basic_normalize("my--function---name") == "my-function-name"

    def test_empty_string(self, normalizer: ResourceNormalizer) -> None:
        """Test empty string returns empty."""
        assert normalizer._basic_normalize("") == ""

    def test_none_returns_empty(self, normalizer: ResourceNormalizer) -> None:
        """Test None-like input returns empty."""
        assert normalizer._basic_normalize("") == ""


class TestHasRandomPatterns:
    """Test random pattern detection."""

    def test_hex_suffix(self, normalizer: ResourceNormalizer) -> None:
        """Test detection of hex suffixes."""
        assert normalizer._has_random_patterns("MyStack-MyFunction-abc123def456")

    def test_cloudformation_suffix(self, normalizer: ResourceNormalizer) -> None:
        """Test detection of CloudFormation suffixes."""
        assert normalizer._has_random_patterns("MyStack-MyFunction-ABCXYZ12345")

    def test_underscore_suffix(self, normalizer: ResourceNormalizer) -> None:
        """Test detection of underscore random suffixes."""
        assert normalizer._has_random_patterns("AmazonBedrockRole_jnwn1abc")

    def test_account_id(self, normalizer: ResourceNormalizer) -> None:
        """Test detection of account IDs."""
        assert normalizer._has_random_patterns("cloud-custodian-480738299408-executor")

    def test_aws_resource_id(self, normalizer: ResourceNormalizer) -> None:
        """Test detection of AWS resource IDs (hex only)."""
        assert normalizer._has_random_patterns("subnet-abc123def")
        assert normalizer._has_random_patterns("vpc-1a2b3c4d")  # Real VPC IDs are hex only
        assert normalizer._has_random_patterns("vol-12345678")

    def test_clean_name(self, normalizer: ResourceNormalizer) -> None:
        """Test clean names are not flagged."""
        assert not normalizer._has_random_patterns("daybreak-transcribe-processor")
        assert not normalizer._has_random_patterns("my-lambda-function")
        assert not normalizer._has_random_patterns("production-api")

    def test_short_hex(self, normalizer: ResourceNormalizer) -> None:
        """Test short hex strings are not flagged."""
        # Less than 8 characters shouldn't trigger
        assert not normalizer._has_random_patterns("my-func-abc")

    def test_empty_is_random(self, normalizer: ResourceNormalizer) -> None:
        """Test empty string is considered random."""
        assert normalizer._has_random_patterns("")


class TestRulesBasedNormalization:
    """Test rules-based normalization priority."""

    def test_cloudformation_logical_id_priority(self, normalizer: ResourceNormalizer) -> None:
        """Test CloudFormation logical ID has highest priority."""
        resource = {
            "arn": "arn:aws:lambda:us-east-1:123456789012:function:MyStack-MyLambda-XYZ789",
            "name": "MyStack-MyLambda-XYZ789",
            "tags": {
                "aws:cloudformation:logical-id": "MyLambdaFunction",
                "Name": "Some Other Name",
            },
        }
        result = normalizer._try_rules_based(resource)
        assert result == "mylambdafunction"

    def test_name_tag_when_no_logical_id(self, normalizer: ResourceNormalizer) -> None:
        """Test Name tag is used when no logical ID."""
        resource = {
            "arn": "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-abc123",
            "name": "subnet-abc123",
            "tags": {"Name": "Private-Subnet-AZ1"},
        }
        result = normalizer._try_rules_based(resource)
        assert result == "private-subnet-az1"

    def test_physical_name_when_clean(self, normalizer: ResourceNormalizer) -> None:
        """Test physical name is used when it's clean."""
        resource = {
            "arn": "arn:aws:lambda:us-east-1:123456789012:function:daybreak-processor",
            "name": "daybreak-processor",
            "tags": {},
        }
        result = normalizer._try_rules_based(resource)
        assert result == "daybreak-processor"

    def test_returns_none_for_random_name(self, normalizer: ResourceNormalizer) -> None:
        """Test returns None when name has random patterns and no good tags."""
        resource = {
            "arn": "arn:aws:lambda:us-east-1:123456789012:function:MyStack-Func-XYZ789ABC",
            "name": "MyStack-Func-XYZ789ABC",
            "tags": {},
        }
        result = normalizer._try_rules_based(resource)
        assert result is None

    def test_name_tag_with_random_pattern_skipped(self, normalizer: ResourceNormalizer) -> None:
        """Test Name tag with random pattern is skipped."""
        resource = {
            "arn": "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-abc123",
            "name": "subnet-abc123",
            "tags": {"Name": "MyStack-Subnet-ABC123DEF"},
        }
        result = normalizer._try_rules_based(resource)
        # Name tag has random pattern, physical name also has random pattern
        assert result is None


class TestNormalizeResources:
    """Test full normalize_resources flow."""

    def test_rules_based_only_no_ai(self, normalizer: ResourceNormalizer) -> None:
        """Test normalization with only rules-based (no AI)."""
        resources = [
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:clean-lambda",
                "name": "clean-lambda",
                "resource_type": "AWS::Lambda::Function",
                "tags": {},
            },
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:MyStack-Func-XYZ",
                "name": "MyStack-Func-XYZ",
                "resource_type": "AWS::Lambda::Function",
                "tags": {"aws:cloudformation:logical-id": "ProcessorFunction"},
            },
        ]

        results = normalizer.normalize_resources(resources, use_ai=False)

        assert results["arn:aws:lambda:us-east-1:123456789012:function:clean-lambda"] == "clean-lambda"
        assert results["arn:aws:lambda:us-east-1:123456789012:function:MyStack-Func-XYZ"] == "processorfunction"

    def test_fallback_when_no_ai(self, normalizer: ResourceNormalizer) -> None:
        """Test fallback normalization when AI is disabled and rules fail."""
        resources = [
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:MyStack-Func-ABC123DEF",
                "name": "MyStack-Func-ABC123DEF",
                "resource_type": "AWS::Lambda::Function",
                "tags": {},
            },
        ]

        results = normalizer.normalize_resources(resources, use_ai=False)

        # Should use basic normalize as fallback
        assert (
            results["arn:aws:lambda:us-east-1:123456789012:function:MyStack-Func-ABC123DEF"] == "mystack-func-abc123def"
        )


class TestParseAiResponse:
    """Test AI response parsing."""

    def test_valid_response(self, normalizer: ResourceNormalizer) -> None:
        """Test parsing valid AI response."""
        content = (
            '{"normalizations": [{"arn": "arn:aws:lambda:us-east-1:123456789012:function:test", '
            '"normalized_name": "test-function"}]}'
        )
        resources = [
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:test",
                "name": "test",
            }
        ]

        result = normalizer._parse_ai_response(content, resources)

        assert result["arn:aws:lambda:us-east-1:123456789012:function:test"] == "test-function"

    def test_invalid_json(self, normalizer: ResourceNormalizer) -> None:
        """Test fallback on invalid JSON."""
        content = "not valid json"
        resources = [
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:test",
                "name": "TestFunction",
            }
        ]

        result = normalizer._parse_ai_response(content, resources)

        # Should use basic normalize as fallback
        assert result["arn:aws:lambda:us-east-1:123456789012:function:test"] == "testfunction"

    def test_missing_arn_in_response(self, normalizer: ResourceNormalizer) -> None:
        """Test fallback when ARN missing from response."""
        content = '{"normalizations": [{"arn": "different-arn", "normalized_name": "something"}]}'
        resources = [
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:test",
                "name": "TestFunc",
            }
        ]

        result = normalizer._parse_ai_response(content, resources)

        # Should use basic normalize for missing ARN
        assert result["arn:aws:lambda:us-east-1:123456789012:function:test"] == "testfunc"


class TestAiNormalization:
    """Test AI normalization with mocked OpenAI client."""

    def test_ai_normalization_success(self) -> None:
        """Test successful AI normalization."""
        config = NormalizerConfig(api_key="test-key", base_url="https://test.api")

        with patch("src.matching.normalizer.OpenAI") as mock_openai_class:
            # Setup mock response
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client

            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(
                    message=MagicMock(
                        content=(
                            '{"normalizations": [{"arn": "arn:aws:lambda:us-east-1:123:function:test", '
                            '"normalized_name": "normalized-test"}]}'
                        )
                    )
                )
            ]
            mock_response.usage = MagicMock(total_tokens=100)
            mock_client.chat.completions.create.return_value = mock_response

            normalizer = ResourceNormalizer(config)

            resources = [
                {
                    "arn": "arn:aws:lambda:us-east-1:123:function:test",
                    "name": "MyStack-Test-ABC123",
                    "resource_type": "AWS::Lambda::Function",
                    "tags": {},
                }
            ]

            results = normalizer._normalize_with_ai(resources)

            assert results["arn:aws:lambda:us-east-1:123:function:test"] == "normalized-test"
            assert normalizer.tokens_used == 100


class TestConfig:
    """Test NormalizerConfig."""

    def test_from_env_defaults(self) -> None:
        """Test config loads with defaults when no env vars."""
        with patch.dict("os.environ", {}, clear=True):
            config = NormalizerConfig.from_env()

            assert config.api_key is None
            assert config.base_url is None
            assert config.model == "gpt-4o-mini"
            assert not config.is_ai_enabled

    def test_from_env_with_api_key(self) -> None:
        """Test config with API key from env."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            config = NormalizerConfig.from_env()

            assert config.api_key == "test-key"
            assert config.is_ai_enabled

    def test_from_env_custom_url(self) -> None:
        """Test config with custom base URL."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_BASE_URL": "https://custom.api/v1",
            },
        ):
            config = NormalizerConfig.from_env()

            assert config.base_url == "https://custom.api/v1"

    def test_from_env_custom_model(self) -> None:
        """Test config with custom model."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "test-key",
                "OPENAI_MODEL": "gpt-4-turbo",
            },
        ):
            config = NormalizerConfig.from_env()

            assert config.model == "gpt-4-turbo"
