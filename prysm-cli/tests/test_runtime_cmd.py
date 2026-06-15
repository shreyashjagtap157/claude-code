"""Tests for the /runtime command — system detection display."""

from unittest.mock import MagicMock, patch
import pytest

from prysm.commands.runtime_cmd import RuntimeCommand
from prysm.system import SystemInfo, GPUInfo


@pytest.fixture
def cmd_with_system():
    """Create a RuntimeCommand with a pre-set SystemInfo mock."""
    gpu = GPUInfo(detected=True, vendor="nvidia", name="NVIDIA RTX 4090",
                  vram_gb=24.0, cuda_version="12.4")
    system = SystemInfo(
        os_name="windows",
        os_version="10.0.22631",
        architecture="x86_64",
        cpu_brand="Intel(R) Core(TM) i7-13700K",
        cpu_cores=16,
        cpu_threads=24,
        cpu_features=["avx2", "avx512", "sse4_1"],
        ram_total_gb=32.0,
        ram_available_gb=18.5,
        gpu=gpu,
        is_wsl=False,
        is_docker=False,
        is_remote=False,
    )
    cmd = RuntimeCommand()
    cmd._detected_system = system
    return cmd


@pytest.fixture
def cmd_no_gpu():
    """Create a RuntimeCommand without GPU."""
    system = SystemInfo(
        os_name="linux", os_version="6.8.0", architecture="x86_64",
        cpu_brand="Intel Core i5", cpu_cores=4, cpu_threads=8,
        ram_total_gb=16.0, ram_available_gb=8.2,
        gpu=GPUInfo(),
    )
    cmd = RuntimeCommand()
    cmd._detected_system = system
    return cmd


class TestRuntimeCommand:
    """Tests for the RuntimeCommand class."""

    def test_name_and_description(self):
        """Should have correct identity."""
        cmd = RuntimeCommand()
        assert cmd.name == "/runtime"
        assert cmd.description

    def test_detect_shows_multiple_tables(self, cmd_with_system):
        """Detection should print multiple tables."""
        with patch("prysm.commands.runtime_cmd.console.print") as mock_print:
            cmd_with_system._show_detect()
        assert mock_print.call_count >= 4

    def test_detect_shows_gpu_info(self, cmd_with_system):
        """Detection output should include GPU info."""
        with patch("prysm.commands.runtime_cmd.console.print") as mock_print:
            cmd_with_system._show_detect()
        # Collect all positional args
        all_args = []
        for c in mock_print.call_args_list:
            if c[0]:
                all_args.append(c[0][0])
        # Should print OS, CPU, RAM, and GPU tables (4 tables)
        from rich.table import Table
        tables = [a for a in all_args if isinstance(a, Table)]
        assert len(tables) >= 4  # OS, CPU, RAM, GPU

    def test_detect_no_gpu(self, cmd_no_gpu):
        """Detection should handle no GPU gracefully."""
        with patch("prysm.commands.runtime_cmd.console.print") as mock_print:
            cmd_no_gpu._show_detect()
        # Should still print 4 tables even with no GPU
        from rich.table import Table
        all_args = []
        for c in mock_print.call_args_list:
            if c[0]:
                all_args.append(c[0][0])
        tables = [a for a in all_args if isinstance(a, Table)]
        assert len(tables) >= 4  # No GPU doesn't skip tables

    def test_summary_shows_one_line(self, cmd_with_system):
        """Summary should produce a one-liner."""
        with patch("prysm.commands.runtime_cmd.console.print") as mock_print:
            cmd_with_system._show_summary()
        assert mock_print.call_count == 1
        output = str(mock_print.call_args[0][0])
        assert "Windows" in output
        assert "i7-13700K" in output

    def test_info_gpu(self, cmd_with_system):
        """'info gpu' should show GPU details."""
        with patch("prysm.commands.runtime_cmd.console.print") as mock_print:
            cmd_with_system._show_info(["gpu"])
        output = str(mock_print.call_args[0][0])
        assert "GPU" in output
        assert "RTX 4090" in output

    def test_info_cpu(self, cmd_with_system):
        """'info cpu' should show CPU details."""
        with patch("prysm.commands.runtime_cmd.console.print") as mock_print:
            cmd_with_system._show_info(["cpu"])
        output = str(mock_print.call_args[0][0])
        assert "CPU" in output
        assert "i7-13700K" in output

    def test_info_ram(self, cmd_with_system):
        """'info ram' should show RAM details."""
        with patch("prysm.commands.runtime_cmd.console.print") as mock_print:
            cmd_with_system._show_info(["ram"])
        output = str(mock_print.call_args[0][0])
        assert "RAM" in output
        assert "32.0 GB" in output

    def test_info_unknown_subsystem(self, cmd_with_system):
        """An unknown subsystem should show a warning."""
        with patch("prysm.commands.runtime_cmd.console.print") as mock_print:
            cmd_with_system._show_info(["unknown"])
        # Check the first print call (Unknown subsystem warning)
        output = str(mock_print.call_args_list[0][0][0])
        assert "unknown" in output.lower()

    def test_execute_no_args_calls_detect(self, cmd_with_system):
        """Execute with no args should call _show_detect."""
        with patch.object(cmd_with_system, "_show_detect") as mock_detect:
            cmd_with_system.execute([])
            mock_detect.assert_called_once()

    def test_execute_detect_subcommand(self, cmd_with_system):
        """Execute 'detect' should call _show_detect."""
        with patch.object(cmd_with_system, "_show_detect") as mock_detect:
            cmd_with_system.execute(["detect"])
            mock_detect.assert_called_once()

    def test_execute_summary_subcommand(self, cmd_with_system):
        """Execute 'summary' should call _show_summary."""
        with patch.object(cmd_with_system, "_show_summary") as mock_summary:
            cmd_with_system.execute(["summary"])
            mock_summary.assert_called_once()

    def test_execute_unknown_subcommand(self, cmd_with_system):
        """Unknown subcommand should show usage."""
        with patch.object(cmd_with_system, "_show_usage") as mock_usage:
            cmd_with_system.execute(["invalid"])
            mock_usage.assert_called_once()

    def test_detected_system_creates_detector(self):
        """detected_system should create a detector on first access."""
        cmd = RuntimeCommand()
        assert cmd._detected_system is None
        with patch("prysm.commands.runtime_cmd.SystemDetector") as mock_detector_cls:
            mock_detector = mock_detector_cls.return_value
            mock_detector.detect.return_value = SystemInfo(os_name="linux")
            _ = cmd.detected_system
            assert cmd._detected_system is not None
            assert cmd._detected_system.os_name == "linux"

    def test_detected_system_caches_result(self):
        """detected_system should only create detector once."""
        cmd = RuntimeCommand()
        with patch("prysm.commands.runtime_cmd.SystemDetector") as mock_detector_cls:
            mock_detector = mock_detector_cls.return_value
            mock_detector.detect.return_value = SystemInfo()
            _ = cmd.detected_system
            _ = cmd.detected_system  # Second call
            assert mock_detector.detect.call_count == 1
