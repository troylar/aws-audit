# Environment Variables

Configure most CLI options via environment variables. Useful for CI/CD pipelines or setting personal defaults.

## Available Variables

### General

| Variable | Description | Equivalent Flag |
|----------|-------------|-----------------|
| `AWSINV_SNAPSHOT_ID` | Default snapshot name for queries | `--snapshot` |
| `AWSINV_COLLECTION_ID` | Default collection name | `--collection` |
| `AWSINV_REGION` | Default region (repeatable via CLI: `-r us-east-1 -r us-west-2`) | `--region` |
| `AWSINV_PROFILE` | AWS CLI profile to use | `--profile` |
| `AWSINV_STORAGE_PATH` | Custom path for SQLite DB and logs | `--storage-path` |

### LLM Provider

| Variable | Description | Equivalent Flag |
|----------|-------------|-----------------|
| `AWSINV_LLM_PROVIDER` | LLM provider: `bedrock` (default) or `openai` | `--provider` |
| `AWSINV_BEDROCK_MODEL_ID` | Bedrock model ID for IaC generation | `--model-id` |
| `AWSINV_BEDROCK_REGION` | AWS region for Bedrock API | `--region` |
| `AWSINV_OPENAI_API_KEY` | OpenAI API key (required when provider is `openai`) | `--openai-api-key` |
| `AWSINV_OPENAI_MODEL` | OpenAI model name (default: `gpt-4o`) | `--openai-model` |
| `AWSINV_OPENAI_BASE_URL` | Custom OpenAI-compatible API base URL | `--openai-base-url` |

## Usage Example

```bash
export AWSINV_COLLECTION_ID="prod-baseline"
export AWSINV_REGION="us-east-1"

# These commands will now use the exported values automatically
awsinv snapshot create daily-snap
awsinv delta --snapshot previous-snap
```

## CI/CD Pipeline Example

```yaml
env:
  AWSINV_REGION: us-east-1
  AWSINV_STORAGE_PATH: /tmp/inventory

steps:
  - run: awsinv snapshot create ci-baseline
  - run: awsinv security scan --output report.json
```

## OpenAI Provider Example

```bash
export AWSINV_LLM_PROVIDER="openai"
export AWSINV_OPENAI_API_KEY="sk-..."

# These commands will now use OpenAI instead of Bedrock
awsinv generate terraform my-snapshot
awsinv guardrails generate "S3 buckets must have encryption"
awsinv patterns generate "serverless REST API"
```

You can also use an OpenAI-compatible API (e.g., Azure OpenAI, local models):

```bash
export AWSINV_LLM_PROVIDER="openai"
export AWSINV_OPENAI_API_KEY="your-key"
export AWSINV_OPENAI_BASE_URL="https://your-endpoint.openai.azure.com/v1"
export AWSINV_OPENAI_MODEL="gpt-4o"
```
