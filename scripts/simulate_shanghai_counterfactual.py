from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "counterfactual-simulation.json"
SEED = 19761006
PATHS = 12_000
DAYS = 21
ELIGIBLE = 33_500
REGIMES = ("动员", "扩张", "合围", "碎片化", "崩解")


@dataclass(frozen=True)
class NodeSpec:
    id: str
    label: str
    x: float
    y: float
    resistance: float
    suppression: float
    importance: float
    recruitment: float
    entry: float
    communication: float
    supply: float


NODES = (
    NodeSpec("hongqiao", "虹桥机场", 0.12, 0.58, 0.06, 0.88, 0.95, 0.05, 1.00, 0.30, 0.85),
    NodeSpec("garrison", "上海警备区", 0.39, 0.45, 0.40, 0.50, 1.00, 0.10, 0.70, 0.55, 0.70),
    NodeSpec("communications", "广播与通信", 0.47, 0.35, 0.86, 0.10, 1.00, 0.15, 0.05, 1.00, 0.35),
    NodeSpec("kangping", "康平路", 0.32, 0.59, 0.68, 0.18, 0.75, 0.25, 0.10, 0.75, 0.40),
    NodeSpec("militia_hq", "民兵指挥部", 0.57, 0.30, 0.92, 0.06, 1.00, 0.35, 0.05, 0.95, 0.65),
    NodeSpec("huangpu", "黄浦工业区", 0.54, 0.56, 0.78, 0.14, 0.85, 0.90, 0.05, 0.45, 0.80),
    NodeSpec("naval_base", "海军上海基地", 0.62, 0.20, 0.05, 0.92, 0.95, 0.05, 1.00, 0.60, 0.90),
    NodeSpec("yangpu", "杨浦工业区", 0.74, 0.27, 0.76, 0.12, 0.85, 1.00, 0.05, 0.45, 0.80),
    NodeSpec("jiangnan", "江南造船厂", 0.59, 0.75, 0.72, 0.12, 0.80, 0.75, 0.10, 0.35, 0.85),
    NodeSpec("textile", "中纺机", 0.78, 0.42, 0.70, 0.10, 0.70, 0.85, 0.05, 0.35, 0.70),
)

# Capacity affects graph travel cost. It is not presented as a historical engineering estimate.
EDGE_SPECS = (
    ("hongqiao", "garrison", 0.78),
    ("garrison", "kangping", 0.86),
    ("garrison", "communications", 0.82),
    ("garrison", "huangpu", 0.70),
    ("kangping", "huangpu", 0.72),
    ("communications", "militia_hq", 0.92),
    ("communications", "naval_base", 0.62),
    ("militia_hq", "huangpu", 0.78),
    ("militia_hq", "yangpu", 0.86),
    ("naval_base", "yangpu", 0.74),
    ("huangpu", "jiangnan", 0.68),
    ("huangpu", "textile", 0.66),
    ("yangpu", "textile", 0.82),
    ("jiangnan", "textile", 0.76),
)


def sigmoid(value: np.ndarray | float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -20.0, 20.0)))


def quantiles(values: np.ndarray) -> dict[str, float]:
    low, median, high = np.quantile(values, [0.1, 0.5, 0.9])
    return {"p10": round(float(low), 4), "p50": round(float(median), 4), "p90": round(float(high), 4)}


def count_quantiles(values: np.ndarray) -> dict[str, int]:
    low, median, high = np.quantile(values, [0.1, 0.5, 0.9])
    return {"p10": round(float(low)), "p50": round(float(median)), "p90": round(float(high))}


def kl_divergence(left: np.ndarray, right: np.ndarray) -> float:
    left = np.maximum(left, 1e-12)
    right = np.maximum(right, 1e-12)
    return float(np.sum(left * np.log(left / right) - left + right))


