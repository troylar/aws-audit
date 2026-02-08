# AWS Baseline Tests

Comprehensive test suite for the AWS Baseline Snapshot & Delta Tracking tool.

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures
├── unit/                            # Unit tests
│   ├── test_collection_model.py     # Collection model tests
│   └── test_collection_storage.py   # CollectionStorage service tests
└── integration/                     # Integration tests
    └── test_collection_cli.py       # CLI command tests
```

## Running Tests

### Quick Start

```bash
# Run all tests with coverage
invoke test

# Run unit tests only
invoke test-unit

# Run integration tests only
invoke test-integration

# Verbose output
invoke test --verbose

# Generate HTML coverage report
invoke coverage-report
```

### Using pytest directly

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_collection_model.py

# Specific test class
pytest tests/unit/test_collection_model.py::TestCollectionModel

# Specific test
pytest tests/unit/test_collection_model.py::TestCollectionModel::test_collection_creation

# With coverage
pytest --cov=src --cov-report=term-missing

# With verbose output
pytest -v
```

## Test Categories

### Unit Tests

Unit tests focus on individual components in isolation, using mocks for dependencies.

**test_collection_model.py** (28 tests)
- Collection creation and initialization
- Serialization (to_dict/from_dict)
- Snapshot management (add/remove)
- Validation rules (name, account_id, etc.)
- Edge cases and error conditions

**test_collection_storage.py** (25 tests)
- File I/O operations
- CRUD operations (load, save, delete)
- Account-scoped queries
- Default collection handling
- Atomic writes and data integrity
- Error handling and edge cases

### Integration Tests

Integration tests are documented as manual test scenarios due to the complexity of mocking file system and AWS credential interactions.

**test_collection_cli_manual.py** - Manual test scenarios:
- `collection create` command (basic, with filters, error cases)
- `collection list` command (empty, multiple collections)
- `collection show` command (details, nonexistent)
- `collection delete` command (with force, last collection protection)
- `collection migrate` command (no snapshots, with snapshots)
- Complete workflows (full lifecycle testing)

**Why Manual?**
- Complex environment setup required (AWS credentials, file system isolation)
- Unit tests provide 100% coverage of business logic
- Manual tests ensure end-to-end functionality works in real environments
- Automated CLI testing would require extensive mocking that duplicates unit test logic

## Test Coverage

Current test coverage goals:

- **Overall**: 80%+ coverage
- **Models**: 95%+ coverage (high criticality)
- **Storage**: 90%+ coverage (high criticality)
- **CLI**: 75%+ coverage (integration focus)

View coverage report:
```bash
invoke coverage-report
```

## Writing Tests

### Test Fixtures

Shared fixtures are defined in `conftest.py`:

- `temp_dir` - Temporary directory for file operations
- `sample_collection_data` - Sample collection dictionary
- `sample_snapshot_data` - Sample snapshot dictionary
- `mock_aws_identity` - Mock AWS credentials

### Example Test

```python
def test_create_collection(temp_dir):
    """Test creating a collection."""
    storage = CollectionStorage(temp_dir)

    collection = Collection(
        name="test",
        account_id="123456789012"
    )

    storage.save(collection)

    retrieved = storage.get_by_name("test", "123456789012")
    assert retrieved.name == "test"
```

### Test Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*` (optional, for grouping)
- Test functions: `test_*`
- Use descriptive names that explain what is being tested

### Mocking

Use `pytest-mock` and `unittest.mock` for mocking:

```python
from unittest.mock import patch, MagicMock

def test_with_mock(mocker):
    mock_validate = mocker.patch('src.cli.main.validate_credentials')
    mock_validate.return_value = {"account_id": "123456789012"}
    # Test code here
```

## Continuous Integration

Tests run automatically in CI pipelines:

```bash
# Run all CI checks
invoke ci
```

This runs:
1. Code formatting check (black)
2. Linting (ruff)
3. Type checking (mypy)
4. All tests with coverage

## Troubleshooting

### Import Errors

If you see import errors, ensure the package is installed in development mode:
```bash
pip install -e ".[dev]"
```

### AWS Credentials

Integration tests mock AWS credentials. No real AWS credentials are required.

### Temporary Files

Tests use temporary directories that are automatically cleaned up. If tests fail, check for leftover files in `/tmp/`.

### Coverage Not Showing

Ensure pytest-cov is installed:
```bash
pip install pytest-cov
```

## Adding New Tests

When adding new features:

1. **Write unit tests first** - Test models and business logic
2. **Add integration tests** - Test CLI commands end-to-end
3. **Update conftest.py** - Add shared fixtures if needed
4. **Run coverage** - Ensure coverage remains above 80%
5. **Update this README** - Document new test files

## Best Practices

- **Keep tests isolated** - Each test should be independent
- **Use fixtures** - Share setup code via fixtures
- **Mock external dependencies** - Don't make real AWS API calls
- **Test edge cases** - Invalid input, empty data, errors
- **Clear assertions** - One logical assertion per test
- **Descriptive names** - Test name should explain what is tested
- **Fast tests** - Unit tests should run in milliseconds

## Test Execution Time

Expected execution times:
- Unit tests: < 5 seconds
- Integration tests: < 30 seconds
- Full suite: < 60 seconds

If tests are slower, consider:
- Reducing file I/O in unit tests
- Using more mocks
- Parallelizing with pytest-xdist
