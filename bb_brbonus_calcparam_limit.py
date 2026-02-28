\
"""
BR bonus (chips) + calc parameters + param limit logic extracted from simdata.js.

Inputs expected by functions in this module:
- draw: dict-like structure holding parts (head/body/arm/leg) and optionally br_inside.
  Each part is a dict of fields; each field is either:
    - scalar (int/float/str), or
    - dict with {"param": <number>, "rank": <rank>, ...}

- chip_reinforcement_br: dict keyed by chip id, each value is a dict that contains:
    - "chipBonusValue" (numeric or numeric-like string)
    - optionally "chipBonusType" / "chipBonusSubType" (not used here)
  This matches drawData[CHIP][CHIP_REINFORCEMENT_BR] usage in simdata.js.

Artifacts used:
- parts_param_config.json (param limits like areaTransport.min = 2.0)
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import json


# -----------------------------
# Small helpers
# -----------------------------

def _to_float(x: Any) -> float:
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().replace(",", "")
        if s == "":
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0
    return 0.0

def _get_param(obj: Dict[str, Any], field: str) -> float:
    v = obj.get(field)
    if isinstance(v, dict):
        return float(v.get("param", 0.0))
    return _to_float(v)

def _set_param(obj: Dict[str, Any], field: str, value: float) -> None:
    if field not in obj or not isinstance(obj[field], dict):
        obj[field] = {}
    obj[field]["param"] = float(value)

def _ensure_inside(draw: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return draw.setdefault("br_inside", {})


# -----------------------------
# BR bonus helpers (ported from simdata.js addBonusBr*)
# -----------------------------

def add_bonus_br_armor(draw: Dict[str, Dict[str, Any]], bonus: float) -> None:
    bonus_val = float(bonus) / 100.0
    # armor is "damage coefficient", lower is better -> subtract
    for cat in ("head", "body", "arm", "leg"):
        _set_param(draw[cat], "armor", _get_param(draw[cat], "armor") - bonus_val)

def add_bonus_br_aim(draw, bonus): _set_param(draw["head"], "aim", _get_param(draw["head"], "aim") + float(bonus))
def add_bonus_br_sakuteki(draw, bonus): _set_param(draw["head"], "sakuteki", _get_param(draw["head"], "sakuteki") + float(bonus))
def add_bonus_br_lockon(draw, bonus): _set_param(draw["head"], "lockOn", _get_param(draw["head"], "lockOn") + float(bonus))

def add_bonus_br_ndef_charge_rate(draw, bonus): _set_param(draw["head"], "ndefChargeRate", _get_param(draw["head"], "ndefChargeRate") - float(bonus))

def add_bonus_br_booster(draw, bonus): _set_param(draw["body"], "booster", _get_param(draw["body"], "booster") + float(bonus))
def add_bonus_br_sp_supply(draw, bonus): _set_param(draw["body"], "spSupply", _get_param(draw["body"], "spSupply") + float(bonus))
def add_bonus_br_ndef_capacity(draw, bonus): _set_param(draw["body"], "ndefCapacity", _get_param(draw["body"], "ndefCapacity") + float(bonus))
def add_bonus_br_area_transport(draw, bonus): _set_param(draw["body"], "areaTransport", _get_param(draw["body"], "areaTransport") - float(bonus))

def add_bonus_br_recoil_ctrl(draw, bonus): _set_param(draw["arm"], "recoilCtrl", _get_param(draw["arm"], "recoilCtrl") + float(bonus))
def add_bonus_br_reload_rate(draw, bonus): _set_param(draw["arm"], "reloadRate", _get_param(draw["arm"], "reloadRate") - float(bonus))
def add_bonus_br_weapon_change(draw, bonus): _set_param(draw["arm"], "weaponChange", _get_param(draw["arm"], "weaponChange") + float(bonus))

def add_bonus_br_walk(draw, bonus): _set_param(draw["leg"], "walk", _get_param(draw["leg"], "walk") + float(bonus))
def add_bonus_br_dash(draw, bonus): _set_param(draw["leg"], "dash", _get_param(draw["leg"], "dash") + float(bonus))
def add_bonus_br_velocity_time_rate(draw, bonus): _set_param(draw["leg"], "velocityTimeRate", _get_param(draw["leg"], "velocityTimeRate") - float(bonus))

def add_bonus_br_load_capacity(draw, bonus):
    b = float(bonus)
    _set_param(draw["leg"], "loadCapacity", _get_param(draw["leg"], "loadCapacity") + b)
    _set_param(draw["leg"], "loadCapacityLeftover", _get_param(draw["leg"], "loadCapacityLeftover") + b)

# inside-related resistances / misc
def add_bonus_br_armor_bullet(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "armorBullet", _get_param(inside, "armorBullet") + float(bonus))

def add_bonus_br_armor_explosion(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "armorExplosion", _get_param(inside, "armorExplosion") + float(bonus))

def add_bonus_br_armor_newd(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "armorNewd", _get_param(inside, "armorNewd") + float(bonus))

def add_bonus_br_armor_infight(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "armorInfight", _get_param(inside, "armorInfight") + float(bonus))

def add_bonus_br_bonus_rate(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "bonusRate", _get_param(inside, "bonusRate") + float(bonus))

def add_bonus_br_step_boost_cost(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "stepBoostCost", _get_param(inside, "stepBoostCost") - float(bonus))

def add_bonus_br_sub_mag_rate(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "subMagRate", _get_param(inside, "subMagRate") + float(bonus))

def add_bonus_br_weight_penalty_regist(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "weightPenaltyRegist", _get_param(inside, "weightPenaltyRegist") - float(bonus))

def add_bonus_br_down_damage(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "downDamage", _get_param(inside, "downDamage") + float(bonus))

def add_bonus_br_anti_fatal(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "antiFatal", _get_param(inside, "antiFatal") + float(bonus))

def add_bonus_br_carrier_bonus(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "carrierBonus", _get_param(inside, "carrierBonus") + float(bonus))

def add_bonus_br_charge_time(draw, bonus):
    inside = _ensure_inside(draw)
    _set_param(inside, "chargeTime", _get_param(inside, "chargeTime") - float(bonus))


# -----------------------------
# Apply BR bonus chips (ported from setDrawdataBrBonus switch table)
# -----------------------------

# Map chip id (string) -> handler
CHIP_HANDLERS = {
    # Base armor
    "BASE_ARMOR_I": lambda d, v: add_bonus_br_armor(d, v),
    "BASE_ARMOR_II": lambda d, v: add_bonus_br_armor(d, v),
    "BASE_ARMOR_III": lambda d, v: add_bonus_br_armor(d, v),
    "BASE_ARMOR_IV": lambda d, v: add_bonus_br_armor(d, v),

    # aim / search / lockon
    "AIM_I": lambda d, v: add_bonus_br_aim(d, v),
    "AIM_II": lambda d, v: add_bonus_br_aim(d, v),
    "AIM_III": lambda d, v: add_bonus_br_aim(d, v),

    "SAKUTEKI_I": lambda d, v: add_bonus_br_sakuteki(d, v),
    "SAKUTEKI_II": lambda d, v: add_bonus_br_sakuteki(d, v),
    "SAKUTEKI_III": lambda d, v: add_bonus_br_sakuteki(d, v),

    "LOCKON_I": lambda d, v: add_bonus_br_lockon(d, v),
    "LOCKON_II": lambda d, v: add_bonus_br_lockon(d, v),
    "LOCKON_III": lambda d, v: add_bonus_br_lockon(d, v),

    # DEF charge rate
    "NDEF_CHARGE_I": lambda d, v: add_bonus_br_ndef_charge_rate(d, v),
    "NDEF_CHARGE_II": lambda d, v: add_bonus_br_ndef_charge_rate(d, v),
    "NDEF_CHARGE_III": lambda d, v: add_bonus_br_ndef_charge_rate(d, v),

    # body
    "BOOSTER_I": lambda d, v: add_bonus_br_booster(d, v),
    "BOOSTER_II": lambda d, v: add_bonus_br_booster(d, v),
    "BOOSTER_III": lambda d, v: add_bonus_br_booster(d, v),
    "BOOSTER_IV": lambda d, v: add_bonus_br_booster(d, v),

    "SP_SUPPLY_I": lambda d, v: add_bonus_br_sp_supply(d, v),
    "SP_SUPPLY_II": lambda d, v: add_bonus_br_sp_supply(d, v),
    "SP_SUPPLY_III": lambda d, v: add_bonus_br_sp_supply(d, v),

    "NDEF_CAPACITY_I": lambda d, v: add_bonus_br_ndef_capacity(d, v),
    "NDEF_CAPACITY_II": lambda d, v: add_bonus_br_ndef_capacity(d, v),
    "NDEF_CAPACITY_III": lambda d, v: add_bonus_br_ndef_capacity(d, v),

    "AREA_TRANSPORT_I": lambda d, v: add_bonus_br_area_transport(d, v),
    "AREA_TRANSPORT_II": lambda d, v: add_bonus_br_area_transport(d, v),
    "AREA_TRANSPORT_III": lambda d, v: add_bonus_br_area_transport(d, v),

    # arm
    "RECOILCTRL_I": lambda d, v: add_bonus_br_recoil_ctrl(d, v),
    "RECOILCTRL_II": lambda d, v: add_bonus_br_recoil_ctrl(d, v),
    "RECOILCTRL_III": lambda d, v: add_bonus_br_recoil_ctrl(d, v),

    "RELOAD_RATE_I": lambda d, v: add_bonus_br_reload_rate(d, v),
    "RELOAD_RATE_II": lambda d, v: add_bonus_br_reload_rate(d, v),
    "RELOAD_RATE_III": lambda d, v: add_bonus_br_reload_rate(d, v),

    "WEAPON_CHANGE_I": lambda d, v: add_bonus_br_weapon_change(d, v),
    "WEAPON_CHANGE_II": lambda d, v: add_bonus_br_weapon_change(d, v),
    "WEAPON_CHANGE_III": lambda d, v: add_bonus_br_weapon_change(d, v),

    # leg movement
    "WALK_I": lambda d, v: add_bonus_br_walk(d, v),
    "WALK_II": lambda d, v: add_bonus_br_walk(d, v),
    "WALK_III": lambda d, v: add_bonus_br_walk(d, v),

    "DASH_I": lambda d, v: add_bonus_br_dash(d, v),
    "DASH_II": lambda d, v: add_bonus_br_dash(d, v),
    "DASH_III": lambda d, v: add_bonus_br_dash(d, v),

    "VELOCITY_I": lambda d, v: add_bonus_br_velocity_time_rate(d, v),
    "VELOCITY_II": lambda d, v: add_bonus_br_velocity_time_rate(d, v),
    "VELOCITY_III": lambda d, v: add_bonus_br_velocity_time_rate(d, v),

    "LOAD_CAPACITY_I": lambda d, v: add_bonus_br_load_capacity(d, v),
    "LOAD_CAPACITY_II": lambda d, v: add_bonus_br_load_capacity(d, v),
    "LOAD_CAPACITY_III": lambda d, v: add_bonus_br_load_capacity(d, v),

    # resistances / misc (inside)
    "ARMOR_BULLET_I": lambda d, v: add_bonus_br_armor_bullet(d, v),
    "ARMOR_BULLET_II": lambda d, v: add_bonus_br_armor_bullet(d, v),
    "ARMOR_BULLET_III": lambda d, v: add_bonus_br_armor_bullet(d, v),
    "ARMOR_BULLET_IV": lambda d, v: add_bonus_br_armor_bullet(d, v),

    "ARMOR_EXPLOSION_I": lambda d, v: add_bonus_br_armor_explosion(d, v),
    "ARMOR_EXPLOSION_II": lambda d, v: add_bonus_br_armor_explosion(d, v),
    "ARMOR_EXPLOSION_III": lambda d, v: add_bonus_br_armor_explosion(d, v),
    "ARMOR_EXPLOSION_IV": lambda d, v: add_bonus_br_armor_explosion(d, v),

    "ARMOR_NEWD_I": lambda d, v: add_bonus_br_armor_newd(d, v),
    "ARMOR_NEWD_II": lambda d, v: add_bonus_br_armor_newd(d, v),
    "ARMOR_NEWD_III": lambda d, v: add_bonus_br_armor_newd(d, v),
    "ARMOR_NEWD_IV": lambda d, v: add_bonus_br_armor_newd(d, v),

    "ARMOR_INFIGHT_I": lambda d, v: add_bonus_br_armor_infight(d, v),
    "ARMOR_INFIGHT_II": lambda d, v: add_bonus_br_armor_infight(d, v),
    "ARMOR_INFIGHT_III": lambda d, v: add_bonus_br_armor_infight(d, v),
    "ARMOR_INFIGHT_IV": lambda d, v: add_bonus_br_armor_infight(d, v),

    "BONUS_RATE_I": lambda d, v: add_bonus_br_bonus_rate(d, v),
    "BONUS_RATE_II": lambda d, v: add_bonus_br_bonus_rate(d, v),

    "STEP_BOOST_I": lambda d, v: add_bonus_br_step_boost_cost(d, v),
    "STEP_BOOST_II": lambda d, v: add_bonus_br_step_boost_cost(d, v),

    "SUB_MAG_I": lambda d, v: add_bonus_br_sub_mag_rate(d, v),
    "SUB_MAG_II": lambda d, v: add_bonus_br_sub_mag_rate(d, v),
    "SUB_MAG_III": lambda d, v: add_bonus_br_sub_mag_rate(d, v),

    "WEIGHT_PENALTY_REGIST_I": lambda d, v: add_bonus_br_weight_penalty_regist(d, v),
    "WEIGHT_PENALTY_REGIST_II": lambda d, v: add_bonus_br_weight_penalty_regist(d, v),
    "WEIGHT_PENALTY_REGIST_III": lambda d, v: add_bonus_br_weight_penalty_regist(d, v),

    "DOWN_DAMAGE_I": lambda d, v: add_bonus_br_down_damage(d, v),
    "DOWN_DAMAGE_II": lambda d, v: add_bonus_br_down_damage(d, v),

    "ANTI_FATAL_I": lambda d, v: add_bonus_br_anti_fatal(d, v),
    "ANTI_FATAL_II": lambda d, v: add_bonus_br_anti_fatal(d, v),

    "CARRIER_BONUS_I": lambda d, v: add_bonus_br_carrier_bonus(d, v),
    "CARRIER_BONUS_II": lambda d, v: add_bonus_br_carrier_bonus(d, v),

    "CHARGE_TIME_I": lambda d, v: add_bonus_br_charge_time(d, v),
    "CHARGE_TIME_II": lambda d, v: add_bonus_br_charge_time(d, v),
}

def _normalize_chip_key(key: str) -> str:
    s = key.strip()
    # already looks like BASE_ARMOR_I
    if s.upper() == s and "_" in s:
        return s
    # best-effort: turn camelCase / kebab into upper snake
    s = s.replace("-", "_")
    s = "".join(["_"+c if c.isupper() else c for c in s]).upper()
    s = s.replace("__", "_").strip("_")
    return s

def apply_br_bonus_chips(
    *,
    draw: Dict[str, Dict[str, Any]],
    chip_reinforcement_br: Dict[str, Dict[str, Any]],
) -> None:
    """
    Apply BR reinforcement chips to draw parts.

    chip_reinforcement_br format (per entry):
      {"chipBonusValue": <value>}  (other fields ignored)

    Keys are matched against CHIP_HANDLERS after normalization.
    """
    if not chip_reinforcement_br:
        return

    for raw_key, chip in chip_reinforcement_br.items():
        key = _normalize_chip_key(str(raw_key))
        bonus_value = None
        if isinstance(chip, dict):
            # site uses ...[CHIP_BONUS_VALUE]
            bonus_value = chip.get("chipBonusValue") if "chipBonusValue" in chip else chip.get("CHIP_BONUS_VALUE")
            # sometimes it's nested
            if isinstance(bonus_value, dict) and "param" in bonus_value:
                bonus_value = bonus_value["param"]
        v = _to_float(bonus_value)
        fn = CHIP_HANDLERS.get(key)
        if fn:
            fn(draw, v)


# -----------------------------
# Calc parameters (ported from DataCommon.calcDrawParam + calcFunc)
# -----------------------------

def calc_param_ndef_charge(src: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not src or "ndefCharge" not in src:
        return None
    charge_time = _get_param(src, "ndefCharge")
    charge_time_rate = 100
    if isinstance(src.get("ndefChargeRate"), dict) and src["ndefChargeRate"].get("param"):
        charge_time_rate = int(_get_param(src, "ndefChargeRate"))
    if charge_time_rate:
        charge_time = charge_time * (charge_time_rate / 100.0)
    return {"rank": src.get("ndefCharge", {}).get("rank"), "param": charge_time}

def calc_param_step(src: Dict[str, Any], step_boost_default: float = 12.0) -> Optional[Dict[str, Any]]:
    if not src or "booster" not in src:
        return None
    booster = _get_param(src, "booster")
    step_boost_cost = step_boost_default
    if isinstance(src.get("stepBoostCost"), dict) and int(_get_param(src, "stepBoostCost")):
        step_boost_cost = int(_get_param(src, "stepBoostCost"))
    if step_boost_cost == 0:
        return None
    step = int(int(booster) / step_boost_cost)
    if int(booster) % step_boost_cost != 0:
        step += 1
    return {"param": step}

def calc_param_velocity(src: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not src or "velocity" not in src:
        return None
    velocity = _get_param(src, "velocity")
    velocity_time_rate = 100
    if isinstance(src.get("velocityTimeRate"), dict) and src["velocityTimeRate"].get("param"):
        velocity_time_rate = int(_get_param(src, "velocityTimeRate"))
    if velocity_time_rate:
        velocity = velocity * (velocity_time_rate / 100.0)
    return {"rank": src.get("velocity", {}).get("rank"), "param": velocity}

def calc_draw_param(src: Dict[str, Any], parts_type: str, sysdata_step_boost: float = 12.0) -> Dict[str, Any]:
    """
    Mimics DataCommon.calcDrawParam for core parts:
      head: ndefCharge
      body: step
      leg: velocity
    parts_type: "head"|"body"|"leg" (case-insensitive). Weapons not handled here.
    """
    pt = parts_type.lower()
    if pt == "head":
        v = calc_param_ndef_charge(src)
        if v is not None:
            src["ndefCharge"] = v
    elif pt == "body":
        v = calc_param_step(src, step_boost_default=sysdata_step_boost)
        if v is not None:
            src["step"] = v
    elif pt == "leg":
        v = calc_param_velocity(src)
        if v is not None:
            src["velocity"] = v
    return src


# -----------------------------
# Param limits (ported from setDrawdataPartsParamLimit)
# -----------------------------

def load_param_limits(path: str | Path) -> Dict[str, float]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    limits = payload.get("param_limits", {})
    return {k: float(v) for k, v in limits.items()}

def apply_parts_param_limits(draw: Dict[str, Dict[str, Any]], param_limits: Dict[str, float]) -> None:
    """
    Current simdata.js applies only:
      body.areaTransport >= paramMin (2.0)
    """
    min_area = param_limits.get("areaTransport")
    if min_area is None:
        return
    if "body" in draw and isinstance(draw["body"].get("areaTransport"), dict):
        if float(draw["body"]["areaTransport"].get("param", 0.0)) < float(min_area):
            draw["body"]["areaTransport"]["param"] = float(min_area)


if __name__ == "__main__":
    # Minimal smoke test
    limits = load_param_limits("parts_param_config.json")
    d = {
        "head": {"armor": {"param": 1.10}, "ndefCharge": {"param": 6.0, "rank": "C"}, "ndefChargeRate": {"param": 90}},
        "body": {"booster": {"param": 140}, "areaTransport": {"param": 1.2}},
        "arm":  {"reloadRate": {"param": 1.2}},
        "leg":  {"walk": {"param": 7.0}, "dash": {"param": 17.0}, "velocity": {"param": 1.8}, "velocityTimeRate": {"param": 90}, "loadCapacity": {"param": 3200}, "loadCapacityLeftover": {"param": 0}},
    }

    chips = {
        "BASE_ARMOR_I": {"chipBonusValue": 60},
        "AREA_TRANSPORT_I": {"chipBonusValue": 0.2},
        "VELOCITY_I": {"chipBonusValue": 10},
    }
    apply_br_bonus_chips(draw=d, chip_reinforcement_br=chips)
    apply_parts_param_limits(d, limits)
    calc_draw_param(d["head"], "head")
    calc_draw_param(d["body"], "body", sysdata_step_boost=12.0)
    calc_draw_param(d["leg"], "leg")
    print(json.dumps(d, ensure_ascii=False, indent=2))
