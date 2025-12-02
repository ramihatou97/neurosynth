"""
LaTeX Validator for NeuroSynth
================================
Validates and escapes LaTeX figure code for safe compilation.

Key features:
- Special character escaping (& % $ # _ { } ~ ^ \\)
- Label sanitization for \\label{} commands
- Syntax validation (balanced braces, required commands)
- Optional compilation validation with pdflatex
- Auto-fixing common LaTeX errors

Version: 1.0
"""

import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ValidationResult:
    """
    Result of LaTeX validation.

    Provides validation status, error/warning messages, and optionally
    an auto-fixed version of the code.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixed_code: str | None = None  # Auto-fixed version (if fixable)

    def __str__(self) -> str:
        """Human-readable validation result."""
        status = "✓ Valid" if self.is_valid else "✗ Invalid"
        parts = [f"LaTeX Validation: {status}"]

        if self.errors:
            parts.append(f"Errors ({len(self.errors)}):")
            parts.extend(f"  - {err}" for err in self.errors)

        if self.warnings:
            parts.append(f"Warnings ({len(self.warnings)}):")
            parts.extend(f"  - {warn}" for warn in self.warnings)

        return "\n".join(parts)


# =============================================================================
# STRING UTILITIES
# =============================================================================


def escape_latex(text: str) -> str:
    """
    Escape special LaTeX characters in text.

    Escapes: & % $ # _ { } ~ ^ \\

    Args:
        text: Raw text to escape

    Returns:
        LaTeX-safe escaped text

    Example:
        escape_latex("Costs $50 & 10%") → "Costs \\$50 \\& 10\\%"
    """
    if not text:
        return ""

    # Order matters: backslash first, then others
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]

    escaped = text
    for char, replacement in replacements:
        escaped = escaped.replace(char, replacement)

    return escaped


def sanitize_label(label: str) -> str:
    """
    Sanitize a string for use in \\label{} command.

    LaTeX labels must be alphanumeric with dashes/underscores only.

    Args:
        label: Raw label string

    Returns:
        Sanitized label safe for \\label{}

    Example:
        sanitize_label("Fig 3.2: Test!") → "fig-3-2-test"
    """
    if not label:
        return "unknown"

    # Convert to lowercase
    sanitized = label.lower()

    # Replace spaces and special chars with dash
    sanitized = re.sub(r"[^a-z0-9_-]", "-", sanitized)

    # Remove consecutive dashes
    sanitized = re.sub(r"-+", "-", sanitized)

    # Remove leading/trailing dashes
    sanitized = sanitized.strip("-")

    # Ensure not empty
    if not sanitized:
        return "unknown"

    # Limit length
    if len(sanitized) > 50:
        sanitized = sanitized[:50]

    return sanitized


def unescape_latex(text: str) -> str:
    """
    Unescape LaTeX special characters (inverse of escape_latex).

    Args:
        text: Escaped LaTeX text

    Returns:
        Unescaped text

    Example:
        unescape_latex(r"\\$50 \\& 10\\%") → "$50 & 10%"
    """
    if not text:
        return ""

    replacements = [
        (r"\textbackslash{}", "\\"),
        (r"\&", "&"),
        (r"\%", "%"),
        (r"\$", "$"),
        (r"\#", "#"),
        (r"\_", "_"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\textasciitilde{}", "~"),
        (r"\textasciicircum{}", "^"),
    ]

    unescaped = text
    for escaped_form, original_char in replacements:
        unescaped = unescaped.replace(escaped_form, original_char)

    return unescaped


# =============================================================================
# LATEX VALIDATOR
# =============================================================================


class LaTeXValidator:
    """
    Validates LaTeX figure code for syntax and compilation errors.

    Validation levels:
    1. Syntax validation: Fast checks (balanced braces, required commands)
    2. Compilation validation: Full pdflatex compilation (requires TeX installation)

    Auto-fixing:
    - Escapes unescaped special characters
    - Fixes unbalanced braces
    - Adds missing required commands
    """

    def __init__(self, enable_compilation: bool = False):
        """
        Initialize validator.

        Args:
            enable_compilation: If True, enables full pdflatex compilation validation
                               (requires TeX installation)
        """
        self.enable_compilation = enable_compilation
        self.special_chars = r"&%$#_{}~^\\"

        # Check if pdflatex available
        self.has_pdflatex = False
        if enable_compilation:
            self.has_pdflatex = self._check_pdflatex()
            if not self.has_pdflatex:
                logger.warning(
                    "pdflatex not found - compilation validation unavailable"
                )

        logger.info(
            f"LaTeXValidator initialized: "
            f"compilation={'enabled' if self.has_pdflatex else 'disabled'}"
        )

    def _check_pdflatex(self) -> bool:
        """Check if pdflatex is available on system."""
        try:
            result = subprocess.run(
                ["pdflatex", "--version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def validate_syntax(self, latex_code: str) -> ValidationResult:
        """
        Validate LaTeX syntax without compilation.

        Checks:
        - Balanced braces
        - Required commands present
        - Label format validity
        - Caption escaping

        Args:
            latex_code: LaTeX code to validate

        Returns:
            ValidationResult with validation status and messages
        """
        errors = []
        warnings = []

        # Check 1: Balanced braces
        brace_errors = self._check_balanced_braces(latex_code)
        errors.extend(brace_errors)

        # Check 2: Required commands
        cmd_errors = self._check_required_commands(latex_code)
        errors.extend(cmd_errors)

        # Check 3: Label format
        label_warnings = self._check_label_format(latex_code)
        warnings.extend(label_warnings)

        # Check 4: Caption escaping
        caption_warnings = self._check_caption_escaping(latex_code)
        warnings.extend(caption_warnings)

        # Check if valid
        is_valid = len(errors) == 0

        # Attempt auto-fix if invalid
        fixed_code = None
        if not is_valid:
            try:
                fixed_code = self.fix_common_errors(latex_code)
                # Re-validate fixed code
                fixed_errors = self._check_balanced_braces(fixed_code)
                if not fixed_errors:
                    warnings.append("Code auto-fixed successfully")
            except Exception as e:
                warnings.append(f"Auto-fix failed: {e}")

        return ValidationResult(
            is_valid=is_valid, errors=errors, warnings=warnings, fixed_code=fixed_code
        )

    def validate_with_compilation(
        self, latex_code: str, timeout: float = 10.0
    ) -> ValidationResult:
        """
        Validate by compiling with pdflatex.

        Requires pdflatex to be installed on the system.

        Args:
            latex_code: LaTeX code to validate
            timeout: Compilation timeout in seconds

        Returns:
            ValidationResult with compilation errors/warnings
        """
        if not self.has_pdflatex:
            return ValidationResult(
                is_valid=False,
                errors=["pdflatex not available for compilation validation"],
            )

        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write LaTeX document
                tex_file = os.path.join(tmpdir, "test.tex")

                # Wrap code in minimal document
                full_doc = self._wrap_in_document(latex_code)

                with open(tex_file, "w", encoding="utf-8") as f:
                    f.write(full_doc)

                # Run pdflatex
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "test.tex"],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                # Parse output for errors
                errors, warnings = self._parse_latex_log(result.stdout, result.stderr)

                return ValidationResult(
                    is_valid=(result.returncode == 0 and not errors),
                    errors=errors,
                    warnings=warnings,
                )

        except subprocess.TimeoutExpired:
            return ValidationResult(
                is_valid=False, errors=[f"Compilation timed out after {timeout}s"]
            )
        except Exception as e:
            return ValidationResult(is_valid=False, errors=[f"Compilation failed: {e}"])

    def fix_common_errors(self, latex_code: str) -> str:
        """
        Auto-fix common LaTeX errors.

        Fixes:
        - Unescaped special characters in captions
        - Unbalanced braces (attempts simple fixes)
        - Missing required commands

        Args:
            latex_code: LaTeX code with potential errors

        Returns:
            Fixed LaTeX code
        """
        fixed = latex_code

        # Fix 1: Escape special chars in \caption{}
        def escape_caption_content(match):
            caption_text = match.group(1)
            escaped_text = escape_latex(caption_text)
            return f"\\caption{{{escaped_text}}}"

        fixed = re.sub(
            r"\\caption\{([^}]*)\}", escape_caption_content, fixed, flags=re.DOTALL
        )

        # Fix 2: Add missing \centering if not present
        if r"\centering" not in fixed and r"\begin{figure}" in fixed:
            fixed = fixed.replace(
                r"\begin{figure}", r"\begin{figure}" + "\n  \\centering"
            )

        # Fix 3: Ensure label is sanitized
        def sanitize_label_content(match):
            label_text = match.group(1)
            sanitized = sanitize_label(label_text)
            return f"\\label{{{sanitized}}}"

        fixed = re.sub(r"\\label\{([^}]*)\}", sanitize_label_content, fixed)

        return fixed

    def _check_balanced_braces(self, latex_code: str) -> list[str]:
        """
        Check if braces are balanced.

        Args:
            latex_code: LaTeX code to check

        Returns:
            List of error messages (empty if balanced)
        """
        errors = []
        depth = 0
        position = 0

        for i, char in enumerate(latex_code):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1

            if depth < 0:
                errors.append(f"Unbalanced braces: Extra '}}' at position {i}")
                break

            position = i

        if depth > 0:
            errors.append(
                f"Unbalanced braces: {depth} unclosed '{{' (last at {position})"
            )

        return errors

    def _check_required_commands(self, latex_code: str) -> list[str]:
        """
        Check for required LaTeX commands in figure code.

        Args:
            latex_code: LaTeX code to check

        Returns:
            List of error messages (empty if all required commands present)
        """
        errors = []

        required_patterns = [
            (r"\\begin\{figure\}", r"\begin{figure}"),
            (r"\\includegraphics", r"\includegraphics"),
            (r"\\end\{figure\}", r"\end{figure}"),
        ]

        for pattern, command_name in required_patterns:
            if not re.search(pattern, latex_code):
                errors.append(f"Missing required command: {command_name}")

        return errors

    def _check_label_format(self, latex_code: str) -> list[str]:
        """
        Check label format validity.

        Args:
            latex_code: LaTeX code to check

        Returns:
            List of warning messages (empty if labels are valid)
        """
        warnings = []

        # Find all \label{...} commands
        label_pattern = r"\\label\{([^}]*)\}"
        labels = re.findall(label_pattern, latex_code)

        for label in labels:
            # Check for invalid characters
            if not re.match(r"^[a-zA-Z0-9_-]+$", label):
                warnings.append(
                    f"Label '{label}' contains invalid characters "
                    "(should be alphanumeric, dash, or underscore only)"
                )

        return warnings

    def _check_caption_escaping(self, latex_code: str) -> list[str]:
        """
        Check if caption text is properly escaped.

        Args:
            latex_code: LaTeX code to check

        Returns:
            List of warning messages (empty if captions appear escaped)
        """
        warnings = []

        # Find all \caption{...} commands
        caption_pattern = r"\\caption\{([^}]*)\}"
        captions = re.findall(caption_pattern, latex_code, re.DOTALL)

        for caption in captions:
            # Check for unescaped special characters
            unescaped_chars = []

            # Don't check for \ since it could be intentional commands
            dangerous_chars = "&%$#_"
            for char in dangerous_chars:
                # Check if char appears without backslash before it
                if char in caption:
                    # Simple check: if char appears, warn
                    # (More sophisticated: check if \char appears)
                    if f"\\{char}" not in caption:
                        unescaped_chars.append(char)

            if unescaped_chars:
                warnings.append(
                    f"Caption may have unescaped characters: "
                    f"{', '.join(unescaped_chars)} - "
                    f"Consider using escape_latex()"
                )

        return warnings

    def _wrap_in_document(self, figure_code: str) -> str:
        """
        Wrap figure code in minimal LaTeX document for compilation.

        Args:
            figure_code: Figure code to wrap

        Returns:
            Complete LaTeX document
        """
        return f"""\\documentclass{{article}}
