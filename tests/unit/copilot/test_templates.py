"""Unit tests for copilot template validation (T033-T035, T053-T054)."""


def estimate_token_count(text: str) -> int:
    """Estimate token count for GPT models.

    Uses a rough estimate of 4 characters per token for English text.
    This is conservative - actual tokenization may be more efficient.
    """
    return len(text) // 4


def get_template_content(template_name: str) -> str:
    """Get template content using importlib.resources."""
    try:
        from importlib.resources import files

        templates_pkg = files("src.copilot.templates")
    except ImportError:
        from importlib_resources import files  # type: ignore

        templates_pkg = files("src.copilot.templates")

    if "/" in template_name:
        parts = template_name.split("/")
        resource = templates_pkg.joinpath(*parts)
    else:
        resource = templates_pkg.joinpath(template_name)

    return resource.read_text(encoding="utf-8")


class TestTokenLimits:
    """Tests for template token limits (T033-T034, T053-T054)."""

    def test_copilot_instructions_under_4000_tokens(self) -> None:
        """copilot-instructions.md should be under 4000 tokens (T033)."""
        content = get_template_content("copilot-instructions.md")
        token_estimate = estimate_token_count(content)

        # Base instructions should be under 4000 tokens
        assert token_estimate < 4000, f"copilot-instructions.md has ~{token_estimate} tokens, should be under 4000"

    def test_generate_terraform_under_2000_tokens(self) -> None:
        """generate-terraform.prompt.md should be under 2000 tokens (T034)."""
        content = get_template_content("prompts/generate-terraform.prompt.md")
        token_estimate = estimate_token_count(content)

        # Task prompts should be under 2000 tokens
        assert token_estimate < 2000, f"generate-terraform.prompt.md has ~{token_estimate} tokens, should be under 2000"

    def test_generate_cdk_typescript_under_2000_tokens(self) -> None:
        """generate-cdk-typescript.prompt.md should be under 2000 tokens (T053)."""
        content = get_template_content("prompts/generate-cdk-typescript.prompt.md")
        token_estimate = estimate_token_count(content)

        # Task prompts should be under 2000 tokens
        assert token_estimate < 2000, (
            f"generate-cdk-typescript.prompt.md has ~{token_estimate} tokens, should be under 2000"
        )

    def test_generate_cdk_python_under_2000_tokens(self) -> None:
        """generate-cdk-python.prompt.md should be under 2000 tokens (T054)."""
        content = get_template_content("prompts/generate-cdk-python.prompt.md")
        token_estimate = estimate_token_count(content)

        # Task prompts should be under 2000 tokens
        assert token_estimate < 2000, (
            f"generate-cdk-python.prompt.md has ~{token_estimate} tokens, should be under 2000"
        )


