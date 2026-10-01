"""Local streaming engine: timed alert producer + in-process queue consumer.

This is a LOCAL STREAMING SIMULATION. It replicates the production
architecture (Kinesis -> Lambda -> DynamoDB) in-process:

  production Kinesis shard      -> queue.Queue partition (this module)
  production Lambda invocation  -> consumer loop iteration (this module)
  production DynamoDB table     -> local DuckDB file (labeled stand-in)

Kafka-style partitioning is emulated by routing alerts to one of N queues
by hash(alert_id) — labeled as emulation, not a real broker.

Latency is measured with time.perf_counter_ns() at ingest (producer puts
event on queue) and at flag emission (consumer finishes spatial join and
writes flags). See docs/latency_methodology.md.
"""
from __future__ import annotations

import hashlib
import queue
import threading
import time
from dataclasses import dataclass

import duckdb
import pandas as pd
import shapely
from shapely import STRtree
from shapely.geometry import Point

from src.generate_alerts import AlertEvent


@dataclass
class AlertLatency:
    alert_id: str
    peril: str
    ingest_ns: int
    flag_ns: int
    flagged_policies: int
    exposed_tiv: float

    @property
    def latency_ms(self) -> float:
        return (self.flag_ns - self.ingest_ns) / 1e6


class PolicyIndex:
    """Spatial index (shapely STRtree) over policy point geometries."""

    def __init__(self, policies: pd.DataFrame):
        self.policies = policies.reset_index(drop=True)
        self.points = [Point(lon, lat) for lat, lon in
                       zip(self.policies["lat"], self.policies["lon"])]
        self.tree = STRtree(self.points)

    def join(self, alert: AlertEvent) -> pd.DataFrame:
        """Point-in-polygon join: policies whose point is within the alert polygon."""
        candidate_idx = self.tree.query(alert.polygon)
        if len(candidate_idx) == 0:
            return self.policies.iloc[0:0].copy()
        cand_points = [self.points[i] for i in candidate_idx]
        mask = shapely.contains(alert.polygon, cand_points)  # vectorized strict contains
        hit_idx = candidate_idx[mask]
        return self.policies.iloc[hit_idx].copy()

    def __len__(self) -> int:
        return len(self.policies)


def partition_for(alert_id: str, n_partitions: int) -> int:
    """Emulated Kafka-style partition assignment (hash of key). Not a broker."""
    return int(hashlib.md5(alert_id.encode()).hexdigest(), 16) % n_partitions


class LocalFlagStore:
    """DuckDB file standing in for DynamoDB (local only, labeled as such)."""

    def __init__(self, path: str):
        self.con = duckdb.connect(path)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS flagged_exposures (
                alert_id VARCHAR, peril VARCHAR, policy_id VARCHAR,
                state VARCHAR, total_insured_value DOUBLE,
                flagged_at_ns BIGINT
            )""")
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS alert_latency (
                alert_id VARCHAR, peril VARCHAR, ingest_ns BIGINT,
                flag_ns BIGINT, latency_ms DOUBLE,
                flagged_policies INTEGER, exposed_tiv DOUBLE
            )""")

    def write_flags(self, alert: AlertEvent, flagged: pd.DataFrame, flag_ns: int) -> None:
        if flagged.empty:
            return
        out = pd.DataFrame({
            "alert_id": alert.alert_id, "peril": alert.peril,
            "policy_id": flagged["policy_id"].values,
            "state": flagged["state"].values,
            "total_insured_value": flagged["total_insured_value"].values,
            "flagged_at_ns": flag_ns,
        })
        self.con.register("_flags_tmp", out)
        self.con.execute("INSERT INTO flagged_exposures SELECT * FROM _flags_tmp")
        self.con.unregister("_flags_tmp")

    def write_latency(self, rec: AlertLatency) -> None:
        self.con.execute(
            "INSERT INTO alert_latency VALUES (?,?,?,?,?,?,?)",
            [rec.alert_id, rec.peril, rec.ingest_ns, rec.flag_ns,
             rec.latency_ms, rec.flagged_policies, rec.exposed_tiv],
        )

    def close(self) -> None:
        self.con.close()


def run_stream(alerts: list[AlertEvent], index: PolicyIndex,
               store: LocalFlagStore, emit_interval_s: float = 0.25,
               n_partitions: int = 4) -> list[AlertLatency]:
    """Timed producer -> partitioned queues -> consumer. Returns latencies in alert order."""
    partitions: list[queue.Queue] = [queue.Queue() for _ in range(n_partitions)]
    results: dict[str, AlertLatency] = {}
    results_lock = threading.Lock()
    store_lock = threading.Lock()  # DuckDB connection is not thread-safe; serialize writes
    errors: list[BaseException] = []

    def consumer(partition_id: int):
        q = partitions[partition_id]
        while True:
            item = q.get()
            try:
                if item is None:
                    return
                alert, ingest_ns = item
                flagged = index.join(alert)
                flag_ns = time.perf_counter_ns()
                exposed = float(flagged["total_insured_value"].sum()) if not flagged.empty else 0.0
                rec = AlertLatency(alert_id=alert.alert_id, peril=alert.peril,
                                   ingest_ns=ingest_ns, flag_ns=flag_ns,
                                   flagged_policies=len(flagged), exposed_tiv=exposed)
                with store_lock:
                    store.write_flags(alert, flagged, flag_ns)
                    store.write_latency(rec)
                with results_lock:
                    results[alert.alert_id] = rec
            except BaseException as exc:  # surface, never deadlock queue.join()
                with results_lock:
                    errors.append(exc)
            finally:
                q.task_done()

    threads = [threading.Thread(target=consumer, args=(i,), daemon=True)
               for i in range(n_partitions)]
    for t in threads:
        t.start()

    # Producer: timed emission on a schedule (the "stream").
    for alert in alerts:
        ingest_ns = time.perf_counter_ns()
        p = partition_for(alert.alert_id, n_partitions)
        partitions[p].put((alert, ingest_ns))
        time.sleep(emit_interval_s)

    for q in partitions:
        q.join()
    for q in partitions:
        q.put(None)
    for t in threads:
        t.join(timeout=10)

    if errors:
        raise RuntimeError(f"stream consumer failed: {errors[0]!r}") from errors[0]
    return [results[a.alert_id] for a in alerts]
