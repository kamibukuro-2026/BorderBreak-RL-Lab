\
"""
Weapon-derived parameter calculations extracted from simdata.js (DataCommon.calcDrawParam + calcFunc).

Implements:
- get_damage_num(damage_obj): returns a list[int] of damage numbers used for calc (supports:
    * list of damage values
    * max/min model (MAX_DAMAGE)
    * charge model (CHARGE_DAMAGE list -> last entry)
    * pellet model (DAMAGE_PARAM * PELLET)
    * scalar)
- calc_magazine_damage(src): damage * clip -> list[int]
- calc_mag_total_damage(src): damage * clip * ammo (ammo==0 => 1) -> list[int]
- calc_magazine_sec(src): clip / rate * 60 (rate may be list) -> float or list[float]
- calc_damage_per_sec(src): damage * rate / 60 (rate may be list) -> list[int]

All formulas are direct ports of simdata.js calcFunc blocks.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
import math


# Key names: in JS they are KEY.WEAPON_PARAM.* and KEY.WEAPON_PARAM_SUB.*.
# Here we keep plain-string defaults matching the constdata keys.
# If your source uses different names, pass a key_map.

DEFAULT_KEY_MAP = {
    # weapon param
    "DAMAGE": "damage",
    "CLIP": "clip",
    "AMMO": "ammo",
    "RATE": "rate",

    # sub-keys for complex damage
    "MAX_DAMAGE": "maxDamage",
    "CHARGE_DAMAGE": "chargeDamage",
    "DAMAGE_PARAM": "damageParam",
    "PELLET": "pellet",
}


def _parse_int(x: Any) -> int:
    # JS baseLib.parseInt: tolerant int parsing
    if x is None:
        return 0
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return int(x)
    if isinstance(x, str):
        s = x.strip().replace(",", "")
        if s == "":
            return 0
        try:
            return int(float(s))
        except ValueError:
            return 0
    return 0


def get_damage_num(damage_obj: Any, key_map: Dict[str, str] = DEFAULT_KEY_MAP) -> List[int]:
    """
    Port of simdata.js function getDamageNum(damageObj).
    Always returns a list[int] (for switch weapons etc.)
    """
    damage: List[int] = []

    if isinstance(damage_obj, list):
        # multiple params
        for v in damage_obj:
            damage.append(_parse_int(v))
    elif isinstance(damage_obj, dict) and key_map["MAX_DAMAGE"] in damage_obj:
        # max/min model: use max damage
        damage.append(_parse_int(damage_obj[key_map["MAX_DAMAGE"]]))
    elif isinstance(damage_obj, dict) and key_map["CHARGE_DAMAGE"] in damage_obj:
        # charge model: use last entry of charge damage list
        arr = damage_obj.get(key_map["CHARGE_DAMAGE"])
        if isinstance(arr, list) and arr:
            damage.append(_parse_int(arr[-1]))
        else:
            damage.append(0)
    elif isinstance(damage_obj, dict) and key_map["DAMAGE_PARAM"] in damage_obj:
        # pellet model: damageParam * pellet
        damage.append(_parse_int(damage_obj[key_map["DAMAGE_PARAM"]]) * _parse_int(damage_obj.get(key_map["PELLET"])))
    else:
        # single number
        damage.append(_parse_int(damage_obj))

    return damage


def calc_magazine_damage(src: Dict[str, Any], key_map: Dict[str, str] = DEFAULT_KEY_MAP) -> Optional[List[int]]:
    if not src or key_map["DAMAGE"] not in src or key_map["CLIP"] not in src:
        return None
    damage = get_damage_num(src[key_map["DAMAGE"]], key_map)
    clip = _parse_int(src[key_map["CLIP"]])
    return [d * clip for d in damage]


def calc_mag_total_damage(src: Dict[str, Any], key_map: Dict[str, str] = DEFAULT_KEY_MAP) -> Optional[List[int]]:
    if not src or key_map["DAMAGE"] not in src or key_map["CLIP"] not in src:
        return None
    damage = get_damage_num(src[key_map["DAMAGE"]], key_map)
    clip = _parse_int(src[key_map["CLIP"]])
    ammo = _parse_int(src.get(key_map["AMMO"]))
    if ammo == 0:
        ammo = 1
    return [d * clip * ammo for d in damage]


def calc_magazine_sec(src: Dict[str, Any], key_map: Dict[str, str] = DEFAULT_KEY_MAP) -> Optional[Union[float, List[float]]]:
    if not src or key_map["RATE"] not in src or key_map["CLIP"] not in src:
        return None

    clip = _parse_int(src[key_map["CLIP"]])
    rate_obj = src[key_map["RATE"]]

    if isinstance(rate_obj, list):
        out: List[float] = []
        for r in rate_obj:
            rate = _parse_int(r)
            out.append(clip / rate * 60 if rate else 0.0)
        return out

    rate = _parse_int(rate_obj)
    if rate == 0:
        return None
    return clip / rate * 60


def calc_damage_per_sec(src: Dict[str, Any], key_map: Dict[str, str] = DEFAULT_KEY_MAP) -> Optional[List[int]]:
    if not src or key_map["DAMAGE"] not in src or key_map["RATE"] not in src:
        return None

    damage = get_damage_num(src[key_map["DAMAGE"]], key_map)
    rate_obj = src[key_map["RATE"]]

    out: List[int] = []

    if isinstance(rate_obj, list):
        for r in rate_obj:
            rate = _parse_int(r)
            for d in damage:
                out.append(int(d * rate / 60))
        return out

    rate = _parse_int(rate_obj)
    if rate == 0:
        return None
    for d in damage:
        out.append(_parse_int(d * rate / 60))
    return out


def apply_weapon_derived_params(dst: Dict[str, Any], key_map: Dict[str, str] = DEFAULT_KEY_MAP) -> Dict[str, Any]:
    """
    Mutates dst by adding:
      magazineDamage, magTotalDamage, magazineSec, damagePerSec
    using the source fields damage/clip/ammo/rate.
    """
    md = calc_magazine_damage(dst, key_map)
    if md is not None:
        dst["magazineDamage"] = md

    mtd = calc_mag_total_damage(dst, key_map)
    if mtd is not None:
        dst["magTotalDamage"] = mtd

    ms = calc_magazine_sec(dst, key_map)
    if ms is not None:
        dst["magazineSec"] = ms

    dps = calc_damage_per_sec(dst, key_map)
    if dps is not None:
        dst["damagePerSec"] = dps

    return dst


if __name__ == "__main__":
    # smoke tests
    w1 = {"damage": 1200, "clip": 10, "ammo": 4, "rate": 300}
    apply_weapon_derived_params(w1)
    print(w1)

    w2 = {"damage": {"damageParam": 240, "pellet": 20}, "clip": 1, "ammo": 0, "rate": [60, 120]}
    apply_weapon_derived_params(w2)
    print(w2)
