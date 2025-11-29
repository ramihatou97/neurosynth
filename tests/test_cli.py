"""Tests for CLI commands."""

from typer.testing import CliRunner

from neurosynth.cli import app

runner = CliRunner()


class TestVersionCommand:
    """Tests for version command."""

    def test_version_output(self):
        """Test that version command shows version."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "NeuroSynth" in result.stdout
        assert "0.1.0" in result.stdout


class TestInitCommand:
    """Tests for init command."""

    def test_init_creates_project(self, tmp_path):
        """Test that init creates project structure."""
        result = runner.invoke(app, ["init", "Test Topic", "-o", str(tmp_path)])

        assert result.exit_code == 0
        assert "Project initialized" in result.stdout

        project_dir = tmp_path / "test_topic"
        assert project_dir.exists()
        assert (project_dir / "sources").exists()
        assert (project_dir / "processed").exists()
        assert (project_dir / "output").exists()
        assert (project_dir / "neurosynth.yaml").exists()

    def test_init_config_content(self, tmp_path):
        """Test that init creates correct config."""
        runner.invoke(app, ["init", "Vestibular Schwannoma", "-o", str(tmp_path)])

        project_dir = tmp_path / "vestibular_schwannoma"
        config_content = (project_dir / "neurosynth.yaml").read_text()

        assert 'topic: "Vestibular Schwannoma"' in config_content
        assert "chunk_size: 1000" in config_content


class TestAddCommand:
    """Tests for add command."""

    def test_add_files(self, temp_project, tmp_path):
        """Test adding files to project."""
        # Create a test file to add
        test_file = tmp_path / "test_doc.txt"
        test_file.write_text("Test content")

        result = runner.invoke(app, ["add", str(test_file), "-p", str(temp_project)])

        assert result.exit_code == 0
        assert "Added:" in result.stdout
        assert (temp_project / "sources" / "test_doc.txt").exists()

    def test_add_nonexistent_file(self, temp_project, tmp_path):
        """Test adding nonexistent file shows warning."""
        result = runner.invoke(app, ["add", "/nonexistent/file.pdf", "-p", str(temp_project)])

        assert "Not found:" in result.stdout

    def test_add_to_invalid_project(self, tmp_path):
        """Test adding to invalid project fails."""
        result = runner.invoke(app, ["add", "file.pdf", "-p", str(tmp_path)])

        assert result.exit_code == 1
        assert "Not a valid NeuroSynth project" in result.stdout


class TestStatusCommand:
    """Tests for status command."""

    def test_status_empty_project(self, temp_project):
        """Test status on empty project."""
        result = runner.invoke(app, ["status", "-p", str(temp_project)])

        assert result.exit_code == 0
        assert "Project Status" in result.stdout
        assert "Sources" in result.stdout

    def test_status_with_sources(self, temp_project):
        """Test status with source files."""
        # Add a source file
        (temp_project / "sources" / "test.pdf").write_bytes(b"PDF content")

        result = runner.invoke(app, ["status", "-p", str(temp_project)])

        assert result.exit_code == 0
        assert "1 files" in result.stdout


class TestProcessCommand:
    """Tests for process command (mocked)."""

    def test_process_no_sources_dir(self, tmp_path):
        """Test process without sources directory."""
        result = runner.invoke(app, ["process", "-p", str(tmp_path)])

        # Should handle missing sources gracefully
        assert "sources/ directory not found" in result.stdout or result.exit_code != 0


class TestHelpCommand:
    """Tests for help output."""

    def test_main_help(self):
        """Test main help output."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Neurosurgical Knowledge Synthesis" in result.stdout
        assert "init" in result.stdout
        assert "process" in result.stdout
        assert "synthesize" in result.stdout

    def test_init_help(self):
        """Test init command help."""
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "Initialize a new synthesis project" in result.stdout

    def test_process_help(self):
        """Test process command help."""
        result = runner.invoke(app, ["process", "--help"])

        assert result.exit_code == 0
        assert "Process source documents" in result.stdout
        assert "--cache" in result.stdout
