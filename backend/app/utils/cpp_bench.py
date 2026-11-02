"""
Credence Core — C++ High-Performance Simulation & Benchmark Harness
Provides a well-defined, tested interface to the C++ core engine as an independent,
benchmarked simulation component, preventing unsynchronized dual sources of truth.
"""

import os
import re
import time
import subprocess
import threading
from typing import Dict, Any, List, Optional

from backend.app.core.config import Config


class CPPEngineHarness:
    """
    Subprocess harness for the C++ Banking Engine.
    Executes transactions against the compiled binary (bank_system.exe / ./bank)
    for benchmarking and computational throughput verification.
    """

    def __init__(self, binary_name: str = "bank_system.exe"):
        self.lock = threading.Lock()
        self.binary_path = os.path.join(Config.BASE_DIR, binary_name)
        self.proc: Optional[subprocess.Popen] = None
        self._is_available = os.path.exists(self.binary_path)

    @property
    def is_available(self) -> bool:
        return self._is_available

    def start_process(self):
        """Start or restart the C++ process."""
        if not self._is_available:
            raise FileNotFoundError(f"C++ binary not found at '{self.binary_path}'")

        if self.proc and self.proc.poll() is None:
            return

        self.proc = subprocess.Popen(
            [self.binary_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=Config.BASE_DIR
        )
        self._read_until("Enter choice: ")

    def _read_until(self, prompt: str = "Enter choice: ", timeout: float = 3.0) -> str:
        """Read stdout until prompt appears."""
        if not self.proc or not self.proc.stdout:
            return ""
        out = []
        start = time.time()
        while time.time() - start < timeout:
            char = self.proc.stdout.read(1)
            if not char:
                break
            out.append(char)
            text = "".join(out)
            if prompt in text:
                return text
        return "".join(out)

    def execute_raw(self, choice: str, inputs: List[str]) -> str:
        """Send choice and inputs to C++ engine synchronously."""
        with self.lock:
            self.start_process()
            if not self.proc or not self.proc.stdin:
                return ""
            self.proc.stdin.write(f"{choice}\n")
            self.proc.stdin.flush()
            for val in inputs:
                self.proc.stdin.write(f"{val}\n")
                self.proc.stdin.flush()
            out = self._read_until("Enter choice: ")
            return self.parse_output(out)

    @staticmethod
    def parse_output(out: str) -> str:
        """Filter interactive prompts and return clean output."""
        clean = re.sub(r"--- Banking Menu ---[\s\S]*?Enter choice:", "", out).strip()
        clean = re.sub(r"Enter .*?:", "", clean).strip()
        return clean

    def benchmark_throughput(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmark transaction throughput of the C++ binary."""
        if not self._is_available:
            return {
                "available": False,
                "message": "C++ binary not compiled on host environment."
            }

        start_time = time.time()
        successful = 0
        try:
            for i in range(iterations):
                # Execute balance inquiry on test account
                out = self.execute_raw("2", ["40273146502136"])
                if out:
                    successful += 1
            duration = time.time() - start_time
            tps = successful / duration if duration > 0 else 0
            return {
                "available": True,
                "iterations": iterations,
                "successful": successful,
                "duration_seconds": round(duration, 4),
                "transactions_per_second": round(tps, 2),
                "avg_latency_ms": round((duration / iterations) * 1000, 3)
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }
        finally:
            self.stop()

    def stop(self):
        """Terminate the subprocess cleanly."""
        with self.lock:
            if self.proc:
                try:
                    if self.proc.stdin:
                        self.proc.stdin.close()
                    if self.proc.stdout:
                        self.proc.stdout.close()
                    if self.proc.stderr:
                        self.proc.stderr.close()
                    if self.proc.poll() is None:
                        self.proc.terminate()
                        self.proc.wait(timeout=1.0)
                except Exception:
                    try:
                        self.proc.kill()
                    except Exception:
                        pass
                self.proc = None


cpp_harness = CPPEngineHarness()
