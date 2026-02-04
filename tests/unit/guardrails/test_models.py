"""Unit tests for guardrails models."""

from __future__ import annotations

from datetime import datetime, timezone


class TestSeverityEnum:
    """Tests for Severity enum (T004)."""

    def test_severity_values(self) -> None:
        from src.guardrails.models import Severity

        assert Severity.CRITICAL.value == "CRITICAL"
        assert Severity.HIGH.value == "HIGH"
        assert Severity.MEDIUM.value == "MEDIUM"
        assert Severity.LOW.value == "LOW"
        assert Severity.INFO.value == "INFO"

    def test_severity_from_string(self) -> None:
        from src.guardrails.models import Severity

        assert Severity("CRITICAL") == Severity.CRITICAL
        assert Severity("HIGH") == Severity.HIGH

    def test_severity_comparison(self) -> None:
        from src.guardrails.models import Severity

        # Severity is a str enum, so string comparison works
        assert Severity.CRITICAL == "CRITICAL"


class TestActionEnum:
    """Tests for Action enum (T005)."""

    def test_action_values(self) -> None:
        from src.guardrails.models import Action

        assert Action.BLOCK.value == "BLOCK"
        assert Action.AUTO_FIX.value == "AUTO-FIX"
        assert Action.WARN.value == "WARN"

    def test_action_from_string(self) -> None:
        from src.guardrails.models import Action

        assert Action("BLOCK") == Action.BLOCK
        assert Action("AUTO-FIX") == Action.AUTO_FIX
        assert Action("WARN") == Action.WARN


class TestEvaluationResultEnum:
    """Tests for EvaluationResult enum (T006)."""

    def test_evaluation_result_values(self) -> None:
        from src.guardrails.models import EvaluationResult

        assert EvaluationResult.PASS.value == "PASS"
        assert EvaluationResult.FAIL.value == "FAIL"
        assert EvaluationResult.AUTO_FIXED.value == "AUTO_FIXED"
        assert EvaluationResult.SKIPPED.value == "SKIPPED"


class TestConditionDataclass:
    """Tests for Condition dataclass (T007)."""

    def test_condition_creation(self) -> None:
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="ServerSideEncryptionConfiguration",
            operator="exists",
        )
        assert condition.attribute == "ServerSideEncryptionConfiguration"
        assert condition.operator == "exists"
        assert condition.value is None
        assert condition.type == "attribute_check"

    def test_condition_with_value(self) -> None:
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="StorageEncrypted",
            operator="equals",
            value=True,
        )
        assert condition.attribute == "StorageEncrypted"
        assert condition.operator == "equals"
        assert condition.value is True

    def test_condition_with_list_value(self) -> None:
        from src.guardrails.models import Condition

        condition = Condition(
            attribute="InstanceType",
            operator="in",
            value=["t3.micro", "t3.small", "t3.medium"],
        )
        assert condition.operator == "in"
        assert "t3.micro" in condition.value


