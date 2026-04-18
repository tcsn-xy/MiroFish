from __future__ import annotations

import threading
from typing import Optional

from ..config import Config
from ..utils.logger import get_logger
from .service import get_consensus_service
from .utils import scheduler_should_start

logger = get_logger("mirofish.consensus.scheduler")


class ConsensusScheduler:
    _instance: Optional["ConsensusScheduler"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ConsensusScheduler":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start(self) -> None:
        if not Config.CONSENSUS_ENABLED:
            logger.info("consensus disabled, scheduler not started")
            return
        if not scheduler_should_start(Config.DEBUG):
            logger.info("consensus scheduler skipped in Werkzeug parent process")
            return
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="consensus-scheduler", daemon=True)
            self._thread.start()
            logger.info("consensus scheduler started")

    def wake(self) -> None:
        self._wake_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    def _run_loop(self) -> None:
        service = get_consensus_service()
        try:
            service.ensure_ready()
        except Exception as exc:
            logger.error(f"consensus scheduler init failed: {exc}")
            return

        while not self._stop_event.is_set():
            try:
                did_work = service.run_due_round()
            except Exception as exc:
                logger.exception(f"consensus scheduler loop failed: {exc}")
                did_work = False
            if did_work:
                continue
            self._wake_event.wait(timeout=2.0)
            self._wake_event.clear()


def get_consensus_scheduler() -> ConsensusScheduler:
    return ConsensusScheduler.instance()