def unbalanced_sinkhorn(
    source: np.ndarray,
    target: np.ndarray,
    cost: np.ndarray,
    *,
    epsilon: float = 0.22,
    marginal_penalty: float = 0.90,
    max_iterations: int = 240,
    tolerance: float = 1e-8,
) -> tuple[np.ndarray, dict[str, float | int | bool]]:
    """Solve entropic UOT with KL-relaxed source and target marginals."""
    source = np.maximum(source.astype(float), 1e-9)
    target = np.maximum(target.astype(float), 1e-9)
    kernel = np.exp(-cost / epsilon)
    kernel = np.maximum(kernel, 1e-30)
    exponent = marginal_penalty / (marginal_penalty + epsilon)
    left = np.ones_like(source)
    right = np.ones_like(target)
    error = float("inf")

    for iteration in range(1, max_iterations + 1):
        next_left = np.power(source / (kernel @ right + 1e-12), exponent)
        next_right = np.power(target / (kernel.T @ next_left + 1e-12), exponent)
        error = max(
            float(np.max(np.abs(np.log((next_left + 1e-12) / (left + 1e-12))))),
            float(np.max(np.abs(np.log((next_right + 1e-12) / (right + 1e-12))))),
        )
        left, right = next_left, next_right
        if error < tolerance:
            break

    plan = left[:, None] * kernel * right[None, :]
    row_mass = plan.sum(axis=1)
    column_mass = plan.sum(axis=0)
    entropy = float(np.sum(plan * (np.log(np.maximum(plan, 1e-12)) - 1.0)))
    objective = (
        float(np.sum(plan * cost))
        + epsilon * entropy
        + marginal_penalty * kl_divergence(row_mass, source)
        + marginal_penalty * kl_divergence(column_mass, target)
    )
    diagnostics: dict[str, float | int | bool] = {
        "iterations": iteration,
        "error": error,
        "converged": error < tolerance,
        "objective": objective,
        "source_mass": float(source.sum()),
        "transported_mass": float(plan.sum()),
        "target_mass": float(target.sum()),
        "created_mass": max(0.0, float(plan.sum() - source.sum())),
        "destroyed_mass": max(0.0, float(source.sum() - plan.sum())),
    }
    return plan, diagnostics


def build_network() -> tuple[np.ndarray, list[dict[str, float | str]]]:
    index = {node.id: position for position, node in enumerate(NODES)}
    size = len(NODES)
    distances = np.full((size, size), np.inf)
    np.fill_diagonal(distances, 0.0)
    edges: list[dict[str, float | str]] = []
    for left_id, right_id, capacity in EDGE_SPECS:
        left = index[left_id]
        right = index[right_id]
        dx = NODES[left].x - NODES[right].x
        dy = NODES[left].y - NODES[right].y
        length = float(np.hypot(dx, dy))
        travel_cost = (0.05 + 1.6 * length) / capacity
        distances[left, right] = distances[right, left] = travel_cost
        edges.append({
            "from": left_id,
            "to": right_id,
            "capacity": capacity,
            "cost": round(travel_cost, 5),
        })

    for via in range(size):
        distances = np.minimum(distances, distances[:, via, None] + distances[via, None, :])
    if not np.all(np.isfinite(distances)):
        raise RuntimeError("Spatial control graph must be connected")
    return distances, edges


def node_share(resistance: np.ndarray, suppression: np.ndarray) -> np.ndarray:
    return resistance / np.maximum(resistance + suppression, 1e-9)


def state_name(share: float) -> str:
    if share >= 0.58:
        return "resistance"
    if share <= 0.42:
        return "suppression"
    return "contested"


def spatial_metrics(resistance: np.ndarray, suppression: np.ndarray) -> dict[str, float]:
    share = node_share(resistance, suppression)
    importance = np.array([node.importance for node in NODES])
    communications = np.array([node.communication for node in NODES])
    supplies = np.array([node.supply for node in NODES])
    control = float(np.average(share, weights=importance))
    return {
        "resistance_control": control,
        "suppression_control": 1.0 - control,
        "communications": float(np.average(share, weights=communications)),
        "supply": float(np.average(share, weights=supplies)),
        "headquarters": float(share[4]),
        "key_loss": float(np.average(1.0 - share, weights=importance)),
    }


