\
"""
Integrated BR assemble calculator (mech + weapons).

This module glues together:
- bb_base_and_brand.py : base aggregation + brand(set) bonus
- bb_brbonus_calcparam_limit.py : BR reinforcement chip bonuses + calc params + param limits
- bb_calc_movement.py (optional logic already embedded in base module; kept for compatibility)
- bb_weapon_calc.py : weapon-derived stats

Main entry:
- calc_full_assemble(...): builds draw parts from constdata, applies:
    1) rank->param loading
    2) brand set bonus
    3) BR reinforcement chip bonuses
    4) param limits (areaTransport min)
    5) calc params (ndefCharge/step/velocity)
    6) base aggregation (armor avg, weight, movement with penalty)
    7) weapon derived params for any provided weapon dicts
Returns a dict with draw parts and summary stats.

NOTE:
This is designed as a faithful port target; you can extend it to cover additional chips,
weapon bonuses, and other derived parameters.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import json
import copy

from bb_base_and_brand import (
    load_const_parts, load_bland_data, load_rank_param, load_sys_consts,
    build_draw_parts_from_const, apply_set_bonus, calc_parts_base
)
from bb_brbonus_calcparam_limit import (
    apply_br_bonus_chips, load_param_limits, apply_parts_param_limits, calc_draw_param
)
from bb_weapon_calc import apply_weapon_derived_params


def calc_full_assemble(
    *,
    constdata_js: str | Path,
    rank_param_json: str | Path,
    sys_consts_json: str | Path,
    bland_data_js: Optional[str | Path] = None,  # if None, uses constdata_js
    parts_keys: Dict[str, str],  # {"head": "a", "body":"a","arm":"a","leg":"a"}
    inside_load_capacity: float = 0.0,
    weight_penalty_per: Optional[float] = None,
    set_bonus_rate_percent: float = 100.0,
    br_reinforcement_chips: Optional[Dict[str, Dict[str, Any]]] = None,
    weapons: Optional[Dict[str, Dict[str, Any]]] = None,  # {"asMain": {...}, ...}
    parts_param_limits_json: str | Path = "parts_param_config.json",
) -> Dict[str, Any]:
    """
    weapons: dict of weapon dicts. Each weapon dict should have at least:
      damage, clip, ammo, rate (or key_map override if different)
    """
    const_parts = load_const_parts(constdata_js)
    bland = load_bland_data(bland_data_js or constdata_js)
    rp = load_rank_param(rank_param_json)
    sysc = load_sys_consts(sys_consts_json)
    limits = load_param_limits(parts_param_limits_json)

    draw = build_draw_parts_from_const(
        const_parts=const_parts,
        rank_param=rp,
        head_key=parts_keys["head"],
        body_key=parts_keys["body"],
        arm_key=parts_keys["arm"],
        leg_key=parts_keys["leg"],
    )

    # 1) set bonus (brand)
    set_bonus_info = apply_set_bonus(draw=draw, bland_data=bland, bonus_rate_percent=set_bonus_rate_percent)

    # 2) br reinforcement chips
    if br_reinforcement_chips:
        apply_br_bonus_chips(draw=draw, chip_reinforcement_br=br_reinforcement_chips)

    # 3) param limits
    apply_parts_param_limits(draw, limits)

    # 4) calc params for mech parts
    calc_draw_param(draw["head"], "head")
    calc_draw_param(draw["body"], "body", sysdata_step_boost=12.0)
    calc_draw_param(draw["leg"], "leg")

    # 5) base aggregation (includes movement w/ penalty)
    base = calc_parts_base(
        draw=draw,
        sysc=sysc,
        rank_param=rp,
        inside_load_capacity=inside_load_capacity,
        weight_penalty_per=weight_penalty_per,
    )

    # 6) weapons derived
    weapons_out = {}
    if weapons:
        for slot, w in weapons.items():
            w2 = copy.deepcopy(w)
            apply_weapon_derived_params(w2)
            weapons_out[slot] = w2

    return {
        "parts_keys": parts_keys,
        "set_bonus": set_bonus_info,
        "base": base,
        "draw": draw,
        "weapons": weapons_out,
    }


if __name__ == "__main__":
    # Example usage:
    result = calc_full_assemble(
        constdata_js="constdata.js",
        rank_param_json="rank_param.json",
        sys_consts_json="sys_calc_constants.json",
        parts_keys={"head":"a","body":"a","arm":"a","leg":"a"},
        br_reinforcement_chips={
            "BASE_ARMOR_I": {"chipBonusValue": 60},
            "WALK_I": {"chipBonusValue": 0.05},
        },
        weapons={
            "asMain": {"damage": 1200, "clip": 10, "ammo": 4, "rate": 300},
            "asSub": {"damage": {"damageParam": 240, "pellet": 20}, "clip": 1, "ammo": 0, "rate": [60, 120]},
        }
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
