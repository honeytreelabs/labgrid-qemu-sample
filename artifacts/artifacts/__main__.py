import logging
import os
import signal
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from types import FrameType

import httpx
import yaml

LISTEN_ADDR = os.environ.get("LISTEN_ADDR", "0.0.0.0")  # noqa S104: running inside container
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", 8000))
ARTIFACTS_FILE = Path(os.environ.get("ARTIFACTS_FILE", "/artifacts_srv/artifacts.yaml"))
ARTIFACTS_DIR = Path(os.environ.get("ARTIFACTS_DIR", "artifacts"))
ARTIFACTS_DIR.mkdir(exist_ok=True)


def download_file(url: str, dest: Path) -> None:
    """Downloads a file from a URL to a specified destination."""
    with httpx.stream("GET", url) as response:
        response.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
    print(f"Downloaded {url} to {dest}")


def load_artifacts(file_path: Path) -> list[dict[str, str]]:
    """Loads artifact URLs from a YAML file."""
    with open(file_path) as f:
        data = yaml.safe_load(f)
    return data.get("artifacts", [])


def download_artifacts(artifacts: list[dict[str, str]]) -> None:
    """Downloads all artifacts defined in the YAML file."""
    for artifact in artifacts:
        url = artifact["url"]
        filename = url.split("/")[-1]
        dest_path = ARTIFACTS_DIR / filename
        if not dest_path.exists():
            print(f"Downloading {filename}...")
            download_file(url, dest_path)
        else:
            print(f"{filename} already exists, skipping download.")


httpd: HTTPServer | None = None


def shutdown_server(signum: int, frame: FrameType) -> None:
    global httpd
    print(f"Received signal {signum}. Initiating shutdown...")
    if httpd is not None:
        httpd.shutdown()


def main() -> None:
    global httpd

    artifacts = load_artifacts(ARTIFACTS_FILE)
    download_artifacts(artifacts)

    # Set up signal handlers for TERM and INT signals
    signal.signal(signal.SIGTERM, shutdown_server)
    signal.signal(signal.SIGINT, shutdown_server)

    os.chdir(ARTIFACTS_DIR)
    print(f"Serving files from {ARTIFACTS_DIR} on port {LISTEN_ADDR}:{LISTEN_PORT}")
    httpd = HTTPServer((LISTEN_ADDR, LISTEN_PORT), SimpleHTTPRequestHandler)

    # Start the HTTP server in a separate thread
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    # Keep the main thread alive to handle server shutdown
    try:
        server_thread.join()
    except KeyboardInterrupt:
        print("KeyboardInterrupt received. Shutting down...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
