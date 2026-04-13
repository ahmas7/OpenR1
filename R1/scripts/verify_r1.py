import sys
import os

# Add parent directory (project root) to path so R1 package can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from R1.api.server import app


CHECKS = [
    ("GET", "/health", None),
    ("GET", "/providers", None),
    ("GET", "/skills", None),
    ("GET", "/skills/enhanced", None),
    ("GET", "/cron/jobs", None),
    ("GET", "/webhooks", None),
    ("GET", "/gateway/sessions", None),
    ("GET", "/system", None),
    ("GET", "/operations/overview", None),
    ("GET", "/voice/languages", None),
    ("POST", "/chat", {"message": "what time is it?"}),
]


def main() -> int:
    failures = []
    with TestClient(app) as client:
        for method, path, payload in CHECKS:
            response = client.request(method, path, json=payload)
            print(f"{method} {path} -> {response.status_code}")
            if response.status_code >= 400:
                failures.append((method, path, response.status_code, response.text[:200]))

    if failures:
        print("\nFailures:")
        for method, path, status_code, body in failures:
            print(f"- {method} {path}: {status_code} {body}")
        return 1

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
