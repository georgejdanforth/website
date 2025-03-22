import logging
import time
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


def run() -> None:
    build()

    lock = Lock()
    build_watcher = _start_build_watcher(lock)
    pages_watcher = _start_pages_watcher(lock)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        build_watcher.join()
        pages_watcher.join()
