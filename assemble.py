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


# 1セルあたりのメートル数（simulation.py の CELL_SIZE_M と同値、循環 import 回避）
_CELL_SIZE_M = 10
# 装甲計算の基準 HP（rank_param["armor"] はダメージ係数: 実効HP = 基準HP / 係数）
_AGENT_HP_BASE = 10_000
# T-2: aim.param → hit_rate 変換定数（constants.py と同値、循環 import 回避）
_HIT_RATE_DEFAULT  = 0.64   # 標準命中率（constants.HIT_RATE と同値: ロックオン内×1.25 → 実効0.80）
_AIM_PARAM_BASE    = 12.0   # B ランクの aim.param 値
_AIM_SCALE         = 0.006  # aim 1点あたりの hit_rate 変化量
_HIT_RATE_MIN      = 0.40   # hit_rate の下限
_HIT_RATE_MAX      = 1.00   # hit_rate の上限


def assemble_agent_params(
    calc_result: Dict[str, Any],
    *,
    default_max_hp: int = _AGENT_HP_BASE,
    default_dps: int = 3000,
    default_search_range_c: float = 8.0,
    default_lockon_range_c: float = 6.0,
    default_cells_per_step: int = 2,
    default_hit_rate: float = _HIT_RATE_DEFAULT,
    default_shots_per_step: int = 1,
) -> Dict[str, Any]:
    """
    calc_full() の出力から Agent.__init__ に渡す per-agent パラメータを抽出する。

    Parameters
    ----------
    calc_result : dict
        calc_full() の戻り値と同じ構造を持つ dict。
    default_max_hp : int
        base.armor_avg が存在しない場合のフォールバック値。
    default_dps : int
        weapons.main.damagePerSec が存在しない場合のフォールバック値。
    default_search_range_c : float
        draw.head.sakuteki が存在しない場合のフォールバック値（セル単位）。
    default_lockon_range_c : float
        draw.head.lockOn が存在しない場合のフォールバック値（セル単位）。
    default_cells_per_step : int
        base.walk が存在しない場合のフォールバック値。
    default_hit_rate : float
        draw.head.aim が存在しない場合のフォールバック値。
    default_shots_per_step : int
        weapons.main.rate が存在しない場合のフォールバック値。

    Returns
    -------
    dict
        ``Agent(**params, agent_id=..., x=..., y=..., team=...)`` に展開できる kwargs dict。
        キー: max_hp, dps, search_range_c, lockon_range_c, cells_per_step, hit_rate, shots_per_step
    """
    # 実効 HP: armor_avg.param はダメージ係数（小さいほど硬い）
    # 実効HP = 基準HP / ダメージ係数  （例: S=0.63 → 15,873、C+=1.0 → 10,000、E-=1.38 → 7,246）
    armor_avg = calc_result.get("base", {}).get("armor_avg", {}).get("param")
    max_hp = round(_AGENT_HP_BASE / armor_avg) if (armor_avg is not None and armor_avg > 0) else default_max_hp

    # DPS: main 武器の damagePerSec[0]
    weapons = calc_result.get("weapons", {})
    main_weapon = weapons.get("main", {})
    dps_list = main_weapon.get("damagePerSec")
    dps = int(dps_list[0]) if dps_list else default_dps

    # 索敵・ロックオン範囲（メートル → セル）
    head = calc_result.get("draw", {}).get("head", {})
    sakuteki = head.get("sakuteki", {}).get("param")
    lockon = head.get("lockOn", {}).get("param")
    search_range_c = (sakuteki / _CELL_SIZE_M) if sakuteki is not None else default_search_range_c
    lockon_range_c = (lockon / _CELL_SIZE_M) if lockon is not None else default_lockon_range_c

    # 移動速度 (m/s) → cells_per_step（最低 1）
    walk = calc_result.get("base", {}).get("walk", {}).get("param")
    cells_per_step = max(1, round(walk / _CELL_SIZE_M)) if walk is not None else default_cells_per_step

    # aim.param → hit_rate（B ランク aim=12 が標準 0.80）
    aim_param = head.get("aim", {}).get("param")
    if aim_param is not None:
        raw = _HIT_RATE_DEFAULT + (aim_param - _AIM_PARAM_BASE) * _AIM_SCALE
        hit_rate = float(max(_HIT_RATE_MIN, min(_HIT_RATE_MAX, raw)))
    else:
        hit_rate = float(default_hit_rate)

    # weapons.main.rate → shots_per_step（最低 1）
    rate = main_weapon.get("rate")
    shots_per_step = max(1, round(rate / 60)) if rate is not None else default_shots_per_step

    return {
        "max_hp": max_hp,
        "dps": dps,
        "search_range_c": search_range_c,
        "lockon_range_c": lockon_range_c,
        "cells_per_step": cells_per_step,
        "hit_rate": hit_rate,
        "shots_per_step": shots_per_step,
    }
