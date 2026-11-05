from __future__ import annotations

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "counterfactual-simulation.json"
SEED = 19761006
PATHS = 12_000
DAYS = 21
ELIGIBLE = 33_500


def sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -20.0, 20.0)))


def quantiles(values: np.ndarray) -> dict[str, float]:
    low, median, high = np.quantile(values, [0.1, 0.5, 0.9])
    return {"p10": round(float(low), 4), "p50": round(float(median), 4), "p90": round(float(high), 4)}


def count_quantiles(values: np.ndarray) -> dict[str, int]:
    low, median, high = np.quantile(values, [0.1, 0.5, 0.9])
    return {"p10": round(float(low)), "p50": round(float(median)), "p90": round(float(high))}


def main() -> None:
    rng = np.random.default_rng(SEED)

    # These distributions are explicit scenario assumptions, not historical estimates.
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
    collapse_day = np.full(PATHS, DAYS + 1, dtype=np.int16)
    collapsed = np.zeros(PATHS, dtype=bool)

    series: list[dict] = []
    for day in range(DAYS):
        central_pressure = sigmoid((day - 8.2) * 0.60 * central_speed) * force_asymmetry / 2.1
        isolation = sigmoid((day - 6.5) * 0.68) * (0.86 + 0.12 * central_speed)

        if day > 0:
            noise = rng.normal(0.0, 0.025, PATHS)
            communications = np.clip(
                communications
                + 0.035 * command
                - 0.105 * isolation
                - 0.095 * central_pressure
                + noise,
                0.0,
                1.0,
            )
            supply = np.clip(
                supply + 0.028 * communications - 0.075 * isolation - 0.070 * central_pressure
                + rng.normal(0.0, 0.018, PATHS),
                0.0,
                1.0,
            )
            public = np.clip(
                public
                + 0.045 * communications * public_receptivity
                + 0.035 * resistance_control
                - 0.070 * central_pressure
                - 0.035 * organisation_loss
                + rng.normal(0.0, 0.015, PATHS),
                0.0,
                1.0,
            )

            desired_share = mobilisation * sigmoid(
                -0.60
                + 1.25 * command
                + 1.10 * communications
                + 0.95 * public
                + 0.55 * supply
                - 1.75 * central_pressure
                - 1.10 * isolation
            )
            participants += 0.38 * (ELIGIBLE * desired_share - participants)
            participants *= np.clip(1.0 - 0.035 * central_pressure - 0.025 * isolation, 0.82, 1.0)

            resistance_control = np.clip(
                resistance_control
                + 0.085 * participants / ELIGIBLE
                + 0.045 * communications
                + 0.030 * local_cohesion
                - 0.120 * central_pressure
                - 0.085 * isolation
                + rng.normal(0.0, 0.014, PATHS),
                0.0,
                1.0,
            )
            suppression_control = np.clip(
                suppression_control
                + 0.105 * central_pressure
                + 0.055 * isolation
                - 0.035 * resistance_control
                + rng.normal(0.0, 0.012, PATHS),
                0.0,
                1.0,
            )
            command = np.clip(
                command
                + 0.022 * local_cohesion
                + 0.018 * communications
                - 0.082 * central_pressure
                - 0.070 * isolation
                - 0.045 * (suppression_control > 0.62)
                + rng.normal(0.0, 0.012, PATHS),
                0.0,
                1.0,
            )
            organisation_loss = np.clip(
                organisation_loss
                + 0.050 * central_pressure
                + 0.045 * isolation
                + 0.035 * suppression_control
                - 0.020 * command,
                0.0,
                1.0,
            )

            newly_collapsed = (~collapsed) & (day >= 10) & (
                ((command < 0.13) & (resistance_control < 0.20))
                | ((participants < ELIGIBLE * 0.055) & (suppression_control > 0.70))
            )
            collapse_day[newly_collapsed] = day
            collapsed |= newly_collapsed
            participants[collapsed] *= 0.60
            command[collapsed] *= 0.52
            resistance_control[collapsed] *= 0.55

        series.append(
            {
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
                "collapsed_share": round(float(np.mean(collapsed)), 4),
            }
        )

    # The film follows the collapse-conditioned branch requested by the user.
    finite = collapse_day[collapse_day <= DAYS]
    collapse_summary = count_quantiles(finite) if len(finite) else {"p10": None, "p50": None, "p90": None}
    collapse_probability = float(np.mean(collapse_day <= DAYS))

    # Competing-risk weights describe a fictional leadership group, not real biographies.
    outcome_weights = np.array([0.34, 0.42, 0.14, 0.10])
    outcome_labels = ["自裁", "被俘后处决", "被俘监禁", "脱离包围"]
    outcome_counts = rng.multinomial(8, outcome_weights)

    nodes = [
        {"id": "hongqiao", "label": "虹桥机场", "x": 0.12, "y": 0.58, "initial": "suppression", "fall_day": 0},
        {"id": "garrison", "label": "上海警备区", "x": 0.39, "y": 0.45, "initial": "contested", "fall_day": 10},
        {"id": "communications", "label": "广播与通信", "x": 0.47, "y": 0.35, "initial": "resistance", "fall_day": 11},
        {"id": "kangping", "label": "康平路", "x": 0.32, "y": 0.59, "initial": "resistance", "fall_day": 13},
        {"id": "militia_hq", "label": "民兵指挥部", "x": 0.57, "y": 0.30, "initial": "resistance", "fall_day": 14},
        {"id": "huangpu", "label": "黄浦工业区", "x": 0.54, "y": 0.56, "initial": "resistance", "fall_day": 15},
        {"id": "naval_base", "label": "海军上海基地", "x": 0.62, "y": 0.20, "initial": "suppression", "fall_day": 0},
        {"id": "yangpu", "label": "杨浦工业区", "x": 0.74, "y": 0.27, "initial": "resistance", "fall_day": 17},
        {"id": "jiangnan", "label": "江南造船厂", "x": 0.59, "y": 0.75, "initial": "resistance", "fall_day": 18},
        {"id": "textile", "label": "中纺机", "x": 0.78, "y": 0.42, "initial": "resistance", "fall_day": 19},
    ]

    milestones = [
        {"day": 0, "title": "抵沪", "detail": "张春桥成功离京抵沪，上海领导层进入紧急动员。"},
        {"day": 1, "title": "市级动员", "detail": "民兵系统从待命转为公开集结，工业节点建立联络。"},
        {"day": 3, "title": "控制扩张", "detail": "抵抗方争夺广播、交通与区级组织网络。"},
        {"day": 6, "title": "外围封锁", "detail": "铁路、机场与沿江通道受压，补给开始失衡。"},
        {"day": 9, "title": "弹压军合围", "detail": "六十军方向与海军基地形成外压，城市指挥链被切割。"},
        {"day": 12, "title": "通信断裂", "detail": "全市协调退化为局部自治，节点逐一失去联系。"},
        {"day": 15, "title": "中心失守", "detail": "指挥部与黄浦节点失守，抵抗转入分散据点。"},
        {"day": 18, "title": "最后据点", "detail": "江南与杨浦方向的残余组织被压缩。"},
        {"day": 20, "title": "公社式结局", "detail": "有组织抵抗归零；领导层结局进入竞争风险分支。"},
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
            "warning": "所有战斗、节点失守与领导层结局均为模型条件分支，不是史实断言。",
        },
        "documented_baseline": {
            "concentrated": 2_500,
            "standby": 31_000,
            "eligible_total": ELIGIBLE,
            "source_ids": ["S1"],
        },
        "model": {
            "modules": [
                "隐状态阶段切换",
                "有限阶段动员闸门",
                "空间控制网络",
                "群体参与均值场",
                "信息冲击与通信衰减",
                "非平衡资源约束",
                "领导层竞争风险",
            ],
            "interpretation": "结构压力测试；参数是透明的情景假设，不是历史频率或客观概率。",
            "condition": "无外省同盟介入、中央持续增援、铁路机场与沿江通道最终受控",
        },
        "summary": {
            "collapse_share": round(collapse_probability, 4),
            "collapse_day": collapse_summary,
            "followed_branch": "collapse-conditioned median path",
            "leadership_group_size": 8,
            "leadership_outcomes": [
                {"label": label, "count": int(count), "weight": float(weight)}
                for label, count, weight in zip(outcome_labels, outcome_counts, outcome_weights)
            ],
        },
        "series": series,
        "nodes": nodes,
        "milestones": milestones,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "collapse_share": collapse_probability, "collapse_day": collapse_summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
