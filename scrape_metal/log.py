"""Loguru setup: coloured console + one UTF-8 file per run, named by a pendulum run id."""

import sys

import pendulum
from loguru import logger

from scrape_metal import LOGS

RUN_ID = pendulum.now("UTC").format("YYYYMMDD_HHmmss")


def setup(level: str = "INFO") -> None:
    logger.remove()
    # Property symbols include Greek letters (ω, α); the default cp1252 console chokes on them.
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
    )
    LOGS.mkdir(exist_ok=True)
    logger.add(
        LOGS / f"{RUN_ID}.log",
        level="DEBUG",
        encoding="utf-8",
        rotation="50 MB",
        format="{time:YYYY-MM-DDTHH:mm:ss.SSSZZ} | {level: <7} | {name}:{function}:{line} | {message}",
    )
    logger.info("run {} started at {}", RUN_ID, pendulum.now().to_datetime_string())


def elapsed(start: pendulum.DateTime) -> str:
    """Human-readable time since `start`, e.g. '3 minutes 12 seconds'."""
    interval = pendulum.now().diff(start)
    return interval.in_words() or f"{interval.total_seconds():.1f} seconds"
