"""Unit tests for generation progress display."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from src.cli.generation_progress import (
    ComparisonResult,
    GenerationProgressDisplay,
    GuardrailsResult,
    LayerStatus,
    TrackedLayer,
    TrackedStep,
    WorkflowStep,
)


class TestLayerStatus:
    """Tests for LayerStatus enum."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert LayerStatus.PENDING.value == "pending"
        assert LayerStatus.GENERATING.value == "generating"
        assert LayerStatus.COMPLETED.value == "completed"
        assert LayerStatus.FAILED.value == "failed"

    def test_all_statuses_count(self):
        """Test that there are exactly 4 statuses."""
        assert len(LayerStatus) == 4


class TestWorkflowStep:
    """Tests for WorkflowStep enum."""

    def test_step_values(self):
        """Test that all expected workflow step values exist."""
        assert WorkflowStep.PARSE_INVENTORY.value == "parse_inventory"
        assert WorkflowStep.BUILD_RESOURCE_MAP.value == "build_resource_map"
        assert WorkflowStep.EVALUATE_GUARDRAILS.value == "evaluate_guardrails"
        assert WorkflowStep.CATEGORIZE_LAYERS.value == "categorize_layers"
        assert WorkflowStep.EXTRACT_LAMBDA.value == "extract_lambda"
        assert WorkflowStep.GENERATE_LAYERS.value == "generate_layers"
        assert WorkflowStep.COMPARE_INVENTORY.value == "compare_inventory"
        assert WorkflowStep.TERRAFORM_INIT.value == "terraform_init"
        assert WorkflowStep.TERRAFORM_VALIDATE.value == "terraform_validate"
        assert WorkflowStep.COMPLETE.value == "complete"

    def test_all_steps_count(self):
        """Test that there are exactly 10 workflow steps."""
        assert len(WorkflowStep) == 10


class TestTrackedLayer:
    """Tests for TrackedLayer dataclass."""

    def test_default_values(self):
        """Test default values for TrackedLayer."""
        layer = TrackedLayer(name="Network Foundation", order=0, resource_count=5)

        assert layer.name == "Network Foundation"
        assert layer.order == 0
        assert layer.resource_count == 5
        assert layer.status == LayerStatus.PENDING
        assert layer.generated_file is None
        assert layer.error is None
        assert layer.start_time is None
        assert layer.end_time is None

    def test_with_all_fields(self):
        """Test TrackedLayer with all fields set."""
        layer = TrackedLayer(
            name="Compute",
            order=3,
            resource_count=10,
            status=LayerStatus.COMPLETED,
            generated_file="output/compute.tf",
            error=None,
            start_time=1000.0,
            end_time=1005.0,
        )

        assert layer.status == LayerStatus.COMPLETED
        assert layer.generated_file == "output/compute.tf"
        assert layer.end_time - layer.start_time == 5.0

    def test_with_error(self):
        """Test TrackedLayer with error set."""
        layer = TrackedLayer(
            name="Database",
            order=2,
            resource_count=3,
            status=LayerStatus.FAILED,
            error="Model invocation error",
        )

        assert layer.status == LayerStatus.FAILED
        assert layer.error == "Model invocation error"


class TestTrackedStep:
    """Tests for TrackedStep dataclass."""

    def test_default_values(self):
        """Test default values for TrackedStep."""
        step = TrackedStep(step=WorkflowStep.PARSE_INVENTORY)

        assert step.step == WorkflowStep.PARSE_INVENTORY
        assert step.status == "pending"
        assert step.start_time is None
        assert step.end_time is None
        assert step.details == ""

    def test_with_all_fields(self):
        """Test TrackedStep with all fields set."""
        step = TrackedStep(
            step=WorkflowStep.GENERATE_LAYERS,
            status="running",
            start_time=1000.0,
            end_time=None,
            details="Generating layer 2/5",
        )

        assert step.status == "running"
        assert step.details == "Generating layer 2/5"
        assert step.end_time is None


