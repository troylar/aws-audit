"""Unit tests for guardrails evaluator."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestEvaluateCondition:
    """Tests for evaluate_condition() operators (T029)."""

    def test_equals_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="StorageEncrypted", operator="equals", value=True)
        config = {"StorageEncrypted": True}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True
        assert reason == ""

    def test_equals_false(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="StorageEncrypted", operator="equals", value=True)
        config = {"StorageEncrypted": False}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False
        assert "expected" in reason.lower() and "storageencrypted" in reason.lower()

    def test_not_equals_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="Status", operator="not_equals", value="deleted")
        config = {"Status": "active"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_not_equals_false(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="Status", operator="not_equals", value="deleted")
        config = {"Status": "deleted"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False

    def test_exists_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="ServerSideEncryption", operator="exists")
        config = {"ServerSideEncryption": {"SSEAlgorithm": "AES256"}}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_exists_false(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="ServerSideEncryption", operator="exists")
        config = {"BucketName": "my-bucket"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False
        assert "not found" in reason.lower() or "does not exist" in reason.lower()

    def test_exists_false_for_none(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="Encryption", operator="exists")
        config = {"Encryption": None}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False

    def test_not_exists_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="PublicAccessBlock", operator="not_exists")
        config = {"BucketName": "my-bucket"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_not_exists_false(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="PublicAccessBlock", operator="not_exists")
        config = {"PublicAccessBlock": {"BlockPublicAcls": True}}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False

    def test_contains_string_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="BucketName", operator="contains", value="prod")
        config = {"BucketName": "my-prod-bucket"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_contains_string_false(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="BucketName", operator="contains", value="prod")
        config = {"BucketName": "my-dev-bucket"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False

    def test_contains_list_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="Tags", operator="contains", value="Environment")
        config = {"Tags": ["Environment", "Owner", "CostCenter"]}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_not_contains_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="CidrIp", operator="not_contains", value="0.0.0.0/0")
        config = {"CidrIp": "10.0.0.0/8"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_matches_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="KmsKeyId",
            operator="matches",
            value=r"^arn:aws:kms:.*:123456789012:key/.*",
        )
        config = {"KmsKeyId": "arn:aws:kms:us-east-1:123456789012:key/abc-123"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_matches_false(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="KmsKeyId",
            operator="matches",
            value=r"^arn:aws:kms:.*:123456789012:key/.*",
        )
        config = {"KmsKeyId": "arn:aws:kms:us-east-1:999999999999:key/abc-123"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False

    def test_in_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="InstanceType",
            operator="in",
            value=["t3.micro", "t3.small", "t3.medium"],
        )
        config = {"InstanceType": "t3.small"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_in_false(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="InstanceType",
            operator="in",
            value=["t3.micro", "t3.small", "t3.medium"],
        )
        config = {"InstanceType": "m5.xlarge"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False

    def test_not_in_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="InstanceType",
            operator="not_in",
            value=["t2.micro", "t2.small"],  # Legacy types
        )
        config = {"InstanceType": "t3.small"}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_greater_than_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="AllocatedStorage", operator="greater_than", value=100)
        config = {"AllocatedStorage": 200}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_greater_than_false(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="AllocatedStorage", operator="greater_than", value=100)
        config = {"AllocatedStorage": 50}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False

    def test_less_than_true(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="MaxConnections", operator="less_than", value=1000)
        config = {"MaxConnections": 500}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_less_than_false(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(attribute="MaxConnections", operator="less_than", value=1000)
        config = {"MaxConnections": 1500}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False

    def test_nested_attribute(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="Tags.Environment",
            operator="equals",
            value="production",
        )
        config = {"Tags": {"Environment": "production", "Owner": "team-a"}}

        passed, reason = evaluate_condition(condition, config)

        assert passed is True

    def test_missing_nested_attribute(self) -> None:
        from src.guardrails.evaluator import evaluate_condition
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="Tags.Environment",
            operator="exists",
        )
        config = {"Tags": {"Owner": "team-a"}}

        passed, reason = evaluate_condition(condition, config)

        assert passed is False


class TestGuardrailEvaluatorEvaluateResource:
    """Tests for GuardrailEvaluator.evaluate_resource() (T030)."""

    def _create_mock_resource(
        self,
        resource_type: str = "s3:bucket",
        name: str = "test-bucket",
        arn: str = "arn:aws:s3:::test-bucket",
        config: dict | None = None,
    ):
        """Create a mock TrackedResource for testing."""
        mock_resource = MagicMock()
        mock_resource.resource_type = resource_type
        mock_resource.name = name
        mock_resource.arn = arn
        mock_resource.config = config or {}
        return mock_resource

    def test_evaluate_resource_pass(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            EvaluationResult,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["s3:bucket"],
            condition=Condition(attribute="Encryption", operator="exists"),
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        evaluator = GuardrailEvaluator(policy, auto_fix_enabled=False)
        resource = self._create_mock_resource(config={"Encryption": {"Type": "AES256"}})

        evaluations = evaluator.evaluate_resource(resource)

        assert len(evaluations) == 1
        assert evaluations[0].result == EvaluationResult.PASS

    def test_evaluate_resource_fail(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            EvaluationResult,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["s3:bucket"],
            condition=Condition(attribute="Encryption", operator="exists"),
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        evaluator = GuardrailEvaluator(policy, auto_fix_enabled=False)
        resource = self._create_mock_resource(config={"BucketName": "my-bucket"})

        evaluations = evaluator.evaluate_resource(resource)

        assert len(evaluations) == 1
        assert evaluations[0].result == EvaluationResult.FAIL
        assert evaluations[0].failure_reason != ""

    def test_evaluate_resource_skips_non_matching_guardrails(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-RDS-001",
            short_description="RDS encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["rds:db"],  # Does not apply to S3
            condition=Condition(attribute="StorageEncrypted", operator="equals", value=True),
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        evaluator = GuardrailEvaluator(policy, auto_fix_enabled=False)
        resource = self._create_mock_resource(resource_type="s3:bucket")

        evaluations = evaluator.evaluate_resource(resource)

        # No evaluations because guardrail doesn't apply to S3
        assert len(evaluations) == 0

    def test_evaluate_resource_multiple_guardrails(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrails = [
            Guardrail(
                id="GR-ENC-001",
                short_description="Encryption required",
                severity=Severity.CRITICAL,
                action=Action.BLOCK,
                applies_to=["s3:bucket"],
                condition=Condition(attribute="Encryption", operator="exists"),
            ),
            Guardrail(
                id="GR-TAG-001",
                short_description="Tags required",
                severity=Severity.HIGH,
                action=Action.WARN,
                applies_to=["*"],  # Applies to all
                condition=Condition(attribute="Tags", operator="exists"),
            ),
        ]
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=guardrails)

        evaluator = GuardrailEvaluator(policy, auto_fix_enabled=False)
        resource = self._create_mock_resource(
            config={"Encryption": {"Type": "AES256"}, "Tags": {"Environment": "prod"}}
        )

        evaluations = evaluator.evaluate_resource(resource)

        assert len(evaluations) == 2

    def test_evaluate_resource_disabled_guardrail_skipped(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-TEST-001",
            short_description="Test",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            applies_to=["*"],
            condition=Condition(attribute="test", operator="exists"),
            enabled=False,  # Disabled
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        evaluator = GuardrailEvaluator(policy, auto_fix_enabled=False)
        resource = self._create_mock_resource()

        evaluations = evaluator.evaluate_resource(resource)

        assert len(evaluations) == 0


class TestGuardrailEvaluatorEvaluateAll:
    """Tests for GuardrailEvaluator.evaluate_all() (T031)."""

    def _create_mock_resource(
        self,
        resource_type: str = "s3:bucket",
        name: str = "test-bucket",
        arn: str = "arn:aws:s3:::test-bucket",
        config: dict | None = None,
    ):
        """Create a mock TrackedResource for testing."""
        mock_resource = MagicMock()
        mock_resource.resource_type = resource_type
        mock_resource.name = name
        mock_resource.arn = arn
        mock_resource.config = config or {}
        return mock_resource

    def test_evaluate_all_returns_report(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="Encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["s3:bucket"],
            condition=Condition(attribute="Encryption", operator="exists"),
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        evaluator = GuardrailEvaluator(policy, auto_fix_enabled=False)
        resources = [
            self._create_mock_resource(name="bucket1", config={"Encryption": {"Type": "AES256"}}),
            self._create_mock_resource(name="bucket2", config={}),
        ]

        report = evaluator.evaluate_all(resources, snapshot_name="test-snapshot")

        assert report.policy_name == "test"
        assert report.snapshot_name == "test-snapshot"
        assert report.summary.total_resources == 2
        assert report.summary.passed == 1
        assert report.summary.failed == 1

    def test_evaluate_all_with_blocking_violations(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-NET-001",
            short_description="No open SSH",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["ec2:security-group"],
            condition=Condition(attribute="OpenSSH", operator="not_exists"),
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        evaluator = GuardrailEvaluator(policy, auto_fix_enabled=False)
        resources = [
            self._create_mock_resource(
                resource_type="ec2:security-group",
                name="web-sg",
                arn="arn:aws:ec2:...:sg/sg-123",
                config={"OpenSSH": True},
            )
        ]

        report = evaluator.evaluate_all(resources, snapshot_name="test")

        assert report.blocked is True
        assert len(report.get_blocking_violations()) == 1

    def test_evaluate_all_progress_callback(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-TEST-001",
            short_description="Test",
            severity=Severity.HIGH,
            action=Action.WARN,
            applies_to=["*"],
            condition=Condition(attribute="test", operator="exists"),
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        evaluator = GuardrailEvaluator(policy, auto_fix_enabled=False)
        resources = [self._create_mock_resource(name=f"resource-{i}") for i in range(5)]

        progress_calls = []

        def progress_callback(current: int, total: int) -> None:
            progress_calls.append((current, total))

        evaluator.evaluate_all(resources, snapshot_name="test", progress_callback=progress_callback)

        assert len(progress_calls) == 5
        assert progress_calls[-1] == (5, 5)

    def test_evaluate_all_empty_resources(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import GuardrailPolicy

        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[])

        evaluator = GuardrailEvaluator(policy, auto_fix_enabled=False)

        report = evaluator.evaluate_all([], snapshot_name="test")

        assert report.summary.total_resources == 0
        assert report.summary.total_evaluations == 0
        assert report.blocked is False


class TestEvaluatorAutoFix:
    """Tests for auto-fix integration with GuardrailEvaluator."""

    def _create_mock_resource(
        self,
        name: str = "test-resource",
        resource_type: str = "s3:bucket",
        config: dict | None = None,
    ) -> MagicMock:
        """Create a mock resource for testing."""
        resource = MagicMock()
        resource.name = name
        resource.resource_type = resource_type
        resource.arn = f"arn:aws:s3:::{name}"
        resource.config = config or {}
        return resource

    def test_auto_fix_called_when_enabled_and_guardrail_has_auto_fix_action(
        self,
    ) -> None:
        """Auto-fix should be attempted when enabled and guardrail action is AUTO-FIX."""
        from unittest.mock import patch

        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            EvaluationResult,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.HIGH,
            action=Action.AUTO_FIX,
            applies_to=["s3:bucket"],
            condition=Condition(attribute="Encryption", operator="exists"),
            ai_context="WHY: Compliance\nHOW TO FIX: Add encryption",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        mock_bedrock = MagicMock()

        with patch("src.guardrails.evaluator.attempt_auto_fix") as mock_auto_fix:
            mock_auto_fix.return_value = (
                True,
                {"encryption": "AES256"},
                "Added encryption",
            )

            evaluator = GuardrailEvaluator(
                policy,
                auto_fix_enabled=True,
                bedrock_client=mock_bedrock,
                output_format="terraform",
            )

            resource = self._create_mock_resource(config={})
            evaluations = evaluator.evaluate_resource(resource)

            # Auto-fix should have been called
            mock_auto_fix.assert_called_once()

            # Evaluation should be AUTO_FIXED
            assert len(evaluations) == 1
            assert evaluations[0].result == EvaluationResult.AUTO_FIXED
            assert evaluations[0].auto_fix_applied == "Added encryption"

    def test_auto_fix_not_called_when_disabled(self) -> None:
        """Auto-fix should not be attempted when disabled."""
        from unittest.mock import patch

        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            EvaluationResult,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.HIGH,
            action=Action.AUTO_FIX,
            applies_to=["s3:bucket"],
            condition=Condition(attribute="Encryption", operator="exists"),
            ai_context="WHY: Compliance\nHOW TO FIX: Add encryption",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        with patch("src.guardrails.evaluator.attempt_auto_fix") as mock_auto_fix:
            evaluator = GuardrailEvaluator(
                policy,
                auto_fix_enabled=False,  # Disabled
                output_format="terraform",
            )

            resource = self._create_mock_resource(config={})
            evaluations = evaluator.evaluate_resource(resource)

            # Auto-fix should NOT have been called
            mock_auto_fix.assert_not_called()

            # Evaluation should be FAIL (not AUTO_FIXED)
            assert len(evaluations) == 1
            assert evaluations[0].result == EvaluationResult.FAIL

    def test_auto_fix_stored_in_auto_fixes_dict(self) -> None:
        """Successful auto-fixes should be stored in _auto_fixes dict."""
        from unittest.mock import patch

        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.HIGH,
            action=Action.AUTO_FIX,
            applies_to=["s3:bucket"],
            condition=Condition(attribute="Encryption", operator="exists"),
            ai_context="WHY: Compliance\nHOW TO FIX: Add encryption",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        mock_bedrock = MagicMock()
        fix_config = {"encryption": "AES256"}

        with patch("src.guardrails.evaluator.attempt_auto_fix") as mock_auto_fix:
            mock_auto_fix.return_value = (True, fix_config, "Added encryption")

            evaluator = GuardrailEvaluator(
                policy,
                auto_fix_enabled=True,
                bedrock_client=mock_bedrock,
                output_format="terraform",
            )

            resource = self._create_mock_resource(name="my-bucket", config={})
            evaluator.evaluate_resource(resource)

            # Check auto-fixes are stored
            auto_fixes = evaluator.get_auto_fixes()
            assert len(auto_fixes) == 1
            assert "GR-ENC-001" in auto_fixes["arn:aws:s3:::my-bucket"]
            assert auto_fixes["arn:aws:s3:::my-bucket"]["GR-ENC-001"] == fix_config

    def test_auto_fix_failure_results_in_fail_evaluation(self) -> None:
        """When auto-fix fails, evaluation should be FAIL."""
        from unittest.mock import patch

        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            EvaluationResult,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.HIGH,
            action=Action.AUTO_FIX,
            applies_to=["s3:bucket"],
            condition=Condition(attribute="Encryption", operator="exists"),
            ai_context="WHY: Compliance\nHOW TO FIX: Add encryption",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        mock_bedrock = MagicMock()

        with patch("src.guardrails.evaluator.attempt_auto_fix") as mock_auto_fix:
            # Auto-fix fails
            mock_auto_fix.return_value = (False, {}, "Bedrock API error")

            evaluator = GuardrailEvaluator(
                policy,
                auto_fix_enabled=True,
                bedrock_client=mock_bedrock,
                output_format="terraform",
            )

            resource = self._create_mock_resource(config={})
            evaluations = evaluator.evaluate_resource(resource)

            # Evaluation should be FAIL
            assert len(evaluations) == 1
            assert evaluations[0].result == EvaluationResult.FAIL
            assert evaluations[0].auto_fix_applied == ""

    def test_auto_fix_report_summary_counts(self) -> None:
        """Report summary should correctly count auto-fixed evaluations."""
        from unittest.mock import patch

        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.HIGH,
            action=Action.AUTO_FIX,
            applies_to=["s3:bucket"],
            condition=Condition(attribute="Encryption", operator="exists"),
            ai_context="WHY: Compliance\nHOW TO FIX: Add encryption",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])

        mock_bedrock = MagicMock()

        with patch("src.guardrails.evaluator.attempt_auto_fix") as mock_auto_fix:
            mock_auto_fix.return_value = (
                True,
                {"encryption": "AES256"},
                "Added encryption",
            )

            evaluator = GuardrailEvaluator(
                policy,
                auto_fix_enabled=True,
                bedrock_client=mock_bedrock,
                output_format="terraform",
            )

            resources = [self._create_mock_resource(name=f"bucket-{i}", config={}) for i in range(3)]
            report = evaluator.evaluate_all(resources, snapshot_name="test")

            # All 3 resources should be auto-fixed
            assert report.summary.auto_fixed == 3
            assert report.summary.failed == 0
            assert report.blocked is False  # AUTO_FIXED doesn't block
