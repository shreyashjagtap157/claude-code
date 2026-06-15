"""GPU detection — NVIDIA CUDA, Apple Metal, AMD ROCm, Vulkan, and fallback."""

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GPUInfo:
    """Information about a detected GPU."""

    detected: bool = False
    vendor: Optional[str] = None          # "nvidia", "amd", "apple", "intel"
    name: Optional[str] = None            # "NVIDIA GeForce RTX 4090"
    vram_gb: Optional[float] = None       # Dedicated VRAM in GB
    driver: Optional[str] = None          # "556.12", "24.20"
    cuda_version: Optional[str] = None    # "12.4"
    cuda_cores: Optional[int] = None      # Number of CUDA cores
    metal_supported: bool = False         # Apple Metal available
    rocm_supported: bool = False          # AMD ROCm available
    vulkan_supported: bool = False        # Vulkan compute available
    openvino_supported: bool = False      # Intel OpenVINO available
    tpu_available: bool = False           # Google TPU (via runtime)

    @property
    def summary(self) -> str:
        """One-line GPU summary."""
        if not self.detected:
            return "No GPU detected"
        parts = [self.name or "Unknown GPU"]
        if self.vram_gb:
            parts.append(f"{self.vram_gb:.0f} GB")
        if self.cuda_version:
            parts.append(f"CUDA {self.cuda_version}")
        backends = []
        if self.metal_supported:
            backends.append("Metal")
        if self.rocm_supported:
            backends.append("ROCm")
        if self.vulkan_supported:
            backends.append("Vulkan")
        if backends:
            parts.append(f"[{', '.join(backends)}]")
        return " | ".join(parts)


def detect_gpu(os_name: str) -> GPUInfo:
    """Detect GPU information using platform-specific methods.

    Detection order:
    1. nvidia-smi (NVIDIA GPU) — works on all OS with NVIDIA drivers
    2. macOS Metal (Apple Silicon / AMD)
    3. rocm-smi (AMD ROCm on Linux)
    4. vulkaninfo (Vulkan-capable GPUs)
    5. Default CPU-only fallback

    Args:
        os_name: Operating system name ("windows", "darwin", "linux").

    Returns:
        GPUInfo with detected fields populated. If no GPU found,
        returns a default GPUInfo with detected=False.
    """
    gpu = GPUInfo()

    # 1. Try NVIDIA detection (works cross-platform)
    if _detect_nvidia(gpu):
        return gpu

    # 2. macOS: try Metal detection
    if os_name == "darwin":
        _detect_metal(gpu)
        if gpu.detected:
            return gpu

    # 3. AMD ROCm on Linux
    if os_name == "linux":
        _detect_rocm(gpu)
        if gpu.detected:
            return gpu

    # 4. Vulkan fallback (cross-platform)
    _detect_vulkan(gpu)
    if gpu.detected:
        return gpu

    return gpu


def _detect_nvidia(gpu: GPUInfo) -> bool:
    """Detect NVIDIA GPU via nvidia-smi.

    Returns:
        True if NVIDIA GPU was detected, False otherwise.
    """
    if not shutil.which("nvidia-smi"):
        return False

    try:
        # Query GPU name, driver version, VRAM, and CUDA version
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False

        line = result.stdout.strip()
        if not line:
            return False

        # Parse: "NVIDIA GeForce RTX 4090, 556.12, 24564 MiB"
        match = re.match(
            r"^(.*?),\s*([\d.]+),\s*([\d.]+)",
            line,
        )
        if match:
            gpu.detected = True
            gpu.vendor = "nvidia"
            gpu.name = match.group(1).strip()
            gpu.driver = match.group(2).strip()
            vram_mib = float(match.group(3))
            gpu.vram_gb = round(vram_mib / 1024, 1)

            # Get CUDA version from nvidia-smi default output header
            cuda_result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            cuda_match = re.search(r"CUDA Version:\s*([\d.]+)", cuda_result.stdout)
            if cuda_match:
                gpu.cuda_version = cuda_match.group(1)

            return True

    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    return False


def _detect_metal(gpu: GPUInfo) -> bool:
    """Detect Apple GPU via Metal on macOS.

    Uses system_profiler to check for Metal-capable GPUs.
    Note: On Apple Silicon, the GPU is integrated with the SoC.

    Returns:
        True if Metal-capable GPU was detected, False otherwise.
    """
    try:
        result = subprocess.run(
            [
                "system_profiler",
                "SPDisplaysDataType",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False

        output = result.stdout
        gpu.detected = True
        gpu.vendor = "apple"

        # Extract GPU name
        chipset_match = re.search(r"Chipset Model:\s*(.+)", output)
        if chipset_match:
            gpu.name = chipset_match.group(1).strip()

        # Extract VRAM (unified memory)
        vram_match = re.search(r"VRAM \(Total\):\s*([\d.]+)\s*(\w+)", output)
        if vram_match:
            value = float(vram_match.group(1))
            unit = vram_match.group(2).lower()
            if unit in ("gb",):
                gpu.vram_gb = value
            elif unit in ("mb",):
                gpu.vram_gb = round(value / 1024, 1)

        # Metal is supported on all modern macOS GPUs
        metal_match = re.search(r"Metal\s*:\s*Supported", output, re.IGNORECASE)
        gpu.metal_supported = bool(metal_match)

        return True

    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    return False


def _detect_rocm(gpu: GPUInfo) -> bool:
    """Detect AMD GPU via rocm-smi on Linux.

    Returns:
        True if AMD ROCm-capable GPU was detected, False otherwise.
    """
    if not shutil.which("rocm-smi"):
        return False

    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False

        output = result.stdout
        name_match = re.search(r"Product Name\s*:\s*(.+)", output)
        if name_match:
            gpu.detected = True
            gpu.vendor = "amd"
            gpu.name = name_match.group(1).strip()
            gpu.rocm_supported = True

            # Try to get VRAM
            try:
                vram_result = subprocess.run(
                    ["rocm-smi", "--showmeminfo", "vram"],
                    capture_output=True, text=True, timeout=5,
                )
                vram_match = re.search(r"VRAM Size\s*:\s*([\d.]+)\s*(\w+)", vram_result.stdout)
                if vram_match:
                    value = float(vram_match.group(1))
                    unit = vram_match.group(2).lower()
                    if unit in ("gb",):
                        gpu.vram_gb = value
                    elif unit in ("mb",):
                        gpu.vram_gb = round(value / 1024, 1)
            except (subprocess.SubprocessError, ValueError):
                pass

            return True

    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    return False


def _detect_vulkan(gpu: GPUInfo) -> bool:
    """Detect Vulkan-capable GPUs via vulkaninfo.

    This is a cross-platform fallback that works on Windows, macOS, and Linux
    if the Vulkan SDK is installed.

    Returns:
        True if Vulkan-capable GPU was detected, False otherwise.
    """
    if not shutil.which("vulkaninfo"):
        return False

    try:
        result = subprocess.run(
            ["vulkaninfo", "--summary"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False

        output = result.stdout
        gpu.vulkan_supported = True

        # Only set detected if we haven't already found a GPU
        if not gpu.detected:
            # Try to extract GPU name from vulkaninfo output
            for line in output.splitlines():
                gpu_match = re.search(r"deviceName\s*=\s*(.+)", line)
                if gpu_match:
                    gpu.detected = True
                    gpu.name = gpu_match.group(1).strip()
                    break

        return True

    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass

    return False
