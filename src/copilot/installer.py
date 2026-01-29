"""Copilot file installer for GitHub Copilot instructions and prompts."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import InstalledFile, InstallResult, UninstallResult
from .version import get_installed_file_info

# Template file names to install
TEMPLATE_FILES = [
    "copilot-instructions.md",
    "prompts/generate-terraform.prompt.md",
    "prompts/generate-cdk-typescript.prompt.md",
    "prompts/generate-cdk-python.prompt.md",
    "prompts/plan-iac.prompt.md",
    "prompts/generate-terraform-layer.prompt.md",
    "instructions/terraform.instructions.md",
]

# Dangerous paths that should never be installation targets
DANGEROUS_PATHS = {"/", "/home", "/Users", "/root", "/etc", "/var", "/usr"}


def validate_target_path(path: Path) -> Optional[str]:
    """Validate that target path is suitable for installation.

    Args:
        path: Target directory path

    Returns:
        Error message string if invalid, None if valid
    """
    if not path.exists():
        return f"Target path does not exist: {path}"

    if not path.is_dir():
        return f"Target path is not a directory: {path}"

    # Check for dangerous root paths
    path_str = str(path.resolve())
    if path_str in DANGEROUS_PATHS:
        return f"Cannot install to system directory: {path}"

    # Check if writable
    if not os.access(path, os.W_OK):
        return f"Target path is not writable: {path}"

    return None


def generate_backup_filename(original: Path) -> Path:
    """Generate a backup filename with timestamp.

    Args:
        original: Original file path

    Returns:
        Backup file path with .bak.YYYYMMDD-HHMMSS suffix
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{original.name}.bak.{timestamp}"
    return original.parent / backup_name


def get_template_files() -> Dict[str, str]:
    """Get all template files and their contents.

    Returns:
        Dictionary mapping relative file paths to content
    """
    try:
        # Python 3.9+
        from importlib.resources import files

        templates_pkg = files("src.copilot.templates")
    except ImportError:
        # Python 3.8 fallback
        from importlib_resources import files  # type: ignore

        templates_pkg = files("src.copilot.templates")

    result: Dict[str, str] = {}

    # Load each template file
    for template_name in TEMPLATE_FILES:
        if "/" in template_name:
            # Nested path (e.g., prompts/generate-terraform.md)
            parts = template_name.split("/")
            resource = templates_pkg.joinpath(*parts)
        else:
            resource = templates_pkg.joinpath(template_name)

        try:
            content = resource.read_text(encoding="utf-8")
            result[template_name] = content
        except (FileNotFoundError, TypeError):
            # Template file not yet created - use placeholder
            result[template_name] = _get_placeholder_content(template_name)

    return result


def _get_placeholder_content(template_name: str) -> str:
    """Get placeholder content for a template file.

    This is used when template files don't exist yet during development.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    if template_name == "copilot-instructions.md":
        return f"""---
model: gpt-4.1
optimizations:
  - token-efficient (4k context pressure)
  - terse rules over prose
  - batch guidance for large inputs
  - explicit chunking instructions
constraints:
  base-instructions-tokens: 4000
  task-prompt-tokens: 2000
  batch-threshold-resources: 50
last-updated: {today}
---

# AWS Inventory Manager - Copilot Instructions

This file provides context for GitHub Copilot about the AWS Inventory Manager
inventory YAML schema and AWS best practices.

## Inventory YAML Schema

| Field | Type | Description |
|-------|------|-------------|
| arn | string | AWS Resource ARN |
| type | string | AWS::Service::Resource format |
| name | string | Resource name or ID |
| region | string | AWS region (e.g., us-east-1) |
| tags | object | Key-value tag pairs |
| raw_config | object | Service-specific configuration |

## Custom Instructions

If `copilot-custom.md` exists in this directory, follow org-specific standards
defined there for naming conventions, tagging policies, and security requirements.
"""

    elif "generate-terraform" in template_name:
        return f"""---
model: gpt-4.1
optimizations:
  - token-efficient
  - terraform-specific best practices
constraints:
  task-prompt-tokens: 2000
last-updated: {today}
---

# Generate Terraform from Inventory

Generate Terraform HCL code from the provided AWS inventory YAML.

## Output Structure

Generate separate files per resource type:
- ec2.tf, rds.tf, lambda.tf, vpc.tf, iam.tf
- variables.tf, outputs.tf, providers.tf

## Rules

1. Use variables for all configurable values
2. Use locals for repeated expressions
3. Include proper resource naming
4. Use provider aliases for multi-region
5. Include tagging strategy
6. Replace secrets with variable references

## Validation

After generation, run:
```bash
terraform validate
terraform fmt
```

## Large Inventories

For 50+ resources, process by type:
1. Generate EC2 first
2. Then RDS, Lambda, etc.
"""

    elif "generate-cdk-typescript" in template_name:
        return f"""---
model: gpt-4.1
optimizations:
  - token-efficient
  - cdk-typescript best practices
constraints:
  task-prompt-tokens: 2000
last-updated: {today}
---

# Generate CDK TypeScript from Inventory

