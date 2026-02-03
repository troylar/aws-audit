"""Real-time generation progress display with detailed workflow view.

Provides a visual display showing IaC generation progress with detailed
step-by-step workflow tracking and layer generation status.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.table import Table
from rich.text import Text


class LayerStatus(Enum):
    """Status of a layer during generation."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStep(Enum):
    """Steps in the generation workflow."""

    PARSE_INVENTORY = "parse_inventory"
    BUILD_RESOURCE_MAP = "build_resource_map"
    CATEGORIZE_LAYERS = "categorize_layers"
    EXTRACT_LAMBDA = "extract_lambda"
    GENERATE_LAYERS = "generate_layers"
    COMPARE_INVENTORY = "compare_inventory"
    TERRAFORM_INIT = "terraform_init"
    TERRAFORM_VALIDATE = "terraform_validate"
    COMPLETE = "complete"


@dataclass
class TrackedLayer:
    """Track state of a layer during generation."""

    name: str
    order: int
    resource_count: int
    status: LayerStatus = LayerStatus.PENDING
    generated_file: Optional[str] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class TrackedStep:
    """Track state of a workflow step."""

    step: WorkflowStep
    status: str = "pending"  # pending, running, completed, failed
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    details: str = ""


@dataclass
class ComparisonResult:
    """Track comparison results."""

    coverage_percentage: float = 0.0
    total_resources: int = 0
    represented_count: int = 0
    missing_count: int = 0
    issues_count: int = 0
    summary: str = ""


