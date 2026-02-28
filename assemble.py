from __future__ import annotations

from typing import Any, Dict, Optional
import copy

from catalog import Catalog, LoadoutKeys, WeaponRef
from bb_weapon_calc import apply_weapon_derived_params
from bb_base_and_brand import apply_set_bonus, calc_parts_base
from bb_brbonus_calcparam_limit import (
    apply_br_bonus_chips,
    apply_parts_param_limits,
    calc_draw_param,
)


def _parts_to_draw_from_normalized(c: Catalog, keys: LoadoutKeys) -> Dict[str, Dict[str, Any]]:
    """Build a minimal draw structure from parts_normalized entries (param already numeric)."""
    head = copy.deepcopy(c.get_part("head", keys.head))
    body = copy.deepcopy(c.get_part("body", keys.body))
    arm  = copy.deepcopy(c.get_part("arm", keys.arm))
    leg  = copy.deepcopy(c.get_part("leg", keys.leg))

    # Convert normalized schema -> draw schema used by our logic modules:
    def to_draw_part(p: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        out["name"] = p.get("name")
        out["blandId"] = p.get("raw_extra", {}).get("blandId") if isinstance(p.get("raw_extra"), dict) else p.get("blandId")
        # common
        out["weight"] = {"param": p.get("weight"), "rank": p.get("weight_rank")}
        out["armor"]  = {"param": p.get("armor"), "rank": p.get("armor_rank")}
        if p.get("chip_capacity") is not None:
            out["chipCapacity"] = {"param": p.get("chip_capacity")}
        # mapped fields
        for dst_field, src_field in mapping.items():
            if p.get(src_field) is None and p.get(src_field + "_rank") is None:
                continue
            out[dst_field] = {"param": p.get(src_field), "rank": p.get(src_field + "_rank")}
        return out

    head_draw = to_draw_part(head, {"aim":"aim","sakuteki":"search","lockOn":"lock_on","ndefCharge":"ndef_charge"})
    body_draw = to_draw_part(body, {"booster":"boost","spSupply":"sp","areaTransport":"areaTransport","ndefCapacity":"ndef_charge"})
    arm_draw  = to_draw_part(arm,  {"reloadRate":"reload","recoilCtrl":"recoil","weaponChange":"handling","ndefChargeRate":"ndef_charge"})
    # for leg, we need loadCapacity, walk, dash, velocity and some auxiliaries; normalized doesn't contain all, keep what exists
    leg_draw  = to_draw_part(leg,  {"walk":"dash", "dash":"dash", "loadCapacity":"carry", "velocity":"accel"})
    # This is a best-effort mapping; for full fidelity, use constdata.js route.
    # Keep leftovers if available
    if "loadCapacity" in leg_draw:
        leg_draw["loadCapacityLeftover"] = {"param": None}

    return {"head": head_draw, "body": body_draw, "arm": arm_draw, "leg": leg_draw}


def calc_loadout(
    catalog: Catalog,
    keys: LoadoutKeys,
    *,
    inside_load_capacity: float = 0.0,
    weight_penalty_per: Optional[float] = None,
    set_bonus_rate_percent: float = 100.0,
    br_reinforcement_chips: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    High-level: compute mech stats (base + bonuses) using the data files.
    NOTE: This wrapper uses normalized part data; it is meant for easy integration.
    If you need full site-equivalent results, use bb_full_calc.py with constdata.js inputs.
    """
    draw = _parts_to_draw_from_normalized(catalog, keys)

    set_bonus = apply_set_bonus(draw=draw, bland_data=catalog.bland, bonus_rate_percent=set_bonus_rate_percent)

    if br_reinforcement_chips:
        apply_br_bonus_chips(draw=draw, chip_reinforcement_br=br_reinforcement_chips)

    apply_parts_param_limits(draw, catalog.param_limits)
    calc_draw_param(draw["head"], "head")
    calc_draw_param(draw["body"], "body", sysdata_step_boost=12.0)
    calc_draw_param(draw["leg"], "leg")

    base = calc_parts_base(
        draw=draw,
        sysc=catalog.sys_consts,
        rank_param=catalog.rank_param,
        inside_load_capacity=inside_load_capacity,
        weight_penalty_per=weight_penalty_per,
    )

    return {"keys": keys.__dict__, "set_bonus": set_bonus, "base": base, "draw": draw}


def calc_weapon(catalog: Catalog, ref: WeaponRef) -> Dict[str, Any]:
    w = copy.deepcopy(catalog.get_weapon(ref.dataset, ref.key))
    apply_weapon_derived_params(w)
    return w


def calc_full(
    catalog: Catalog,
    keys: LoadoutKeys,
    weapons: Optional[Dict[str, WeaponRef]] = None,
    **kwargs,
) -> Dict[str, Any]:
    out = calc_loadout(catalog, keys, **kwargs)
    if weapons:
        out["weapons"] = {slot: calc_weapon(catalog, wref) for slot, wref in weapons.items()}
    return out
