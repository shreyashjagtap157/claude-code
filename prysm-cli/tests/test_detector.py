"""Tests for system detection — SystemInfo, SystemDetector, GPU detection."""

import platform
import subprocess
from unittest.mock import MagicMock, PropertyMock, patch
import pytest

from prysm.system import SystemInfo, SystemDetector, GPUInfo, detect_gpu
from prysm.system.detector import SystemDetector
from prysm.system.gpu import GPUInfo, _detect_nvidia, _detect_metal, _detect_rocm, _detect_vulkan


# ═══════════════════════════════════════════════════════════════════════════════
# GPUInfo Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestGPUInfo:
    """Tests for the GPUInfo dataclass."""

    def test_default_no_gpu(self):
        """Default GPUInfo should have detected=False."""
        gpu = GPUInfo()
        assert gpu.detected is False
        assert gpu.vendor is None

    def test_summary_no_gpu(self):
        """Summary should say 'No GPU detected'."""
        gpu = GPUInfo()
        assert gpu.summary == "No GPU detected"

    def test_summary_nvidia(self):
        """Summary should include GPU details."""
        gpu = GPUInfo(
            detected=True, vendor="nvidia",
            name="NVIDIA GeForce RTX 4090",
            vram_gb=24.0, cuda_version="12.4",
        )
        assert "RTX 4090" in gpu.summary
        assert "24 GB" in gpu.summary
        assert "CUDA 12.4" in gpu.summary

    def test_summary_with_backends(self):
        """Summary should list GPU backends."""
        gpu = GPUInfo(
            detected=True, vendor="apple",
            name="Apple M3 Max",
            metal_supported=True,
            vulkan_supported=True,
        )
        assert "Metal" in gpu.summary
        assert "Vulkan" in gpu.summary

    def test_gpu_without_vram(self):
        """GPU summary should work without VRAM info."""
        gpu = GPUInfo(detected=True, vendor="nvidia", name="NVIDIA GTX 1080")
        assert "GTX 1080" in gpu.summary
        assert "GB" not in gpu.summary


# ═══════════════════════════════════════════════════════════════════════════════
# SystemInfo Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSystemInfo:
    """Tests for the SystemInfo dataclass."""

    def test_default_creation(self):
        """Default SystemInfo should have empty fields."""
        info = SystemInfo()
        assert info.os_name == ""
        assert info.cpu_cores == 0

    def test_has_gpu_true(self):
        """has_gpu should return True when GPU detected."""
        info = SystemInfo(gpu=GPUInfo(detected=True, vendor="nvidia"))
        assert info.has_gpu is True

    def test_has_gpu_false(self):
        """has_gpu should return False when no GPU detected."""
        info = SystemInfo()
        assert info.has_gpu is False

    def test_summary_no_gpu(self):
        """Summary should include OS, arch, CPU without GPU."""
        info = SystemInfo(
            os_name="linux",
            os_version="6.8.0",
            architecture="x86_64",
            cpu_brand="Intel Core i7",
            cpu_cores=8,
            cpu_threads=16,
        )
        summary = info.summary
        assert "Linux" in summary
        assert "6.8.0" in summary
        assert "x86_64" in summary
        assert "i7" in summary
        assert "8C/16T" in summary

    def test_summary_with_gpu(self):
        """Summary should include GPU info when available."""
        info = SystemInfo(
            os_name="windows",
            os_version="10.0.22631",
            architecture="x86_64",
            cpu_brand="Intel Core i7-13700K",
            cpu_cores=16,
            cpu_threads=24,
            gpu=GPUInfo(detected=True, vendor="nvidia",
                         name="NVIDIA RTX 4090", vram_gb=24.0),
        )
        summary = info.summary
        assert "RTX 4090" in summary
        assert "24 GB" in summary

    def test_summary_with_env(self):
        """Summary should include WSL/Docker/Remote flags."""
        info = SystemInfo(
            os_name="linux", os_version="5.15.0",
            architecture="x86_64", cpu_brand="CPU",
            cpu_cores=4, cpu_threads=8,
            is_wsl=True, is_remote=True,
        )
        summary = info.summary
        assert "WSL" in summary
        assert "Remote" in summary


