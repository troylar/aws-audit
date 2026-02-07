"""Formula-based condition evaluator using simpleeval.

Provides a Python-like syntax for guardrail conditions:
    - Simple checks: "Encryption exists", "Tags.Environment == 'prod'"
    - Boolean logic: "Encryption exists and Versioning.Status == 'Enabled'"
    - If/then: "if PublicAccess then Encryption exists"
    - Array iteration: "all(rule.Description exists for rule in IpPermissions)"
    - Counts: "count(AvailabilityZones) >= 2"
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from simpleeval import EvalWithCompoundTypes, SimpleEval
except ImportError:
    SimpleEval = None  # type: ignore
    EvalWithCompoundTypes = None  # type: ignore


class FormulaError(Exception):
    """Raised when formula evaluation fails."""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        super().__init__(message)
        self.suggestion = suggestion


# Common mistakes and their suggestions
# Format: (pattern, (correct_form, suggestion))
# Use regex patterns for word boundary matching
COMMON_MISTAKES_PATTERNS = [
    # Typos in function names - use word boundaries to avoid false positives
    (r"\bexist\b(?!s)", "exists", "Did you mean 'exists'? Use: 'Attribute exists'"),
    (r"\bexsits\b", "exists", "Did you mean 'exists'? Use: 'Attribute exists'"),
    (r"\bexsist\b", "exists", "Did you mean 'exists'? Use: 'Attribute exists'"),
    (r"\bcnt\b", "count", "Did you mean 'count'? Use: count(list)"),
    (r"\blength\b", "len", "Use 'len()' or 'count()' for length"),
    (r"\bmatch\b(?!es)", "matches", "Did you mean 'matches'? Use: matches(value, pattern)"),
    (r"\bcontain\b(?!s)", "contains", "Did you mean 'contains'? Use: contains(container, item)"),
    (r"\benviron\b", "env", "Use 'env()' to access context variables: env('KEY')"),
    (r"\bgetenv\b", "env", "Use 'env()' to access context variables: env('KEY')"),
]

# Simple string-based mistakes (operators)
COMMON_MISTAKES = {
    # Common operator mistakes
    "===": ("==", "Use '==' for equality comparison, not '==='"),
    "!==": ("!=", "Use '!=' for inequality comparison, not '!=='"),
    "&&": ("and", "Use 'and' for logical AND, not '&&'"),
    "||": ("or", "Use 'or' for logical OR, not '||'"),
}

# Patterns that indicate common mistakes
MISTAKE_PATTERNS = [
    # Missing quotes around string values
    (r"==\s+[a-z][a-z0-9_-]+\s*(?:and|or|$)", "String values need quotes. Use: get('attr') == 'value'"),
    # Using = instead of ==
    (r"(?<![=!<>])=(?!=)", "Use '==' for comparison, not '='"),
    # Using dot notation without get()
    (
        r"(?<!['\"])\b([A-Z][a-z]+(?:\.[A-Z][a-z]+)+)\s*(?:==|!=|>|<|>=|<=|in\b)",
        "Wrap attribute paths in get(): get('Path.To.Attr')",
    ),
]


def _get_nested_value(obj: Any, path: str) -> Any:
    """Get a nested value using dot notation.

    Args:
        obj: Object to traverse (dict or object with attributes).
        path: Dot-separated path (e.g., "Tags.Environment").

    Returns:
        The value at the path, or None if not found.
    """
    parts = path.split(".")
    current = obj

    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None

    return current


def _exists(value: Any) -> bool:
    """Check if a value exists (is not None and not empty)."""
    if value is None:
        return False
    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return False
    return True


def _count(value: Any) -> int:
    """Return count/length of a value."""
    if value is None:
        return 0
    if isinstance(value, (list, tuple, dict, str)):
        return len(value)
    return 1


def _matches(value: Any, pattern: str) -> bool:
    """Check if value matches a regex pattern."""
    if value is None:
        return False
    try:
        return bool(re.match(pattern, str(value)))
    except re.error:
        return False


def _contains(container: Any, item: Any) -> bool:
    """Check if container contains item."""
    if container is None:
        return False
    try:
        return item in container
    except TypeError:
        return False


def _preprocess_formula(formula: str, config: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Preprocess formula to handle special syntax.

    Transforms:
        - "X exists" -> "exists(X)"
        - "if X then Y" -> "(not (X) or (Y))"
        - Attribute access -> config lookups

    Args:
        formula: The formula string.
        config: Resource configuration dict.

    Returns:
        Tuple of (processed_formula, variables_dict).
    """
    processed = formula
    variables: Dict[str, Any] = {}

    # Keywords that should not be treated as attribute names
    keywords = {"and", "or", "not", "in", "is", "if", "then", "else", "for", "true", "false", "none", "null"}

    def replace_exists(match: re.Match) -> str:
        """Replace X exists pattern, but skip keywords."""
        attr = match.group(1)
        if attr.lower() in keywords:
            return match.group(0)  # Return unchanged
        return f"__EXISTS__(get('{attr}'))"

    def replace_not_exists(match: re.Match) -> str:
        """Replace X not exists pattern, but skip keywords."""
        attr = match.group(1)
        if attr.lower() in keywords:
            return match.group(0)  # Return unchanged
        return f"not __EXISTS__(get('{attr}'))"

    # Handle "X not exists" pattern -> "not __EXISTS__(get('X'))"
    # Use placeholder to prevent double-processing, then restore
    not_exists_pattern = r"\b([\w.]+)\s+not\s+exists\b"
    processed = re.sub(
        not_exists_pattern,
        replace_not_exists,
        processed,
        flags=re.IGNORECASE,
    )

    # Handle "X exists" pattern -> "__EXISTS__(get('X'))"
    # Match: word.path exists (but not inside function calls)
    exists_pattern = r"\b([\w.]+)\s+exists\b"
    processed = re.sub(
        exists_pattern,
        replace_exists,
        processed,
        flags=re.IGNORECASE,
    )

    # Restore exists function name
    processed = processed.replace("__EXISTS__", "exists")

    # Handle "if X then Y" pattern -> "(not (X) or (Y))"
    # This implements logical implication: if A then B ≡ ¬A ∨ B
    if_then_pattern = r"\bif\s+(.+?)\s+then\s+(.+?)(?:\s*$|\s+else\s+)"
    match = re.search(if_then_pattern, processed, re.IGNORECASE)
    if match:
        condition = match.group(1)
        consequence = match.group(2)
        # Recursively preprocess the inner parts
        processed = re.sub(
            if_then_pattern,
            f"(not ({condition}) or ({consequence}))",
            processed,
            flags=re.IGNORECASE,
        )

    # Handle bare attribute access (not in quotes, not a function call)
    # Convert "Tags.Environment" to "get('Tags.Environment')"
    # But preserve things like function names, operators, quoted strings
    def replace_attr(match: re.Match) -> str:
        attr = match.group(0)
        # Skip if it's a known function or keyword
        known = {
            "and",
            "or",
            "not",
            "in",
            "is",
            "if",
            "then",
            "else",
            "for",
            "True",
            "False",
            "None",
            "true",
            "false",
            "null",
            "exists",
            "count",
            "matches",
            "contains",
            "get",
            "all",
            "any",
            "none",
            "len",
            "str",
            "int",
            "float",
            "bool",
        }
        if attr.lower() in {k.lower() for k in known}:
            return attr
        # Skip if it looks like a function call (followed by parenthesis)
        return attr

    # Add config accessor function
    def get_value(path: str) -> Any:
        return _get_nested_value(config, path)

    variables["get"] = get_value
    variables["config"] = config

    return processed, variables