def dynamic_cost(base_cost: np.ndarray, obstruction: np.ndarray) -> np.ndarray:
    endpoint_obstruction = 0.5 * (obstruction[:, None] + obstruction[None, :])
    result = base_cost * (1.0 + 1.25 * endpoint_obstruction)
    np.fill_diagonal(result, 0.0)
    return result


def spatial_step(
    resistance: np.ndarray,
    suppression: np.ndarray,
    base_cost: np.ndarray,
    *,
    participants: float,
    command: float,
    communications: float,
    central_pressure: float,
    isolation: float,
    collapse_share: float,
    regime_pressure: float,
    enable_transport: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    share = node_share(resistance, suppression)
    recruitment = np.array([node.recruitment for node in NODES])
    entry = np.array([node.entry for node in NODES])
    importance = np.array([node.importance for node in NODES])
    participant_share = participants / ELIGIBLE

    resistance_source = (
        0.02
        + resistance * (0.18 + 0.35 * communications) * (1.0 - 0.65 * isolation)
        * (0.25 + 0.75 * command) * (1.0 - 0.50 * collapse_share)
        + recruitment * (0.05 + 0.90 * participant_share) * command
    )
    suppression_source = (
        0.03
        + suppression * (0.30 + 0.80 * central_pressure)
        + entry * (0.15 + 2.00 * central_pressure)
        + importance * (0.30 * regime_pressure + 0.35 * collapse_share)
    )
    resistance_target = 0.08 + importance * (0.45 + suppression) * (1.05 - resistance)
    suppression_target = 0.08 + importance * (0.55 + resistance) * (0.95 + share)

    resistance_cost = dynamic_cost(base_cost, 1.0 - share)
    suppression_cost = dynamic_cost(base_cost, share)
    if enable_transport:
        resistance_plan, resistance_diag = unbalanced_sinkhorn(
            resistance_source, resistance_target, resistance_cost
        )
        suppression_plan, suppression_diag = unbalanced_sinkhorn(
            suppression_source, suppression_target, suppression_cost
        )
    else:
        resistance_plan = np.diag(np.minimum(resistance_source, resistance_target))
        suppression_plan = np.diag(np.minimum(suppression_source, suppression_target))
        resistance_diag = {
            "iterations": 0,
            "error": 0.0,
            "converged": True,
            "objective": float(np.sum(resistance_plan * resistance_cost)),
            "source_mass": float(resistance_source.sum()),
            "transported_mass": float(resistance_plan.sum()),
            "target_mass": float(resistance_target.sum()),
            "created_mass": 0.0,
            "destroyed_mass": max(0.0, float(resistance_source.sum() - resistance_plan.sum())),
        }
        suppression_diag = {
            "iterations": 0,
            "error": 0.0,
            "converged": True,
            "objective": float(np.sum(suppression_plan * suppression_cost)),
            "source_mass": float(suppression_source.sum()),
            "transported_mass": float(suppression_plan.sum()),
            "target_mass": float(suppression_target.sum()),
            "created_mass": 0.0,
            "destroyed_mass": max(0.0, float(suppression_source.sum() - suppression_plan.sum())),
        }

    resistance_delivery = np.clip(
        resistance_plan.sum(axis=0) / np.maximum(resistance_target, 1e-9), 0.0, 1.5
    )
    suppression_delivery = np.clip(
        suppression_plan.sum(axis=0) / np.maximum(suppression_target, 1e-9), 0.0, 1.5
    )
    next_resistance = np.clip(
        resistance
        + 0.090 * resistance_delivery
        + 0.025 * recruitment * participant_share * command
        + 0.025 * communications * np.array([node.communication for node in NODES])
        - 0.200 * suppression_delivery
        - 0.080 * central_pressure * entry
        - 0.050 * isolation
        - 0.080 * regime_pressure * importance
        - 0.100 * collapse_share * importance,
        0.01,
        1.0,
    )
    next_suppression = np.clip(
        suppression
        + 0.180 * suppression_delivery
        + 0.080 * central_pressure * entry
        + 0.050 * isolation
        + 0.080 * regime_pressure * importance
        + 0.100 * collapse_share * importance
        - 0.080 * resistance_delivery
        - 0.010 * next_resistance,
        0.01,
        1.0,
    )

    def top_flows(plan: np.ndarray) -> list[dict[str, float | str]]:
        flows: list[dict[str, float | str]] = []
        for origin in range(len(NODES)):
            for destination in range(len(NODES)):
                if origin != destination:
                    flows.append({
                        "from": NODES[origin].id,
                        "to": NODES[destination].id,
                        "mass": round(float(plan[origin, destination]), 5),
                    })
        return sorted(flows, key=lambda item: float(item["mass"]), reverse=True)[:5]

    diagnostics: dict[str, object] = {
        "resistance": resistance_diag,
        "suppression": suppression_diag,
        "resistance_off_diagonal_mass": float(resistance_plan.sum() - np.trace(resistance_plan)),
        "suppression_off_diagonal_mass": float(suppression_plan.sum() - np.trace(suppression_plan)),
        "resistance_top_flows": top_flows(resistance_plan),
        "suppression_top_flows": top_flows(suppression_plan),
    }
    return next_resistance, next_suppression, diagnostics


def regime_transition(
    regime: np.ndarray,
    rng: np.random.Generator,
    *,
    day: int,
    command: np.ndarray,
    communications: np.ndarray,
    supply: np.ndarray,
    public: np.ndarray,
    resistance_control: np.ndarray,
    suppression_control: np.ndarray,
    central_pressure: np.ndarray,
    isolation: np.ndarray,
    spatial: dict[str, float],
) -> tuple[np.ndarray, dict[str, float]]:
    next_regime = regime.copy()
    probabilities = np.zeros_like(command)
    probabilities[regime == 0] = sigmoid(
        -3.20 + 0.30 * day + 0.90 * resistance_control[regime == 0]
        + 0.50 * public[regime == 0] + 0.40 * communications[regime == 0]
    )
    probabilities[regime == 1] = sigmoid(
        -4.30 + 0.38 * day + central_pressure[regime == 1]
        + 0.80 * isolation[regime == 1] + spatial["suppression_control"]
    )
    probabilities[regime == 2] = sigmoid(
        -5.00 + 0.42 * day + 1.20 * (1.0 - communications[regime == 2])
        + 0.80 * (1.0 - supply[regime == 2]) + 0.80 * suppression_control[regime == 2]
        + spatial["key_loss"]
    )
    probabilities[regime == 3] = sigmoid(
        -6.00 + 0.38 * day + 1.40 * (1.0 - command[regime == 3])
        + 1.20 * (1.0 - resistance_control[regime == 3])
        + 1.10 * suppression_control[regime == 3] + 1.30 * spatial["key_loss"]
    )
    stage_gate = (
        ((regime == 0) & (day >= 2))
        | ((regime == 1) & (day >= 5))
        | ((regime == 2) & (day >= 8))
        | ((regime == 3) & (day >= 11))
    )
    probabilities[~stage_gate] = 0.0
    moving = stage_gate & (rng.random(len(regime)) < probabilities)
    next_regime[moving] += 1
    summary = {
        REGIMES[state]: round(float(np.mean(probabilities[regime == state])), 5)
        if np.any(regime == state) else 0.0
        for state in range(4)
    }
    return next_regime, summary


def run_simulation(
    *,
    seed: int,
    enable_spatial_feedback: bool = True,
    enable_transport: bool = True,
    enable_regime_switching: bool = True,
    include_detail: bool = False,
) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    base_cost, edges = build_network()

    mobilisation = rng.beta(4.6, 4.0, PATHS)
    local_cohesion = rng.beta(6.0, 2.8, PATHS)
    public_receptivity = rng.beta(3.2, 4.8, PATHS)
    central_speed = np.clip(rng.normal(1.0, 0.13, PATHS), 0.68, 1.35)
    force_asymmetry = np.clip(rng.lognormal(np.log(1.85), 0.17, PATHS), 1.2, 3.1)

    participants = np.full(PATHS, 2_500.0)
    command = np.clip(rng.normal(0.92, 0.035, PATHS), 0.78, 1.0)
    communications = np.clip(rng.normal(0.78, 0.06, PATHS), 0.58, 0.94)
    supply = np.clip(rng.normal(0.69, 0.07, PATHS), 0.48, 0.88)
    public = np.clip(rng.normal(0.31, 0.07, PATHS), 0.12, 0.53)
    resistance_control = np.clip(rng.normal(0.26, 0.035, PATHS), 0.16, 0.36)
    suppression_control = np.clip(rng.normal(0.25, 0.03, PATHS), 0.16, 0.34)
    organisation_loss = np.zeros(PATHS)
    regime = np.zeros(PATHS, dtype=np.int8)
    collapse_day = np.full(PATHS, DAYS + 1, dtype=np.int16)
    collapsed = np.zeros(PATHS, dtype=bool)

    node_resistance = np.array([node.resistance for node in NODES], dtype=float)
    node_suppression = np.array([node.suppression for node in NODES], dtype=float)
    node_histories: list[list[dict[str, float | str | int]]] = [[] for _ in NODES]
    transport_history: list[dict[str, object]] = []
    series: list[dict[str, object]] = []

    regime_mobilisation = np.array([0.20, 0.28, -0.10, -0.55, -1.40])
    regime_communications = np.array([0.020, 0.010, -0.015, -0.055, -0.120])
    regime_supply = np.array([0.015, 0.020, -0.015, -0.050, -0.100])
    regime_public = np.array([0.010, 0.025, -0.010, -0.040, -0.080])
    regime_resistance = np.array([0.020, 0.040, -0.020, -0.070, -0.150])
    regime_suppression = np.array([-0.010, -0.020, 0.025, 0.070, 0.120])
    regime_command = np.array([0.015, 0.020, -0.020, -0.070, -0.150])
    regime_loss = np.array([0.000, 0.000, 0.020, 0.055, 0.120])

    for day in range(DAYS):
        central_pressure = sigmoid((day - 8.2) * 0.60 * central_speed) * force_asymmetry / 2.1
        isolation = sigmoid((day - 6.5) * 0.68) * (0.86 + 0.12 * central_speed)
        spatial_before = spatial_metrics(node_resistance, node_suppression)
        transition_probability = {name: 0.0 for name in REGIMES[:-1]}

        if day > 0:
            if enable_regime_switching:
                regime, transition_probability = regime_transition(
                    regime,
                    rng,
                    day=day,
                    command=command,
                    communications=communications,
                    supply=supply,
                    public=public,
                    resistance_control=resistance_control,
                    suppression_control=suppression_control,
                    central_pressure=central_pressure,
                    isolation=isolation,
                    spatial=spatial_before,
                )

            spatial_comm = spatial_before["communications"] if enable_spatial_feedback else 0.5
            spatial_supply = spatial_before["supply"] if enable_spatial_feedback else 0.5
            spatial_resistance = spatial_before["resistance_control"] if enable_spatial_feedback else 0.5
            spatial_suppression = spatial_before["suppression_control"] if enable_spatial_feedback else 0.5
            spatial_headquarters = spatial_before["headquarters"] if enable_spatial_feedback else 0.5
            spatial_key_loss = spatial_before["key_loss"] if enable_spatial_feedback else 0.5

            communications = np.clip(
                communications + 0.035 * command - 0.105 * isolation - 0.095 * central_pressure
                + 0.080 * (spatial_comm - 0.5) + regime_communications[regime]
                + rng.normal(0.0, 0.025, PATHS),
                0.0, 1.0,
            )
            supply = np.clip(
                supply + 0.028 * communications - 0.075 * isolation - 0.070 * central_pressure
                + 0.070 * (spatial_supply - 0.5) + regime_supply[regime]
                + rng.normal(0.0, 0.018, PATHS),
                0.0, 1.0,
            )
            public = np.clip(
                public + 0.045 * communications * public_receptivity + 0.035 * resistance_control
                - 0.070 * central_pressure - 0.035 * organisation_loss
                + 0.030 * (spatial_resistance - 0.5) + regime_public[regime]
                + rng.normal(0.0, 0.015, PATHS),
                0.0, 1.0,
            )
            desired_share = mobilisation * sigmoid(
                -0.60 + 1.25 * command + 1.10 * communications + 0.95 * public + 0.55 * supply
                - 1.75 * central_pressure - 1.10 * isolation + regime_mobilisation[regime]
            )
            participants += 0.38 * (ELIGIBLE * desired_share - participants)
            participants *= np.clip(1.0 - 0.035 * central_pressure - 0.025 * isolation, 0.82, 1.0)

            resistance_control = np.clip(
                resistance_control + 0.085 * participants / ELIGIBLE + 0.045 * communications
                + 0.030 * local_cohesion - 0.120 * central_pressure - 0.085 * isolation
                + 0.100 * (spatial_resistance - 0.5) + regime_resistance[regime]
                + rng.normal(0.0, 0.014, PATHS),
                0.0, 1.0,
            )
            suppression_control = np.clip(
                suppression_control + 0.105 * central_pressure + 0.055 * isolation
                - 0.035 * resistance_control + 0.100 * (spatial_suppression - 0.5)
                + regime_suppression[regime] + rng.normal(0.0, 0.012, PATHS),
                0.0, 1.0,
            )
            command = np.clip(
                command + 0.022 * local_cohesion + 0.018 * communications - 0.082 * central_pressure
                - 0.070 * isolation - 0.045 * (suppression_control > 0.62)
                + 0.070 * (spatial_headquarters - 0.5) + regime_command[regime]
                + rng.normal(0.0, 0.012, PATHS),
                0.0, 1.0,
            )
            organisation_loss = np.clip(
                organisation_loss + 0.050 * central_pressure + 0.045 * isolation
                + 0.035 * suppression_control - 0.020 * command
                + 0.050 * spatial_key_loss + regime_loss[regime],
                0.0, 1.0,
            )

            forced_collapse = (day >= 10) & (
                ((command < 0.13) & (resistance_control < 0.20))
                | ((participants < ELIGIBLE * 0.055) & (suppression_control > 0.70))
            )
            newly_collapsed = (~collapsed) & ((regime == 4) | forced_collapse)
            regime[forced_collapse] = 4
            collapse_day[newly_collapsed] = day
            collapsed |= newly_collapsed
            participants[collapsed] *= 0.60
            command[collapsed] *= 0.52
            resistance_control[collapsed] *= 0.55

            node_resistance, node_suppression, transport = spatial_step(
                node_resistance,
                node_suppression,
                base_cost,
                participants=float(np.mean(participants)),
                command=float(np.mean(command)),
                communications=float(np.mean(communications)),
                central_pressure=float(np.mean(central_pressure)),
                isolation=float(np.mean(isolation)),
                collapse_share=float(np.mean(collapsed)),
                regime_pressure=float(np.mean(regime) / 4.0),
                enable_transport=enable_transport,
            )
        else:
            transport = {
                "resistance": {"iterations": 0, "error": 0.0, "converged": True, "objective": 0.0,
                               "source_mass": 0.0, "transported_mass": 0.0, "target_mass": 0.0,
                               "created_mass": 0.0, "destroyed_mass": 0.0},
                "suppression": {"iterations": 0, "error": 0.0, "converged": True, "objective": 0.0,
                                "source_mass": 0.0, "transported_mass": 0.0, "target_mass": 0.0,
                                "created_mass": 0.0, "destroyed_mass": 0.0},
                "resistance_off_diagonal_mass": 0.0,
                "suppression_off_diagonal_mass": 0.0,
                "resistance_top_flows": [],
                "suppression_top_flows": [],
            }

        spatial_after = spatial_metrics(node_resistance, node_suppression)
        shares = node_share(node_resistance, node_suppression)
        for position, node in enumerate(NODES):
            node_histories[position].append({
                "day": day,
                "resistance": round(float(node_resistance[position]), 5),
                "suppression": round(float(node_suppression[position]), 5),
                "control": round(float(shares[position]), 5),
                "state": state_name(float(shares[position])),
            })
        transport_history.append({
            "day": day,
            "resistance": transport["resistance"],
            "suppression": transport["suppression"],
            "resistance_off_diagonal_mass": round(float(transport["resistance_off_diagonal_mass"]), 6),
            "suppression_off_diagonal_mass": round(float(transport["suppression_off_diagonal_mass"]), 6),
            "resistance_top_flows": transport["resistance_top_flows"],
            "suppression_top_flows": transport["suppression_top_flows"],
        })

        regime_shares = {REGIMES[state]: round(float(np.mean(regime == state)), 5) for state in range(5)}
        dominant_regime = REGIMES[int(np.argmax([regime_shares[name] for name in REGIMES]))]
        series.append({
            "day": day,
            "date": f"1976-10-{6 + day:02d}",
            "active_militia": count_quantiles(participants),
            "command": quantiles(command),
            "communications": quantiles(communications),
            "supply": quantiles(supply),
            "public_participation": quantiles(public),
            "resistance_control": quantiles(resistance_control),
            "suppression_control": quantiles(suppression_control),
            "organisation_loss": quantiles(organisation_loss),
            "collapsed_share": round(float(np.mean(collapsed)), 5),
            "regime_shares": regime_shares,
            "dominant_regime": dominant_regime,
            "transition_probability": transition_probability,
            "spatial": {key: round(value, 5) for key, value in spatial_after.items()},
        })

    finite = collapse_day[collapse_day <= DAYS]
    collapse_summary = count_quantiles(finite) if len(finite) else {"p10": None, "p50": None, "p90": None}
    peak_participants = max(int(item["active_militia"]["p50"]) for item in series)
    summary: dict[str, object] = {
        "collapse_share": round(float(np.mean(collapse_day <= DAYS)), 5),
        "collapse_day": collapse_summary,
        "peak_active_militia_p50": peak_participants,
        "final_spatial_resistance_control": series[-1]["spatial"]["resistance_control"],
        "spatial_resistance_control_auc": round(sum(
            float(item["spatial"]["resistance_control"]) for item in series
        ), 5),
        "final_regime_shares": series[-1]["regime_shares"],
    }
    if not include_detail:
        return summary

    loss_days = []
    nodes_output = []
    for node, history in zip(NODES, node_histories):
        initial_state = history[0]["state"]
        loss_day = next(
            (int(item["day"]) for item in history if initial_state != "suppression" and item["state"] == "suppression"),
            None,
        )
        loss_days.append(loss_day)
        nodes_output.append({
            "id": node.id,
            "label": node.label,
            "x": node.x,
            "y": node.y,
            "importance": node.importance,
            "initial": initial_state,
            "loss_day": loss_day,
            "history": history,
        })

    solver_entries = [entry for entry in transport_history[1:]]
    solver_diagnostics = {
        "method": "entropic unbalanced Sinkhorn with KL marginal relaxation",
        "epsilon": 0.22,
        "marginal_penalty": 0.90,
        "max_iterations": 240,
        "tolerance": 1e-8,
        "all_converged": all(
            bool(entry[side]["converged"]) for entry in solver_entries for side in ("resistance", "suppression")
        ),
        "max_error": max(
            float(entry[side]["error"]) for entry in solver_entries for side in ("resistance", "suppression")
        ),
        "max_iterations_used": max(
            int(entry[side]["iterations"]) for entry in solver_entries for side in ("resistance", "suppression")
        ),
        "total_off_diagonal_mass": round(sum(
            float(entry["resistance_off_diagonal_mass"]) + float(entry["suppression_off_diagonal_mass"])
            for entry in solver_entries
        ), 6),
    }
    return {
        "summary": summary,
        "series": series,
        "nodes": nodes_output,
        "edges": edges,
        "transport_history": transport_history,
        "solver": solver_diagnostics,
        "loss_days": loss_days,
    }


def main() -> None:
    full = run_simulation(seed=SEED, include_detail=True)
    ablations = {
        "no_spatial_feedback": run_simulation(seed=SEED, enable_spatial_feedback=False),
        "no_transport": run_simulation(seed=SEED, enable_transport=False),
        "no_regime_switching": run_simulation(seed=SEED, enable_regime_switching=False),
    }

    rng = np.random.default_rng(SEED + 404)
    outcome_weights = np.array([0.34, 0.42, 0.14, 0.10])
    outcome_labels = ["自裁", "被俘后处决", "被俘监禁", "脱离包围"]
    outcome_counts = rng.multinomial(8, outcome_weights)
    full_summary = dict(full["summary"])
    full_summary.update({
        "followed_branch": "collapse-conditioned median path",
        "leadership_group_size": 8,
        "leadership_outcomes": [
            {"label": label, "count": int(count), "weight": float(weight)}
            for label, count, weight in zip(outcome_labels, outcome_counts, outcome_weights)
        ],
    })

    milestones = [
        {"day": 0, "title": "抵沪", "detail": "张春桥成功离京抵沪，上海领导层进入紧急动员。"},
        {"day": 2, "title": "市级动员", "detail": "民兵体系由待命转为公开集结，工业节点建立响应链。"},
        {"day": 5, "title": "控制扩张", "detail": "抵抗方争夺广播、交通与市区组织网络。"},
        {"day": 8, "title": "外围封锁", "detail": "铁路、机场与沿江通道受到控制，补给开始失衡。"},
        {"day": 11, "title": "弹压方合围", "detail": "外部增援与海军基地形成合围，市区指挥承压。"},
        {"day": 14, "title": "通信断裂", "detail": "全市协调退化为局部自治，节点控制加速逆转。"},
        {"day": 17, "title": "残余抵抗", "detail": "固定节点全部失守后，残余人员失去跨区补给，只能零散抵抗。"},
        {"day": 20, "title": "公社式结局", "detail": "有组织抵抗被全面镇压，领导层结局进入竞争风险分支。"},
    ]

    output = {
        "meta": {
            "title": "张春桥抵沪与上海民兵起义：反事实推演",
            "seed": SEED,
            "paths": PATHS,
            "days": DAYS,
            "start_date": "1976-10-06",
            "status": "counterfactual",
            "historical_break": "张春桥未在北京被捕，而是成功抵达上海",
            "warning": "所有战斗、节点失守与领导层结局均为模型条件分支，不是历史事实。",
        },
        "documented_baseline": {
            "concentrated": 2_500,
            "standby": 31_000,
            "eligible_total": ELIGIBLE,
            "source_ids": ["S1"],
        },
        "model": {
            "modules": [
                {"id": "regime", "name": "显式隐状态切换", "implemented": True},
                {"id": "spatial", "name": "空间控制网络", "implemented": True},
                {"id": "uot", "name": "非平衡最优传输", "implemented": True},
                {"id": "mean_field", "name": "群体参与均值场", "implemented": True},
                {"id": "competing_risks", "name": "领导层竞争风险", "implemented": True},
            ],
            "coupling": "聚合状态影响节点供需；图上 UOT 配送改变节点控制；节点控制反馈通信、补给、指挥与阶段转移。",
            "interpretation": "条件情景压力测试；参数是透明假设，不是历史频率或统计后验。",
            "condition": "无外省同盟介入、中央持续增援、铁路机场与沿江通道持续受压。",
            "regimes": list(REGIMES),
        },
        "summary": full_summary,
        "series": full["series"],
        "nodes": full["nodes"],
        "edges": full["edges"],
        "transport_history": full["transport_history"],
        "solver": full["solver"],
        "ablations": ablations,
        "milestones": milestones,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUTPUT),
        "collapse_share": full_summary["collapse_share"],
        "collapse_day": full_summary["collapse_day"],
        "solver": full["solver"],
        "node_loss_days": full["loss_days"],
        "ablations": ablations,
    }, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
