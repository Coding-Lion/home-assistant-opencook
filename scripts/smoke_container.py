"""Boot the actual add-on image with Supervisor-style data and check persistence."""

import json
import os
import subprocess
import time
import urllib.request
from uuid import uuid4

NAME = f"opencook-smoke-{uuid4().hex[:8]}"
VOLUME = f"{NAME}-data"
PLATFORM = os.environ.get("TEST_PLATFORM", "linux/amd64")


def docker(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True).strip()


def request(path: str, body: dict | None = None):
    req = urllib.request.Request(
        f"http://127.0.0.1:18000{path}",
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as response:
        return json.load(response)


try:
    docker("volume", "create", VOLUME)
    # Use the image's Python to write options without host bind-mount ownership issues.
    docker(
        "run",
        "--rm",
        "--platform",
        PLATFORM,
        "-v",
        f"{VOLUME}:/data",
        "--entrypoint",
        "python",
        "opencook-test:latest",
        "-c",
        "from pathlib import Path; Path('/data/options.json').write_text('{}')",
    )
    docker(
        "run",
        "-d",
        "--name",
        NAME,
        "--platform",
        PLATFORM,
        "-v",
        f"{VOLUME}:/data",
        "-p",
        "127.0.0.1:18000:8000",
        "opencook-test:latest",
    )
    for _ in range(60):
        try:
            assert request("/health") == {"status": "ok"}
            break
        except (OSError, AssertionError):
            time.sleep(1)
    else:
        raise RuntimeError("openCook did not become healthy")
    household = request("/households", {"name": "Persistent kitchen"})
    assert household["invite_code"]
    assert docker("exec", NAME, "id", "-u") == "0"  # exec defaults to container config user
    # PID 1 is the launcher/uvicorn; its effective UID must be the service user.
    status = docker("exec", NAME, "cat", "/proc/1/status")
    assert "Uid:\t10001\t10001\t10001\t10001" in status
    docker("restart", NAME)
    for _ in range(60):
        try:
            households = request("/households")
            assert households[0]["id"] == household["household_id"]
            break
        except (OSError, AssertionError):
            time.sleep(1)
    else:
        raise RuntimeError("Household did not survive a restart")
    print(f"Container smoke test passed for {PLATFORM}")
finally:
    subprocess.run(["docker", "logs", NAME], check=False)
    subprocess.run(["docker", "rm", "--force", NAME], check=False)
    subprocess.run(["docker", "volume", "rm", VOLUME], check=False)