# ═══════════════════════════════════════════════════════════════════════════════
# SystemDetector Unit Tests (with mocking)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSystemDetectorOS:
    """Tests for OS detection."""

    def test_detect_windows(self):
        """Windows detection should set os_name and os_version."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch("platform.system", return_value="Windows"):
            with patch("platform.version", return_value="10.0.22631"):
                detector._detect_os(info)
        assert info.os_name == "windows"
        assert info.os_version == "10.0.22631"

    def test_detect_macos(self):
        """macOS detection should set os_name and version."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch("platform.system", return_value="Darwin"):
            with patch("platform.mac_ver", return_value=("14.3.0", "", "")):
                detector._detect_os(info)
        assert info.os_name == "darwin"
        assert info.os_version == "14.3.0"

    def test_detect_linux(self):
        """Linux detection should set os_name and version from platform.release."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch("platform.system", return_value="Linux"):
            with patch("platform.release", return_value="6.8.0-arch1-1"):
                with patch.dict("sys.modules", {"distro": None}):
                    with patch("prysm.system.detector.SystemDetector._read_cpuinfo_field",
                               return_value=None):
                        detector._detect_os(info)
        assert info.os_name == "linux"
        assert info.os_version == "6.8.0-arch1-1"

    def test_detect_unknown_os(self):
        """Unknown OS should pass through system name."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch("platform.system", return_value="SomeOS"):
            with patch("platform.release", return_value="1.0"):
                detector._detect_os(info)
        assert info.os_name == "someos"


class TestSystemDetectorArch:
    """Tests for architecture detection."""

    @pytest.mark.parametrize("machine,expected", [
        ("AMD64", "x86_64"),
        ("x86_64", "x86_64"),
        ("arm64", "arm64"),
        ("aarch64", "arm64"),
        ("i386", "x86"),
        ("armv7l", "armv7"),
        ("unknown_arch", "unknown_arch"),
    ])
    def test_arch_normalization(self, machine, expected):
        """Architecture should be normalized to standard names."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch("platform.machine", return_value=machine):
            detector._detect_arch(info)
        assert info.architecture == expected


class TestSystemDetectorCPU:
    """Tests for CPU detection."""

    def test_detect_cpu_cores(self):
        """CPU core detection should use psutil."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch("psutil.cpu_count", side_effect=lambda logical: 8 if not logical else 16):
            with patch("prysm.system.detector.SystemDetector._detect_os") as mock_os:
                detector._detect_cpu(info)
        assert info.cpu_cores == 8
        assert info.cpu_threads == 16

    def test_detect_cpu_with_cpuinfo(self):
        """CPU brand should use py-cpuinfo when available."""
        detector = SystemDetector()
        info = SystemInfo()
        mock_cpu_info = {
            "brand_raw": "Intel(R) Core(TM) i7-13700K",
            "flags": ["avx2", "avx512", "sse4_1"],
        }
        with patch("psutil.cpu_count", return_value=16):
            with patch.dict("sys.modules", {"cpuinfo": MagicMock()}):
                with patch("cpuinfo.get_cpu_info", return_value=mock_cpu_info):
                    detector._detect_cpu(info)
        assert info.cpu_brand == "Intel(R) Core(TM) i7-13700K"
        assert "avx2" in info.cpu_features
        assert "avx512" in info.cpu_features

    def test_detect_cpu_without_cpuinfo(self):
        """CPU detection should fallback gracefully without py-cpuinfo."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch("psutil.cpu_count", return_value=8):
            with patch("platform.processor", return_value="Intel64 Family 6 Model 183"):
                # Remove cpuinfo from available modules
                detector._detect_cpu(info)
        assert info.cpu_brand  # Should have some brand string
        assert isinstance(info.cpu_features, list)

    def test_detect_cpu_fallback_empty(self):
        """CPU detection should handle complete failure gracefully."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch("psutil.cpu_count", side_effect=ValueError("Cannot detect")):
            detector._detect_cpu(info)
        assert info.cpu_cores == 0
        assert info.cpu_threads == 0