Generate AWS CDK TypeScript code from the provided AWS inventory YAML.

## Rules

1. Use L2 constructs where available
2. Use proper Stack organization
3. Use Props interfaces for configuration
4. Use CDK Aspects for tagging
5. Handle cross-stack references properly
6. Use environment-agnostic patterns

## Validation

After generation, run:
```bash
cdk synth
```

## Large Inventories

For 50+ resources, process by type.
"""

    elif "generate-cdk-python" in template_name:
        return f"""---
model: gpt-4.1
optimizations:
  - token-efficient
  - cdk-python best practices
constraints:
  task-prompt-tokens: 2000
last-updated: {today}
---

# Generate CDK Python from Inventory

Generate AWS CDK Python code from the provided AWS inventory YAML.

## Rules

1. Use L2 constructs where available
2. Use proper Stack organization
3. Use type hints throughout
4. Use CDK Aspects for tagging
5. Handle cross-stack references properly
6. Use environment-agnostic patterns

## Validation

After generation, run:
```bash
cdk synth
```

## Large Inventories

For 50+ resources, process by type.
"""

    return f"# Placeholder for {template_name}\n"


def install_files(target_path: Path) -> InstallResult:
    """Install Copilot files to target directory.

    Args:
        target_path: Target project directory

    Returns:
        InstallResult with details of installed, backed up, skipped, and errored files
    """
    result = InstallResult()

    # Validate target path
    error = validate_target_path(target_path)
    if error:
        result.errors.append((target_path, error))
        return result

    # Create .github directory if needed
    github_dir = target_path / ".github"
    github_dir.mkdir(exist_ok=True)

    # Create prompts directory if needed
    prompts_dir = github_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    # Create instructions directory if needed
    instructions_dir = github_dir / "instructions"
    instructions_dir.mkdir(exist_ok=True)

    # Check for custom file (never overwrite)
    custom_file = github_dir / "copilot-custom.md"
    if custom_file.exists():
        result.skipped.append(custom_file)

    # Get template files
    templates = get_template_files()

    # Install each template
    for template_name, content in templates.items():
        target_file = github_dir / template_name

        try:
            # Backup existing file if present
            if target_file.exists():
                backup_path = generate_backup_filename(target_file)
                shutil.copy2(target_file, backup_path)
                result.backed_up.append((target_file, backup_path))

            # Write new file
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content, encoding="utf-8")
            result.installed.append(target_file)

        except OSError as e:
            result.errors.append((target_file, str(e)))

    return result


def uninstall_files(target_path: Path) -> UninstallResult:
    """Remove installed Copilot files from target directory.

    Args:
        target_path: Target project directory

    Returns:
        UninstallResult with details of removed, not found, preserved, and errored files
    """
    result = UninstallResult()

    # Validate target path
    error = validate_target_path(target_path)
    if error:
        result.errors.append((target_path, error))
        return result

    github_dir = target_path / ".github"

    # Remove each template file
    for template_name in TEMPLATE_FILES:
        target_file = github_dir / template_name

        if not target_file.exists():
            result.not_found.append(target_file)
            continue

        try:
            target_file.unlink()
            result.removed.append(target_file)
        except OSError as e:
            result.errors.append((target_file, str(e)))

    # Preserve custom file
    custom_file = github_dir / "copilot-custom.md"
    if custom_file.exists():
        result.preserved.append(custom_file)

    # Remove empty prompts directory
    prompts_dir = github_dir / "prompts"
    if prompts_dir.exists() and not any(prompts_dir.iterdir()):
        try:
            prompts_dir.rmdir()
        except OSError:
            pass  # Ignore errors removing empty directory

    # Remove empty instructions directory
    instructions_dir = github_dir / "instructions"
    if instructions_dir.exists() and not any(instructions_dir.iterdir()):
        try:
            instructions_dir.rmdir()
        except OSError:
            pass  # Ignore errors removing empty directory

    return result


def list_installed_files(target_path: Path) -> List[InstalledFile]:
    """List installed Copilot files in target directory.

    Args:
        target_path: Target project directory

    Returns:
        List of InstalledFile objects with version info
    """
    # Validate path exists
    if not target_path.exists():
        return []

    github_dir = target_path / ".github"
    if not github_dir.exists():
        return []

    files: List[InstalledFile] = []

    # Check for main instructions file
    instructions_file = github_dir / "copilot-instructions.md"
    if instructions_file.exists():
        files.append(get_installed_file_info(instructions_file))

    # Check for custom file
    custom_file = github_dir / "copilot-custom.md"
    if custom_file.exists():
        files.append(get_installed_file_info(custom_file))

    # Check for prompt files
    prompts_dir = github_dir / "prompts"
    if prompts_dir.exists():
        for prompt_file in prompts_dir.glob("*.md"):
            files.append(get_installed_file_info(prompt_file))

    # Check for instruction files
    instructions_dir = github_dir / "instructions"
    if instructions_dir.exists():
        for instruction_file in instructions_dir.glob("*.md"):
            files.append(get_installed_file_info(instruction_file))

    return files
