"""Hospital surge and same-city overflow routing (PRD 6.2).

Per city, never across cities:
  required_w = beds needed (peak week of the window), capacity_w = proxy or uploaded,
  deficit_w  = max(0, required_w - capacity_w),
  usable_w   = capacity_w - floor(capacity_w * buffer),  headroom_w = max(0, usable_w - required_w).
Deficit wards go in priority order. Each pulls patients from donors with headroom, least
utilised first (utilisation = (required + received) / capacity, ties by ward_id).

There are no coordinates, so every deficit ward reaches every donor in its city at the
same cost. The most patients that can be placed is then min(total deficit, total
headroom), which is the max flow; the greedy places exactly that, and max_flow_moved
checks it with scipy's max-flow solver.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_flow

from src import config as cfg

BUFFER_PCT = 10
ROUTE_INPUT_COLS = (cfg.WARD_COL, cfg.CITY_COL, cfg.BEDS_COL, "capacity", "priority")
TRANSFER_COLS = (cfg.CITY_COL, "from_ward", "to_ward", "patients")
WARD_ROUTE_COLS = (
    cfg.WARD_COL,
    cfg.CITY_COL,
    "required",
    "capacity",
    "usable",
    "deficit_before",
    "sent",
    "received",
    "unplaced",
    "headroom_after",
    "utilization_after",
)
CITY_COLS = (
    cfg.CITY_COL,
    "required",
    "capacity",
    "usable",
    "utilization_pct",
    "moved",
    "max_flow",
    "unplaced",
    "headroom_left",
    "alert",
)


@dataclass(frozen=True)
class RoutingResult:
    transfers: pd.DataFrame
    wards: pd.DataFrame
    cities: pd.DataFrame


def usable_capacity(capacity, buffer_pct: int = BUFFER_PCT) -> np.ndarray:
    """capacity - floor(capacity x buffer_pct / 100): the buffer is whole beds, rounded down.

    The PRD's floor(capacity x 0.9) takes a whole bed from every 1-9 bed ward, and the
    proxy capacities are 1-5 beds, so routing could almost never place anyone (1 patient
    over Jun-Aug 2025). A ward cannot keep a fraction of a bed free, so the buffer is
    rounded down instead; 10+ bed wards keep at least one bed free. Chosen with the team.
    """
    if not 0 <= buffer_pct < 100:
        raise ValueError(f"buffer_pct must be from 0 to 99, got {buffer_pct}")
    beds = np.asarray(capacity, dtype=np.int64)
    return beds - beds * buffer_pct // 100


def _deficit_and_headroom(required, capacity, buffer_pct: int) -> tuple[np.ndarray, np.ndarray]:
    req, cap = np.asarray(required, dtype=np.int64), np.asarray(capacity, dtype=np.int64)
    return np.maximum(req - cap, 0), np.maximum(usable_capacity(cap, buffer_pct) - req, 0)


def max_flow_moved(required, capacity, buffer_pct: int = BUFFER_PCT) -> int:
    """Max patients placeable in one city: source -> deficit wards -> donors -> sink."""
    deficit, headroom = _deficit_and_headroom(required, capacity, buffer_pct)
    senders, donors = np.flatnonzero(deficit), np.flatnonzero(headroom)
    if not len(senders) or not len(donors):
        return 0
    sink = 1 + len(senders) + len(donors)
    edges = [(0, 1 + i, deficit[s]) for i, s in enumerate(senders)]
    edges += [(1 + i, 1 + len(senders) + j, deficit[s]) for i, s in enumerate(senders) for j in range(len(donors))]
    edges += [(1 + len(senders) + j, sink, headroom[d]) for j, d in enumerate(donors)]
    rows, cols, caps = zip(*edges)
    graph = csr_matrix((np.asarray(caps, dtype=np.int32), (rows, cols)), shape=(sink + 1, sink + 1))
    return int(maximum_flow(graph, 0, sink).flow_value)


def _route_city(rows: pd.DataFrame, buffer_pct: int) -> tuple[list, pd.DataFrame]:
    """Greedy routing inside one city; rows are sorted by ward_id."""
    city, wards = rows[cfg.CITY_COL].iloc[0], rows[cfg.WARD_COL].to_numpy()
    req, cap = rows[cfg.BEDS_COL].to_numpy(dtype=np.int64), rows["capacity"].to_numpy(dtype=np.int64)
    deficit, left = _deficit_and_headroom(req, cap, buffer_pct)
    sent, received = np.zeros_like(req), np.zeros_like(req)
    priority = rows["priority"].to_numpy(dtype=float)
    transfers = []
    for i in sorted(np.flatnonzero(deficit), key=lambda k: (-priority[k], wards[k])):
        while sent[i] < deficit[i] and (left > 0).any():
            utilisation = np.where(left > 0, (req + received) / cap, np.inf)
            j = int(np.argmin(utilisation))  # first minimum = lowest ward_id
            move = int(min(deficit[i] - sent[i], left[j]))
            transfers.append((city, wards[i], wards[j], move))
            sent[i], received[j], left[j] = sent[i] + move, received[j] + move, left[j] - move
    ward_table = pd.DataFrame(
        {
            cfg.WARD_COL: wards,
            cfg.CITY_COL: city,
            "required": req,
            "capacity": cap,
            "usable": usable_capacity(cap, buffer_pct),
            "deficit_before": deficit,
            "sent": sent,
            "received": received,
            "unplaced": deficit - sent,
            "headroom_after": left,
            "utilization_after": (req - sent + received) / cap,
        }
    )
    return transfers, ward_table


def _city_summary(wards: pd.DataFrame, buffer_pct: int) -> dict:
    required, capacity = int(wards["required"].sum()), int(wards["capacity"].sum())
    unplaced = int(wards["unplaced"].sum())
    return {
        cfg.CITY_COL: wards[cfg.CITY_COL].iloc[0],
        "required": required,
        "capacity": capacity,
        "usable": int(wards["usable"].sum()),
        "utilization_pct": required / capacity * 100,
        "moved": int(wards["sent"].sum()),
        "max_flow": max_flow_moved(wards["required"], wards["capacity"], buffer_pct),
        "unplaced": unplaced,
        "headroom_left": int(wards["headroom_after"].sum()),
        "alert": "CITY_SATURATED" if unplaced > 0 else "OK",
    }


def route_overflow(table: pd.DataFrame, buffer_pct: int = BUFFER_PCT) -> RoutingResult:
    """Route each city's bed deficit to same-city donors. Input is not modified."""
    missing = [c for c in ROUTE_INPUT_COLS if c not in table.columns]
    if missing:
        raise ValueError(f"routing table is missing columns: {missing}")
    if (table["capacity"] <= 0).any():
        raise ValueError("capacity must be > 0 for every ward")
    transfers, ward_tables = [], []
    for _, rows in table.sort_values([cfg.CITY_COL, cfg.WARD_COL]).groupby(cfg.CITY_COL, sort=True):
        city_transfers, wards = _route_city(rows.reset_index(drop=True), buffer_pct)
        transfers += city_transfers
        ward_tables.append(wards)
    wards = pd.concat(ward_tables, ignore_index=True)[list(WARD_ROUTE_COLS)]
    cities = pd.DataFrame(
        [_city_summary(rows, buffer_pct) for _, rows in wards.groupby(cfg.CITY_COL, sort=True)]
    )[list(CITY_COLS)]
    return RoutingResult(pd.DataFrame(transfers, columns=list(TRANSFER_COLS)), wards, cities)
