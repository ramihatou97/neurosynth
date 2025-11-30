"""
Unit tests for LaTeX validator.

Tests Phase 4.1 Module 4:
- String escaping
- Label sanitization
- Syntax validation
- Brace balancing
- Required commands
- Auto-fixing
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from neurosynth.enhancements.latex_validator import (
    LaTeXValidator,
    ValidationResult,
    escape_latex,
    sanitize_label,
    unescape_latex,
    validate_figure_environment,
    extract_label_from_code,
    extract_caption_from_code,
)


class TestLatexValidator:
    """Test suite for LaTeX validator."""

    def test_escape_latex_special_chars(self):
        """Test escaping of LaTeX special characters."""
        # Test individual characters
        assert escape_latex("&") == r"\&"
        assert escape_latex("%") == r"\%"
        assert escape_latex("$") == r"\$"
        assert escape_latex("#") == r"\#"
        assert escape_latex("_") == r"\_"
        assert escape_latex("{") == r"\{"
        assert escape_latex("}") == r"\}"

        # Test combined string
        text = "Costs $50 & 10% discount"
        escaped = escape_latex(text)
        assert escaped == r"Costs \$50 \& 10\% discount"

        print("✓ Special character escaping works")

    def test_escape_latex_empty_string(self):
        """Test escaping empty string."""
        assert escape_latex("") == ""
        assert escape_latex(None) == ""

        print("✓ Empty string escaping handled")

    def test_sanitize_label(self):
        """Test label sanitization for \\label{}."""
        # Test with spaces and special chars
        assert sanitize_label("Fig 3.2: Test!") == "fig-3-2-test"

        # Test with uppercase
        assert sanitize_label("FIGURE_TEST") == "figure_test"

        # Test with consecutive dashes
        assert sanitize_label("test---label") == "test-label"

        # Test empty
        assert sanitize_label("") == "unknown"

        # Test length limiting
        long_label = "a" * 100
        sanitized = sanitize_label(long_label)
        assert len(sanitized) <= 50

        print("✓ Label sanitization works")

    def test_unescape_latex(self):
        """Test unescaping LaTeX text."""
        escaped = r"Costs \$50 \& 10\% discount"
        unescaped = unescape_latex(escaped)

        assert unescaped == "Costs $50 & 10% discount"

        print("✓ LaTeX unescaping works")

    def test_validator_initialization(self):
        """Test validator initializes correctly."""
        validator = LaTeXValidator(enable_compilation=False)

        assert validator.enable_compilation is False
        assert validator.has_pdflatex is False

        print("✓ Validator initialization works")

    def test_check_balanced_braces_valid(self):
        """Test balanced brace detection."""
        validator = LaTeXValidator()

        latex_code = r"\begin{figure} \includegraphics{test.png} \end{figure}"

        errors = validator._check_balanced_braces(latex_code)

        assert len(errors) == 0

        print("✓ Balanced braces validated correctly")

    def test_check_balanced_braces_extra_closing(self):
        """Test detection of extra closing brace."""
        validator = LaTeXValidator()

        latex_code = r"\begin{figure}} \end{figure}"

        errors = validator._check_balanced_braces(latex_code)

        assert len(errors) > 0
        assert "Extra '}'" in errors[0]

        print("✓ Extra closing brace detected")

    def test_check_balanced_braces_missing_closing(self):
        """Test detection of missing closing brace."""
        validator = LaTeXValidator()

        latex_code = r"\begin{figure \end{figure}"

        errors = validator._check_balanced_braces(latex_code)

        assert len(errors) > 0
        assert "unclosed" in errors[0]

        print("✓ Missing closing brace detected")

    def test_check_required_commands_valid(self):
        """Test required commands check passes."""
        validator = LaTeXValidator()

        latex_code = r"""
\begin{figure}
  \centering
  \includegraphics{test.png}
  \caption{Test}
\end{figure}
"""

        errors = validator._check_required_commands(latex_code)

        assert len(errors) == 0

        print("✓ Required commands validated")

    def test_check_required_commands_missing_includegraphics(self):
        """Test detection of missing \\includegraphics."""
        validator = LaTeXValidator()

        latex_code = r"\begin{figure} \caption{Test} \end{figure}"

        errors = validator._check_required_commands(latex_code)

        assert len(errors) > 0
        assert any(r'\includegraphics' in err for err in errors)

        print("✓ Missing \\includegraphics detected")

    def test_validate_syntax_valid_code(self):
        """Test syntax validation on valid code."""
        validator = LaTeXValidator()

        latex_code = r"""
\begin{figure}[ht]
  \centering
  \includegraphics[width=0.8\textwidth]{figure.png}
  \caption{Test figure}
  \label{fig:test}
\end{figure}
"""

        result = validator.validate_syntax(latex_code)

        assert result.is_valid is True
        assert len(result.errors) == 0

        print("✓ Syntax validation passes for valid code")

    def test_validate_syntax_invalid_code(self):
        """Test syntax validation on invalid code."""
        validator = LaTeXValidator()

        # Missing \end{figure}
        latex_code = r"\begin{figure} \includegraphics{test.png}"

        result = validator.validate_syntax(latex_code)

        assert result.is_valid is False
        assert len(result.errors) > 0

        print("✓ Syntax validation fails for invalid code")

    def test_fix_common_errors_escapes_caption(self):
        """Test auto-fixing escapes caption content."""
        validator = LaTeXValidator()

        latex_code = r"\begin{figure} \caption{Cost: $50 & 10%} \end{figure}"

        fixed = validator.fix_common_errors(latex_code)

        # Should escape special chars in caption
        assert r"\$" in fixed
        assert r"\&" in fixed
        assert r"\%" in fixed

        print("✓ Auto-fix escapes caption content")

    def test_validate_figure_environment(self):
        """Test quick figure environment validation."""
        valid_code = r"\begin{figure} \includegraphics{x.png} \end{figure}"
        invalid_code = r"\begin{figure} \end{figure}"  # Missing includegraphics

        assert validate_figure_environment(valid_code) is True
        assert validate_figure_environment(invalid_code) is False

        print("✓ Figure environment validation works")

    def test_extract_label_from_code(self):
        """Test label extraction."""
        latex_code = r"\begin{figure} \label{fig:test-123} \end{figure}"

        label = extract_label_from_code(latex_code)

        assert label == "fig:test-123"

        print("✓ Label extraction works")

    def test_extract_label_not_found(self):
        """Test label extraction when no label present."""
        latex_code = r"\begin{figure} \caption{Test} \end{figure}"

        label = extract_label_from_code(latex_code)

        assert label is None

        print("✓ Missing label returns None")

    def test_extract_caption_from_code(self):
        """Test caption extraction."""
        latex_code = r"\caption{This is a test caption}"

        caption = extract_caption_from_code(latex_code)

        assert caption == "This is a test caption"

        print("✓ Caption extraction works")

    def test_extract_caption_with_escapes(self):
        """Test caption extraction unescapes content."""
        latex_code = r"\caption{Cost: \$50 \& 10\%}"

        caption = extract_caption_from_code(latex_code)

        assert caption == "Cost: $50 & 10%"

        print("✓ Caption extraction unescapes content")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