class TestComparisonResult:
    """Tests for ComparisonResult dataclass."""

    def test_default_values(self):
        """Test default values for ComparisonResult."""
        result = ComparisonResult()

        assert result.coverage_percentage == 0.0
        assert result.total_resources == 0
        assert result.represented_count == 0
        assert result.missing_count == 0
        assert result.issues_count == 0
        assert result.summary == ""

    def test_with_values(self):
        """Test ComparisonResult with all fields set."""
        result = ComparisonResult(
            coverage_percentage=85.5,
            total_resources=20,
            represented_count=17,
            missing_count=3,
            issues_count=2,
            summary="3 resources missing coverage",
        )

        assert result.coverage_percentage == 85.5
        assert result.total_resources == 20
        assert result.represented_count == 17
        assert result.missing_count == 3
        assert result.issues_count == 2
        assert result.summary == "3 resources missing coverage"


class TestGuardrailsResult:
    """Tests for GuardrailsResult dataclass."""

    def test_default_values(self):
        """Test default values for GuardrailsResult."""
        result = GuardrailsResult()

        assert result.total_evaluations == 0
        assert result.passed == 0
        assert result.failed == 0
        assert result.auto_fixed == 0
        assert result.warnings == 0
        assert result.blocked is False
        assert result.block_reason == ""
        assert result.current_guardrail == ""
        assert result.current_resource == ""

    def test_with_values(self):
        """Test GuardrailsResult with all fields set."""
        result = GuardrailsResult(
            total_evaluations=50,
            passed=40,
            failed=3,
            auto_fixed=5,
            warnings=2,
            blocked=True,
            block_reason="Critical violation: unencrypted S3",
            current_guardrail="encryption-at-rest",
            current_resource="aws_s3_bucket.data",
        )

        assert result.total_evaluations == 50
        assert result.passed == 40
        assert result.failed == 3
        assert result.auto_fixed == 5
        assert result.warnings == 2
        assert result.blocked is True
        assert result.block_reason == "Critical violation: unencrypted S3"


