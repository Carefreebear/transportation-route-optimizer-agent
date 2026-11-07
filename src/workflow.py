"""Agentic route optimization workflow using only the Python standard library."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Stop:
    stop_id: str
    latitude: float
    longitude: float
    priority: int = 3
    service_minutes: int = 15


@dataclass(frozen=True)
class RouteLeg:
    origin: str
    destination: str
    distance_miles: float


def haversine_miles(a: Stop, b: Stop) -> float:
    radius = 3958.8
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


class IntakeAgent:
    role = "Intake Agent"

    def load(self, path: Path) -> tuple[list[Stop], dict[str, Any]]:
        stops: list[Stop] = []
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                stop = Stop(
                    stop_id=row["stop_id"].strip(),
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    priority=int(row.get("priority", 3)),
                    service_minutes=int(row.get("service_minutes", 15)),
                )
                if not (-90 <= stop.latitude <= 90 and -180 <= stop.longitude <= 180):
                    raise ValueError(f"Invalid coordinates for {stop.stop_id}")
                if not 1 <= stop.priority <= 5:
                    raise ValueError(f"Priority must be 1-5 for {stop.stop_id}")
                stops.append(stop)
        if len(stops) < 2:
            raise ValueError("At least two stops are required")
        if len({s.stop_id for s in stops}) != len(stops):
            raise ValueError("Stop IDs must be unique")
        return stops, {"agent": self.role, "event": "validated_stops", "count": len(stops)}


class OptimizationAgent:
    role = "Optimization Agent"

    def optimize(self, stops: list[Stop]) -> tuple[list[Stop], list[RouteLeg], dict[str, Any]]:
        depot, remaining = stops[0], stops[1:].copy()
        route = [depot]
        while remaining:
            current = route[-1]
            # Distance leads; priority provides a small tie-breaking benefit.
            next_stop = min(remaining, key=lambda s: haversine_miles(current, s) - (6 - s.priority) * 0.15)
            route.append(next_stop)
            remaining.remove(next_stop)
        route.append(depot)
        legs = [
            RouteLeg(a.stop_id, b.stop_id, round(haversine_miles(a, b), 2))
            for a, b in zip(route, route[1:])
        ]
        return route, legs, {
            "agent": self.role,
            "event": "route_optimized",
            "ordered_stops": [s.stop_id for s in route],
            "total_miles": round(sum(leg.distance_miles for leg in legs), 2),
        }


class AlertAgent:
    role = "Alert Agent"

    def evaluate(self, legs: list[RouteLeg], config: dict[str, Any], today: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        long_leg = float(config.get("long_leg_miles", 25))
        for leg in legs:
            if leg.distance_miles > long_leg:
                alerts.append({
                    "severity": "warning",
                    "type": "long_route_leg",
                    "message": f"{leg.origin} to {leg.destination} is {leg.distance_miles:.1f} miles.",
                })
        reviewed = datetime.strptime(config["last_optimization_review"], "%Y-%m-%d").date()
        interval = int(config.get("review_interval_days", 182))
        days_since = (today - reviewed).days
        if days_since >= interval:
            alerts.append({
                "severity": "high",
                "type": "optimization_review_due",
                "message": f"Route optimization policy review is {days_since - interval} days overdue.",
            })
        return alerts, {"agent": self.role, "event": "alerts_evaluated", "alert_count": len(alerts)}


class RouteOptimizationCoordinator:
    def run(self, stops_path: Path, config_path: Path, today: date | None = None) -> dict[str, Any]:
        today = today or date.today()
        config = json.loads(config_path.read_text(encoding="utf-8"))
        trace: list[dict[str, Any]] = []
        stops, event = IntakeAgent().load(stops_path)
        trace.append(event)
        route, legs, event = OptimizationAgent().optimize(stops)
        trace.append(event)
        alerts, event = AlertAgent().evaluate(legs, config, today)
        trace.append(event)
        return {
            "run_date": today.isoformat(),
            "route": [s.stop_id for s in route],
            "legs": [asdict(leg) for leg in legs],
            "total_miles": round(sum(leg.distance_miles for leg in legs), 2),
            "alerts": alerts,
            "trace": trace,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the transportation route optimization agents")
    parser.add_argument("--stops", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(RouteOptimizationCoordinator().run(args.stops, args.config), indent=2))


if __name__ == "__main__":
    main()