class TestFrontmatterValidation:
    """Tests for template frontmatter (T035)."""

    def test_copilot_instructions_has_valid_frontmatter(self) -> None:
        """copilot-instructions.md has valid frontmatter."""
        from src.copilot.version import parse_frontmatter

        content = get_template_content("copilot-instructions.md")
        frontmatter = parse_frontmatter(content)

        assert frontmatter.get("model") == "gpt-4.1"
        assert "optimizations" in frontmatter
        assert isinstance(frontmatter["optimizations"], list)
        assert frontmatter.get("last-updated") is not None

    def test_generate_terraform_has_valid_frontmatter(self) -> None:
        """generate-terraform.prompt.md has valid frontmatter."""
        from src.copilot.version import parse_frontmatter

        content = get_template_content("prompts/generate-terraform.prompt.md")
        frontmatter = parse_frontmatter(content)

        assert frontmatter.get("model") == "gpt-4.1"
        assert "optimizations" in frontmatter
        assert frontmatter.get("last-updated") is not None

    def test_generate_cdk_typescript_has_valid_frontmatter(self) -> None:
        """generate-cdk-typescript.prompt.md has valid frontmatter."""
        from src.copilot.version import parse_frontmatter

        content = get_template_content("prompts/generate-cdk-typescript.prompt.md")
        frontmatter = parse_frontmatter(content)

        assert frontmatter.get("model") == "gpt-4.1"
        assert "optimizations" in frontmatter
        assert frontmatter.get("last-updated") is not None

    def test_generate_cdk_python_has_valid_frontmatter(self) -> None:
        """generate-cdk-python.prompt.md has valid frontmatter."""
        from src.copilot.version import parse_frontmatter

        content = get_template_content("prompts/generate-cdk-python.prompt.md")
        frontmatter = parse_frontmatter(content)

        assert frontmatter.get("model") == "gpt-4.1"
        assert "optimizations" in frontmatter
        assert frontmatter.get("last-updated") is not None

    def test_all_templates_have_consistent_model_version(self) -> None:
        """All templates should have the same model version."""
        from src.copilot.version import parse_frontmatter

        templates = [
            "copilot-instructions.md",
            "prompts/generate-terraform.prompt.md",
            "prompts/generate-cdk-typescript.prompt.md",
            "prompts/generate-cdk-python.prompt.md",
        ]

        models = []
        for template in templates:
            content = get_template_content(template)
            frontmatter = parse_frontmatter(content)
            models.append(frontmatter.get("model"))

        # All should be the same model
        assert len(set(models)) == 1, f"Inconsistent models: {models}"
        assert models[0] == "gpt-4.1"


class TestTemplateContent:
    """Tests for template content quality."""

    def test_copilot_instructions_has_schema_section(self) -> None:
        """copilot-instructions.md has inventory YAML schema section."""
        content = get_template_content("copilot-instructions.md")

        assert "Inventory YAML Schema" in content or "Schema" in content
        assert "arn" in content.lower()
        assert "raw_config" in content

    def test_copilot_instructions_has_security_section(self) -> None:
        """copilot-instructions.md has security best practices."""
        content = get_template_content("copilot-instructions.md")

        assert "Security" in content or "security" in content
        # Should mention encryption, IAM, or secrets
        assert any(term in content.lower() for term in ["encryption", "iam", "secrets", "kms"])

    def test_copilot_instructions_has_custom_reference(self) -> None:
        """copilot-instructions.md references custom instructions file."""
        content = get_template_content("copilot-instructions.md")

        assert "copilot-custom.md" in content

    def test_terraform_prompt_has_output_structure(self) -> None:
        """generate-terraform.prompt.md has output structure guidance."""
        content = get_template_content("prompts/generate-terraform.prompt.md")

        assert "Output Structure" in content or "output" in content.lower()
        # Should mention common Terraform files
        assert "variables.tf" in content or "tf" in content.lower()

    def test_terraform_prompt_has_validation_guidance(self) -> None:
        """generate-terraform.prompt.md has validation guidance."""
        content = get_template_content("prompts/generate-terraform.prompt.md")

        assert "terraform validate" in content or "validate" in content.lower()
        assert "terraform fmt" in content or "fmt" in content.lower()

    def test_terraform_prompt_has_batching_guidance(self) -> None:
        """generate-terraform.prompt.md has large inventory guidance."""
        content = get_template_content("prompts/generate-terraform.prompt.md")

        assert "50" in content or "large" in content.lower() or "batch" in content.lower()

    def test_cdk_typescript_has_l2_construct_guidance(self) -> None:
        """generate-cdk-typescript.prompt.md mentions L2 constructs."""
        content = get_template_content("prompts/generate-cdk-typescript.prompt.md")

        assert "L2" in content or "construct" in content.lower()

    def test_cdk_typescript_has_stack_organization(self) -> None:
        """generate-cdk-typescript.prompt.md has stack organization guidance."""
        content = get_template_content("prompts/generate-cdk-typescript.prompt.md")

        assert "Stack" in content

    def test_cdk_python_has_type_hints_guidance(self) -> None:
        """generate-cdk-python.prompt.md mentions type hints."""
        content = get_template_content("prompts/generate-cdk-python.prompt.md")

        assert "type hint" in content.lower() or "typing" in content.lower() or ": str" in content
