"""System detection — OS, architecture, CPU, RAM, and environment detection."""

import os
import platform
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import psutil

from prysm.system.gpu import GPUInfo, detect_gpu


@dataclass
class SystemInfo:
    """Comprehensive system information detected at runtime."""

    # OS
    os_name: str = ""               # "windows", "darwin", "linux"
    os_version: str = ""            # "10.0.22631", "24.3.0", "6.8.0"
    architecture: str = ""           # "x86_64", "aarch64", "arm64"

    # CPU
    cpu_brand: str = ""             # "Intel(R) Core(TM) i7-13700K"
    cpu_cores: int = 0              # Physical cores
    cpu_threads: int = 0            # Logical threads
    cpu_features: list[str] = field(default_factory=list)  # ["avx2", "avx512", "neon", ...]

    # RAM
    ram_total_gb: float = 0.0       # Total system RAM in GB
    ram_available_gb: float = 0.0   # Available RAM at detection time in GB

    # GPU (delegated to gpu.py)
    gpu: GPUInfo = field(default_factory=GPUInfo)

    # Environment
    is_wsl: bool = False            # Windows Subsystem for Linux
    is_docker: bool = False         # Running inside a container
    is_remote: bool = False         # SSH/remote session

    @property
    def has_gpu(self) -> bool:
        """Whether a GPU was detected."""
        return self.gpu.detected

    @property
    def summary(self) -> str:
        """One-line summary of the system."""
        parts = [
            f"{self.os_name.title()} {self.os_version}",
            f"{self.architecture}",
            f"{self.cpu_brand or 'Unknown CPU'} ({self.cpu_cores}C/{self.cpu_threads}T)",
        ]
        if self.has_gpu:
            parts.append(f"{self.gpu.name or 'Unknown GPU'} ({self.gpu.vram_gb:.0f} GB VRAM)" if self.gpu.vram_gb else f"{self.gpu.name or 'Unknown GPU'}")
        extras = []
        if self.is_wsl:
            extras.append("WSL")
        if self.is_docker:
            extras.append("Docker")
        if self.is_remote:
            extras.append("Remote")
        if extras:
            parts.append(f"[{', '.join(extras)}]")
        return " | ".join(parts)


class SystemDetector:
    """Detects system hardware and environment information."""

    def detect(self) -> SystemInfo:
        """Run all system detection and return a complete SystemInfo.

        Returns:
            SystemInfo with all fields populated.
        """
        info = SystemInfo()
        self._detect_os(info)
        self._detect_arch(info)
        self._detect_cpu(info)
        self._detect_ram(info)
        self._detect_gpu(info)
        self._detect_environment(info)
        return info

    def _detect_os(self, info: SystemInfo) -> None:
        """Detect operating system name and version."""
        system = platform.system().lower()
        if system == "windows":
            info.os_name = "windows"
            info.os_version = platform.version()  # "10.0.22631"
        elif system == "darwin":
            info.os_name = "darwin"
            info.os_version = platform.mac_ver()[0]  # "14.3.0"
        elif system == "linux":
            info.os_name = "linux"
            try:
                import distro
                info.os_version = distro.version() or platform.release()
            except ImportError:
                info.os_version = platform.release()
        else:
            info.os_name = system
            info.os_version = platform.release()

    def _detect_arch(self, info: SystemInfo) -> None:
        """Detect CPU architecture."""
        machine = platform.machine().lower()
        # Normalize common architecture names
        arch_map = {
            "amd64": "x86_64",
            "x86_64": "x86_64",
            "x86": "x86",
            "i386": "x86",
            "i686": "x86",
            "aarch64": "arm64",
            "arm64": "arm64",
            "armv7l": "armv7",
            "armv6l": "armv6",
        }
        info.architecture = arch_map.get(machine, machine)

    def _detect_cpu(self, info: SystemInfo) -> None:
        """Detect CPU brand, cores, threads, and features."""
        # Physical cores
        try:
            info.cpu_cores = psutil.cpu_count(logical=False) or 0
        except (ValueError, RuntimeError):
            info.cpu_cores = 0

        # Logical threads
        try:
            info.cpu_threads = psutil.cpu_count(logical=True) or 0
        except (ValueError, RuntimeError):
            info.cpu_threads = 0

        # CPU brand and features via py-cpuinfo (optional dependency)
        try:
            import cpuinfo
            cpu_info = cpuinfo.get_cpu_info()
            info.cpu_brand = cpu_info.get("brand_raw", "")
            info.cpu_features = cpu_info.get("flags", [])
            # Ensure features is a list of strings
            if isinstance(info.cpu_features, str):
                info.cpu_features = info.cpu_features.split()
        except ImportError:
            # Fallback: basic brand from platform
            info.cpu_brand = platform.processor() or ""
            # Try /proc/cpuinfo on Linux
            if info.os_name == "linux":
                cpu_model = self._read_cpuinfo_field("model name")
                if cpu_model:
                    info.cpu_brand = cpu_model
            info.cpu_features = []

    def _detect_ram(self, info: SystemInfo) -> None:
        """Detect total and available RAM in GB."""
        try:
            mem = psutil.virtual_memory()
            info.ram_total_gb = round(mem.total / (1024 ** 3), 1)
            info.ram_available_gb = round(mem.available / (1024 ** 3), 1)
        except (ValueError, RuntimeError):
            info.ram_total_gb = 0.0
            info.ram_available_gb = 0.0

    def _detect_gpu(self, info: SystemInfo) -> None:
        """Detect GPU information."""
        info.gpu = detect_gpu(info.os_name)

    def _detect_environment(self, info: SystemInfo) -> None:
        """Detect WSL, Docker, and remote session."""
        # WSL detection
        if info.os_name == "linux":
            try:
                proc_version = Path("/proc/version")
                if proc_version.exists():
                    content = proc_version.read_text().lower()
                    info.is_wsl = "microsoft" in content or "wsl" in content
            except (OSError, IOError):
                info.is_wsl = False

        # Docker detection
        if info.os_name == "linux":
            try:
                dockerenv = Path("/.dockerenv")
                if dockerenv.exists():
                    info.is_docker = True
            except (OSError, IOError):
                info.is_docker = False
            try:
                cgroup = Path("/proc/1/cgroup")
                if cgroup.exists():
                    content = cgroup.read_text().lower()
                    if "docker" in content:
                        info.is_docker = True
            except (OSError, IOError):
                pass

        # Remote session detection
        info.is_remote = bool(
            os.environ.get("SSH_TTY")
            or os.environ.get("SSH_CONNECTION")
            or os.environ.get("SSH_CLIENT")
        )

    @staticmethod
    def _read_cpuinfo_field(field: str) -> Optional[str]:
        """Read a field from /proc/cpuinfo on Linux."""
        try:
            cpuinfo_path = Path("/proc/cpuinfo")
            if not cpuinfo_path.exists():
                return None
            content = cpuinfo_path.read_text()
            for line in content.splitlines():
                if line.startswith(field):
                    match = re.search(r":\s*(.*)", line)
                    if match:
                        return match.group(1).strip()
            return None
        except (OSError, IOError):
            return None