def evaluate_formula(
    formula: str,
    config: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """Evaluate a formula against a resource configuration.

    Args:
        formula: The formula string to evaluate.
        config: Resource configuration dictionary.
        context: Optional context dict for cross-resource references.
            Accessed via env('key') in formulas.
            Example: {"ACCOUNT_VPC": "vpc-123", "SHARED_ROLE": "arn:aws:iam::..."}

    Returns:
        Tuple of (passed: bool, failure_reason: str).

    Raises:
        FormulaError: If the formula cannot be evaluated.

    Examples:
        # Check VPC matches account-specific value
        evaluate_formula(
            "VpcId == env('ACCOUNT_VPC')",
            {"VpcId": "vpc-123"},
            context={"ACCOUNT_VPC": "vpc-123"}
        )

        # Check role ARN matches shared role
        evaluate_formula(
            "RoleArn == env('SHARED_IAM_ROLE')",
            {"RoleArn": "arn:aws:iam::123:role/shared"},
            context={"SHARED_IAM_ROLE": "arn:aws:iam::123:role/shared"}
        )
    """
    if SimpleEval is None:
        raise FormulaError("simpleeval is required for formula evaluation. Install with: pip install simpleeval")

    context = context or {}

    try:
        # Preprocess the formula
        processed, variables = _preprocess_formula(formula, config)

        # Create evaluator with safe functions
        evaluator = EvalWithCompoundTypes()

        # Add custom functions
        evaluator.functions = {
            "exists": _exists,
            "count": _count,
            "matches": _matches,
            "contains": _contains,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "all": all,
            "any": any,
            "abs": abs,
            "min": min,
            "max": max,
        }

        # Add variables
        evaluator.names = variables

        # Add helper to access config values
        def get_config_value(path: str) -> Any:
            return _get_nested_value(config, path)

        evaluator.functions["get"] = get_config_value

        # Add env() function for cross-resource context
        def get_env_value(key: str, default: Any = None) -> Any:
            """Get a value from the context dict.

            Used for account-specific values like VPC IDs, shared roles, etc.
            Falls back to environment variables if not in context.
            """
            if key in context:
                return context[key]
            # Fall back to OS environment variable
            import os

            return os.environ.get(key, default)

        evaluator.functions["env"] = get_env_value

        # Evaluate
        result = evaluator.eval(processed)

        # Convert to boolean
        if isinstance(result, bool):
            passed = result
        else:
            # Truthy evaluation
            passed = bool(result)

        if passed:
            return True, ""
        else:
            return False, f"Condition not met: {formula}"

    except Exception as e:
        raise FormulaError(f"Failed to evaluate formula '{formula}': {e}") from e


def validate_formula(formula: str) -> List[str]:
    """Validate a formula without evaluating it.

    Args:
        formula: The formula string to validate.

    Returns:
        List of validation errors (empty if valid).
    """
    errors: List[str] = []

    if not formula or not formula.strip():
        errors.append("Formula cannot be empty")
        return errors

    # Check for pattern-based common mistakes (typos)
    for pattern, correct, suggestion in COMMON_MISTAKES_PATTERNS:
        if re.search(pattern, formula, re.IGNORECASE):
            errors.append(f"Possible typo. {suggestion}")

    # Check for simple string-based mistakes (operators)
    for mistake, (_, suggestion) in COMMON_MISTAKES.items():
        if mistake in formula:
            errors.append(f"Possible mistake: '{mistake}'. {suggestion}")

    # Check for pattern-based mistakes
    for pattern, suggestion in MISTAKE_PATTERNS:
        if re.search(pattern, formula):
            errors.append(suggestion)

    # Check for balanced parentheses
    depth = 0
    paren_positions: List[int] = []
    for i, char in enumerate(formula):
        if char == "(":
            depth += 1
            paren_positions.append(i)
        elif char == ")":
            depth -= 1
            if paren_positions:
                paren_positions.pop()
        if depth < 0:
            errors.append(f"Unbalanced parentheses: extra closing ')' at position {i}")
            break
    if depth > 0:
        positions = ", ".join(str(p) for p in paren_positions[:3])
        errors.append(f"Unbalanced parentheses: {depth} unclosed '(' at position(s): {positions}")

    # Check for balanced quotes
    in_single = False
    in_double = False
    single_start = -1
    double_start = -1
    for i, char in enumerate(formula):
        if char == "'" and not in_double:
            if not in_single:
                single_start = i
            in_single = not in_single
        elif char == '"' and not in_single:
            if not in_double:
                double_start = i
            in_double = not in_double
    if in_single:
        errors.append(f"Unbalanced single quote starting at position {single_start}")
    if in_double:
        errors.append(f"Unbalanced double quote starting at position {double_start}")

    # Try to parse with a dummy config
    if SimpleEval is not None and not errors:
        try:
            evaluate_formula(formula, {"_test": True})
        except FormulaError as e:
            error_str = str(e)
            # Parse simpleeval errors to give better messages
            suggestion = _get_error_suggestion(error_str, formula)
            if suggestion:
                errors.append(suggestion)
            elif "name" not in error_str.lower() and "undefined" not in error_str.lower():
                errors.append(str(e))
        except Exception as e:
            errors.append(f"Parse error: {e}")

    return errors


def _get_error_suggestion(error_str: str, formula: str) -> Optional[str]:
    """Get a helpful suggestion based on the error message.

    Args:
        error_str: The error message from simpleeval.
        formula: The original formula.

    Returns:
        A suggestion string, or None if no suggestion available.
    """
    error_lower = error_str.lower()

    # Unknown function
    if "function" in error_lower and ("not defined" in error_lower or "unknown" in error_lower):
        # Try to extract function name
        match = re.search(r"function['\"]?\s*['\"]?(\w+)", error_lower)
        if match:
            func_name = match.group(1)
            valid_funcs = [
                "get",
                "exists",
                "count",
                "matches",
                "contains",
                "env",
                "len",
                "str",
                "int",
                "float",
                "bool",
                "all",
                "any",
                "abs",
                "min",
                "max",
            ]
            suggestions = [f for f in valid_funcs if f.startswith(func_name[0].lower())]
            if suggestions:
                return (
                    f"Unknown function '{func_name}'. Did you mean: {', '.join(suggestions)}? "
                    f"Available functions: {', '.join(valid_funcs)}"
                )
            return f"Unknown function '{func_name}'. Available functions: {', '.join(valid_funcs)}"

    # Syntax error
    if "syntax" in error_lower:
        # Check for common syntax issues
        if "==" in formula and "= =" in formula:
            return "Syntax error: Remove space in '= =', use '=='"
        return "Syntax error in formula. Check parentheses, quotes, and operators."

    # Name not defined (usually a bare string)
    if "name" in error_lower and "not defined" in error_lower:
        match = re.search(r"name\s*['\"](\w+)['\"]", error_lower)
        if match:
            name = match.group(1)
            return f"Undefined name '{name}'. String values need quotes: '{name}'. Attribute access: get('{name}')"

    return None


def format_formula_errors(errors: List[str]) -> str:
    """Format validation errors for display.

    Args:
        errors: List of error messages.

    Returns:
        Formatted error string with bullets and newlines.
    """
    if not errors:
        return ""
    if len(errors) == 1:
        return f"Formula error: {errors[0]}"
    return "Formula errors:\n" + "\n".join(f"  - {e}" for e in errors)
