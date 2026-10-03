from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar


T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True)
class WorkerResult:
    name: str
    ok: bool
    value: object | None = None
    error: str | None = None


def run_parallel(named_jobs: dict[str, Callable[[], object]], *, max_workers: int = 8) -> tuple[WorkerResult, ...]:
    if max_workers <= 0:
        raise ValueError("max_workers must be positive")
    rows: list[WorkerResult] = []
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="rudrila-hot") as pool:
        futures = {pool.submit(fn): name for name, fn in named_jobs.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                rows.append(WorkerResult(name, True, future.result(), None))
            except Exception as exc:
                rows.append(WorkerResult(name, False, None, f"{type(exc).__name__}: {exc}"))
    return tuple(sorted(rows, key=lambda x: x.name))
