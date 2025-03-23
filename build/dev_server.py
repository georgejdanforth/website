import logging
import http.server
from multiprocessing import Process
from pathlib import Path

from build.build import build
from build.logging_config import configure_logging
from build.env import Env

logger = logging.getLogger(__name__)


def _watch_dirs() -> None:
    # Use dynamic import so that build doesn't fail when watchfiles isn't installed
    import watchfiles

    configure_logging()

    dirs = [
        Path("build").resolve(),
        Path("assets").resolve(),
        Path("templates").resolve(),
        Path("pages").resolve(),
    ]
    
    logger.info("Watching for changes")
    try:
        for _ in watchfiles.watch(*dirs):
            logger.info("Detected change. Rebuilding...")
            build(Env.dev)
    except KeyboardInterrupt:
        logger.info("Stopping watcher")


def _start_watcher() -> Process:
    process = Process(target=_watch_dirs, args=())
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
    build(Env.dev)

    watcher = _start_watcher()

    dist_path = Path("dist").resolve()
    server = _create_server(dist_path, port)

    try:
        logger.info("Starting server on http://localhost:%d", port)
        server.serve_forever()
    except KeyboardInterrupt:
        watcher.join()
