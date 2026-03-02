from __future__ import annotations

import heapq
from dataclasses import dataclass, field


@dataclass(order=True)
class Job:
    priority: int
    name: str = field(compare=False)
    retries: int = field(default=0, compare=False)


def run_queue(jobs: list[Job], max_retries: int = 1) -> list[str]:
    heap = jobs[:]
    heapq.heapify(heap)
    completed: list[str] = []
    while heap:
        job = heapq.heappop(heap)
        if 'fail' in job.name and job.retries < max_retries:
            job.retries += 1
            heapq.heappush(heap, job)
            continue
        completed.append(job.name)
    return completed


def run_demo() -> dict[str, object]:
    done = run_queue([Job(2, 'email'), Job(1, 'fail-once-task')])
    return {'project': 'distributed_job_queue', 'completed': done}


if __name__ == '__main__':
    print(run_demo())
