# Installation

## Prerequisites

Before installing, ensure you have:

- **Python 3.11+** (3.11, 3.12, 3.13, or 3.14)
- **AWS CLI configured** with credentials (`aws configure` or environment variables)
- **Sufficient IAM permissions** (see [IAM Permissions](../reference/iam-permissions.md))

To verify your setup:

```bash
python3 --version            # Should be 3.11+ (use 'python' on some systems)
aws sts get-caller-identity  # Should return your account info
```

## Install from PyPI

```bash
pip install aws-inventory-manager
```

Or with [pipx](https://pypa.github.io/pipx/) for isolated installation:

```bash
pipx install aws-inventory-manager
```

## Optional Extras

Install optional dependencies for specific features:

```bash
# Web UI (Resource Explorer)
pip install aws-inventory-manager[web]

# IaC Generation (Terraform/CDK)
pip install aws-inventory-manager[generate]

# OpenAI LLM provider (alternative to AWS Bedrock)
pip install aws-inventory-manager[openai]

# Multiple extras
pip install aws-inventory-manager[generate,openai]

# All extras
pip install aws-inventory-manager[web,generate,openai]
```

## Development Installation

```bash
git clone https://github.com/troylar/aws-inventory-manager.git
cd aws-inventory-manager
pip install -e ".[dev]"
```

## Verify Installation

```bash
awsinv --help
awsinv version
```
