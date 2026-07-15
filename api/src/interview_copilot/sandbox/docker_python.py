import asyncio
import json
import time
from dataclasses import dataclass
from uuid import uuid4

from interview_copilot.domain.coding import (
    CodingExecutionResult,
    CodingProblemSpec,
)

RESULT_PREFIX = "__INTERVIEW_COPILOT_RESULT__"

_HARNESS = r'''
import contextlib
import io
import json
import sys
import time

PREFIX = "__INTERVIEW_COPILOT_RESULT__"


def safe_value(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError, OverflowError):
        return repr(value)[:1000]


payload = json.loads(sys.stdin.read())
namespace = {"__name__": "candidate"}
started = time.monotonic()
try:
    exec(compile(payload["source"], "candidate.py", "exec"), namespace)
except BaseException as exc:
    status = "compile_error" if isinstance(exc, SyntaxError) else "runtime_error"
    result = {
        "status": status,
        "tests": [],
        "duration_ms": int((time.monotonic() - started) * 1000),
        "error": f"{type(exc).__name__}: {str(exc)[:900]}",
    }
else:
    target = namespace.get(payload["entrypoint"])
    if not callable(target):
        result = {
            "status": "runtime_error",
            "tests": [],
            "duration_ms": int((time.monotonic() - started) * 1000),
            "error": "没有找到可调用的 solve 函数",
        }
    else:
        tests = []
        has_runtime_error = False
        for case in payload["tests"]:
            case_started = time.monotonic()
            output = io.StringIO()
            actual = None
            error = None
            try:
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    actual = target(*case["arguments"])
                passed = actual == case["expected"]
            except BaseException as exc:
                passed = False
                has_runtime_error = True
                error = f"{type(exc).__name__}: {str(exc)[:900]}"
            tests.append({
                "name": case["name"],
                "passed": passed,
                "expected": case["expected"],
                "actual": safe_value(actual),
                "error": error,
                "stdout": output.getvalue()[:4000],
                "duration_ms": int((time.monotonic() - case_started) * 1000),
            })
        status = "runtime_error" if has_runtime_error else (
            "passed" if all(item["passed"] for item in tests) else "failed"
        )
        result = {
            "status": status,
            "tests": tests,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "error": None,
        }

sys.stdout.write(PREFIX + json.dumps(result, ensure_ascii=False, separators=(",", ":")))
'''


class SandboxUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class DockerPythonSandboxConfig:
    image: str
    timeout_seconds: float = 3.0
    memory_mb: int = 128
    cpu_count: float = 0.5
    pids_limit: int = 64
    output_limit_bytes: int = 65_536
    max_concurrency: int = 2


class DockerPythonSandbox:
    def __init__(self, config: DockerPythonSandboxConfig) -> None:
        if "@sha256:" not in config.image:
            raise ValueError("Coding 沙箱镜像必须固定到 sha256 摘要")
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrency)

    async def execute(
        self, *, source: str, problem: CodingProblemSpec
    ) -> CodingExecutionResult:
        payload = json.dumps(
            {
                "source": source,
                "entrypoint": problem.entrypoint,
                "tests": [item.model_dump(mode="json") for item in problem.public_tests],
            },
            ensure_ascii=False,
        ).encode()
        container_name = f"interview-coding-{uuid4().hex}"
        command = self._command(container_name)
        async with self._semaphore:
            started = time.monotonic()
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            except (FileNotFoundError, OSError) as exc:
                raise SandboxUnavailableError("Coding 沙箱当前不可用") from exc
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(payload)
            await process.stdin.drain()
            process.stdin.close()
            try:
                output = await asyncio.wait_for(
                    self._read_limited(process.stdout),
                    timeout=self._config.timeout_seconds,
                )
                remaining = max(
                    0.1,
                    self._config.timeout_seconds - (time.monotonic() - started),
                )
                exit_code = await asyncio.wait_for(process.wait(), timeout=remaining)
            except TimeoutError:
                await self._terminate(container_name, process)
                return CodingExecutionResult(
                    status="timed_out",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error=f"代码执行超过 {self._config.timeout_seconds:g} 秒限制",
                )
            except _OutputLimitError:
                await self._terminate(container_name, process)
                return CodingExecutionResult(
                    status="output_limit",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error=(
                        f"程序输出超过 {self._config.output_limit_bytes // 1024}KB 限制"
                    ),
                )
            except asyncio.CancelledError:
                await self._terminate(container_name, process)
                raise
        if exit_code != 0:
            if exit_code == 137:
                return CodingExecutionResult(
                    status="memory_limit",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    error=f"代码执行超过 {self._config.memory_mb}MB 内存限制",
                )
            raise SandboxUnavailableError("Coding 沙箱启动失败，请确认 Docker 镜像可用")
        marker = output.rfind(RESULT_PREFIX.encode())
        if marker < 0:
            raise SandboxUnavailableError("Coding 沙箱返回了无法解析的结果")
        try:
            data = json.loads(output[marker + len(RESULT_PREFIX) :])
            return CodingExecutionResult.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise SandboxUnavailableError("Coding 沙箱返回了无效结果") from exc

    def _command(self, container_name: str) -> list[str]:
        config = self._config
        return [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--name",
            container_name,
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--workdir",
            "/tmp",
            "--user",
            "65534:65534",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(config.pids_limit),
            "--memory",
            f"{config.memory_mb}m",
            "--memory-swap",
            f"{config.memory_mb}m",
            "--cpus",
            str(config.cpu_count),
            "--ulimit",
            "nofile=64:64",
            "--ipc",
            "none",
            "--log-driver",
            "none",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            config.image,
            "python",
            "-I",
            "-S",
            "-c",
            _HARNESS,
        ]

    async def _read_limited(self, stream: asyncio.StreamReader) -> bytes:
        chunks: list[bytes] = []
        size = 0
        while chunk := await stream.read(8_192):
            size += len(chunk)
            if size > self._config.output_limit_bytes:
                raise _OutputLimitError
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    async def _terminate(container_name: str, process: asyncio.subprocess.Process) -> None:
        killer = await asyncio.create_subprocess_exec(
            "docker",
            "kill",
            container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
        if process.returncode is None:
            process.kill()
        await process.wait()


class _OutputLimitError(RuntimeError):
    pass
