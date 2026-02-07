# Multi-Account Support

## Option 1: AWS Config Aggregator (Recommended)

If you have a [Config Aggregator](https://docs.aws.amazon.com/config/latest/developerguide/aggregate-data.html) set up (common with AWS Organizations):

```bash
# Query all accounts via the aggregator
awsinv snapshot create org-wide --config-aggregator my-aggregator
```

**Prerequisites:**

- Config Aggregator already configured in your management account
    - See [Setting Up an Aggregator Using the Console](https://docs.aws.amazon.com/config/latest/developerguide/setup-aggregator-console.html)
- Appropriate IAM permissions to query the aggregator (see [IAM Permissions](../reference/iam-permissions.md))

## Option 2: Profile Switching

```bash
# Snapshot each account separately
awsinv snapshot create account-dev --profile dev-account
awsinv snapshot create account-prod --profile prod-account
```

## Option 3: Cross-Account Roles

Configure your AWS CLI with cross-account role assumption, then use profiles as above.
