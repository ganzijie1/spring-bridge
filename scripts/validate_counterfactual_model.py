from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "counterfactual-simulation.json"
REPORT = ROOT / "output" / "counterfactual-model-validation.json"
REGIMES = ("动员", "扩张", "合围", "碎片化", "崩解")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    errors: list[str] = []
    days = int(data["meta"]["days"])

    modules = {module["id"]: module for module in data["model"]["modules"]}
    for module_id in ("regime", "spatial", "uot"):
        require(module_id in modules, f"missing model module: {module_id}", errors)
        require(bool(modules.get(module_id, {}).get("implemented")), f"module is not implemented: {module_id}", errors)

    solver = data["solver"]
    require(bool(solver["all_converged"]), "at least one UOT solve did not converge", errors)
    require(float(solver["max_error"]) < float(solver["tolerance"]), "UOT residual exceeds tolerance", errors)
    require(int(solver["max_iterations_used"]) <= int(solver["max_iterations"]), "UOT iteration limit exceeded", errors)
    require(float(solver["total_off_diagonal_mass"]) > 1.0, "UOT produced no material cross-node transport", errors)

    edges = data["edges"]
    node_ids = {node["id"] for node in data["nodes"]}
    require(len(edges) >= len(node_ids) - 1, "spatial graph has too few edges to be connected", errors)
    for edge in edges:
        require(edge["from"] in node_ids and edge["to"] in node_ids, "edge references an unknown node", errors)
        require(float(edge["capacity"]) > 0 and float(edge["cost"]) > 0, "edge capacity and cost must be positive", errors)

    loss_days = []
    for node in data["nodes"]:
        history = node["history"]
        require(len(history) == days, f"{node['id']} history length mismatch", errors)
        for expected_day, item in enumerate(history):
            require(int(item["day"]) == expected_day, f"{node['id']} history day mismatch", errors)
            require(0 <= float(item["control"]) <= 1, f"{node['id']} control outside [0,1]", errors)
            require(item["state"] in ("resistance", "contested", "suppression"), f"{node['id']} invalid state", errors)
        if node["loss_day"] is not None:
            loss_day = int(node["loss_day"])
            loss_days.append(loss_day)
            require(history[loss_day]["state"] == "suppression", f"{node['id']} loss day is not endogenous", errors)
    require(len(loss_days) >= 4, "too few initially non-suppression nodes change control", errors)
    require(len(set(loss_days)) >= 2, "all node loss days are mechanically identical", errors)

    previous_collapse = -1.0
    dominant_regimes = set()
    for item in data["series"]:
        shares = item["regime_shares"]
        require(set(shares) == set(REGIMES), "regime share keys mismatch", errors)
        require(abs(sum(float(shares[name]) for name in REGIMES) - 1.0) < 2e-4, "regime shares do not sum to one", errors)
        collapse = float(item["collapsed_share"])
        require(collapse + 1e-9 >= previous_collapse, "absorbing collapse share decreases", errors)
        previous_collapse = collapse
        dominant_regimes.add(item["dominant_regime"])
        for value in item["spatial"].values():
            require(math.isfinite(float(value)), "non-finite spatial metric", errors)
    require(len(dominant_regimes) >= 4, "explicit regime chain does not visit enough dominant states", errors)

    transports = data["transport_history"][1:]
    require(len(transports) == days - 1, "transport history length mismatch", errors)
    for entry in transports:
        for side in ("resistance", "suppression"):
            diagnostics = entry[side]
            require(bool(diagnostics["converged"]), f"day {entry['day']} {side} UOT failed", errors)
            for field in ("objective", "source_mass", "transported_mass", "target_mass", "created_mass", "destroyed_mass"):
                value = float(diagnostics[field])
                require(math.isfinite(value), f"day {entry['day']} {side} {field} is not finite", errors)
                if field != "objective":
                    require(value >= 0, f"day {entry['day']} {side} {field} is negative", errors)

    full = data["summary"]
    ablations = data["ablations"]
    require(
        abs(float(full["spatial_resistance_control_auc"]) - float(ablations["no_transport"]["spatial_resistance_control_auc"])) > 0.01,
        "transport ablation has no measurable spatial effect",
        errors,
    )
    require(
        abs(float(full["peak_active_militia_p50"]) - float(ablations["no_spatial_feedback"]["peak_active_militia_p50"])) > 10,
        "spatial feedback ablation has no measurable aggregate effect",
        errors,
    )
    require(
        int(full["collapse_day"]["p50"]) != int(ablations["no_regime_switching"]["collapse_day"]["p50"]),
        "regime switching ablation has no measurable timing effect",
        errors,
    )

    if errors:
        raise SystemExit("\n".join(errors))

    report = {
        "status": "PASS",
        "nodes": len(data["nodes"]),
        "edges": len(edges),
        "uot_solves": 2 * (days - 1),
        "max_uot_error": solver["max_error"],
        "off_diagonal_mass": solver["total_off_diagonal_mass"],
        "endogenous_loss_days": sorted(loss_days),
        "dominant_regimes": sorted(dominant_regimes),
        "ablations": list(ablations),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
