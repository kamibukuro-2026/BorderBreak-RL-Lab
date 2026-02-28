\
"""
Movement / weight penalty logic extracted from simdata.js.
- setWeightPenalty(): computes overweight penalty and applies it to walk/dash with min/max clamps
- get_rank_closest(): chooses the rank whose mapped value is closest to the numeric param
Rank tables are loaded from rank_param.json (extracted from constdata.js GAMEDATAOPE.RANK_PARAM).
System constants are loaded from sys_calc_constants.json (extracted from constdata_sys.js).
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import json
import math


@dataclass(frozen=True)
class SysConsts:
    WEIGHT_PENALTY: float
    WALK_MIN: float
    DASH_MIN: float
    WALK_MIN_HOVER: float
    WALK_MAX_HOVER: float
    DASH_MIN_HOVER: float


def load_sys_consts(path: str | Path) -> SysConsts:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    c = data.get("constants", data)
    # tolerate both wrapper and raw
    return SysConsts(
        WEIGHT_PENALTY=float(c["WEIGHT_PENALTY"]),
        WALK_MIN=float(c["WALK_MIN"]),
        DASH_MIN=float(c["DASH_MIN"]),
        WALK_MIN_HOVER=float(c["WALK_MIN_HOVER"]),
        WALK_MAX_HOVER=float(c["WALK_MAX_HOVER"]),
        DASH_MIN_HOVER=float(c["DASH_MIN_HOVER"]),
    )


def load_rank_param(path: str | Path) -> Dict[str, Dict[str, float]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rp = data.get("rank_param", data)
    # ensure floats
    out: Dict[str, Dict[str, float]] = {}
    for group, table in rp.items():
        if not isinstance(table, dict):
            continue
        out[group] = {str(rk): float(val) for rk, val in table.items()}
    return out


def get_rank_closest(const_data: Dict[str, float], param: float) -> str:
    """
    JS getRank(constData, param):
      choose the rank key whose value is closest to param (min abs diff).
    """
    app_rank = ""
    app_value = float("inf")
    for rk, val in const_data.items():
        diff = abs(float(val) - float(param))
        if diff < app_value:
            app_value = diff
            app_rank = rk
    return app_rank


def set_weight_penalty(
    *,
    sysc: SysConsts,
    rank_param: Dict[str, Dict[str, float]],
    load_capa: float,
    weight: float,
    weight_penalty_per: float,
    walk: float,
    dash: float,
    is_hover: bool,
) -> Dict[str, Any]:
    """
    Port of simdata.js setWeightPenalty(setObj, loadCapa, weight, weightPenaltyPer, walk, dash, legType).

    - leftOver = loadCapa - weight
    - if leftOver < 0:
        penalty = leftOver / WEIGHT_PENALTY * (weightPenaltyPer / 100)
      else penalty = 0
    - apply to walk/dash: base * (1 + penalty/100)
    - clamp:
        hover: walk in [WALK_MIN_HOVER, WALK_MAX_HOVER], dash >= DASH_MIN_HOVER
        normal: walk >= WALK_MIN, dash >= DASH_MIN
    - ranks: computed by closest match against RANK_PARAM['walk'/'walk_hover'] and ['dash'] or ['dash_hover']
    """
    left_over = load_capa - weight
    penalty = 0.0
    if left_over < 0:
        penalty = (left_over / sysc.WEIGHT_PENALTY) * (weight_penalty_per / 100.0)

    walk_adj = walk * (1.0 + (penalty / 100.0))
    dash_adj = dash * (1.0 + (penalty / 100.0))

    if is_hover:
        if walk_adj < sysc.WALK_MIN_HOVER:
            walk_adj = sysc.WALK_MIN_HOVER
        elif walk_adj > sysc.WALK_MAX_HOVER:
            walk_adj = sysc.WALK_MAX_HOVER

        if dash_adj < sysc.DASH_MIN_HOVER:
            dash_adj = sysc.DASH_MIN_HOVER
        walk_rank_table = rank_param.get("walk_hover", {})
        dash_rank_table = rank_param.get("dash_hover", rank_param.get("dash", {}))
    else:
        if walk_adj < sysc.WALK_MIN:
            walk_adj = sysc.WALK_MIN
        if dash_adj < sysc.DASH_MIN:
            dash_adj = sysc.DASH_MIN
        walk_rank_table = rank_param.get("walk", {})
        dash_rank_table = rank_param.get("dash", {})

    return {
        "weight": weight,
        "loadcapacity_leftover": left_over,
        "weight_penalty": penalty,
        "walk": {"param": walk_adj, "rank": get_rank_closest(walk_rank_table, walk_adj) if walk_rank_table else None},
        "dash": {"param": dash_adj, "rank": get_rank_closest(dash_rank_table, dash_adj) if dash_rank_table else None},
    }


if __name__ == "__main__":
    # quick smoke test (you can edit inputs)
    sysc = load_sys_consts("sys_calc_constants.json")
    rp = load_rank_param("rank_param.json")

    result = set_weight_penalty(
        sysc=sysc,
        rank_param=rp,
        load_capa=3300,
        weight=3600,
        weight_penalty_per=60,  # example "万分率" factor used by the site
        walk=rp["walk"]["C+"],
        dash=rp["dash"]["C+"],
        is_hover=False,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