class TestGuardrailDataclass:
    """Tests for Guardrail dataclass and matches_resource_type() (T008)."""

    def test_guardrail_creation(self) -> None:
        from src.guardrails.models import Action, Condition, Guardrail, Severity

        condition = Condition(attribute="StorageEncrypted", operator="equals", value=True)
        guardrail = Guardrail(
            id="GR-ENC-001",
            short_description="S3 bucket must have encryption at rest",
            severity=Severity.CRITICAL,
            action=Action.AUTO_FIX,
            applies_to=["s3:bucket"],
            condition=condition,
            ai_context="WHY: Compliance requires encryption.",
        )
        assert guardrail.id == "GR-ENC-001"
        assert guardrail.severity == Severity.CRITICAL
        assert guardrail.action == Action.AUTO_FIX
        assert guardrail.enabled is True
        assert guardrail.tags == []

    def test_matches_resource_type_exact(self) -> None:
        from src.guardrails.models import Action, Condition, Guardrail, Severity

        condition = Condition(attribute="test", operator="exists")
        guardrail = Guardrail(
            id="GR-TEST-001",
            short_description="Test guardrail",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            applies_to=["s3:bucket", "rds:db"],
            condition=condition,
        )
        assert guardrail.matches_resource_type("s3:bucket") is True
        assert guardrail.matches_resource_type("rds:db") is True
        assert guardrail.matches_resource_type("ec2:instance") is False

    def test_matches_resource_type_wildcard(self) -> None:
        from src.guardrails.models import Action, Condition, Guardrail, Severity

        condition = Condition(attribute="test", operator="exists")
        guardrail = Guardrail(
            id="GR-TAG-001",
            short_description="All resources must have tags",
            severity=Severity.HIGH,
            action=Action.WARN,
            applies_to=["*"],
            condition=condition,
        )
        assert guardrail.matches_resource_type("s3:bucket") is True
        assert guardrail.matches_resource_type("ec2:instance") is True
        assert guardrail.matches_resource_type("anything") is True

    def test_matches_resource_type_prefix_wildcard(self) -> None:
        from src.guardrails.models import Action, Condition, Guardrail, Severity

        condition = Condition(attribute="test", operator="exists")
        guardrail = Guardrail(
            id="GR-EC2-001",
            short_description="EC2 resources check",
            severity=Severity.MEDIUM,
            action=Action.WARN,
            applies_to=["ec2:*"],
            condition=condition,
        )
        assert guardrail.matches_resource_type("ec2:instance") is True
        assert guardrail.matches_resource_type("ec2:security-group") is True
        assert guardrail.matches_resource_type("s3:bucket") is False


class TestPolicyOverrideDataclass:
    """Tests for PolicyOverride dataclass (T009)."""

    def test_policy_override_creation(self) -> None:
        from src.guardrails.models import Action, PolicyOverride, Severity

        override = PolicyOverride(
            guardrail_id="GR-TAG-001",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
        )
        assert override.guardrail_id == "GR-TAG-001"
        assert override.severity == Severity.CRITICAL
        assert override.action == Action.BLOCK
        assert override.enabled is None

    def test_policy_override_disable(self) -> None:
        from src.guardrails.models import PolicyOverride

        override = PolicyOverride(
            guardrail_id="GR-TAG-001",
            enabled=False,
        )
        assert override.enabled is False
        assert override.severity is None
        assert override.action is None


class TestGuardrailPolicyDataclass:
    """Tests for GuardrailPolicy dataclass and get_guardrails_for_env() (T010)."""

    def test_policy_creation(self) -> None:
        from src.guardrails.models import GuardrailPolicy

        policy = GuardrailPolicy(
            name="production",
            version="1.0",
            description="Production policy",
        )
        assert policy.name == "production"
        assert policy.version == "1.0"
        assert policy.guardrails == []
        assert policy.overrides == {}

    def test_get_guardrails_for_env_no_overrides(self) -> None:
        from src.guardrails.models import Action, Condition, Guardrail, GuardrailPolicy, Severity

        condition = Condition(attribute="test", operator="exists")
        guardrail = Guardrail(
            id="GR-TEST-001",
            short_description="Test",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            applies_to=["*"],
            condition=condition,
        )
        policy = GuardrailPolicy(
            name="test",
            version="1.0",
            guardrails=[guardrail],
        )
        result = policy.get_guardrails_for_env("default")
        assert len(result) == 1
        assert result[0].id == "GR-TEST-001"

    def test_get_guardrails_for_env_with_severity_override(self) -> None:
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            PolicyOverride,
            Severity,
        )

        condition = Condition(attribute="test", operator="exists")
        guardrail = Guardrail(
            id="GR-TAG-001",
            short_description="Tags required",
            severity=Severity.HIGH,
            action=Action.WARN,
            applies_to=["*"],
            condition=condition,
        )
        override = PolicyOverride(
            guardrail_id="GR-TAG-001",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
        )
        policy = GuardrailPolicy(
            name="prod",
            version="1.0",
            guardrails=[guardrail],
            overrides={"production": [override]},
        )

        # Default env - no override applied
        default_result = policy.get_guardrails_for_env("default")
        assert default_result[0].severity == Severity.HIGH
        assert default_result[0].action == Action.WARN

        # Production env - override applied
        prod_result = policy.get_guardrails_for_env("production")
        assert prod_result[0].severity == Severity.CRITICAL
        assert prod_result[0].action == Action.BLOCK

    def test_get_guardrails_for_env_with_disabled_override(self) -> None:
        from src.guardrails.models import (
            Action,
            Condition,
            Guardrail,
            GuardrailPolicy,
            PolicyOverride,
            Severity,
        )

        condition = Condition(attribute="test", operator="exists")
        guardrail = Guardrail(
            id="GR-TEST-001",
            short_description="Test",
            severity=Severity.HIGH,
            action=Action.BLOCK,
            applies_to=["*"],
            condition=condition,
        )
        override = PolicyOverride(guardrail_id="GR-TEST-001", enabled=False)
        policy = GuardrailPolicy(
            name="test",
            version="1.0",
            guardrails=[guardrail],
            overrides={"development": [override]},
        )

        # Default env - guardrail included
        default_result = policy.get_guardrails_for_env("default")
        assert len(default_result) == 1

        # Development env - guardrail disabled
        dev_result = policy.get_guardrails_for_env("development")
        assert len(dev_result) == 0


