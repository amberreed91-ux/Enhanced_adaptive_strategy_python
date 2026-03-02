from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ServiceStatus:
    name: str
    version: str
    healthy: bool


def health_check(dependencies_ok: bool) -> ServiceStatus:
    return ServiceStatus(name='portfolio-service', version='1.0.0', healthy=dependencies_ok)


def run_demo() -> dict[str, object]:
    status = health_check(True)
    return {'project': 'dockerized_microservice', 'healthy': status.healthy, 'version': status.version}


if __name__ == '__main__':
    print(run_demo())
