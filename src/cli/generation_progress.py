"""Real-time generation progress display with layer view.

Provides a visual display showing IaC generation progress organized by layer,
with real-time status updates as each layer is generated.
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
    VALIDATE_TERRAFORM = "validate_terraform"
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
    """Manages real-time generation progress display.

    Displays workflow steps and layer generation with real-time status updates.
    """

    STEP_NAMES: Dict[WorkflowStep, str] = {
        WorkflowStep.PARSE_INVENTORY: "Loading inventory",
        WorkflowStep.BUILD_RESOURCE_MAP: "Building resource map",
        WorkflowStep.CATEGORIZE_LAYERS: "Categorizing layers",
        WorkflowStep.EXTRACT_LAMBDA: "Extracting Lambda code",
        WorkflowStep.GENERATE_LAYERS: "Generating Terraform",
        WorkflowStep.COMPARE_INVENTORY: "Comparing coverage",
        WorkflowStep.VALIDATE_TERRAFORM: "Validating Terraform",
        WorkflowStep.COMPLETE: "Complete",
    }

    STEP_ICONS: Dict[WorkflowStep, str] = {
        WorkflowStep.PARSE_INVENTORY: "📦",
        WorkflowStep.BUILD_RESOURCE_MAP: "🗺️",
        WorkflowStep.CATEGORIZE_LAYERS: "📑",
        WorkflowStep.EXTRACT_LAMBDA: "λ",
        WorkflowStep.GENERATE_LAYERS: "⚙️",
        WorkflowStep.COMPARE_INVENTORY: "🔍",
        WorkflowStep.VALIDATE_TERRAFORM: "✅",
        WorkflowStep.COMPLETE: "🎉",
    }

    LAYER_ICONS: Dict[str, str] = {
        "Network Foundation": "🌐",
        "Security Groups": "🛡️",
        "IAM": "🔑",
        "Storage": "💾",
        "Database": "🗄️",
        "Compute": "💻",
        "Serverless": "λ",
        "Integration": "🔗",
        "Monitoring": "📊",
        "Other": "📦",
    }

    STATUS_ICONS: Dict[LayerStatus, str] = {
        LayerStatus.PENDING: "○",
        LayerStatus.GENERATING: "⋯",
        LayerStatus.COMPLETED: "✓",
        LayerStatus.FAILED: "✗",
    }

    STATUS_COLORS: Dict[LayerStatus, str] = {
        LayerStatus.PENDING: "dim",
        LayerStatus.GENERATING: "yellow",
        LayerStatus.COMPLETED: "green",
        LayerStatus.FAILED: "red",
    }

    def __init__(self, console: Console) -> None:
        """Initialize the generation progress display.

        Args:
            console: Rich Console instance for output
        """
        self.console = console
        self.layers: Dict[str, TrackedLayer] = {}
        self.layer_order: List[str] = []
        self.current_step: WorkflowStep = WorkflowStep.PARSE_INVENTORY
        self.completed_steps: List[WorkflowStep] = []
        self.total_resources: int = 0
        self.source_name: str = ""
        self.output_dir: str = ""
        self.comparison: Optional[ComparisonResult] = None
        self.validation_errors: List[str] = []
        self.live: Optional[Live] = None
        self.start_time: float = 0.0
        self.generated_files: List[str] = []

    def set_source(self, source_name: str, output_dir: str) -> None:
        """Set the source snapshot/file name and output directory.

        Args:
            source_name: Name of snapshot or file being processed
            output_dir: Output directory path
        """
        self.source_name = source_name
        self.output_dir = output_dir

    def set_layers(self, layers: Dict[str, List[Any]], layer_order: List[str]) -> None:
        """Set the layers to be generated.

        Args:
            layers: Dictionary mapping layer names to resource lists
            layer_order: Ordered list of layer names
        """
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
        """Set total resource count.

        Args:
            count: Total number of resources
        """
        self.total_resources = count
        self._refresh()

    def start_step(self, step: WorkflowStep) -> None:
        """Mark a workflow step as started.

        Args:
            step: The workflow step that is starting
        """
        self.current_step = step
        self._refresh()

    def complete_step(self, step: WorkflowStep) -> None:
        """Mark a workflow step as completed.

        Args:
            step: The workflow step that completed
        """
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        self._refresh()

    def start_layer(self, layer_name: str) -> None:
        """Mark a layer as currently generating.

        Args:
            layer_name: Name of layer being generated
        """
        if layer_name in self.layers:
            self.layers[layer_name].status = LayerStatus.GENERATING
            self._refresh()

    def complete_layer(self, layer_name: str, generated_file: Optional[str] = None) -> None:
        """Mark a layer as completed.

        Args:
            layer_name: Name of layer that completed
            generated_file: Path to generated file
        """
        if layer_name in self.layers:
            self.layers[layer_name].status = LayerStatus.COMPLETED
            self.layers[layer_name].generated_file = generated_file
            if generated_file:
                self.generated_files.append(generated_file)
            self._refresh()

    def fail_layer(self, layer_name: str, error: str) -> None:
        """Mark a layer as failed.

        Args:
            layer_name: Name of layer that failed
            error: Error message
        """
        if layer_name in self.layers:
            self.layers[layer_name].status = LayerStatus.FAILED
            self.layers[layer_name].error = error
            self._refresh()

    def set_comparison_result(self, result: Dict[str, Any]) -> None:
        """Set the comparison result.

        Args:
            result: Comparison result dictionary
        """
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
        """Set validation errors.

        Args:
            errors: List of validation error messages
        """
        self.validation_errors = errors
        self._refresh()

    def _get_layer_icon(self, layer_name: str) -> str:
        """Get icon for a layer name.

        Args:
            layer_name: Name of the layer

        Returns:
            Emoji icon for the layer
        """
        for key, icon in self.LAYER_ICONS.items():
            if key.lower() in layer_name.lower():
                return icon
        return self.LAYER_ICONS["Other"]

    def _make_progress_bar(self, completed: int, total: int, width: int = 20) -> str:
        """Create a text-based progress bar.

        Args:
            completed: Number of completed items
            total: Total number of items
            width: Width of the bar in characters

        Returns:
            Progress bar string
        """
        if total == 0:
            return "━" * width

        filled = int((completed / total) * width)
        empty = width - filled

        return "━" * filled + "○" * empty

    def _build_display(self) -> RenderableType:
        """Build the Rich renderable for current state.

        Returns:
            Rich renderable for the live display
        """
        lines: List[Text] = []

        # Header
        elapsed = time.time() - self.start_time if self.start_time else 0
        header = Text()
        header.append("🏗️  ", style="bold")
        header.append("Terraform Generation", style="bold cyan")
        header.append(f"  {elapsed:.0f}s", style="dim")
        lines.append(header)

        # Source info
        source_line = Text()
        source_line.append("   Source: ", style="dim")
        source_line.append(self.source_name, style="cyan")
        source_line.append("  →  ", style="dim")
        source_line.append(self.output_dir, style="cyan")
        lines.append(source_line)
        lines.append(Text())

        # Workflow steps
        steps_line = Text()
        steps_line.append("   ", style="")
        workflow_steps = [
            WorkflowStep.PARSE_INVENTORY,
            WorkflowStep.BUILD_RESOURCE_MAP,
            WorkflowStep.CATEGORIZE_LAYERS,
            WorkflowStep.EXTRACT_LAMBDA,
            WorkflowStep.GENERATE_LAYERS,
            WorkflowStep.COMPARE_INVENTORY,
            WorkflowStep.VALIDATE_TERRAFORM,
        ]

        for i, step in enumerate(workflow_steps):
            if step in self.completed_steps:
                steps_line.append("●", style="green")
            elif step == self.current_step:
                steps_line.append("◉", style="yellow bold")
            else:
                steps_line.append("○", style="dim")

            if i < len(workflow_steps) - 1:
                if step in self.completed_steps:
                    steps_line.append("───", style="green")
                else:
                    steps_line.append("───", style="dim")

        lines.append(steps_line)

        # Current step name
        step_name_line = Text()
        step_name_line.append("   ", style="")
        step_icon = self.STEP_ICONS.get(self.current_step, "")
        step_name = self.STEP_NAMES.get(self.current_step, "")
        style = "green" if self.current_step == WorkflowStep.COMPLETE else "yellow"
        step_name_line.append(f"{step_icon} {step_name}", style=style)
        lines.append(step_name_line)
        lines.append(Text())

        # Layers section (only show if we have layers)
        if self.layers:
            completed_layers = sum(
                1 for layer in self.layers.values() if layer.status == LayerStatus.COMPLETED
            )
            failed_layers = sum(
                1 for layer in self.layers.values() if layer.status == LayerStatus.FAILED
            )
            total_layers = len(self.layers)

            layers_header = Text()
            layers_header.append("   Layers: ", style="bold")
            layers_header.append(f"{completed_layers}/{total_layers}", style="cyan")
            layers_header.append("  ", style="")
            layers_header.append(self._make_progress_bar(completed_layers, total_layers, 15), style="cyan")
            if failed_layers > 0:
                layers_header.append(f"  ({failed_layers} failed)", style="red")
            lines.append(layers_header)
            lines.append(Text())

            # Individual layers
            for layer_name in self.layer_order:
                layer = self.layers.get(layer_name)
                if not layer:
                    continue

                icon = self._get_layer_icon(layer_name)
                status_icon = self.STATUS_ICONS[layer.status]
                status_color = self.STATUS_COLORS[layer.status]

                layer_line = Text()
                layer_line.append(f"   {icon} ", style="")
                layer_line.append(status_icon, style=status_color)
                layer_line.append(" ", style="")
                layer_line.append(f"{layer_name}", style=status_color if layer.status != LayerStatus.PENDING else "")
                layer_line.append(f" ({layer.resource_count})", style="dim")

                if layer.status == LayerStatus.GENERATING:
                    layer_line.append("  ← generating", style="yellow italic")
                elif layer.status == LayerStatus.FAILED and layer.error:
                    error_short = layer.error[:40] + "..." if len(layer.error) > 40 else layer.error
                    layer_line.append(f" - {error_short}", style="red dim")

                lines.append(layer_line)

            lines.append(Text())

        # Comparison result (if available)
        if self.comparison:
            comp_line = Text()
            comp_line.append("   🔍 Coverage: ", style="bold")
            coverage = self.comparison.coverage_percentage
            if coverage >= 90:
                color = "green"
            elif coverage >= 70:
                color = "yellow"
            else:
                color = "red"
            comp_line.append(f"{coverage:.1f}%", style=f"bold {color}")
            represented = self.comparison.represented_count
            total = self.comparison.total_resources
            comp_line.append(f" ({represented}/{total} resources)", style="dim")
            if self.comparison.issues_count > 0:
                comp_line.append(f"  ⚠️ {self.comparison.issues_count} issues", style="yellow")
            lines.append(comp_line)
            lines.append(Text())

        # Validation status
        if self.validation_errors:
            val_line = Text()
            val_line.append(f"   ⚠️  Validation: {len(self.validation_errors)} errors", style="yellow")
            lines.append(val_line)
        elif WorkflowStep.VALIDATE_TERRAFORM in self.completed_steps:
            val_line = Text()
            val_line.append("   ✅ Validation: passed", style="green")
            lines.append(val_line)

        return Group(*lines)

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
        """Print a final summary of the generation.

        Args:
            success: Whether generation was successful overall
        """
        self.console.print()

        if success:
            self.console.print("   🎉  [bold green]Generation complete![/bold green]")
        else:
            self.console.print("   ❌  [bold red]Generation failed[/bold red]")

        self.console.print()

        # Summary table
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Label", style="dim")
        table.add_column("Value", style="cyan")

        completed_layers = sum(
            1 for layer in self.layers.values() if layer.status == LayerStatus.COMPLETED
        )
        table.add_row("Layers", f"{completed_layers}/{len(self.layers)}")
        table.add_row("Resources", str(self.total_resources))
        table.add_row("Files", str(len(self.generated_files)))
        table.add_row("Output", self.output_dir)

        if self.comparison:
            coverage = self.comparison.coverage_percentage
            if coverage >= 90:
                color = "green"
            elif coverage >= 70:
                color = "yellow"
            else:
                color = "red"
            table.add_row("Coverage", f"[{color}]{coverage:.1f}%[/{color}]")

        self.console.print(table)
        self.console.print()

        # Show generated files
        if self.generated_files:
            self.console.print("   [bold]Generated files:[/bold]")
            for f in self.generated_files:
                self.console.print(f"     [dim]•[/dim] {f}")
            self.console.print()

        # Show comparison details if available
        if self.comparison and self.comparison.missing_count > 0:
            self.console.print(f"   [yellow]⚠️  {self.comparison.missing_count} resources not fully covered[/yellow]")
            self.console.print()

        # Show validation errors if any
        if self.validation_errors:
            self.console.print(f"   [yellow]⚠️  {len(self.validation_errors)} validation warnings[/yellow]")
            for err in self.validation_errors[:5]:
                self.console.print(f"     [dim]•[/dim] {err}")
            if len(self.validation_errors) > 5:
                self.console.print(f"     [dim]... and {len(self.validation_errors) - 5} more[/dim]")
            self.console.print()