class TestGuardrailEvaluationDataclass:
    """Tests for GuardrailEvaluation dataclass and is_blocking property (T011)."""

    def test_evaluation_creation(self) -> None:
        from src.guardrails.models import Action, EvaluationResult, GuardrailEvaluation, Severity

        evaluation = GuardrailEvaluation(
            guardrail_id="GR-ENC-001",
            guardrail_short_description="S3 encryption required",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            resource_type="s3:bucket",
            resource_name="my-bucket",
            resource_arn="arn:aws:s3:::my-bucket",
            result=EvaluationResult.FAIL,
            failure_reason="No encryption configured",
        )
        assert evaluation.guardrail_id == "GR-ENC-001"
        assert evaluation.result == EvaluationResult.FAIL
        assert evaluation.failure_reason == "No encryption configured"

    def test_is_blocking_true(self) -> None:
        from src.guardrails.models import Action, EvaluationResult, GuardrailEvaluation, Severity

        evaluation = GuardrailEvaluation(
            guardrail_id="GR-NET-001",
            guardrail_short_description="No SSH from 0.0.0.0/0",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            resource_type="ec2:security-group",
            resource_name="web-sg",
            resource_arn="arn:aws:ec2:...",
            result=EvaluationResult.FAIL,
        )
        assert evaluation.is_blocking is True

    def test_is_blocking_false_for_pass(self) -> None:
        from src.guardrails.models import Action, EvaluationResult, GuardrailEvaluation, Severity

        evaluation = GuardrailEvaluation(
            guardrail_id="GR-NET-001",
            guardrail_short_description="No SSH from 0.0.0.0/0",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            resource_type="ec2:security-group",
            resource_name="web-sg",
            resource_arn="arn:aws:ec2:...",
            result=EvaluationResult.PASS,
        )
        assert evaluation.is_blocking is False

    def test_is_blocking_false_for_warn_action(self) -> None:
        from src.guardrails.models import Action, EvaluationResult, GuardrailEvaluation, Severity

        evaluation = GuardrailEvaluation(
            guardrail_id="GR-TAG-001",
            guardrail_short_description="Missing tags",
            severity=Severity.CRITICAL,
            action=Action.WARN,
            resource_type="s3:bucket",
            resource_name="my-bucket",
            resource_arn="arn:aws:s3:::my-bucket",
            result=EvaluationResult.FAIL,
        )
        assert evaluation.is_blocking is False

    def test_is_blocking_false_for_low_severity(self) -> None:
        from src.guardrails.models import Action, EvaluationResult, GuardrailEvaluation, Severity

        evaluation = GuardrailEvaluation(
            guardrail_id="GR-TEST-001",
            guardrail_short_description="Test",
            severity=Severity.LOW,
            action=Action.BLOCK,
            resource_type="s3:bucket",
            resource_name="my-bucket",
            resource_arn="arn:aws:s3:::my-bucket",
            result=EvaluationResult.FAIL,
        )
        assert evaluation.is_blocking is False


