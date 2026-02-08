# Environment Variables

Configure most CLI options via environment variables. Useful for CI/CD pipelines or setting personal defaults.

## Available Variables

| Variable | Description | Equivalent Flag |
|----------|-------------|-----------------|
| `AWSINV_SNAPSHOT_ID` | Default snapshot name for queries | `--snapshot` |
| `AWSINV_COLLECTION_ID` | Default collection name | `--collection` |
| `AWSINV_REGION` | Default region (repeatable via CLI: `-r us-east-1 -r us-west-2`) | `--region` |
| `AWSINV_PROFILE` | AWS CLI profile to use | `--profile` |
| `AWSINV_STORAGE_PATH` | Custom path for SQLite DB and logs | `--storage-path` |
| `AWSINV_BEDROCK_MODEL_ID` | Bedrock model ID for IaC generation | `--model-id` |
| `AWSINV_BEDROCK_REGION` | AWS region for Bedrock API | `--region` |

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
