"""Unit tests for guardrails evaluator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestEvaluateFormula:
    """Tests for evaluate_formula() - formula-based condition evaluation."""

    def test_exists_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"ServerSideEncryption": {"SSEAlgorithm": "AES256"}}
        passed, reason = evaluate_formula("ServerSideEncryption exists", config)

        assert passed is True
        assert reason == ""

    def test_exists_false(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"BucketName": "my-bucket"}
        passed, reason = evaluate_formula("ServerSideEncryption exists", config)

        assert passed is False
        assert "not met" in reason.lower()

    def test_exists_false_for_none(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Encryption": None}
        passed, reason = evaluate_formula("Encryption exists", config)

        assert passed is False

    def test_not_exists_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"BucketName": "my-bucket"}
        passed, reason = evaluate_formula("PublicAccessBlock not exists", config)

        assert passed is True

    def test_not_exists_false(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"PublicAccessBlock": {"BlockPublicAcls": True}}
        passed, reason = evaluate_formula("PublicAccessBlock not exists", config)

        assert passed is False

    def test_equals_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"StorageEncrypted": True}
        passed, reason = evaluate_formula("get('StorageEncrypted') == True", config)

        assert passed is True

    def test_equals_false(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"StorageEncrypted": False}
        passed, reason = evaluate_formula("get('StorageEncrypted') == True", config)

        assert passed is False

    def test_not_equals_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Status": "active"}
        passed, reason = evaluate_formula("get('Status') != 'deleted'", config)

        assert passed is True

    def test_not_equals_false(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Status": "deleted"}
        passed, reason = evaluate_formula("get('Status') != 'deleted'", config)

        assert passed is False

    def test_contains_string_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Description": "Production server for main app"}
        passed, reason = evaluate_formula("contains(get('Description'), 'Production')", config)

        assert passed is True

    def test_contains_string_false(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Description": "Test server"}
        passed, reason = evaluate_formula("contains(get('Description'), 'Production')", config)

        assert passed is False

    def test_contains_list_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Regions": ["us-east-1", "us-west-2", "eu-west-1"]}
        passed, reason = evaluate_formula("contains(get('Regions'), 'us-east-1')", config)

        assert passed is True

    def test_matches_regex_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"BucketName": "prod-logs-2024"}
        passed, reason = evaluate_formula("matches(get('BucketName'), r'^prod-.*')", config)

        assert passed is True

    def test_matches_regex_false(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"BucketName": "test-bucket"}
        passed, reason = evaluate_formula("matches(get('BucketName'), r'^prod-.*')", config)

        assert passed is False

    def test_in_list_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Environment": "production"}
        passed, reason = evaluate_formula("get('Environment') in ['production', 'staging', 'development']", config)

        assert passed is True

    def test_in_list_false(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Environment": "test"}
        passed, reason = evaluate_formula("get('Environment') in ['production', 'staging', 'development']", config)

        assert passed is False

    def test_greater_than_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"RetentionDays": 30}
        passed, reason = evaluate_formula("get('RetentionDays') > 7", config)

        assert passed is True

    def test_greater_than_false(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"RetentionDays": 3}
        passed, reason = evaluate_formula("get('RetentionDays') > 7", config)

        assert passed is False

    def test_less_than_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"MaxConnections": 50}
        passed, reason = evaluate_formula("get('MaxConnections') < 100", config)

        assert passed is True

    def test_nested_attribute(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Tags": {"Environment": "production", "Team": "platform"}}
        passed, reason = evaluate_formula("Tags.Environment exists", config)

        assert passed is True

    def test_nested_attribute_missing(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Tags": {"Team": "platform"}}
        passed, reason = evaluate_formula("Tags.Environment exists", config)

        assert passed is False

    def test_boolean_and_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Encryption": {"Type": "AES256"}, "Versioning": {"Status": "Enabled"}}
        passed, reason = evaluate_formula("Encryption exists and get('Versioning.Status') == 'Enabled'", config)

        assert passed is True

    def test_boolean_and_false(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"Encryption": {"Type": "AES256"}, "Versioning": {"Status": "Suspended"}}
        passed, reason = evaluate_formula("Encryption exists and get('Versioning.Status') == 'Enabled'", config)

        assert passed is False

    def test_boolean_or_true(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"PublicAccess": False}
        passed, reason = evaluate_formula("get('PublicAccess') == False or Encryption exists", config)

        assert passed is True

    def test_if_then_pattern_condition_false(self) -> None:
        """When 'if' condition is false, the whole expression should pass."""
        from src.guardrails.formula import evaluate_formula

        # If PublicAccess is false, we don't need to check encryption
        config = {"PublicAccess": False}
        passed, reason = evaluate_formula("not get('PublicAccess') or Encryption exists", config)

        assert passed is True

    def test_if_then_pattern_condition_true_then_true(self) -> None:
        """When 'if' condition is true and 'then' is satisfied."""
        from src.guardrails.formula import evaluate_formula

        # If PublicAccess is true, encryption must exist
        config = {"PublicAccess": True, "Encryption": {"Type": "AES256"}}
        passed, reason = evaluate_formula("not get('PublicAccess') or Encryption exists", config)

        assert passed is True

    def test_if_then_pattern_condition_true_then_false(self) -> None:
        """When 'if' condition is true but 'then' is not satisfied."""
        from src.guardrails.formula import evaluate_formula

        # If PublicAccess is true, encryption must exist - but it doesn't
        config = {"PublicAccess": True}
        passed, reason = evaluate_formula("not get('PublicAccess') or Encryption exists", config)

        assert passed is False

    def test_count_function(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"AvailabilityZones": ["us-east-1a", "us-east-1b", "us-east-1c"]}
        passed, reason = evaluate_formula("count(get('AvailabilityZones')) >= 2", config)

        assert passed is True

    def test_count_function_fails(self) -> None:
        from src.guardrails.formula import evaluate_formula

        config = {"AvailabilityZones": ["us-east-1a"]}
        passed, reason = evaluate_formula("count(get('AvailabilityZones')) >= 2", config)

        assert passed is False


class TestGuardrailEvaluator:
    """Tests for GuardrailEvaluator class (T030-T032)."""

    def test_evaluate_resource_pass(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, EvaluationResult, Guardrail, GuardrailPolicy, Severity

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["s3:bucket"],
            condition="Encryption exists",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=False)

        resource = MagicMock()
        resource.resource_type = "s3:bucket"
        resource.name = "test-bucket"
        resource.arn = "arn:aws:s3:::test-bucket"
        resource.config = {"Encryption": {"Type": "AES256"}}

        results = evaluator.evaluate_resource(resource)

        assert len(results) == 1
        assert results[0].result == EvaluationResult.PASS

    def test_evaluate_resource_fail(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, EvaluationResult, Guardrail, GuardrailPolicy, Severity

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["s3:bucket"],
            condition="Encryption exists",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=False)

        resource = MagicMock()
        resource.resource_type = "s3:bucket"
        resource.name = "test-bucket"
        resource.arn = "arn:aws:s3:::test-bucket"
        resource.config = {"BucketName": "test-bucket"}  # No Encryption

        results = evaluator.evaluate_resource(resource)

        assert len(results) == 1
        assert results[0].result == EvaluationResult.FAIL

    def test_evaluate_resource_skips_non_matching_type(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, Guardrail, GuardrailPolicy, Severity

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["s3:bucket"],
            condition="Encryption exists",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=False)

        resource = MagicMock()
        resource.resource_type = "ec2:instance"  # Different type
        resource.name = "test-instance"
        resource.arn = "arn:aws:ec2:::instance/test"
        resource.config = {}

        results = evaluator.evaluate_resource(resource)

        assert len(results) == 0  # Should skip, not evaluate

    def test_evaluate_all_generates_report(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, Guardrail, GuardrailPolicy, Severity

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["s3:bucket"],
            condition="Encryption exists",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=False)

        resource1 = MagicMock()
        resource1.resource_type = "s3:bucket"
        resource1.name = "bucket-1"
        resource1.arn = "arn:aws:s3:::bucket-1"
        resource1.config = {"Encryption": {"Type": "AES256"}}

        resource2 = MagicMock()
        resource2.resource_type = "s3:bucket"
        resource2.name = "bucket-2"
        resource2.arn = "arn:aws:s3:::bucket-2"
        resource2.config = {}  # No encryption

        report = evaluator.evaluate_all([resource1, resource2], snapshot_name="test-snapshot")

        assert report.summary.total_resources == 2
        assert report.summary.total_evaluations == 2
        assert report.summary.passed == 1
        assert report.summary.failed == 1

    def test_blocking_violations_block_report(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, Guardrail, GuardrailPolicy, Severity

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            applies_to=["s3:bucket"],
            condition="Encryption exists",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=False)

        resource = MagicMock()
        resource.resource_type = "s3:bucket"
        resource.name = "test-bucket"
        resource.arn = "arn:aws:s3:::test-bucket"
        resource.config = {}  # No encryption

        report = evaluator.evaluate_all([resource], snapshot_name="test-snapshot")

        assert report.blocked is True
        assert "CRITICAL" in report.block_reason or "violation" in report.block_reason.lower()

    def test_warn_action_does_not_block(self) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, Guardrail, GuardrailPolicy, Severity

        guardrail = Guardrail(
            id="GR-TAG-001",
            short_description="Environment tag recommended",
            severity=Severity.LOW,
            action=Action.WARN,
            applies_to=["*"],
            condition="Tags.Environment exists",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=False)

        resource = MagicMock()
        resource.resource_type = "s3:bucket"
        resource.name = "test-bucket"
        resource.arn = "arn:aws:s3:::test-bucket"
        resource.config = {"Tags": {}}  # No Environment tag

        report = evaluator.evaluate_all([resource], snapshot_name="test-snapshot")

        assert report.blocked is False  # WARN action should not block


class TestAIRuleEvaluation:
    """Tests for AI-based rule evaluation."""

    def test_ai_rule_detection(self) -> None:
        from src.guardrails.models import Action, Guardrail, Severity

        guardrail = Guardrail(
            id="GR-AI-001",
            short_description="AI security check",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            applies_to=["*"],
            ai_fail_if="This resource has overly permissive access",
        )

        assert guardrail.is_ai_rule() is True
        ai_rule = guardrail.get_ai_rule()
        assert ai_rule is not None
        assert ai_rule[0] == "This resource has overly permissive access"
        assert ai_rule[1] == "fail"

    def test_condition_rule_not_ai(self) -> None:
        from src.guardrails.models import Action, Guardrail, Severity

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="Encryption check",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            applies_to=["*"],
            condition="Encryption exists",
        )

        assert guardrail.is_ai_rule() is False
        assert guardrail.get_ai_rule() is None

    @patch("src.guardrails.evaluator.evaluate_ai_rule")
    def test_evaluate_ai_rule_pass(self, mock_ai_eval: MagicMock) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, EvaluationResult, Guardrail, GuardrailPolicy, Severity

        mock_ai_eval.return_value = (False, "Resource is properly secured")

        guardrail = Guardrail(
            id="GR-AI-001",
            short_description="AI security check",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            applies_to=["*"],
            ai_fail_if="This resource has overly permissive access",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=False)

        resource = MagicMock()
        resource.resource_type = "iam:policy"
        resource.name = "test-policy"
        resource.arn = "arn:aws:iam::123456789012:policy/test"
        resource.config = {"PolicyDocument": {}}

        results = evaluator.evaluate_resource(resource)

        assert len(results) == 1
        assert results[0].result == EvaluationResult.PASS

    @patch("src.guardrails.evaluator.evaluate_ai_rule")
    def test_evaluate_ai_rule_fail(self, mock_ai_eval: MagicMock) -> None:
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, EvaluationResult, Guardrail, GuardrailPolicy, Severity

        mock_ai_eval.return_value = (True, "Resource allows * access")

        guardrail = Guardrail(
            id="GR-AI-001",
            short_description="AI security check",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            applies_to=["*"],
            ai_fail_if="This resource has overly permissive access",
        )
        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=False)

        resource = MagicMock()
        resource.resource_type = "iam:policy"
        resource.name = "test-policy"
        resource.arn = "arn:aws:iam::123456789012:policy/test"
        resource.config = {"PolicyDocument": {"Statement": [{"Effect": "Allow", "Action": "*"}]}}

        results = evaluator.evaluate_resource(resource)

        assert len(results) == 1
        assert results[0].result == EvaluationResult.FAIL
        assert "allows * access" in results[0].failure_reason


class TestCrossResourceContext:
    """Tests for env() function and cross-resource context."""

    def test_env_function_from_context(self) -> None:
        """Test that env() reads from context dict."""
        from src.guardrails.formula import evaluate_formula

        config = {"VpcId": "vpc-prod123"}
        context = {"ACCOUNT_VPC": "vpc-prod123"}

        passed, reason = evaluate_formula(
            "get('VpcId') == env('ACCOUNT_VPC')",
            config,
            context=context,
        )

        assert passed is True

    def test_env_function_mismatch(self) -> None:
        """Test that env() detects mismatches."""
        from src.guardrails.formula import evaluate_formula

        config = {"VpcId": "vpc-wrong"}
        context = {"ACCOUNT_VPC": "vpc-prod123"}

        passed, reason = evaluate_formula(
            "get('VpcId') == env('ACCOUNT_VPC')",
            config,
            context=context,
        )

        assert passed is False

    def test_env_function_default_value(self) -> None:
        """Test that env() supports default values."""
        from src.guardrails.formula import evaluate_formula

        config = {"RoleArn": "default-role"}
        context = {}  # No ACCOUNT_ROLE defined

        passed, reason = evaluate_formula(
            "get('RoleArn') == env('ACCOUNT_ROLE', 'default-role')",
            config,
            context=context,
        )

        assert passed is True

    def test_evaluator_with_context(self) -> None:
        """Test that GuardrailEvaluator passes context to formulas."""
        from unittest.mock import MagicMock

        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, EvaluationResult, Guardrail, GuardrailPolicy, Severity

        guardrail = Guardrail(
            id="GR-NET-001",
            short_description="VPC must match account VPC",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            applies_to=["ec2:instance"],
            condition="get('VpcId') == env('ACCOUNT_VPC')",
        )

        policy = GuardrailPolicy(
            name="test",
            version="1.0",
            guardrails=[guardrail],
            context={"ACCOUNT_VPC": "vpc-default"},
            context_overrides={
                "production": {"ACCOUNT_VPC": "vpc-prod123"},
            },
        )

        # Test with production environment
        evaluator = GuardrailEvaluator(
            policy=policy,
            auto_fix_enabled=False,
            environment="production",
        )

        resource = MagicMock()
        resource.resource_type = "ec2:instance"
        resource.name = "web-server"
        resource.arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-123"
        resource.config = {"VpcId": "vpc-prod123"}

        results = evaluator.evaluate_resource(resource)

        assert len(results) == 1
        assert results[0].result == EvaluationResult.PASS

    def test_context_overrides_per_environment(self) -> None:
        """Test that context_overrides work per environment."""
        from src.guardrails.models import GuardrailPolicy

        policy = GuardrailPolicy(
            name="test",
            version="1.0",
            context={"SHARED_ROLE": "arn:aws:iam::123:role/Shared"},
            context_overrides={
                "production": {"ACCOUNT_VPC": "vpc-prod"},
                "staging": {"ACCOUNT_VPC": "vpc-staging"},
            },
        )

        # Default env gets base context only
        default_ctx = policy.get_context_for_env("default")
        assert default_ctx == {"SHARED_ROLE": "arn:aws:iam::123:role/Shared"}

        # Production gets base + override
        prod_ctx = policy.get_context_for_env("production")
        assert prod_ctx["SHARED_ROLE"] == "arn:aws:iam::123:role/Shared"
        assert prod_ctx["ACCOUNT_VPC"] == "vpc-prod"

        # Staging gets base + different override
        staging_ctx = policy.get_context_for_env("staging")
        assert staging_ctx["ACCOUNT_VPC"] == "vpc-staging"


class TestFixConflictDetection:
    """Tests for post-fix validation and conflict detection."""

    @patch("src.guardrails.evaluator.attempt_auto_fix")
    def test_validate_fixes_detects_conflict(self, mock_auto_fix: MagicMock) -> None:
        """Test that validate_fixes detects when a fix causes a new violation."""
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, Guardrail, GuardrailPolicy, Severity

        # Guardrail 1: Requires encryption (will be auto-fixed)
        guardrail1 = Guardrail(
            id="GR-ENC-001",
            short_description="Encryption required",
            severity=Severity.HIGH,
            action=Action.AUTO_FIX,
            applies_to=["s3:bucket"],
            condition="Encryption exists",
            ai_context="Add encryption",
        )

        # Guardrail 2: No encryption allowed (conflicting rule)
        guardrail2 = Guardrail(
            id="GR-ENC-002",
            short_description="No encryption for logs",
            severity=Severity.MEDIUM,
            action=Action.BLOCK,
            applies_to=["s3:bucket"],
            condition="Encryption not exists",
        )

        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail1, guardrail2])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=True)

        # Mock auto-fix to add encryption
        mock_auto_fix.return_value = (True, {"Encryption": {"SSEAlgorithm": "AES256"}}, "Added encryption")

        # Resource without encryption
        resource = MagicMock()
        resource.resource_type = "s3:bucket"
        resource.name = "log-bucket"
        resource.arn = "arn:aws:s3:::log-bucket"
        resource.config = {"BucketName": "log-bucket"}

        # Evaluate all resources
        report = evaluator.evaluate_all([resource], validate_fixes=True)

        # Should detect conflict
        assert len(report.fix_conflicts) == 1
        conflict = report.fix_conflicts[0]
        assert conflict.original_guardrail_id == "GR-ENC-001"
        assert conflict.conflicting_guardrail_id == "GR-ENC-002"

    def test_validate_fixes_no_conflict_when_no_fixes(self) -> None:
        """Test that validate_fixes returns empty when no fixes applied."""
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import Action, Guardrail, GuardrailPolicy, Severity

        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="Encryption check",
            severity=Severity.HIGH,
            action=Action.WARN,  # WARN, not AUTO_FIX
            applies_to=["s3:bucket"],
            condition="Encryption exists",
        )

        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=False)

        resource = MagicMock()
        resource.resource_type = "s3:bucket"
        resource.name = "my-bucket"
        resource.arn = "arn:aws:s3:::my-bucket"
        resource.config = {"BucketName": "my-bucket"}

        report = evaluator.evaluate_all([resource], validate_fixes=True)

        assert len(report.fix_conflicts) == 0

    def test_report_blocked_on_conflict(self) -> None:
        """Test that conflicts are detected when fix causes new violation."""
        from src.guardrails.evaluator import GuardrailEvaluator
        from src.guardrails.models import (
            Action,
            EvaluationResult,
            Guardrail,
            GuardrailEvaluation,
            GuardrailPolicy,
            Severity,
        )

        # Create two conflicting guardrails
        guardrail1 = Guardrail(
            id="GR-TEST-001",
            short_description="Must have X",
            severity=Severity.MEDIUM,
            action=Action.AUTO_FIX,
            applies_to=["test:resource"],
            condition="X exists",
            ai_context="Add X",
        )

        guardrail2 = Guardrail(
            id="GR-TEST-002",
            short_description="Must not have X",
            severity=Severity.MEDIUM,
            action=Action.BLOCK,
            applies_to=["test:resource"],
            condition="X not exists",
        )

        policy = GuardrailPolicy(name="test", version="1.0", guardrails=[guardrail1, guardrail2])
        evaluator = GuardrailEvaluator(policy=policy, auto_fix_enabled=True)

        resource = MagicMock()
        resource.resource_type = "test:resource"
        resource.name = "test"
        resource.arn = "arn:test:resource"
        resource.config = {}

        # Manually add a fix to simulate auto-fix happened (use ARN as resource_id)
        evaluator._auto_fixes["arn:test:resource"] = {"GR-TEST-001": {"X": True}}

        # Create original evaluation showing GR-TEST-001 was auto-fixed
        original_evaluations = [
            GuardrailEvaluation(
                guardrail_id="GR-TEST-001",
                guardrail_short_description="Must have X",
                severity=Severity.MEDIUM,
                action=Action.AUTO_FIX,
                resource_type="test:resource",
                resource_name="test",
                resource_arn="arn:test:resource",
                result=EvaluationResult.AUTO_FIXED,
            )
        ]

        conflicts = evaluator.validate_fixes([resource], original_evaluations)

        # Should detect the conflict
        assert len(conflicts) == 1
        assert conflicts[0].original_guardrail_id == "GR-TEST-001"
        assert conflicts[0].conflicting_guardrail_id == "GR-TEST-002"
