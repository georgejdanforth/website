import logging
import sys
import multiprocessing


def configure_logging():
    """Configure logging that works with multiprocessing."""
    # This will ensure logging config is applied in both main and child processes
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d [%(levelname)s] -- %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    
    # Clear existing handlers and configure root logger
    root_logger = logging.getLogger()
    # Only clear handlers if they exist (prevents issues in child processes)
    if root_logger.handlers:
        root_logger.handlers = []
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    
    # Set the multiprocessing start method if not already set
    # This must be called before any Process objects are created
    if multiprocessing.get_start_method(allow_none=True) is None:
        try:
            multiprocessing.set_start_method('spawn', force=False)
        except RuntimeError:
            # Method may already be set in child process
            pass