"""The handcart's record: what happened (events) and how the charges went (samples), on the Pi in SQLite.

Not the Python log, which is text for developers (in journald): this is data, to query and to show.

- events: few, one row each: a transition, a command, a device coming or going, the errors a device
  reports... Each says who did it (actor: "api" for now, the operator once there is a login) and, when
  known, which event led to it (cause_id): a command and the transition it caused. The operator's list
  of what went wrong and, later, an audit log or a search for the cause of an error are queries on it.
- samples: the readings every SAMPLE_PERIOD while the handcart is doing something: the graphs.

The ticks must never wait for the SD card: record() and sample() only add rows to a list, and a thread
writes them every FLUSH_PERIOD, or at once after a critical event. The ids are given here, not by SQLite,
so an event can name its cause before either is written.
"""

import json
import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from shared.models import RecordedEvent, Sample, Severity

log = logging.getLogger(__name__)

FLUSH_PERIOD = 2.0  # s between two writes to the SD card
KEEP_DAYS = 30  # older events and samples are deleted at every start
SEVERITY_ORDER = [Severity.INFO, Severity.NOTICE, Severity.CRITICAL]

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    time REAL NOT NULL,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    source TEXT NOT NULL,
    actor TEXT,
    cause_id INTEGER,
    summary TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_time ON events (time);
CREATE TABLE IF NOT EXISTS samples (
    time REAL NOT NULL,
    state TEXT NOT NULL,
    pack_voltage REAL,
    current REAL,
    cell_min REAL,
    cell_max REAL,
    temp_max REAL,
    charger_voltage REAL,
    charger_current REAL
);
CREATE INDEX IF NOT EXISTS samples_time ON samples (time);
"""
EVENT_COLUMNS = "id, time, kind, severity, source, actor, cause_id, summary, data"
SAMPLE_COLUMNS = (
    "time, state, pack_voltage, current, cell_min, cell_max, temp_max, charger_voltage, charger_current"
)


class Recorder:
    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        self._path = path
        self._clock = clock  # the wall clock: the record is read by people, at a date
        self._lock = threading.Lock()  # the rows waiting, shared by the ticks and the writing thread
        self._events: list[RecordedEvent] = []
        self._samples: list[Sample] = []
        self._wake = threading.Event()
        self._stopping = False
        self._thread: threading.Thread | None = None

        path.parent.mkdir(exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA journal_mode=WAL")  # the API reads while the thread writes
            db.executescript(SCHEMA)
            self._last_id = db.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()[0]
            too_old = clock() - KEEP_DAYS * 24 * 3600
            db.execute("DELETE FROM events WHERE time < ?", (too_old,))
            db.execute("DELETE FROM samples WHERE time < ?", (too_old,))

    def start(self) -> None:
        """Write the rows from a thread from now on, until close()."""
        self._thread = threading.Thread(target=self._write_for_ever, name="recorder", daemon=True)
        self._thread.start()

    def close(self) -> None:
        """Stop the thread, and write what is left."""
        self._stopping = True
        self._wake.set()
        if self._thread is not None:
            self._thread.join()
        self.flush()

    def record(
        self,
        kind: str,
        severity: Severity,
        source: str,
        summary: str,
        data: dict | None = None,
        actor: str | None = None,
        cause_id: int | None = None,
    ) -> int:
        """Add an event; returns its id, for the events it leads to. Written within FLUSH_PERIOD."""
        with self._lock:
            self._last_id += 1
            event = RecordedEvent(
                id=self._last_id,
                time=self._clock(),
                kind=kind,
                severity=severity,
                source=source,
                actor=actor,
                cause_id=cause_id,
                summary=summary,
                data=data or {},
            )
            self._events.append(event)
        log.debug("recorded %s: %s", kind, summary)
        if severity is Severity.CRITICAL:
            self._wake.set()  # written now: the backend may be about to stop
        return event.id

    def sample(self, sample: Sample) -> None:
        with self._lock:
            self._samples.append(sample)

    def now(self) -> float:
        return self._clock()

    def flush(self) -> None:
        """Write the rows waiting. Called by the thread; the reads call it too, to see the newest ones."""
        with self._lock:
            events, self._events = self._events, []
            samples, self._samples = self._samples, []
        if not events and not samples:
            return
        event_rows = [
            (
                e.id,
                e.time,
                e.kind,
                e.severity.value,
                e.source,
                e.actor,
                e.cause_id,
                e.summary,
                json.dumps(e.data),
            )
            for e in events
        ]
        sample_rows = [
            (
                s.time,
                s.state.value,
                s.pack_voltage,
                s.current,
                s.cell_min,
                s.cell_max,
                s.temp_max,
                s.charger_voltage,
                s.charger_current,
            )
            for s in samples
        ]
        with closing(self._connect()) as db, db:
            db.executemany(
                f"INSERT INTO events ({EVENT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", event_rows
            )
            db.executemany(
                f"INSERT INTO samples ({SAMPLE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", sample_rows
            )

    # reads, for the API

    def events(
        self, before_id: int | None = None, limit: int = 100, at_least: Severity = Severity.INFO
    ) -> list[RecordedEvent]:
        """The newest events first, as important as at_least or more; before_id: the page after that one."""
        self.flush()
        severities = [s.value for s in SEVERITY_ORDER[SEVERITY_ORDER.index(at_least) :]]
        marks = ", ".join("?" * len(severities))
        query = f"SELECT {EVENT_COLUMNS} FROM events WHERE severity IN ({marks})"
        values: list = list(severities)
        if before_id is not None:
            query += " AND id < ?"
            values.append(before_id)
        query += " ORDER BY id DESC LIMIT ?"
        values.append(limit)
        with closing(self._connect()) as db:
            rows = db.execute(query, values).fetchall()
        return [event_from_row(row) for row in rows]

    def samples(self, since: float, until: float | None = None) -> list[Sample]:
        """The samples from since to until (s since 1970), oldest first."""
        self.flush()
        query = f"SELECT {SAMPLE_COLUMNS} FROM samples WHERE time >= ?"
        values: list = [since]
        if until is not None:
            query += " AND time <= ?"
            values.append(until)
        query += " ORDER BY time"
        with closing(self._connect()) as db:
            rows = db.execute(query, values).fetchall()
        return [sample_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=5)
        db.execute("PRAGMA synchronous=NORMAL")  # with WAL: safe, and fewer waits on the SD card
        return db

    def _write_for_ever(self) -> None:
        while not self._stopping:
            self._wake.wait(FLUSH_PERIOD)
            self._wake.clear()
            try:
                self.flush()
            except sqlite3.Error:
                # a full or broken SD card loses the record, never the charge
                log.exception("could not write the record")


def event_from_row(row: tuple) -> RecordedEvent:
    event_id, at, kind, severity, source, actor, cause_id, summary, data = row
    return RecordedEvent(
        id=event_id,
        time=at,
        kind=kind,
        severity=Severity(severity),
        source=source,
        actor=actor,
        cause_id=cause_id,
        summary=summary,
        data=json.loads(data),
    )


def sample_from_row(row: tuple) -> Sample:
    at, state, pack_voltage, current, cell_min, cell_max, temp_max, charger_voltage, charger_current = row
    return Sample(
        time=at,
        state=state,
        pack_voltage=pack_voltage,
        current=current,
        cell_min=cell_min,
        cell_max=cell_max,
        temp_max=temp_max,
        charger_voltage=charger_voltage,
        charger_current=charger_current,
    )
