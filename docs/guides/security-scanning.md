# Security Scanning

Run automated security checks against your AWS resources based on CIS Benchmark alignment.

## Running a Security Scan

```bash
# Scan all resources
awsinv security scan

# Filter by severity
awsinv security scan --severity HIGH

# Export results
awsinv security scan --export security-report.json
```

## Security Checks

The scanner includes 12+ CIS-aligned checks:

| Category | Examples |
|----------|----------|
| **S3** | Public buckets, missing encryption, disabled versioning |
| **EC2** | Open security group ports, public IPs |
| **IAM** | Credential age, overly permissive policies |
| **RDS** | Public accessibility, missing encryption |
| **Network** | Open SSH/RDP access from 0.0.0.0/0 |

## Severity Levels

| Severity | Description |
|----------|-------------|
| `CRITICAL` | Immediate security risk, must fix |
| `HIGH` | Significant risk, fix soon |
| `MEDIUM` | Notable risk, should address |
| `LOW` | Minor issue, fix when convenient |

Each finding includes remediation guidance.