class TestReportSummaryDataclass:
    """Tests for ReportSummary dataclass (T012)."""

    def test_report_summary_creation(self) -> None:
        from src.guardrails.models import ReportSummary

        summary = ReportSummary(
            total_resources=100,
            total_evaluations=500,
        )
        assert summary.total_resources == 100
        assert summary.total_evaluations == 500
        assert summary.passed == 0
        assert summary.failed == 0
        assert summary.auto_fixed == 0
        assert summary.warnings == 0
        assert summary.skipped == 0
        assert summary.by_severity == {}
        assert summary.by_category == {}

    def test_report_summary_with_counts(self) -> None:
        from src.guardrails.models import ReportSummary

        summary = ReportSummary(
            total_resources=100,
            total_evaluations=500,
            passed=450,
            failed=30,
            auto_fixed=15,
            warnings=5,
            skipped=0,
            by_severity={"CRITICAL": 20, "HIGH": 10},
            by_category={"ENC": 15, "NET": 10, "TAG": 5},
        )
        assert summary.passed == 450
        assert summary.by_severity["CRITICAL"] == 20


class TestGuardrailReportDataclass:
    """Tests for GuardrailReport dataclass (add_evaluation, get_blocking_violations, to_dict) (T013)."""

    def test_report_creation(self) -> None:
        from src.guardrails.models import GuardrailReport

        report = GuardrailReport(
            run_id="gr-20260204-143052-a1b2c3",
            policy_name="production",
            policy_version="1.0",
            snapshot_name="my-snapshot",
            started_at=datetime(2026, 2, 4, 14, 30, 52, tzinfo=timezone.utc),
        )
        assert report.run_id == "gr-20260204-143052-a1b2c3"
        assert report.blocked is False
        assert report.evaluations == []

    def test_add_evaluation(self) -> None:
        from src.guardrails.models import (
            Action,
            EvaluationResult,
            GuardrailEvaluation,
            GuardrailReport,
            Severity,
        )

        report = GuardrailReport(
            run_id="test-run",
            policy_name="test",
            policy_version="1.0",
            snapshot_name="test-snapshot",
            started_at=datetime.now(timezone.utc),
        )

        evaluation = GuardrailEvaluation(
            guardrail_id="GR-ENC-001",
            guardrail_short_description="S3 encryption",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            resource_type="s3:bucket",
            resource_name="my-bucket",
            resource_arn="arn:aws:s3:::my-bucket",
            result=EvaluationResult.PASS,
        )

        report.add_evaluation(evaluation)

        assert len(report.evaluations) == 1
        assert report.summary.total_evaluations == 1
        assert report.summary.passed == 1
        assert report.summary.by_severity.get("CRITICAL", 0) == 1
        assert report.summary.by_category.get("ENC", 0) == 1

    def test_add_evaluation_fail(self) -> None:
        from src.guardrails.models import (
            Action,
            EvaluationResult,
            GuardrailEvaluation,
            GuardrailReport,
            Severity,
        )

        report = GuardrailReport(
            run_id="test-run",
            policy_name="test",
            policy_version="1.0",
            snapshot_name="test-snapshot",
            started_at=datetime.now(timezone.utc),
        )

        evaluation = GuardrailEvaluation(
            guardrail_id="GR-NET-001",
            guardrail_short_description="No SSH",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            resource_type="ec2:security-group",
            resource_name="web-sg",
            resource_arn="arn:...",
            result=EvaluationResult.FAIL,
        )

        report.add_evaluation(evaluation)

        assert report.summary.failed == 1

    def test_get_blocking_violations(self) -> None:
        from src.guardrails.models import (
            Action,
            EvaluationResult,
            GuardrailEvaluation,
            GuardrailReport,
            Severity,
        )

        report = GuardrailReport(
            run_id="test-run",
            policy_name="test",
            policy_version="1.0",
            snapshot_name="test-snapshot",
            started_at=datetime.now(timezone.utc),
        )

        # Blocking violation
        blocking_eval = GuardrailEvaluation(
            guardrail_id="GR-NET-001",
            guardrail_short_description="No SSH",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            resource_type="ec2:security-group",
            resource_name="web-sg",
            resource_arn="arn:...",
            result=EvaluationResult.FAIL,
        )

        # Non-blocking violation (WARN action)
        warn_eval = GuardrailEvaluation(
            guardrail_id="GR-TAG-001",
            guardrail_short_description="Missing tags",
            severity=Severity.HIGH,
            action=Action.WARN,
            resource_type="s3:bucket",
            resource_name="my-bucket",
            resource_arn="arn:...",
            result=EvaluationResult.FAIL,
        )

        # Passing evaluation
        pass_eval = GuardrailEvaluation(
            guardrail_id="GR-ENC-001",
            guardrail_short_description="S3 encryption",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            resource_type="s3:bucket",
            resource_name="my-bucket",
            resource_arn="arn:...",
            result=EvaluationResult.PASS,
        )

        report.add_evaluation(blocking_eval)
        report.add_evaluation(warn_eval)
        report.add_evaluation(pass_eval)

        blocking = report.get_blocking_violations()
        assert len(blocking) == 1
        assert blocking[0].guardrail_id == "GR-NET-001"

    def test_to_dict(self) -> None:
        from src.guardrails.models import (
            Action,
            EvaluationResult,
            GuardrailEvaluation,
            GuardrailReport,
            Severity,
        )

        started = datetime(2026, 2, 4, 14, 30, 52, tzinfo=timezone.utc)
        completed = datetime(2026, 2, 4, 14, 31, 5, tzinfo=timezone.utc)

        report = GuardrailReport(
            run_id="test-run",
            policy_name="production",
            policy_version="1.0",
            snapshot_name="my-snapshot",
            started_at=started,
            completed_at=completed,
            blocked=True,
            block_reason="Critical violations found",
        )

        evaluation = GuardrailEvaluation(
            guardrail_id="GR-ENC-001",
            guardrail_short_description="S3 encryption",
            severity=Severity.CRITICAL,
            action=Action.BLOCK,
            resource_type="s3:bucket",
            resource_name="my-bucket",
            resource_arn="arn:aws:s3:::my-bucket",
            result=EvaluationResult.FAIL,
            failure_reason="No encryption",
        )
        report.add_evaluation(evaluation)

        result = report.to_dict()

        assert result["run_id"] == "test-run"
        assert result["policy_name"] == "production"
        assert result["blocked"] is True
        assert result["started_at"] == "2026-02-04T14:30:52+00:00"
        assert result["completed_at"] == "2026-02-04T14:31:05+00:00"
        assert result["summary"]["total_evaluations"] == 1
        assert len(result["evaluations"]) == 1
        assert result["evaluations"][0]["guardrail_id"] == "GR-ENC-001"


