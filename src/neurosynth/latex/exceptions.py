"""Custom exceptions for LaTeX/PDF generation."""

from pathlib import Path
from typing import Any


class PDFGenerationError(Exception):
    """Base exception for PDF generation failures."""

    pass


class LaTeXCompilationError(PDFGenerationError):
    """LaTeX compilation failed with errors.

    Attributes:
        returncode: pdflatex exit code
        stdout: pdflatex stdout output
        stderr: pdflatex stderr output
        log_path: Path to .log file with detailed errors
        errors: Parsed error messages from log file
    """

    def __init__(
        self,
        message: str,
        returncode: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        log_path: Path | None = None,
        errors: str | None = None,
    ):
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.log_path = log_path
        self.errors = errors


class PDFValidationError(PDFGenerationError):
    """Generated PDF failed validation checks.

    Attributes:
        pdf_path: Path to the invalid PDF file
    """

    def __init__(self, message: str, pdf_path: Path | None = None):
        super().__init__(message)
        self.pdf_path = pdf_path


class ImagePreparationError(PDFGenerationError):
    """Image preparation for LaTeX failed.

    Attributes:
        image_path: Source image path
        target_path: Target path where copy failed
    """

    def __init__(
        self,
        message: str,
        image_path: Path | None = None,
        target_path: Path | None = None,
    ):
        super().__init__(message)
        self.image_path = image_path
        self.target_path = target_path