class TestSystemDetectorRAM:
    """Tests for RAM detection."""

    def test_detect_ram(self):
        """RAM detection should use psutil."""
        detector = SystemDetector()
        info = SystemInfo()
        mock_mem = MagicMock()
        mock_mem.total = 32 * 1024 ** 3  # 32 GB
        mock_mem.available = 16 * 1024 ** 3  # 16 GB
        with patch("psutil.virtual_memory", return_value=mock_mem):
            detector._detect_ram(info)
        assert info.ram_total_gb == 32.0
        assert info.ram_available_gb == 16.0

    def test_detect_ram_fallback(self):
        """RAM detection should handle failure gracefully."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch("psutil.virtual_memory", side_effect=ValueError):
            detector._detect_ram(info)
        assert info.ram_total_gb == 0.0
        assert info.ram_available_gb == 0.0


class TestSystemDetectorEnvironment:
    """Tests for environment detection (WSL, Docker, remote)."""

    def test_not_wsl_on_windows(self):
        """WSL detection should be skipped on Windows."""
        detector = SystemDetector()
        info = SystemInfo(os_name="windows")
        detector._detect_environment(info)
        assert info.is_wsl is False

    def test_wsl_detected_on_linux(self):
        """WSL should be detected on Linux with /proc/version containing 'microsoft'."""
        detector = SystemDetector()
        info = SystemInfo(os_name="linux")
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value="Linux version 5.15.0-microsoft-standard-WSL2"):
                detector._detect_environment(info)
        assert info.is_wsl is True

    def test_docker_detected(self):
        """Docker should be detected via /.dockerenv existence."""
        detector = SystemDetector()
        info = SystemInfo(os_name="linux")
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.read_text", return_value="Linux version 6.8.0"):
                detector._detect_environment(info)
        assert info.is_docker is True
        assert info.is_wsl is False

    def test_remote_detected_via_ssh(self):
        """Remote session should be detected via SSH_TTY env var."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch.dict("os.environ", {"SSH_TTY": "/dev/pts/0"}, clear=True):
            detector._detect_environment(info)
        assert info.is_remote is True

    def test_no_remote_local_session(self):
        """Local session should have is_remote=False."""
        detector = SystemDetector()
        info = SystemInfo()
        with patch.dict("os.environ", {}, clear=True):
            detector._detect_environment(info)
        assert info.is_remote is False


# ═══════════════════════════════════════════════════════════════════════════════
# GPU Detection Tests (mocked)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGPUDectionNVIDIA:
    """Tests for NVIDIA GPU detection via nvidia-smi."""

    def test_nvidia_no_smi(self):
        """nvidia-smi not found should return False."""
        gpu = GPUInfo()
        with patch("shutil.which", return_value=None):
            result = _detect_nvidia(gpu)
        assert result is False
        assert gpu.detected is False

    def test_nvidia_detected(self):
        """nvidia-smi output should be parsed correctly."""
        gpu = GPUInfo()
        smi_output = "NVIDIA GeForce RTX 4090, 556.12, 24564 MiB\n"
        query_output = "0\n"

        def mock_run(args, **kwargs):
            mock = MagicMock()
            cmd = " ".join(args)
            if "query-gpu=name" in cmd:
                mock.stdout = smi_output
                mock.returncode = 0
            elif len(args) == 1 and "nvidia-smi" in args[0]:
                # Plain nvidia-smi call (no args) — CUDA version from header
                mock.stdout = "header | CUDA Version: 12.4 |"
                mock.returncode = 0
            return mock

        with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
            with patch("subprocess.run", side_effect=mock_run):
                result = _detect_nvidia(gpu)
        assert result is True
        assert gpu.detected is True
        assert gpu.vendor == "nvidia"
        assert "RTX 4090" in gpu.name
        assert gpu.driver == "556.12"
        assert gpu.vram_gb == 24.0
        assert gpu.cuda_version == "12.4"

    def test_nvidia_smi_failure(self):
        """nvidia-smi failure should be handled gracefully."""
        gpu = GPUInfo()
        with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 10)):
                result = _detect_nvidia(gpu)
        assert result is False
        assert gpu.detected is False


class TestGPUDectionMetal:
    """Tests for Apple Metal GPU detection."""

    def test_metal_no_system_profiler(self):
        """Missing system_profiler should return False."""
        gpu = GPUInfo()
        with patch("shutil.which", return_value=None):
            result = _detect_metal(gpu)
        assert result is False

    def test_metal_detected(self):
        """system_profiler output should be parsed correctly."""
        gpu = GPUInfo()
        sp_output = """Graphics/Displays:
    Chipset Model: Apple M3 Max
    VRAM (Total): 36 GB
    Metal: Supported
"""
        mock_result = MagicMock()
        mock_result.stdout = sp_output
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/sbin/system_profiler"):
            with patch("subprocess.run", return_value=mock_result):
                result = _detect_metal(gpu)
        assert result is True
        assert gpu.detected is True
        assert gpu.vendor == "apple"
        assert "M3 Max" in gpu.name
        assert gpu.vram_gb == 36.0
        assert gpu.metal_supported is True


