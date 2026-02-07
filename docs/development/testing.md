# Testing Strategy

## Running Tests

```bash
# Run all tests
invoke test

# Run unit tests only (recommended for CI/CD)
invoke test-unit

# Run with verbose output
invoke test --verbose

# Run all quality checks + tests
invoke ci
```

## Test Coverage Summary

**Unit Tests: 2400+ PASSING**

**Coverage by Module:**

- `src/models/inventory.py`: **100% coverage**
- `src/models/resource.py`: **97% coverage**
- `src/models/snapshot.py`: **100% coverage**
- `src/snapshot/inventory_storage.py`: **90% coverage**
- `src/snapshot/storage.py`: **99% coverage**
- `src/snapshot/filter.py`: **94% coverage**
- **Overall Project**: **61% coverage**

## Test Files

```
tests/
+-- conftest.py                         # Shared test fixtures
+-- unit/                               # Unit tests (automated)
|   +-- test_inventory_model.py         # Model tests (28 tests)
|   +-- test_inventory_storage.py       # Storage tests (25 tests)
|   +-- test_resource_model.py          # Resource model tests (29 tests)
|   +-- test_snapshot_model.py          # Snapshot model tests (20 tests)
|   +-- test_resource_filter.py         # Filter tests (20 tests)
|   +-- test_snapshot_storage.py        # Storage tests (27 tests)
|   +-- ...
+-- integration/                        # Integration tests
    +-- test_inventory_cli.py           # Placeholder
    +-- test_inventory_cli_manual.py    # Manual test scenarios
```

## Test Philosophy

This project follows a **pragmatic testing strategy**:

1. **Unit Tests First**: Comprehensive coverage of all business logic
2. **Integration via Manual QA**: Real-world testing in actual environments
3. **Fast CI/CD**: Unit tests run in seconds
4. **High Confidence**: 90%+ coverage on critical paths (models, storage)

## CI/CD Integration

```bash
invoke ci
```

This runs:

1. Code formatting check (ruff)
2. Linting (ruff)
3. Type checking (mypy)
4. Unit tests with coverage
5. Coverage report

## Coverage Goals

| Module | Goal | Actual | Status |
|--------|------|--------|--------|
| Inventory Model | 95%+ | 100% | Exceeded |
| Resource Model | 95%+ | 97% | Exceeded |
| Snapshot Model | 95%+ | 100% | Exceeded |
| Inventory Storage | 90%+ | 90% | Met |
| Snapshot Storage | 90%+ | 99% | Exceeded |
| Resource Filter | 90%+ | 94% | Exceeded |
| Cleanup Module | 95%+ | 98%+ | Exceeded |
| Guardrails Module | 70%+ | 75%+ | Exceeded |

## Adding New Tests

When adding new features:

1. **Write unit tests first** -- Test models and business logic
2. **Document integration scenarios** -- Add to manual test file
3. **Run coverage** -- Ensure coverage stays high

## Troubleshooting

### Tests Fail

```bash
invoke clean
pip install -e ".[dev]"
invoke test
```

### Import Errors

```bash
pip install -e ".[dev]"
```

### Coverage Issues

```bash
rm -rf .coverage htmlcov/
invoke test
```

## Best Practices

**DO:**

- Write unit tests for all business logic
- Use fixtures for test data
- Mock external dependencies (AWS, file system)
- Keep tests fast
- Test edge cases and error conditions

**DON'T:**

- Make real AWS API calls in tests
- Write slow integration tests without clear value
- Duplicate unit test logic in integration tests
- Write tests that depend on other tests
- Use production data in tests
