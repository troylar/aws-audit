# Lambda Code Management

Work with Lambda function deployment code stored in snapshots.

## Listing Lambda Functions

```bash
awsinv lambda list [--snapshot my-snapshot]
```

Shows all Lambda functions with code info including size, hash, and storage status.

## Extracting Code

```bash
# Extract a single function
awsinv lambda extract my-function

# Extract all functions
awsinv lambda extract --all --output ./lambda-code

# From a specific snapshot
awsinv lambda extract my-function --snapshot my-snapshot
```

## Viewing Code

```bash
# View code with syntax highlighting
awsinv lambda show my-function

# Just the handler file
awsinv lambda show my-function --handler
```

Supports Python, JavaScript, TypeScript, Go, Ruby, Java, and more.

## Comparing Code Between Snapshots

```bash
awsinv lambda diff my-function --snapshot1 snap-before --snapshot2 snap-after
```

Shows a unified diff output of code changes between two snapshots.

## Fetching Code for Existing Snapshots

```bash
# Fetch missing code
awsinv lambda fetch my-snapshot

# Specific function only
awsinv lambda fetch my-snapshot --function my-func

# Re-fetch all code
awsinv lambda fetch my-snapshot --force

# Store inline up to 50MB
awsinv lambda fetch my-snapshot --max-size 50
```

## Code Storage Options

When creating snapshots, control how Lambda code is stored:

```bash
# Default: Store code inline up to 10MB, hash-only for larger
awsinv snapshot create my-snap --region us-east-1

# Store code inline up to 50MB
awsinv snapshot create my-snap --region us-east-1 --lambda-code-max-size 50

# Store all code externally (none inline)
awsinv snapshot create my-snap --region us-east-1 --lambda-code-max-size 0

# Store all code inline regardless of size
awsinv snapshot create my-snap --region us-east-1 --lambda-code-max-size -1
```

Large packages are stored to `~/.snapshots/lambda-code/<snapshot>/` and automatically loaded when needed.