class TestGenerationProgressDisplay:
    """Tests for GenerationProgressDisplay class."""

    def _make_display(self) -> GenerationProgressDisplay:
        """Create a GenerationProgressDisplay with a mock console."""
        console = MagicMock()
        return GenerationProgressDisplay(console=console)

    def test_init_default_state(self):
        """Test that __init__ sets correct default state."""
        display = self._make_display()

        assert display.layers == {}
        assert display.layer_order == []
        assert display.current_step == WorkflowStep.PARSE_INVENTORY
        assert display.total_resources == 0
        assert display.source_name == ""
        assert display.output_dir == ""
        assert display.output_format == "terraform"
        assert display.comparison is None
        assert display.validation_errors == []
        assert display.live is None
        assert display.start_time == 0.0
        assert display.generated_files == []
        assert display.current_activity == ""
        assert display.resource_types_found == {}
        assert display.lambda_functions_extracted == 0
        assert display.guardrails is None
        assert display.guardrails_enabled is False
        assert display.best_practices_mode is False

    def test_init_creates_steps_for_all_except_complete(self):
        """Test that all workflow steps except COMPLETE are initialized."""
        display = self._make_display()

        for step in WorkflowStep:
            if step == WorkflowStep.COMPLETE:
                assert step not in display.steps
            else:
                assert step in display.steps
                assert display.steps[step].status == "pending"

    def test_set_source(self):
        """Test setting source name and output directory."""
        display = self._make_display()
        display.set_source("my-snapshot", "/tmp/output")

        assert display.source_name == "my-snapshot"
        assert display.output_dir == "/tmp/output"

    def test_set_output_format(self):
        """Test setting output format."""
        display = self._make_display()
        display.set_output_format("cdk-typescript")

        assert display.output_format == "cdk-typescript"

    def test_set_layers(self):
        """Test setting layers to be generated."""
        display = self._make_display()
        layers = {
            "Network Foundation": [{"id": "vpc-1"}, {"id": "subnet-1"}],
            "Compute": [{"id": "i-1"}],
            "Storage": [{"id": "bucket-1"}, {"id": "bucket-2"}, {"id": "bucket-3"}],
        }
        layer_order = ["Network Foundation", "Compute", "Storage"]
        display.set_layers(layers, layer_order)

        assert len(display.layers) == 3
        assert display.layer_order == layer_order
        assert display.total_resources == 6
        assert display.layers["Network Foundation"].resource_count == 2
        assert display.layers["Network Foundation"].order == 0
        assert display.layers["Compute"].resource_count == 1
        assert display.layers["Compute"].order == 1
        assert display.layers["Storage"].resource_count == 3
        assert display.layers["Storage"].order == 2

    def test_set_layers_all_start_pending(self):
        """Test that all layers start in PENDING status."""
        display = self._make_display()
        layers = {"Network Foundation": [{"id": "1"}], "Compute": [{"id": "2"}]}
        display.set_layers(layers, ["Network Foundation", "Compute"])

        for layer in display.layers.values():
            assert layer.status == LayerStatus.PENDING

    def test_set_total_resources(self):
        """Test setting total resource count."""
        display = self._make_display()
        display.set_total_resources(42)

        assert display.total_resources == 42

    def test_set_resource_types(self):
        """Test setting resource types breakdown."""
        display = self._make_display()
        types = {"AWS::EC2::Instance": 5, "AWS::S3::Bucket": 3}
        display.set_resource_types(types)

        assert display.resource_types_found == types

    def test_set_lambda_count(self):
        """Test setting lambda function count."""
        display = self._make_display()
        display.set_lambda_count(7)

        assert display.lambda_functions_extracted == 7

    def test_set_activity(self):
        """Test setting current activity."""
        display = self._make_display()
        display.set_activity("Parsing resources...")

        assert display.current_activity == "Parsing resources..."
        assert "Parsing resources..." in display.activity_history

    def test_set_activity_history_limit(self):
        """Test that activity history respects max_activity_history."""
        display = self._make_display()
        display.max_activity_history = 3

        display.set_activity("Activity 1")
        display.set_activity("Activity 2")
        display.set_activity("Activity 3")
        display.set_activity("Activity 4")

        assert len(display.activity_history) == 3
        assert display.activity_history[0] == "Activity 2"
        assert display.activity_history[2] == "Activity 4"

    def test_set_activity_empty_string_not_added_to_history(self):
        """Test that empty activity is not added to history."""
        display = self._make_display()
        display.set_activity("")

        assert display.current_activity == ""
        assert len(display.activity_history) == 0

    def test_start_step(self):
        """Test starting a workflow step."""
        display = self._make_display()
        display.start_step(WorkflowStep.BUILD_RESOURCE_MAP)

        assert display.current_step == WorkflowStep.BUILD_RESOURCE_MAP
        assert display.steps[WorkflowStep.BUILD_RESOURCE_MAP].status == "running"
        assert display.steps[WorkflowStep.BUILD_RESOURCE_MAP].start_time is not None

    def test_complete_step(self):
        """Test completing a workflow step."""
        display = self._make_display()
        display.start_step(WorkflowStep.PARSE_INVENTORY)
        display.complete_step(WorkflowStep.PARSE_INVENTORY)

        step = display.steps[WorkflowStep.PARSE_INVENTORY]
        assert step.status == "completed"
        assert step.end_time is not None
        assert step.end_time >= step.start_time

    def test_fail_step(self):
        """Test failing a workflow step."""
        display = self._make_display()
        display.start_step(WorkflowStep.TERRAFORM_VALIDATE)
        display.fail_step(WorkflowStep.TERRAFORM_VALIDATE, error="Syntax error in main.tf")

        step = display.steps[WorkflowStep.TERRAFORM_VALIDATE]
        assert step.status == "failed"
        assert step.end_time is not None
        assert step.details == "Syntax error in main.tf"

    def test_fail_step_no_error_message(self):
        """Test failing a step without an error message."""
        display = self._make_display()
        display.start_step(WorkflowStep.TERRAFORM_INIT)
        display.fail_step(WorkflowStep.TERRAFORM_INIT)

        step = display.steps[WorkflowStep.TERRAFORM_INIT]
        assert step.status == "failed"
        assert step.details == ""

    def test_start_layer(self):
        """Test starting a layer generation."""
        display = self._make_display()
        layers = {"Network Foundation": [{"id": "1"}]}
        display.set_layers(layers, ["Network Foundation"])

        display.start_layer("Network Foundation")

        layer = display.layers["Network Foundation"]
        assert layer.status == LayerStatus.GENERATING
        assert layer.start_time is not None
        assert display.current_activity == "Generating Network Foundation layer..."

    def test_start_layer_unknown_name_no_crash(self):
        """Test that starting an unknown layer does not crash."""
        display = self._make_display()
        display.start_layer("NonExistent")

    def test_complete_layer(self):
        """Test completing a layer."""
        display = self._make_display()
        layers = {"Compute": [{"id": "1"}]}
        display.set_layers(layers, ["Compute"])

        display.start_layer("Compute")
        display.complete_layer("Compute", generated_file="output/compute.tf")

        layer = display.layers["Compute"]
        assert layer.status == LayerStatus.COMPLETED
        assert layer.generated_file == "output/compute.tf"
        assert layer.end_time is not None
        assert "output/compute.tf" in display.generated_files

    def test_complete_layer_without_file(self):
        """Test completing a layer without specifying a generated file."""
        display = self._make_display()
        layers = {"IAM": [{"id": "1"}]}
        display.set_layers(layers, ["IAM"])

        display.start_layer("IAM")
        display.complete_layer("IAM")

        layer = display.layers["IAM"]
        assert layer.status == LayerStatus.COMPLETED
        assert layer.generated_file is None
        assert len(display.generated_files) == 0

    def test_complete_layer_unknown_name_no_crash(self):
        """Test that completing an unknown layer does not crash."""
        display = self._make_display()
        display.complete_layer("NonExistent", generated_file="file.tf")

    def test_fail_layer(self):
        """Test failing a layer."""
        display = self._make_display()
        layers = {"Database": [{"id": "1"}]}
        display.set_layers(layers, ["Database"])

        display.start_layer("Database")
        display.fail_layer("Database", error="Bedrock throttling error")

        layer = display.layers["Database"]
        assert layer.status == LayerStatus.FAILED
        assert layer.error == "Bedrock throttling error"
        assert layer.end_time is not None

    def test_fail_layer_unknown_name_no_crash(self):
        """Test that failing an unknown layer does not crash."""
        display = self._make_display()
        display.fail_layer("NonExistent", error="some error")

    def test_set_comparison_result(self):
        """Test setting comparison result from dict."""
        display = self._make_display()
        result_dict = {
            "coverage_percentage": 92.5,
            "total_resources": 40,
            "represented_count": 37,
            "missing_count": 3,
            "issues": [{"type": "missing", "resource": "x"}, {"type": "drift", "resource": "y"}],
            "summary": "Good coverage overall",
        }
        display.set_comparison_result(result_dict)

        assert display.comparison is not None
        assert display.comparison.coverage_percentage == 92.5
        assert display.comparison.total_resources == 40
        assert display.comparison.represented_count == 37
        assert display.comparison.missing_count == 3
        assert display.comparison.issues_count == 2
        assert display.comparison.summary == "Good coverage overall"

    def test_set_comparison_result_empty_dict(self):
        """Test setting comparison result from empty dict uses defaults."""
        display = self._make_display()
        display.set_comparison_result({})

        assert display.comparison is not None
        assert display.comparison.coverage_percentage == 0.0
        assert display.comparison.total_resources == 0
        assert display.comparison.issues_count == 0

    def test_set_validation_errors(self):
        """Test setting validation errors."""
        display = self._make_display()
        errors = ["Warning: deprecated attribute", "Warning: missing provider"]
        display.set_validation_errors(errors)

        assert display.validation_errors == errors
        assert len(display.validation_errors) == 2

    def test_enable_guardrails(self):
        """Test enabling guardrails tracking."""
        display = self._make_display()
        display.enable_guardrails()

        assert display.guardrails_enabled is True
        assert display.best_practices_mode is False
        assert display.guardrails is not None
        assert isinstance(display.guardrails, GuardrailsResult)

    def test_enable_guardrails_best_practices_mode(self):
        """Test enabling guardrails in best practices mode."""
        display = self._make_display()
        display.enable_guardrails(best_practices_mode=True)

        assert display.guardrails_enabled is True
        assert display.best_practices_mode is True
        assert display.guardrails is not None

    def test_update_guardrails_progress(self):
        """Test updating guardrails evaluation progress."""
        display = self._make_display()
        display.enable_guardrails()

        display.update_guardrails_progress(
            current_guardrail="encryption-at-rest",
            current_resource="aws_s3_bucket.data",
            passed=10,
            failed=1,
            auto_fixed=2,
            warnings=3,
            total=16,
        )

        gr = display.guardrails
        assert gr.current_guardrail == "encryption-at-rest"
        assert gr.current_resource == "aws_s3_bucket.data"
        assert gr.passed == 10
        assert gr.failed == 1
        assert gr.auto_fixed == 2
        assert gr.warnings == 3
        assert gr.total_evaluations == 16

    def test_update_guardrails_progress_without_enable_no_crash(self):
        """Test that updating guardrails progress without enabling does not crash."""
        display = self._make_display()
        display.update_guardrails_progress(passed=5, total=5)

    def test_set_guardrails_result(self):
        """Test setting final guardrails result."""
        display = self._make_display()
        display.enable_guardrails()
        display.update_guardrails_progress(
            current_guardrail="check-x",
            current_resource="res-y",
        )

        display.set_guardrails_result(
            passed=15,
            failed=2,
            auto_fixed=3,
            warnings=1,
            blocked=True,
            block_reason="Encryption violations found",
        )

        gr = display.guardrails
        assert gr.passed == 15
        assert gr.failed == 2
        assert gr.auto_fixed == 3
        assert gr.warnings == 1
        assert gr.blocked is True
        assert gr.block_reason == "Encryption violations found"
        assert gr.current_guardrail == ""
        assert gr.current_resource == ""

    def test_set_guardrails_result_not_blocked(self):
        """Test setting guardrails result without blocking."""
        display = self._make_display()
        display.enable_guardrails()

        display.set_guardrails_result(
            passed=20,
            failed=0,
            auto_fixed=5,
            warnings=2,
        )

        gr = display.guardrails
        assert gr.blocked is False
        assert gr.block_reason == ""

    def test_set_guardrails_result_without_enable_no_crash(self):
        """Test that setting guardrails result without enabling does not crash."""
        display = self._make_display()
        display.set_guardrails_result(passed=5, failed=0, auto_fixed=0, warnings=0)

    def test_start_and_stop_lifecycle(self):
        """Test start/stop lifecycle with mocked Live."""
        display = self._make_display()
        display.set_source("snapshot", "/output")

        with patch("src.cli.generation_progress.Live") as MockLive:
            mock_live_instance = MagicMock()
            MockLive.return_value = mock_live_instance

            display.start()

            assert display.start_time > 0
            assert display.live is not None
            MockLive.assert_called_once()
            mock_live_instance.start.assert_called_once()

            display.stop()

            mock_live_instance.stop.assert_called_once()
            assert display.live is None

    def test_stop_when_not_started(self):
        """Test that stop does nothing when live is not started."""
        display = self._make_display()
        display.stop()
        assert display.live is None

    def test_refresh_updates_live(self):
        """Test that _refresh calls live.update when live is active."""
        display = self._make_display()

        with patch("src.cli.generation_progress.Live") as MockLive:
            mock_live_instance = MagicMock()
            MockLive.return_value = mock_live_instance

            display.start()
            display.set_total_resources(10)

            assert mock_live_instance.update.call_count >= 1

    def test_refresh_no_op_when_live_is_none(self):
        """Test that _refresh does not crash when live is None."""
        display = self._make_display()
        display._refresh()

    def test_build_display_returns_renderable(self):
        """Test that _build_display produces a renderable without errors."""
        display = self._make_display()
        display.set_source("test-snapshot", "/tmp/output")
        display.start_time = time.time() - 5.0

        result = display._build_display()
        assert result is not None

    def test_build_display_with_layers_during_generation(self):
        """Test _build_display when layers are being generated."""
        display = self._make_display()
        display.set_source("snap", "/out")
        display.start_time = time.time()

        layers = {
            "Network Foundation": [{"id": "1"}],
            "Compute": [{"id": "2"}, {"id": "3"}],
        }
        display.set_layers(layers, ["Network Foundation", "Compute"])
        display.current_step = WorkflowStep.GENERATE_LAYERS
        display.start_layer("Network Foundation")
        display.complete_layer("Network Foundation", generated_file="net.tf")
        display.start_layer("Compute")

        result = display._build_display()
        assert result is not None

    def test_build_display_with_guardrails(self):
        """Test _build_display when guardrails are enabled and evaluating."""
        display = self._make_display()
        display.set_source("snap", "/out")
        display.start_time = time.time()
        display.enable_guardrails()
        display.current_step = WorkflowStep.EVALUATE_GUARDRAILS
        display.update_guardrails_progress(
            current_guardrail="encryption",
            current_resource="aws_s3_bucket.x",
            passed=3,
            failed=1,
            auto_fixed=1,
            warnings=2,
            total=7,
        )

        result = display._build_display()
        assert result is not None

    def test_build_display_with_comparison(self):
        """Test _build_display when comparison result is set."""
        display = self._make_display()
        display.set_source("snap", "/out")
        display.start_time = time.time()
        display.current_step = WorkflowStep.COMPARE_INVENTORY
        display.set_comparison_result({
            "coverage_percentage": 95.0,
            "total_resources": 20,
            "represented_count": 19,
            "missing_count": 1,
            "issues": [{"type": "missing"}],
            "summary": "Almost full coverage",
        })

        result = display._build_display()
        assert result is not None

    def test_build_display_with_validation_errors(self):
        """Test _build_display when validation errors are present."""
        display = self._make_display()
        display.set_source("snap", "/out")
        display.start_time = time.time()
        display.steps[WorkflowStep.TERRAFORM_VALIDATE].status = "completed"
        display.steps[WorkflowStep.TERRAFORM_VALIDATE].end_time = time.time()
        display.set_validation_errors(["warning1", "warning2"])

        result = display._build_display()
        assert result is not None

    def test_get_layer_icon_known(self):
        """Test _get_layer_icon returns correct icon for known layers."""
        display = self._make_display()

        assert display._get_layer_icon("Network Foundation") == "\U0001f310"
        assert display._get_layer_icon("Security Groups") == "\U0001f6e1\ufe0f"
        assert display._get_layer_icon("IAM") == "\U0001f511"
        assert display._get_layer_icon("Storage") == "\U0001f4be"
        assert display._get_layer_icon("Compute") == "\U0001f4bb"
        assert display._get_layer_icon("Serverless") == "\u03bb"

    def test_get_layer_icon_unknown_returns_other(self):
        """Test _get_layer_icon returns 'Other' icon for unknown layers."""
        display = self._make_display()

        assert display._get_layer_icon("CustomLayer") == "\U0001f4e6"

    def test_get_layer_icon_case_insensitive(self):
        """Test _get_layer_icon matching is case insensitive."""
        display = self._make_display()

        assert display._get_layer_icon("network foundation") == "\U0001f310"
        assert display._get_layer_icon("COMPUTE") == "\U0001f4bb"

    def test_format_duration_sub_second(self):
        """Test _format_duration for sub-second durations."""
        display = self._make_display()
        assert display._format_duration(0.5) == "<1s"

    def test_format_duration_seconds(self):
        """Test _format_duration for second-range durations."""
        display = self._make_display()
        assert display._format_duration(30.0) == "30s"

    def test_format_duration_minutes(self):
        """Test _format_duration for minute-range durations."""
        display = self._make_display()
        assert display._format_duration(125.0) == "2m 5s"

    def test_get_format_display_name_terraform(self):
        """Test display name for terraform format."""
        display = self._make_display()
        display.output_format = "terraform"
        assert display._get_format_display_name() == "Terraform"

    def test_get_format_display_name_cdk_typescript(self):
        """Test display name for CDK TypeScript format."""
        display = self._make_display()
        display.output_format = "cdk-typescript"
        assert display._get_format_display_name() == "CDK TypeScript"

    def test_get_format_display_name_cdk_python(self):
        """Test display name for CDK Python format."""
        display = self._make_display()
        display.output_format = "cdk-python"
        assert display._get_format_display_name() == "CDK Python"

    def test_is_cdk_format(self):
        """Test _is_cdk_format for CDK and non-CDK formats."""
        display = self._make_display()

        display.output_format = "terraform"
        assert display._is_cdk_format() is False

        display.output_format = "cdk-typescript"
        assert display._is_cdk_format() is True

        display.output_format = "cdk-python"
        assert display._is_cdk_format() is True

    def test_get_step_config_terraform_overrides(self):
        """Test _get_step_config returns terraform-specific config."""
        display = self._make_display()
        display.output_format = "terraform"

        config = display._get_step_config(WorkflowStep.GENERATE_LAYERS)
        assert config["name"] == "Generate Terraform"
        assert "HCL" in config["description"]

        config = display._get_step_config(WorkflowStep.TERRAFORM_INIT)
        assert config["name"] == "Terraform Init"

        config = display._get_step_config(WorkflowStep.TERRAFORM_VALIDATE)
        assert config["name"] == "Terraform Validate"

    def test_get_step_config_cdk_overrides(self):
        """Test _get_step_config returns CDK-specific config."""
        display = self._make_display()
        display.output_format = "cdk-typescript"

        config = display._get_step_config(WorkflowStep.GENERATE_LAYERS)
        assert config["name"] == "Generate CDK"
        assert "CDK" in config["description"]

        config = display._get_step_config(WorkflowStep.TERRAFORM_INIT)
        assert config["name"] == "NPM Build"

        config = display._get_step_config(WorkflowStep.TERRAFORM_VALIDATE)
        assert config["name"] == "CDK Synth"

    def test_get_step_config_best_practices_mode(self):
        """Test _get_step_config overrides guardrails name in best-practices mode."""
        display = self._make_display()
        display.best_practices_mode = True

        config = display._get_step_config(WorkflowStep.EVALUATE_GUARDRAILS)
        assert config["name"] == "Best Practices"
        assert config["description"] == "Advisory best-practice checks"

    def test_get_step_config_guardrails_without_best_practices(self):
        """Test _get_step_config keeps default guardrails name when not best-practices mode."""
        display = self._make_display()
        display.best_practices_mode = False

        config = display._get_step_config(WorkflowStep.EVALUATE_GUARDRAILS)
        assert config["name"] == "Evaluate Guardrails"

    def test_step_config_base_covers_all_steps(self):
        """Test that STEP_CONFIG_BASE has entries for all WorkflowStep values."""
        for step in WorkflowStep:
            assert step in GenerationProgressDisplay.STEP_CONFIG_BASE

    def test_step_config_base_has_required_keys(self):
        """Test that each step config has name, icon, and description."""
        for step, config in GenerationProgressDisplay.STEP_CONFIG_BASE.items():
            assert "name" in config, f"Missing 'name' for {step}"
            assert "icon" in config, f"Missing 'icon' for {step}"
            assert "description" in config, f"Missing 'description' for {step}"

    def test_layer_icons_has_other(self):
        """Test that LAYER_ICONS has an 'Other' fallback."""
        assert "Other" in GenerationProgressDisplay.LAYER_ICONS

    def test_print_final_summary_success(self):
        """Test print_final_summary with success."""
        console = MagicMock()
        display = GenerationProgressDisplay(console=console)
        display.set_source("snap", "/out")
        display.start_time = time.time() - 10.0
        display.generated_files = ["net.tf", "compute.tf"]
        display.total_resources = 15

        layers = {"Network": [{"id": "1"}], "Compute": [{"id": "2"}]}
        display.set_layers(layers, ["Network", "Compute"])
        display.complete_layer("Network", "net.tf")
        display.complete_layer("Compute", "compute.tf")

        display.print_final_summary(success=True)

        assert console.print.call_count > 0

    def test_print_final_summary_failure(self):
        """Test print_final_summary with failure."""
        console = MagicMock()
        display = GenerationProgressDisplay(console=console)
        display.start_time = time.time() - 5.0

        display.print_final_summary(success=False)

        calls = [str(c) for c in console.print.call_args_list]
        found_fail = any("failed" in c.lower() for c in calls)
        assert found_fail

    def test_print_final_summary_with_comparison(self):
        """Test print_final_summary includes comparison data."""
        console = MagicMock()
        display = GenerationProgressDisplay(console=console)
        display.start_time = time.time()
        display.set_comparison_result({
            "coverage_percentage": 75.0,
            "total_resources": 20,
            "represented_count": 15,
            "missing_count": 5,
            "issues": [],
            "summary": "",
        })

        display.print_final_summary(success=True)
        assert console.print.call_count > 0

    def test_print_final_summary_with_guardrails_blocked(self):
        """Test print_final_summary shows blocked guardrails info."""
        console = MagicMock()
        display = GenerationProgressDisplay(console=console)
        display.start_time = time.time()
        display.enable_guardrails()
        display.set_guardrails_result(
            passed=5, failed=3, auto_fixed=0, warnings=0, blocked=True, block_reason="Violations"
        )

        display.print_final_summary(success=False)
        assert console.print.call_count > 0

    def test_print_final_summary_with_validation_errors(self):
        """Test print_final_summary shows validation warnings."""
        console = MagicMock()
        display = GenerationProgressDisplay(console=console)
        display.start_time = time.time()
        display.set_validation_errors(["warn1", "warn2", "warn3", "warn4", "warn5", "warn6"])

        display.print_final_summary(success=True)

        calls_text = " ".join(str(c) for c in console.print.call_args_list)
        assert "validation" in calls_text.lower() or "warning" in calls_text.lower()

    def test_full_workflow_lifecycle(self):
        """Integration test: simulate a complete generation workflow."""
        display = self._make_display()
        display.set_source("prod-snapshot", "/tmp/iac-output")
        display.set_output_format("terraform")

        with patch("src.cli.generation_progress.Live") as MockLive:
            mock_live_instance = MagicMock()
            MockLive.return_value = mock_live_instance

            display.start()

            display.start_step(WorkflowStep.PARSE_INVENTORY)
            display.set_total_resources(20)
            display.set_resource_types({"AWS::EC2::Instance": 10, "AWS::S3::Bucket": 10})
            display.complete_step(WorkflowStep.PARSE_INVENTORY)

            display.start_step(WorkflowStep.BUILD_RESOURCE_MAP)
            display.complete_step(WorkflowStep.BUILD_RESOURCE_MAP)

            display.start_step(WorkflowStep.CATEGORIZE_LAYERS)
            layers = {
                "Network Foundation": [{"id": "1"}, {"id": "2"}],
                "Compute": [{"id": "3"}],
            }
            display.set_layers(layers, ["Network Foundation", "Compute"])
            display.complete_step(WorkflowStep.CATEGORIZE_LAYERS)

            display.start_step(WorkflowStep.GENERATE_LAYERS)
            display.start_layer("Network Foundation")
            display.complete_layer("Network Foundation", "network.tf")
            display.start_layer("Compute")
            display.complete_layer("Compute", "compute.tf")
            display.complete_step(WorkflowStep.GENERATE_LAYERS)

            display.start_step(WorkflowStep.TERRAFORM_INIT)
            display.complete_step(WorkflowStep.TERRAFORM_INIT)

            display.start_step(WorkflowStep.TERRAFORM_VALIDATE)
            display.complete_step(WorkflowStep.TERRAFORM_VALIDATE)

            display.stop()

        assert display.steps[WorkflowStep.PARSE_INVENTORY].status == "completed"
        assert display.steps[WorkflowStep.TERRAFORM_VALIDATE].status == "completed"
        assert display.layers["Network Foundation"].status == LayerStatus.COMPLETED
        assert display.layers["Compute"].status == LayerStatus.COMPLETED
        assert len(display.generated_files) == 2
        assert display.live is None
