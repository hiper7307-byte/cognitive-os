from __future__ import annotations

import json
import threading
import time
from typing import Optional

from .memory import memory_service
from .temporal_executor import temporal_executor
from .temporal_locking import temporal_locking
from .temporal_store import temporal_store


class TemporalTaskRunner:
    def __init__(self, poll_interval_seconds: float = 1.0) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="temporal-runner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def enqueue(
        self,
        *,
        user_id: str,
        task_id: str,
        kind: str,
        payload_json: str,
        run_at_epoch: int,
    ) -> int:
        return temporal_store.create_task(
            user_id=user_id,
            task_id=task_id,
            kind=kind,
            payload_json=payload_json,
            run_at_epoch=run_at_epoch,
        )

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_due_once()
            except Exception:
                pass
            time.sleep(self.poll_interval_seconds)

    def run_due_once(self) -> int:
        due = temporal_store.list_due(limit=20)
        processed = 0

        for row in due:
            row_id = int(row["id"])
            if not temporal_locking.claim_task(task_row_id=row_id):
                continue

            try:
                user_id = str(row["user_id"])
                task_id = str(row["task_id"])
                kind = str(row["kind"])
                payload = json.loads(str(row["payload_json"]))

                result = temporal_executor.execute(
                    user_id=user_id,
                    task_id=task_id,
                    kind=kind,
                    payload=payload,
                )

                temporal_store.mark_done(task_row_id=row_id)

                memory_service.write_task_event(
                    user_id=user_id,
                    task_id=task_id,
                    intent="temporal_run",
                    user_input=f"kind={kind}",
                    outcome="temporal_task_completed",
                    executor="temporal_executor.execute",
                    status="success",
                    extra={"temporal_task_id": row_id, "result": result},
                    confidence=0.8,
                )
                processed += 1
            except Exception as ex:
                temporal_store.mark_failed(task_row_id=row_id, error=str(ex))
                processed += 1

        return processed