class GenerationProgressDisplay:
    """Manages real-time generation progress display with detailed workflow view."""

    STEP_CONFIG: Dict[WorkflowStep, Dict[str, str]] = {
        WorkflowStep.PARSE_INVENTORY: {
            "name": "Parse Inventory",
            "icon": "📦",
            "description": "Loading resources from snapshot",
        },
        WorkflowStep.BUILD_RESOURCE_MAP: {
            "name": "Build Resource Map",
            "icon": "🗺️",
            "description": "Creating AWS ID to Terraform reference mapping",
        },
        WorkflowStep.CATEGORIZE_LAYERS: {
            "name": "Categorize Layers",
            "icon": "📑",
            "description": "Organizing resources by dependency layer",
        },
        WorkflowStep.EXTRACT_LAMBDA: {
            "name": "Extract Lambda Code",
            "icon": "λ",
            "description": "Extracting Lambda function deployment packages",
        },
        WorkflowStep.GENERATE_LAYERS: {
            "name": "Generate Terraform",
            "icon": "⚙️",
            "description": "Generating HCL code via AWS Bedrock",
        },
        WorkflowStep.COMPARE_INVENTORY: {
            "name": "Compare Coverage",
            "icon": "🔍",
            "description": "AI analysis of inventory vs generated code",
        },
        WorkflowStep.TERRAFORM_INIT: {
            "name": "Terraform Init",
            "icon": "🔧",
            "description": "Initializing Terraform providers",
        },
        WorkflowStep.TERRAFORM_VALIDATE: {
            "name": "Terraform Validate",
            "icon": "✅",
            "description": "Validating generated configuration",
        },
        WorkflowStep.COMPLETE: {
            "name": "Complete",
            "icon": "🎉",
            "description": "Generation finished",
        },
    }

    LAYER_ICONS: Dict[str, str] = {
        "Network Foundation": "🌐",
        "Security Groups": "🛡️",
        "IAM": "🔑",
        "Storage": "💾",
        "Data": "📊",
        "Database": "🗄️",
        "Compute": "💻",
        "Serverless": "λ",
        "Integration": "🔗",
        "Monitoring": "📈",
        "Other": "📦",
    }

    def __init__(self, console: Console) -> None:
        """Initialize the generation progress display."""
        self.console = console
        self.layers: Dict[str, TrackedLayer] = {}
        self.layer_order: List[str] = []
        self.steps: Dict[WorkflowStep, TrackedStep] = {}
        self.current_step: WorkflowStep = WorkflowStep.PARSE_INVENTORY
        self.total_resources: int = 0
        self.source_name: str = ""
        self.output_dir: str = ""
        self.comparison: Optional[ComparisonResult] = None
        self.validation_errors: List[str] = []
        self.live: Optional[Live] = None
        self.start_time: float = 0.0
        self.generated_files: List[str] = []
        self.current_activity: str = ""
        self.resource_types_found: Dict[str, int] = {}
        self.lambda_functions_extracted: int = 0
        self.activity_history: List[str] = []  # Recent activity messages
        self.max_activity_history: int = 3  # Show last N activities

        # Initialize all steps
        for step in WorkflowStep:
            if step != WorkflowStep.COMPLETE:
                self.steps[step] = TrackedStep(step=step)

    def set_source(self, source_name: str, output_dir: str) -> None:
        """Set the source snapshot/file name and output directory."""
        self.source_name = source_name
        self.output_dir = output_dir

    def set_layers(self, layers: Dict[str, List[Any]], layer_order: List[str]) -> None:
        """Set the layers to be generated."""
        self.layer_order = layer_order
        for i, name in enumerate(layer_order):
            resources = layers.get(name, [])
            self.layers[name] = TrackedLayer(
                name=name,
                order=i,
                resource_count=len(resources),
            )
        self.total_resources = sum(len(layers.get(name, [])) for name in layer_order)
        self._refresh()

    def set_total_resources(self, count: int) -> None:
        """Set total resource count."""
        self.total_resources = count
        self._refresh()

    def set_resource_types(self, resource_types: Dict[str, int]) -> None:
        """Set resource types breakdown."""
        self.resource_types_found = resource_types
        self._refresh()

    def set_lambda_count(self, count: int) -> None:
        """Set number of Lambda functions extracted."""
        self.lambda_functions_extracted = count
        self._refresh()

    def set_activity(self, activity: str) -> None:
        """Set current activity description and add to history."""
        self.current_activity = activity
        if activity:
            # Add to history, keeping only recent entries
            self.activity_history.append(activity)
            if len(self.activity_history) > self.max_activity_history:
                self.activity_history.pop(0)
        self._refresh()

    def start_step(self, step: WorkflowStep) -> None:
        """Mark a workflow step as started."""
        self.current_step = step
        if step in self.steps:
            self.steps[step].status = "running"
            self.steps[step].start_time = time.time()
        self._refresh()

    def complete_step(self, step: WorkflowStep) -> None:
        """Mark a workflow step as completed."""
        if step in self.steps:
            self.steps[step].status = "completed"
            self.steps[step].end_time = time.time()
        self._refresh()

    def fail_step(self, step: WorkflowStep, error: str = "") -> None:
        """Mark a workflow step as failed."""
        if step in self.steps:
            self.steps[step].status = "failed"
            self.steps[step].end_time = time.time()
            self.steps[step].details = error
        self._refresh()

    def start_layer(self, layer_name: str) -> None:
        """Mark a layer as currently generating."""
        if layer_name in self.layers:
            self.layers[layer_name].status = LayerStatus.GENERATING
            self.layers[layer_name].start_time = time.time()
            self.current_activity = f"Generating {layer_name} layer..."
        self._refresh()

    def complete_layer(self, layer_name: str, generated_file: Optional[str] = None) -> None:
        """Mark a layer as completed."""
        if layer_name in self.layers:
            self.layers[layer_name].status = LayerStatus.COMPLETED
            self.layers[layer_name].generated_file = generated_file
            self.layers[layer_name].end_time = time.time()
            if generated_file:
                self.generated_files.append(generated_file)
        self._refresh()

    def fail_layer(self, layer_name: str, error: str) -> None:
        """Mark a layer as failed."""
        if layer_name in self.layers:
            self.layers[layer_name].status = LayerStatus.FAILED
            self.layers[layer_name].error = error
            self.layers[layer_name].end_time = time.time()
        self._refresh()

    def set_comparison_result(self, result: Dict[str, Any]) -> None:
        """Set the comparison result."""
        self.comparison = ComparisonResult(
            coverage_percentage=result.get("coverage_percentage", 0.0),
            total_resources=result.get("total_resources", 0),
            represented_count=result.get("represented_count", 0),
            missing_count=result.get("missing_count", 0),
            issues_count=len(result.get("issues", [])),
            summary=result.get("summary", ""),
        )
        self._refresh()

    def set_validation_errors(self, errors: List[str]) -> None:
        """Set validation errors."""
        self.validation_errors = errors
        self._refresh()

    def _get_layer_icon(self, layer_name: str) -> str:
        """Get icon for a layer name."""
        for key, icon in self.LAYER_ICONS.items():
            if key.lower() in layer_name.lower():
                return icon
        return self.LAYER_ICONS["Other"]

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable."""
        if seconds < 1:
            return "<1s"
        elif seconds < 60:
            return f"{seconds:.0f}s"
        else:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"

    def _build_display(self) -> RenderableType:
        """Build the Rich renderable for current state."""
        elements: List[RenderableType] = []

        # Header with elapsed time
        elapsed = time.time() - self.start_time if self.start_time else 0
        header = Text()
        header.append("\n")
        header.append("  🏗️  ", style="bold")
        header.append("Terraform Generation", style="bold cyan")
        header.append(f"   ⏱️  {self._format_duration(elapsed)}", style="dim")
        elements.append(header)

        # Source info
        source_line = Text()
        source_line.append("\n  ")
        source_line.append("Source: ", style="dim")
        source_line.append(self.source_name, style="cyan")
        source_line.append("  →  ", style="dim")
        source_line.append(self.output_dir, style="cyan")
        if self.total_resources > 0:
            source_line.append(f"  ({self.total_resources} resources)", style="dim")
        elements.append(source_line)
        elements.append(Text("\n"))

        # Workflow steps table
        steps_table = Table(
            show_header=True,
            header_style="bold dim",
            box=None,
            padding=(0, 1),
            collapse_padding=True,
        )
        steps_table.add_column("", width=3)
        steps_table.add_column("Step", width=22)
        steps_table.add_column("Status", width=12)
        steps_table.add_column("Time", width=8)
        steps_table.add_column("Details", style="dim")

        workflow_order = [
            WorkflowStep.PARSE_INVENTORY,
            WorkflowStep.BUILD_RESOURCE_MAP,
            WorkflowStep.CATEGORIZE_LAYERS,
            WorkflowStep.EXTRACT_LAMBDA,
            WorkflowStep.GENERATE_LAYERS,
            WorkflowStep.COMPARE_INVENTORY,
            WorkflowStep.TERRAFORM_INIT,
            WorkflowStep.TERRAFORM_VALIDATE,
        ]

        for step in workflow_order:
            config = self.STEP_CONFIG[step]
            tracked = self.steps.get(step)

            # Status icon
            if tracked:
                if tracked.status == "completed":
                    status_icon = "[green]✓[/green]"
                    status_text = "[green]done[/green]"
                elif tracked.status == "running":
                    status_icon = "[yellow]●[/yellow]"
                    status_text = "[yellow]running[/yellow]"
                elif tracked.status == "failed":
                    status_icon = "[red]✗[/red]"
                    status_text = "[red]failed[/red]"
                else:
                    status_icon = "[dim]○[/dim]"
                    status_text = "[dim]waiting[/dim]"
            else:
                status_icon = "[dim]○[/dim]"
                status_text = "[dim]waiting[/dim]"

            # Duration
            duration = ""
            if tracked and tracked.start_time:
                if tracked.end_time:
                    duration = self._format_duration(tracked.end_time - tracked.start_time)
                else:
                    duration = self._format_duration(time.time() - tracked.start_time)

            # Details
            details = config["description"]
            if step == WorkflowStep.PARSE_INVENTORY and self.total_resources > 0:
                details = f"Found {self.total_resources} resources"
            elif step == WorkflowStep.CATEGORIZE_LAYERS and self.layers:
                details = f"Organized into {len(self.layers)} layers"
            elif step == WorkflowStep.EXTRACT_LAMBDA and self.lambda_functions_extracted > 0:
                details = f"Extracted {self.lambda_functions_extracted} functions"
            elif step == WorkflowStep.GENERATE_LAYERS and self.layers:
                completed = sum(1 for lyr in self.layers.values() if lyr.status == LayerStatus.COMPLETED)
                if tracked and tracked.status == "running":
                    generating = [lyr.name for lyr in self.layers.values() if lyr.status == LayerStatus.GENERATING]
                    if generating:
                        details = f"Layer {completed + 1}/{len(self.layers)}: {generating[0]}"
                    else:
                        details = f"{completed}/{len(self.layers)} layers"
                elif tracked and tracked.status == "completed":
                    details = f"Generated {completed} layers"
            elif step == WorkflowStep.COMPARE_INVENTORY and self.comparison:
                details = f"{self.comparison.coverage_percentage:.0f}% coverage"
            elif step == WorkflowStep.TERRAFORM_VALIDATE and self.validation_errors:
                details = f"{len(self.validation_errors)} warnings"

            steps_table.add_row(
                status_icon,
                f"{config['icon']} {config['name']}",
                status_text,
                duration,
                details,
            )

        elements.append(steps_table)

        # Current activity indicator
        if self.current_activity:
            elements.append(Text("\n"))
            activity_line = Text()
            activity_line.append("  ", style="")
            activity_line.append("⟳ ", style="yellow")
            activity_line.append(self.current_activity, style="yellow italic")
            elements.append(activity_line)

        # Layer details (show during generation)
        if self.layers and self.current_step == WorkflowStep.GENERATE_LAYERS:
            elements.append(Text("\n"))
            layer_header = Text()
            layer_header.append("  ", style="")
            layer_header.append("Layer Progress:", style="bold")

            completed = sum(1 for lyr in self.layers.values() if lyr.status == LayerStatus.COMPLETED)
            layer_header.append(f" {completed}/{len(self.layers)}", style="cyan")
            elements.append(layer_header)

            for layer_name in self.layer_order:
                layer = self.layers.get(layer_name)
                if not layer:
                    continue

                icon = self._get_layer_icon(layer_name)
                layer_line = Text()
                layer_line.append("    ", style="")

                if layer.status == LayerStatus.COMPLETED:
                    layer_line.append("✓ ", style="green")
                    layer_line.append(f"{icon} {layer_name}", style="green")
                    layer_line.append(f" ({layer.resource_count})", style="dim")
                    if layer.start_time and layer.end_time:
                        dur = self._format_duration(layer.end_time - layer.start_time)
                        layer_line.append(f"  {dur}", style="dim")
                elif layer.status == LayerStatus.GENERATING:
                    layer_line.append("● ", style="yellow")
                    layer_line.append(f"{icon} {layer_name}", style="yellow bold")
                    layer_line.append(f" ({layer.resource_count})", style="dim")
                    layer_line.append("  generating...", style="yellow italic")
                    if layer.start_time:
                        dur = self._format_duration(time.time() - layer.start_time)
                        layer_line.append(f" {dur}", style="dim")
                elif layer.status == LayerStatus.FAILED:
                    layer_line.append("✗ ", style="red")
                    layer_line.append(f"{icon} {layer_name}", style="red")
                    if layer.error:
                        err_short = layer.error[:30] + "..." if len(layer.error) > 30 else layer.error
                        layer_line.append(f"  {err_short}", style="red dim")
                else:
                    layer_line.append("○ ", style="dim")
                    layer_line.append(f"{icon} {layer_name}", style="dim")
                    layer_line.append(f" ({layer.resource_count})", style="dim")

                elements.append(layer_line)

        # Comparison result
        if self.comparison and self.current_step in [
            WorkflowStep.COMPARE_INVENTORY,
            WorkflowStep.TERRAFORM_INIT,
            WorkflowStep.TERRAFORM_VALIDATE,
            WorkflowStep.COMPLETE,
        ]:
            elements.append(Text("\n"))
            comp_line = Text()
            comp_line.append("  ", style="")
            comp_line.append("Coverage: ", style="bold")
            coverage = self.comparison.coverage_percentage
            color = "green" if coverage >= 90 else "yellow" if coverage >= 70 else "red"
            comp_line.append(f"{coverage:.1f}%", style=f"bold {color}")
            comp_line.append(
                f" ({self.comparison.represented_count}/{self.comparison.total_resources} resources)",
                style="dim",
            )
            if self.comparison.issues_count > 0:
                comp_line.append(f"  ⚠️ {self.comparison.issues_count} issues", style="yellow")
            elements.append(comp_line)

        # Validation result
        validate_step = self.steps.get(WorkflowStep.TERRAFORM_VALIDATE, TrackedStep(WorkflowStep.TERRAFORM_VALIDATE))
        if validate_step.status == "completed":
            elements.append(Text("\n"))
            val_line = Text()
            val_line.append("  ", style="")
            if self.validation_errors:
                val_line.append(f"⚠️  Validation: {len(self.validation_errors)} warnings", style="yellow")
            else:
                val_line.append("✅ Validation: passed", style="green")
            elements.append(val_line)

        elements.append(Text("\n"))

        return Group(*elements)

    def start(self) -> None:
        """Start the live display."""
        self.start_time = time.time()
        self.live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self.live.start()

    def _refresh(self) -> None:
        """Refresh the live display with current state."""
        if self.live:
            self.live.update(self._build_display())

    def stop(self) -> None:
        """Stop the live display."""
        if self.live:
            self.live.stop()
            self.live = None

    def print_final_summary(self, success: bool) -> None:
        """Print a final summary of the generation."""
        self.console.print()

        if success:
            self.console.print("  🎉  [bold green]Generation complete![/bold green]")
        else:
            self.console.print("  ❌  [bold red]Generation failed[/bold red]")

        self.console.print()

        # Summary table
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Label", style="dim")
        table.add_column("Value", style="cyan")

        elapsed = time.time() - self.start_time if self.start_time else 0
        table.add_row("Duration", self._format_duration(elapsed))

        completed_layers = sum(
            1 for layer in self.layers.values() if layer.status == LayerStatus.COMPLETED
        )
        table.add_row("Layers", f"{completed_layers}/{len(self.layers)}")
        table.add_row("Resources", str(self.total_resources))
        table.add_row("Files", str(len(self.generated_files)))
        table.add_row("Output", self.output_dir)

        if self.comparison:
            coverage = self.comparison.coverage_percentage
            color = "green" if coverage >= 90 else "yellow" if coverage >= 70 else "red"
            table.add_row("Coverage", f"[{color}]{coverage:.1f}%[/{color}]")

        self.console.print(table)
        self.console.print()

        # Show generated files
        if self.generated_files:
            self.console.print("  [bold]Generated files:[/bold]")
            for f in self.generated_files:
                self.console.print(f"    [dim]•[/dim] {f}")
            self.console.print()

        # Show comparison details if available
        if self.comparison and self.comparison.missing_count > 0:
            self.console.print(
                f"  [yellow]⚠️  {self.comparison.missing_count} resources not fully covered[/yellow]"
            )
            self.console.print()

        # Show validation errors if any
        if self.validation_errors:
            self.console.print(f"  [yellow]⚠️  {len(self.validation_errors)} validation warnings[/yellow]")
            for err in self.validation_errors[:5]:
                self.console.print(f"    [dim]•[/dim] {err}")
            if len(self.validation_errors) > 5:
                self.console.print(f"    [dim]... and {len(self.validation_errors) - 5} more[/dim]")
            self.console.print()