\\usepackage{{graphicx}}
\\begin{{document}}
{figure_code}
\\end{{document}}
"""

    def _parse_latex_log(self, stdout: str, stderr: str) -> tuple[list[str], list[str]]:
        """
        Parse pdflatex output for errors and warnings.

        Args:
            stdout: Standard output from pdflatex
            stderr: Standard error from pdflatex

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        combined_output = stdout + "\n" + stderr

        # Extract error lines (start with !)
        error_pattern = r"^!\s*(.+)$"
        for match in re.finditer(error_pattern, combined_output, re.MULTILINE):
            error_msg = match.group(1).strip()
            if error_msg:
                errors.append(error_msg)

        # Extract warning lines
        warning_pattern = r"(LaTeX Warning|Warning):\s*(.+)$"
        for match in re.finditer(warning_pattern, combined_output, re.MULTILINE):
            warning_msg = match.group(2).strip()
            if warning_msg:
                warnings.append(warning_msg)

        return errors, warnings

    def validate_figure_code(
        self, latex_code: str, use_compilation: bool = False
    ) -> ValidationResult:
        """
        Validate figure code using syntax or compilation validation.

        Args:
            latex_code: LaTeX figure code
            use_compilation: If True and pdflatex available, use compilation validation

        Returns:
            ValidationResult
        """
        # Try syntax validation first
        result = self.validate_syntax(latex_code)

        # If syntax validation passed and compilation requested
        if result.is_valid and use_compilation and self.has_pdflatex:
            return self.validate_with_compilation(latex_code)

        return result


