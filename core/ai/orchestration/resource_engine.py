
"""Vault AI Resource Engine.

Collects hardware information and assesses whether sufficient
resources are available for local AI tasks.

This module only inspects system resources.
It does not modify system settings or execute AI models.
"""

import platform
import shutil
import subprocess

import psutil


class ResourceEngine:
    """Collect and assess system resources for Vault AI."""

    # General system thresholds (GB)
    CRITICAL_RAM_GB = 1.5
    HEALTHY_RAM_GB = 3.5

    # Configurable model estimates (GB) - for quantized 7B/8B models (e.g. qwen3:8b Q4)
    DEFAULT_MODEL_RAM_GB = 4.0
    DEFAULT_MODEL_VRAM_GB = 3.0

    def get_cpu_info(self):
        """Collect CPU information."""

        return {
            "processor": platform.processor() or "Unknown",
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "usage_percent": psutil.cpu_percent(interval=1),
        }

    def get_memory_info(self):
        """Collect RAM information."""

        memory = psutil.virtual_memory()

        return {
            "total_gb": round(memory.total / (1024 ** 3), 2),
            "available_gb": round(memory.available / (1024 ** 3), 2),
            "used_gb": round(memory.used / (1024 ** 3), 2),
            "usage_percent": memory.percent,
        }

    def get_disk_info(self):
        """Collect disk information."""

        disk = shutil.disk_usage("C:\\")

        return {
            "total_gb": round(disk.total / (1024 ** 3), 2),
            "used_gb": round(disk.used / (1024 ** 3), 2),
            "free_gb": round(disk.free / (1024 ** 3), 2),
        }

    def get_gpu_info(self):
        """Collect NVIDIA GPU information using nvidia-smi."""

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )

            gpu = result.stdout.strip().split(",")

            if len(gpu) != 4:
                raise ValueError("Unexpected nvidia-smi output.")

            return {
                "available": True,
                "name": gpu[0].strip(),
                "total_vram_mb": int(gpu[1].strip()),
                "used_vram_mb": int(gpu[2].strip()),
                "free_vram_mb": int(gpu[3].strip()),
            }

        except (
            FileNotFoundError,
            subprocess.SubprocessError,
            ValueError,
            IndexError,
        ):
            return {
                "available": False,
                "name": "GPU information unavailable",
            }

    def get_resource_report(self):
        """Collect a complete system resource report."""

        return {
            "system": platform.system(),
            "platform": platform.platform(),
            "cpu": self.get_cpu_info(),
            "memory": self.get_memory_info(),
            "disk": self.get_disk_info(),
            "gpu": self.get_gpu_info(),
        }

    def assess_resources(self, report=None):
        """Assess general system resource availability."""

        if report is None:
            report = self.get_resource_report()

        memory = report["memory"]
        gpu = report["gpu"]
        cpu = report["cpu"]

        available_ram = memory["available_gb"]
        free_vram = gpu.get("free_vram_mb", 0)
        cpu_usage = cpu["usage_percent"]

        warnings = []

        # RAM assessment
        if available_ram < self.CRITICAL_RAM_GB:
            warnings.append(
                "Critical: Less than 2 GB RAM available."
            )
            ram_status = "critical"

        elif available_ram < self.HEALTHY_RAM_GB:
            warnings.append("Low available RAM.")
            ram_status = "low"

        else:
            ram_status = "healthy"

        # GPU assessment
        if not gpu.get("available"):
            gpu_status = "unavailable"

        elif free_vram < 1024:
            gpu_status = "insufficient"

        else:
            gpu_status = "limited"

        # CPU assessment
        if cpu_usage >= 90:
            cpu_status = "high_load"
        else:
            cpu_status = "available"

        # Execution recommendation
        if ram_status == "critical":
            execution_mode = "defer"
            reason = "Insufficient available system RAM."

        elif cpu_status == "high_load":
            execution_mode = "defer"
            reason = "CPU is under heavy load."

        elif gpu_status == "insufficient":
            execution_mode = "cpu"
            reason = "Insufficient free GPU memory."

        else:
            execution_mode = "cpu"
            reason = "CPU execution selected as the conservative default."

        return {
            "ram_status": ram_status,
            "gpu_status": gpu_status,
            "cpu_status": cpu_status,
            "execution_mode": execution_mode,
            "recommended": execution_mode != "defer",
            "reason": reason,
            "warnings": warnings,
        }

    def assess_model_resources(
        self,
        model_name="qwen3:8b",
        estimated_ram_gb=DEFAULT_MODEL_RAM_GB,
        estimated_vram_gb=DEFAULT_MODEL_VRAM_GB,
        report=None,
    ):
        """Assess whether sufficient resources are available for a model.

        Memory estimates are configurable planning assumptions,
        not guaranteed runtime requirements.
        """

        if report is None:
            report = self.get_resource_report()

        memory = report["memory"]
        gpu = report["gpu"]

        available_ram = memory["available_gb"]

        available_vram = (
            gpu.get("free_vram_mb", 0) / 1024
            if gpu.get("available")
            else 0
        )

        warnings = []

        # 0. Check if model is already resident in Ollama memory
        try:
            from core.ai.ollama_client import OllamaClient
            client = OllamaClient()
            if client.is_model_loaded(model_name):
                return {
                    "model_name": model_name,
                    "available_ram_gb": available_ram,
                    "estimated_ram_gb": estimated_ram_gb,
                    "available_vram_gb": round(available_vram, 2),
                    "estimated_vram_gb": estimated_vram_gb,
                    "ram_sufficient": True,
                    "gpu_sufficient": True,
                    "execution_mode": "gpu" if gpu.get("available") else "cpu",
                    "recommended": True,
                    "reason": f"Model '{model_name}' is already loaded in memory and ready for inference.",
                    "warnings": [],
                }
        except Exception:
            pass

        ram_sufficient = available_ram >= estimated_ram_gb
        total_ram = memory.get("total_gb", 0)
        gpu_has_capacity = gpu.get("available", False) and (available_vram >= 1.0 or gpu.get("total_vram_mb", 0) >= 3000)

        if not ram_sufficient:
            warnings.append(
                f"RAM below estimated optimal requirement for {model_name}. "
                f"Available: {available_ram} GB; optimal estimate: {estimated_ram_gb} GB."
            )

        if not gpu.get("available", False):
            warnings.append(
                f"Dedicated GPU unavailable for {model_name}; will use CPU."
            )

        # 1. GPU / Hybrid Execution if dedicated GPU is available
        if gpu_has_capacity:
            if available_vram >= estimated_vram_gb:
                execution_mode = "gpu"
                reason = f"Sufficient dedicated GPU memory ({available_vram:.1f} GB) available for {model_name}."
            else:
                execution_mode = "hybrid"
                reason = f"GPU acceleration ({available_vram:.1f} GB VRAM) available for hybrid inference."
            recommended = True

        # 2. CPU Execution if RAM is adequate (or total RAM >= 8GB with available RAM >= 1.0GB)
        elif ram_sufficient or (total_ram >= 8.0 and available_ram >= 1.0):
            execution_mode = "cpu"
            recommended = True
            reason = f"Available system RAM ({available_ram:.1f} GB) is adequate for {model_name}."

        # 3. Defer only if memory is critically low (< 1 GB free with no GPU)
        else:
            execution_mode = "defer"
            recommended = False
            reason = (
                f"Insufficient memory ({available_ram:.1f} GB available) to safely load {model_name}."
            )

        return {
            "model_name": model_name,
            "available_ram_gb": available_ram,
            "estimated_ram_gb": estimated_ram_gb,
            "available_vram_gb": round(available_vram, 2),
            "estimated_vram_gb": estimated_vram_gb,
            "ram_sufficient": ram_sufficient,
            "gpu_sufficient": gpu_has_capacity,
            "execution_mode": execution_mode,
            "recommended": recommended,
            "reason": reason,
            "warnings": warnings,
        }
