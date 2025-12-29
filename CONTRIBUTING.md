# Contributing to cluster-execution-mcp

Thank you for your interest in contributing to cluster-execution-mcp!

## Code of Conduct

Be respectful and constructive. We're all here to build great software together.

## Getting Started

### Prerequisites

- Python 3.10+
- SSH access configured (for testing actual cluster operations)
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/marc-shade/cluster-execution-mcp.git
cd cluster-execution-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Verify installation
python -c "from cluster_execution_mcp.server import main; print('OK')"
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=cluster_execution_mcp --cov-report=html

# Run specific test file
pytest tests/test_config.py -v

# Run tests matching pattern
pytest tests/ -k "test_validate" -v
```

## How to Contribute

### Reporting Bugs

1. Check existing issues to avoid duplicates
2. Use the bug report template
3. Include:
   - Python version
   - OS and architecture
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant logs/error messages

### Suggesting Features

1. Open an issue with the feature request template
2. Describe the use case
3. Explain why existing functionality doesn't suffice
4. Propose implementation approach (optional)

### Submitting Changes

1. **Fork the repository**

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the code style guidelines below
   - Add tests for new functionality
   - Update documentation as needed

4. **Run tests**
   ```bash
   pytest tests/ -v
   ```

5. **Commit with clear messages**
   ```bash
   git commit -m "Add feature: description of change"
   ```

6. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open Pull Request**
   - Fill out the PR template
   - Link related issues
   - Describe changes and testing done

## Code Style

### Python Style

- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use `ruff` for linting and formatting

```bash
# Check code style
ruff check .

# Auto-format
ruff format .
```

### Type Hints

```python
# Good
def route_command(command: str, requires_os: str | None = None) -> dict[str, Any]:
    ...

# Avoid
def route_command(command, requires_os=None):
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def cluster_bash(command: str, requires_os: str | None = None) -> dict[str, Any]:
    """Execute bash command with automatic cluster routing.

    Routes commands to optimal nodes based on load and requirements.
    Heavy commands are automatically offloaded to least-loaded nodes.

    Args:
        command: Bash command to execute
        requires_os: Force specific OS (linux/darwin)

    Returns:
        dict containing:
            - success: bool
            - output: str
            - node: str (which node executed)
            - execution_time: float

    Raises:
        ValidationError: If command contains dangerous patterns
        SSHConnectionError: If unable to reach target node
    """
```

### Error Handling

```python
# Good - specific exceptions
try:
    result = execute_command(cmd)
except SSHConnectionError as e:
    logger.error(f"SSH failed: {e}")
    return {"success": False, "error": str(e)}
except CommandTimeoutError as e:
    logger.warning(f"Command timed out: {e}")
    return {"success": False, "error": "timeout"}

# Avoid - bare except
try:
    result = execute_command(cmd)
except:
    return {"success": False}
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed debugging info")
logger.info("Normal operation events")
logger.warning("Something unexpected but handled")
logger.error("Operation failed")
```

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py       # Shared fixtures
├── test_config.py    # Config module tests
├── test_router.py    # Router module tests
└── test_server.py    # Server and tool tests
```

### Writing Tests

```python
import pytest
from cluster_execution_mcp.config import validate_command

class TestValidateCommand:
    """Tests for command validation."""

    def test_safe_command_passes(self):
        """Safe commands should pass validation."""
        assert validate_command("ls -la") == True

    def test_dangerous_command_blocked(self):
        """Dangerous patterns should be blocked."""
        with pytest.raises(ValidationError):
            validate_command("rm -rf /")

    @pytest.mark.parametrize("command,expected", [
        ("echo hello", True),
        ("rm -rf /*", False),
    ])
    def test_various_commands(self, command, expected):
        """Test various command patterns."""
        result = validate_command(command)
        assert result == expected
```

### Mock External Dependencies

```python
from unittest.mock import patch, MagicMock

def test_ssh_execution():
    """Test SSH command execution with mocked subprocess."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"success",
            stderr=b""
        )

        result = execute_remote("hostname", "192.168.1.100")

        assert result["success"] == True
        mock_run.assert_called_once()
```

## Project Structure

```
cluster-execution-mcp/
├── src/cluster_execution_mcp/
│   ├── __init__.py      # Package exports
│   ├── config.py        # Configuration and validation
│   ├── router.py        # Task routing logic
│   └── server.py        # MCP server implementation
├── tests/               # Test suite
├── pyproject.toml       # Package configuration
├── README.md            # Documentation
├── SECURITY.md          # Security policy
├── CONTRIBUTING.md      # This file
└── LICENSE              # MIT License
```

## Release Process

Releases are managed by maintainers:

1. Update version in `pyproject.toml`
2. Update CHANGELOG in README.md
3. Create GitHub release with tag
4. CI automatically publishes to PyPI (if configured)

## Questions?

- Open a GitHub issue for questions
- Tag issues with `question` label
- Check existing issues and documentation first

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