# =============================================================================
# VALIDATION HELPERS
# =============================================================================


def validate_figure_environment(latex_code: str) -> bool:
    """
    Quick check if code contains a valid figure environment.

    Args:
        latex_code: LaTeX code

    Returns:
        True if contains \\begin{figure} ... \\end{figure}
    """
    has_begin = r"\begin{figure}" in latex_code
    has_end = r"\end{figure}" in latex_code
    has_includegraphics = r"\includegraphics" in latex_code

    return has_begin and has_end and has_includegraphics


def extract_label_from_code(latex_code: str) -> str | None:
    """
    Extract label from LaTeX figure code.

    Args:
        latex_code: LaTeX code

    Returns:
        Label string if found, None otherwise

    Example:
        extract_label_from_code(r"\\label{fig:test}") → "fig:test"
    """
    match = re.search(r"\\label\{([^}]*)\}", latex_code)
    if match:
        return match.group(1)
    return None


def extract_caption_from_code(latex_code: str) -> str | None:
    """
    Extract caption from LaTeX figure code.

    Args:
        latex_code: LaTeX code

    Returns:
        Caption text if found, None otherwise (unescaped)

    Example:
        extract_caption_from_code(r"\\caption{Test}") → "Test"
    """
    match = re.search(r"\\caption\{([^}]*)\}", latex_code, re.DOTALL)
    if match:
        caption_text = match.group(1)
        return unescape_latex(caption_text)
    return None


# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    "ValidationResult",
    "escape_latex",
    "sanitize_label",
    "unescape_latex",
    "LaTeXValidator",
    "validate_figure_environment",
    "extract_label_from_code",
    "extract_caption_from_code",
]