class TestGuardrailExceptions:
    """Tests for GuardrailError exception hierarchy (T014)."""

    def test_guardrail_error(self) -> None:
        from src.guardrails.models import GuardrailError

        error = GuardrailError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert isinstance(error, Exception)

    def test_guardrail_validation_error(self) -> None:
        from src.guardrails.models import GuardrailValidationError

        errors = ["id is required", "severity must be valid"]
        error = GuardrailValidationError(errors)
        assert error.errors == errors
        assert "id is required" in str(error)
        assert "severity must be valid" in str(error)

    def test_guardrail_load_error(self) -> None:
        from src.guardrails.models import GuardrailLoadError

        error = GuardrailLoadError("File not found: policy.yaml")
        assert "File not found" in str(error)

    def test_guardrail_evaluation_error(self) -> None:
        from src.guardrails.models import GuardrailEvaluationError

        error = GuardrailEvaluationError("Failed to evaluate condition")
        assert "Failed to evaluate" in str(error)

    def test_auto_fix_error(self) -> None:
        from src.guardrails.models import AutoFixError

        error = AutoFixError("Bedrock call failed")
        assert "Bedrock call failed" in str(error)

    def test_exception_hierarchy(self) -> None:
        from src.guardrails.models import (
            AutoFixError,
            GuardrailError,
            GuardrailEvaluationError,
            GuardrailLoadError,
            GuardrailValidationError,
        )

        # All should inherit from GuardrailError
        assert issubclass(GuardrailValidationError, GuardrailError)
        assert issubclass(GuardrailLoadError, GuardrailError)
        assert issubclass(GuardrailEvaluationError, GuardrailError)
        assert issubclass(AutoFixError, GuardrailError)

        # GuardrailError should inherit from Exception
        assert issubclass(GuardrailError, Exception)
