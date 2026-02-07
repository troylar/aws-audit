# CI/CD Integration

Use guardrails as a compliance gate in your CI/CD pipeline.

## Standalone Check

The `guardrails check` command evaluates guardrails without generating IaC, making it ideal for CI/CD:

```bash
# Check a snapshot
awsinv guardrails check my-snapshot

# Check from a file
awsinv guardrails check --from-file inventory.yaml

# Use custom policy and strict mode
awsinv guardrails check my-snapshot --policy ./policy.yaml --strict

# Output as JSON
awsinv guardrails check my-snapshot --format json

# Save report to file
awsinv guardrails check my-snapshot --format json --output report.json
```

## Exit Codes

| Exit Code | Meaning |
|-----------|---------|
| `0` | All checks passed |
| `1` | Blocking violations found |

## Pipeline Example

```bash
# Exit code 0 = all checks passed
# Exit code 1 = blocking violations found
awsinv guardrails check my-snapshot --format json > report.json
if [ $? -ne 0 ]; then
  echo "Compliance check failed!"
  exit 1
fi
```

## GitHub Actions Example

```yaml
- name: Run compliance check
  run: |
    awsinv guardrails check my-snapshot \
      --policy ./guardrails/policy.yaml \
      --strict \
      --format json \
      --output compliance-report.json

- name: Upload compliance report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: compliance-report
    path: compliance-report.json
```

## Output Formats

=== "Table (default)"

    Human-readable table output for interactive use.

=== "JSON"

    ```json
    {
      "summary": {
        "total": 10,
        "passed": 8,
        "failed": 2,
        "warnings": 1
      },
      "violations": [...]
    }
    ```

=== "YAML"

    ```yaml
    summary:
      total: 10
      passed: 8
      failed: 2
      warnings: 1
    violations: [...]
    ```
