"""CDK generator - high-level API for CDK IaC generation."""

import os
from pathlib import Path
from string import Template
from typing import Any, Callable, Dict, Optional

from .agent import compile_cdk_agent
from .state import GenerationConfig, GenerationState, set_progress_callback
from .terraform_generator import GenerationResult

# Progress callback type: (step_name, step_data) -> None
ProgressCallback = Callable[[str, Dict[str, Any]], None]

# Template directory relative to this file
TEMPLATE_DIR = Path(__file__).parent / "templates"


class CDKGenerator:
    """High-level CDK generator from AWS inventory snapshots.

    Uses AWS Bedrock for AI-powered code generation.

    Usage:
        generator = CDKGenerator(
            output_dir="./cdk",
            output_format="cdk-typescript",
            model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            region="us-east-1",
        )
        result = generator.run("my-snapshot")

        if result.success:
            print(f"Generated {len(result.generated_files)} files")
        else:
            print(f"Errors: {result.errors}")
    """

    def __init__(
        self,
        output_dir: str = "./cdk",
        output_format: str = "cdk-typescript",
        model_id: Optional[str] = None,
        region: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
        project_name: Optional[str] = None,
    ):
        """Initialize generator.

        Args:
            output_dir: Directory to write CDK files
            output_format: Either "cdk-typescript" or "cdk-python"
            model_id: Bedrock model ID (or use AWSINV_BEDROCK_MODEL_ID env)
            region: AWS region for Bedrock (or use AWSINV_BEDROCK_REGION env)
            progress_callback: Optional callback for progress updates
            project_name: Project name for package.json/setup.py (default: derived from output_dir)
        """
        self.output_dir = output_dir
        self.output_format = output_format
        self.progress_callback = progress_callback
        self.project_name = project_name or Path(output_dir).name.replace("-", "_").replace(" ", "_")

        base_config = GenerationConfig.from_env()

        self.config = GenerationConfig(
            bedrock_model_id=model_id or base_config.bedrock_model_id,
            bedrock_region=region or base_config.bedrock_region,
            max_retries=base_config.max_retries,
            output_format=output_format,
        )

        self.agent = compile_cdk_agent()

    def run(
        self,
        snapshot_name: Optional[str] = None,
        input_file: Optional[str] = None,
    ) -> GenerationResult:
        """Generate CDK from a snapshot or export file.

        Args:
            snapshot_name: Name of the snapshot to generate from
            input_file: Path to JSON/YAML export file (alternative to snapshot)

        Returns:
            GenerationResult with generated files and any errors

        Raises:
            ValueError: If neither snapshot_name nor input_file is provided
        """
        if not snapshot_name and not input_file:
            raise ValueError("Either snapshot_name or input_file must be provided")

        os.makedirs(self.output_dir, exist_ok=True)

        # Generate project config files BEFORE running agent (npm_build needs package.json)
        # We use empty layer_order for initial generation, will update app.ts/app.py later
        self._generate_project_config_files()

        initial_state: GenerationState = {
            "snapshot_name": snapshot_name or "",
            "input_file": input_file or "",
            "output_dir": self.output_dir,
            "output_format": self.output_format,
            "inventory": [],
            "resource_map": {},
            "layers": {},
            "layer_order": [],
            "current_layer_index": 0,
            "current_layer_status": "pending",
            "attempt_count": 0,
            "max_attempts": self.config.max_retries,
            "validation_errors": [],
            "generated_code": {},
            "generated_files": [],
            "lambda_code_paths": {},
            "total_resources": 0,
            "processed_resources": 0,
            "errors": [],
            "messages": [],
        }

        try:
            final_state = self._run_with_progress(initial_state)

            # Generate app entry point with stack imports (now that we know the layers)
            self._generate_app_entry_point(final_state)

            generated_files = final_state.get("generated_files") or []
            layers_dict = final_state.get("layers") or {}
            layer_order = final_state.get("layer_order") or []
            errors = final_state.get("errors") or []
            validation_errors = final_state.get("validation_errors") or []
            comparison_result = final_state.get("comparison_result") or {}

            layers = [layers_dict[layer_name] for layer_name in layer_order if layer_name in layers_dict]

            success = len(errors) == 0 and len(generated_files) > 0

            result = GenerationResult(
                success=success,
                output_dir=self.output_dir,
                generated_files=generated_files,
                layers=layers,
                errors=[str(e) for e in errors] if errors else [],
                validation_errors=([str(e) for e in validation_errors] if validation_errors else []),
            )

            if self.progress_callback and comparison_result:
                self.progress_callback("comparison_complete", {"result": comparison_result})

            return result

        except Exception as e:
            return GenerationResult(
                success=False,
                output_dir=self.output_dir,
                errors=[f"Generation failed: {e}"],
            )

    def _run_with_progress(self, initial_state: GenerationState) -> Dict[str, Any]:
        """Run the agent with progress streaming.

        Args:
            initial_state: Initial state for the agent

        Returns:
            Final state after agent execution
        """
        if not self.progress_callback:
            return self.agent.invoke(initial_state)

        # Set the global progress callback for nodes to use
        set_progress_callback(self.progress_callback)

        final_state = dict(initial_state)
        last_node = None
        last_layer_index = -1
        format_label = "CDK TypeScript" if self.output_format == "cdk-typescript" else "CDK Python"

        try:
            for event in self.agent.stream(initial_state, stream_mode="updates"):
                for node_name, state_update in event.items():
                    if node_name != last_node:
                        self.progress_callback("node_start", {"node": node_name})
                        last_node = node_name

                        if node_name == "generate_layer":
                            layer_order = final_state.get("layer_order", [])
                            current_idx = final_state.get("current_layer_index", 0)
                            if current_idx != last_layer_index and current_idx < len(layer_order):
                                layer_name = layer_order[current_idx]
                                self.progress_callback(
                                    "layer_start",
                                    {
                                        "layer_name": layer_name,
                                        "layer_index": current_idx,
                                        "total_layers": len(layer_order),
                                        "format": format_label,
                                    },
                                )
                                last_layer_index = current_idx

                    # Skip processing if state_update is None or empty
                    if not state_update:
                        self.progress_callback("node_complete", {"node": node_name})
                        continue

                    final_state.update(state_update)

                    if node_name == "parse_inventory":
                        resources = state_update.get("resources", [])
                        self.progress_callback(
                            "resources_loaded",
                            {
                                "count": len(resources),
                                "resources": resources,
                            },
                        )

                    elif node_name == "categorize_layers":
                        layers = state_update.get("layers", {})
                        layer_order = state_update.get("layer_order", [])
                        self.progress_callback(
                            "layers_categorized",
                            {
                                "layers": layers,
                                "layer_order": layer_order,
                            },
                        )

                    elif node_name == "generate_layer":
                        layer_order = final_state.get("layer_order", [])
                        current_idx = state_update.get("current_layer_index", 0) - 1
                        if 0 <= current_idx < len(layer_order):
                            layer_name = layer_order[current_idx]
                            status = state_update.get("current_layer_status", "")
                            generated_code = state_update.get("generated_code", {})
                            generated_files = state_update.get("generated_files", [])

                            self.progress_callback(
                                "layer_complete",
                                {
                                    "layer_name": layer_name,
                                    "status": status,
                                    "generated_code": generated_code.get(layer_name, ""),
                                    "generated_file": (generated_files[0] if generated_files else None),
                                },
                            )

                    elif node_name == "compare_inventory":
                        comparison = state_update.get("comparison_result", {})
                        if comparison:
                            self.progress_callback("comparison_complete", {"result": comparison})

                    elif node_name == "npm_build":
                        npm_success = state_update.get("npm_build_success", False)
                        npm_errors = state_update.get("validation_errors", [])
                        self.progress_callback(
                            "npm_build_complete",
                            {
                                "success": npm_success,
                                "errors": npm_errors,
                            },
                        )

                    elif node_name == "cdk_synth":
                        errors = state_update.get("validation_errors", [])
                        self.progress_callback("validation_complete", {"errors": errors})

                    self.progress_callback("node_complete", {"node": node_name})

            return final_state
        finally:
            set_progress_callback(None)

    def _generate_project_config_files(self) -> None:
        """Generate project configuration files BEFORE agent runs.

        This is called before the agent runs so that npm_build can find package.json.
        The app entry point is generated after the agent runs (once we know the layers).
        """
        if self.output_format == "cdk-typescript":
            self._generate_typescript_config_files()
        else:
            self._generate_python_config_files()

    def _generate_app_entry_point(self, state: Dict[str, Any]) -> None:
        """Generate app entry point with stack imports AFTER agent runs.

        Args:
            state: Final state with layer_order populated
        """
        if self.output_format == "cdk-typescript":
            self._generate_typescript_app(state)
        else:
            self._generate_python_app(state)

    def _generate_typescript_config_files(self) -> None:
        """Generate TypeScript CDK config files (package.json, tsconfig.json, cdk.json)."""
        template_dir = TEMPLATE_DIR / "typescript"

        # Generate package.json
        self._render_template(
            template_dir / "package.json.template",
            os.path.join(self.output_dir, "package.json"),
            {"PROJECT_NAME": self.project_name},
        )

        # Generate tsconfig.json
        self._render_template(
            template_dir / "tsconfig.json.template",
            os.path.join(self.output_dir, "tsconfig.json"),
            {},
        )

        # Generate cdk.json
        self._render_template(
            template_dir / "cdk.json.template",
            os.path.join(self.output_dir, "cdk.json"),
            {},
        )

        # Create lib directory for stacks
        lib_dir = os.path.join(self.output_dir, "lib")
        os.makedirs(lib_dir, exist_ok=True)

    def _generate_python_config_files(self) -> None:
        """Generate Python CDK config files (requirements.txt, cdk.json, setup.py)."""
        template_dir = TEMPLATE_DIR / "python"

        # Generate requirements.txt
        self._render_template(
            template_dir / "requirements.txt.template",
            os.path.join(self.output_dir, "requirements.txt"),
            {},
        )

        # Generate cdk.json
        self._render_template(
            template_dir / "cdk.json.template",
            os.path.join(self.output_dir, "cdk.json"),
            {},
        )

        # Generate setup.py
        self._render_template(
            template_dir / "setup.py.template",
            os.path.join(self.output_dir, "setup.py"),
            {"PROJECT_NAME": self.project_name},
        )

        # Generate stacks/__init__.py
        stacks_dir = os.path.join(self.output_dir, "stacks")
        os.makedirs(stacks_dir, exist_ok=True)
        init_file = os.path.join(stacks_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write('"""CDK stack modules."""\n')

    def _generate_typescript_app(self, state: Dict[str, Any]) -> None:
        """Generate bin/app.ts with stack imports and instantiations."""
        layer_order = state.get("layer_order", [])

        # Build import statements
        imports = []
        instantiations = []

        for layer_name in layer_order:
            class_name = self._to_pascal_case(layer_name) + "Stack"
            file_name = layer_name.lower().replace(" ", "_").replace("-", "_") + "_stack"

            imports.append(f"import {{ {class_name} }} from '../lib/{file_name}';")
            var_name = self._to_camel_case(layer_name) + "Stack"
            instantiations.append(f"const {var_name} = new {class_name}(app, '{class_name}');")

        stack_imports = "\n".join(imports) if imports else "// No stacks generated"
        stack_instantiations = "\n".join(instantiations) if instantiations else "// No stacks to instantiate"

        template_dir = TEMPLATE_DIR / "typescript"
        bin_dir = os.path.join(self.output_dir, "bin")
        os.makedirs(bin_dir, exist_ok=True)

        self._render_template(
            template_dir / "bin" / "app.ts.template",
            os.path.join(bin_dir, "app.ts"),
            {
                "STACK_IMPORTS": stack_imports,
                "STACK_INSTANTIATIONS": stack_instantiations,
            },
        )

    def _generate_python_app(self, state: Dict[str, Any]) -> None:
        """Generate app.py with stack imports and instantiations."""
        layer_order = state.get("layer_order", [])

        imports = []
        instantiations = []

        for layer_name in layer_order:
            class_name = self._to_pascal_case(layer_name) + "Stack"
            module_name = layer_name.lower().replace(" ", "_").replace("-", "_") + "_stack"

            imports.append(f"from stacks.{module_name} import {class_name}")
            var_name = self._to_snake_case(layer_name) + "_stack"
            instantiations.append(f'{var_name} = {class_name}(app, "{class_name}")')

        stack_imports = "\n".join(imports) if imports else "# No stacks generated"
        stack_instantiations = "\n".join(instantiations) if instantiations else "# No stacks to instantiate"

        template_dir = TEMPLATE_DIR / "python"
        self._render_template(
            template_dir / "app.py.template",
            os.path.join(self.output_dir, "app.py"),
            {
                "STACK_IMPORTS": stack_imports,
                "STACK_INSTANTIATIONS": stack_instantiations,
            },
        )

    def _render_template(self, template_path: Path, output_path: str, substitutions: Dict[str, str]) -> None:
        """Render a template file with substitutions.

        Args:
            template_path: Path to the template file
            output_path: Path to write the rendered output
            substitutions: Dictionary of ${VAR} -> value substitutions
        """
        with open(template_path) as f:
            template_content = f.read()

        # Use simple string substitution for ${VAR} patterns
        template = Template(template_content)
        rendered = template.safe_substitute(substitutions)

        with open(output_path, "w") as f:
            f.write(rendered)

    def _to_pascal_case(self, name: str) -> str:
        """Convert a name to PascalCase."""
        parts = name.replace("-", "_").replace(" ", "_").split("_")
        return "".join(part.capitalize() for part in parts if part)

    def _to_camel_case(self, name: str) -> str:
        """Convert a name to camelCase."""
        pascal = self._to_pascal_case(name)
        if not pascal:
            return ""
        return pascal[0].lower() + pascal[1:]

    def _to_snake_case(self, name: str) -> str:
        """Convert a name to snake_case."""
        import re

        result = name.replace("-", "_").replace(" ", "_")
        result = re.sub(r"([a-z])([A-Z])", r"\1_\2", result)
        return result.lower()


def generate_cdk(
    snapshot_name: Optional[str] = None,
    output_dir: str = "./cdk",
    output_format: str = "cdk-typescript",
    model_id: Optional[str] = None,
    region: Optional[str] = None,
    input_file: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
    project_name: Optional[str] = None,
) -> GenerationResult:
    """Generate CDK from a snapshot or export file.

    Args:
        snapshot_name: Name of the snapshot (use this OR input_file)
        output_dir: Output directory for CDK files
        output_format: Either "cdk-typescript" or "cdk-python"
        model_id: Bedrock model ID
        region: AWS region for Bedrock
        input_file: Path to JSON/YAML export file (use this OR snapshot_name)
        progress_callback: Optional callback for progress updates
        project_name: Project name for package.json/setup.py

    Returns:
        GenerationResult
    """
    generator = CDKGenerator(
        output_dir=output_dir,
        output_format=output_format,
        model_id=model_id,
        region=region,
        progress_callback=progress_callback,
        project_name=project_name,
    )
    return generator.run(snapshot_name=snapshot_name, input_file=input_file)
