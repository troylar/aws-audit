# Contributing

## Getting Started

```bash
# Clone and install
git clone https://github.com/troylar/aws-inventory-manager.git
cd aws-inventory-manager
pip install -e ".[dev]"
```

## Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Run tests: `invoke test`
4. Run quality checks: `invoke quality`
5. Submit a pull request

## Commands

```bash
# Run all tests with coverage
invoke test

# Unit tests only (faster)
invoke test-unit

# Code quality (lint + typecheck)
invoke quality

# Auto-fix lint issues
invoke quality --fix

# Build package
invoke build
```

## Test Coverage

2400+ tests, 61% overall coverage. Cleanup module: 98%+ coverage. Guardrails module: 75%+ coverage.

See [Testing](testing.md) for the full testing strategy.