class TestGPUDectionROCm:
    """Tests for AMD ROCm GPU detection."""

    def test_rocm_no_smi(self):
        """Missing rocm-smi should return False."""
        gpu = GPUInfo()
        with patch("shutil.which", return_value=None):
            result = _detect_rocm(gpu)
        assert result is False

    def test_rocm_detected(self):
        """rocm-smi output should be parsed correctly."""
        gpu = GPUInfo()
        mock_result = MagicMock()
        mock_result.stdout = "Product Name: AMD Radeon RX 7900 XTX\n"
        mock_result.returncode = 0

        mock_vram = MagicMock()
        mock_vram.stdout = "VRAM Size: 24 GB\n"
        mock_vram.returncode = 0

        with patch("shutil.which", return_value="/opt/rocm/bin/rocm-smi"):
            with patch("subprocess.run", side_effect=[mock_result, mock_vram]):
                result = _detect_rocm(gpu)
        assert result is True
        assert gpu.detected is True
        assert gpu.vendor == "amd"
        assert "RX 7900 XTX" in gpu.name
        assert gpu.rocm_supported is True
        assert gpu.vram_gb == 24.0


class TestGPUDectionVulkan:
    """Tests for Vulkan GPU detection."""

    def test_vulkan_no_vulkaninfo(self):
        """Missing vulkaninfo should return False."""
        gpu = GPUInfo()
        with patch("shutil.which", return_value=None):
            result = _detect_vulkan(gpu)
        assert result is False

    def test_vulkan_detected(self):
        """vulkaninfo output should be parsed correctly."""
        gpu = GPUInfo()
        mock_result = MagicMock()
        mock_result.stdout = """
Vulkan Instance Version: 1.3.275
GPU0:
    deviceName     = NVIDIA GeForce RTX 4090
    deviceType     = DISCRETE_GPU
"""
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/vulkaninfo"):
            with patch("subprocess.run", return_value=mock_result):
                result = _detect_vulkan(gpu)
        assert result is True
        assert gpu.vulkan_supported is True
        assert "RTX 4090" in gpu.name

    def test_vulkan_detected_but_no_new_gpu(self):
        """Vulkan should not overwrite existing NVIDIA detection."""
        gpu = GPUInfo(detected=True, vendor="nvidia", name="NVIDIA RTX 4090")
        with patch("shutil.which", return_value="/usr/bin/vulkaninfo"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("vulkaninfo", 10)):
                result = _detect_vulkan(gpu)
        assert result is False
        # Original detection preserved
        assert gpu.vendor == "nvidia"


# ═══════════════════════════════════════════════════════════════════════════════
# Full Detection Integration Tests (mocked)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullDetection:
    """Integration tests for full system detection."""

    def test_detect_full_windows(self):
        """Full detection on Windows should populate all fields."""
        detector = SystemDetector()

        with patch.multiple(
            "platform",
            system=MagicMock(return_value="Windows"),
            version=MagicMock(return_value="10.0.22631"),
            machine=MagicMock(return_value="AMD64"),
            processor=MagicMock(return_value="Intel64 Family 6"),
        ):
            with patch("psutil.cpu_count", side_effect=lambda logical: 16 if logical else 8):
                mock_mem = MagicMock()
                mock_mem.total = 32 * 1024 ** 3
                mock_mem.available = 18 * 1024 ** 3
                with patch("psutil.virtual_memory", return_value=mock_mem):
                    with patch("prysm.system.detector.detect_gpu",
                               return_value=GPUInfo()):
                        info = detector.detect()

        assert info.os_name == "windows"
        assert info.architecture == "x86_64"
        assert info.ram_total_gb == 32.0

    def test_detect_lightweight(self):
        """detect() should not raise on minimal system."""
        detector = SystemDetector()
        with patch.multiple(
            "psutil",
            cpu_count=MagicMock(return_value=8),
            virtual_memory=MagicMock(side_effect=ValueError("no perms")),
        ):
            with patch("prysm.system.detector.detect_gpu",
                       return_value=GPUInfo()):
                with patch("pathlib.Path.exists", return_value=False):
                    info = detector.detect()

        assert isinstance(info, SystemInfo)
        assert info.ram_total_gb == 0.0  # fallback value
