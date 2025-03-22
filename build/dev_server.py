import logging
import http.server
from multiprocessing import Lock, Process
from multiprocessing.synchronize import Lock as LockType
from pathlib import Path

import watchfiles

from build.build import build
from build.logging_config import configure_logging

logger = logging.getLogger(__name__)


def _watch_dir(directory: Path, lock: LockType) -> None:
    configure_logging()
    
    logger.info("Watching %s for changes", directory)
    try:
        for _ in watchfiles.watch(directory):
            with lock:
                logger.info("Detected change in %s, rebuilding", directory)
                build()
    except KeyboardInterrupt:
        logger.info("Stopping watcher for %s", directory)


def _start_build_watcher(lock: LockType) -> Process:
    build_dir = Path("build").resolve()
    process = Process(target=_watch_dir, args=(build_dir, lock))
    process.start()
    return process


def _start_pages_watcher(lock: LockType) -> Process:
    pages_dir = Path("pages").resolve()
    process = Process(target=_watch_dir, args=(pages_dir, lock))
    process.start()
    return process


def _create_server(directory: Path, port: int = 8000) -> http.server.HTTPServer:
    """Create an HTTP server for serving files from the specified directory."""
    # Create a handler class that serves from the specified directory
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    # Create and return the server
    return http.server.HTTPServer(("localhost", port), Handler)


def run(port: int) -> None:
    build()

    lock = Lock()
    build_watcher = _start_build_watcher(lock)
    pages_watcher = _start_pages_watcher(lock)

    dist_path = Path("dist").resolve()
    server = _create_server(dist_path, port)

    try:
        logger.info("Starting server on http://localhost:%d", port)
        server.serve_forever()
    except KeyboardInterrupt:
        build_watcher.join()
        pages_watcher.join()
