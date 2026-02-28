\
"""
Base parameter aggregation + brand (set) bonus logic extracted from simdata.js.

What this module provides:
- load_const_parts(): loads PARTS_HEAD/BODY/ARM/LEG from constdata.js
- load_bland_data(): loads BLAND (brand set bonus definitions) from constdata.js
- load_rank_param(): loads rank->param tables (rank_param.json extracted from constdata.js)
- rank_param_load_part(): fills {rank: "..."} fields with {param: ...} using rank tables
- apply_set_bonus(): applies brand set bonus (if all 4 parts share the same 'blandId')
- calc_parts_base(): aggregates "raw/base" parameters (armor average, total weight, load capacity leftover, walk/dash with overweight penalty)

Notes:
- This code follows simdata.js behavior for:
  - setDrawdataSetBonus() and addBonusBr* helpers
  - setDrawdataBaseParam() for armor average and weight/movement aggregation
- _get_rank_closest is re-exported from bb_calc_movement.get_rank_closest to avoid duplication
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import copy
import json
import re
import ast

from bb_calc_movement import get_rank_closest as _get_rank_closest


# -----------------------------
# Loaders / JS object parsing
# -----------------------------

def _strip_js_comments(code: str) -> str:
    out=[]
    i=0; n=len(code); in_str=False; str_char=''; escape=False
    while i<n:
        ch=code[i]; nxt=code[i+1] if i+1<n else ''
        if in_str:
            out.append(ch)
            if escape: escape=False
            elif ch=='\\': escape=True
            elif ch==str_char: in_str=False
            i+=1; continue
        if ch in ('"', "'"):
            in_str=True; str_char=ch; out.append(ch); i+=1; continue
        if ch=='/' and nxt=='/':
            i+=2
            while i<n and code[i] not in '\n\r': i+=1
            continue
        if ch=='/' and nxt=='*':
            i+=2
            while i+1<n and not (code[i]=='*' and code[i+1]=='/'): i+=1
            i+=2; continue
        out.append(ch); i+=1
    return ''.join(out)

def _extract_brace_block(s: str, start_idx: int) -> Tuple[str,int]:
    depth=0
    for i in range(start_idx, len(s)):
        ch=s[i]
        if ch=='{': depth+=1
        elif ch=='}':
            depth-=1
            if depth==0:
                return s[start_idx:i+1], i+1
    raise ValueError("no matching brace")

def _parse_js_object_literal(block: str) -> dict:
    blk = re.sub(r",(\s*[}\]])", r"\1", block)
    blk = re.sub(r"\bnull\b", "None", blk)
    blk = re.sub(r"\btrue\b", "True", blk)
    blk = re.sub(r"\bfalse\b", "False", blk)
    return ast.literal_eval(blk)

def _extract_section_dict(code: str, section_key: str) -> dict:
    m = re.search(rf"'{re.escape(section_key)}'\s*:\s*\{{", code)
    if not m:
        raise ValueError(f"Section not found: {section_key}")
    brace_start = code.find("{", m.end()-1)
    block,_ = _extract_brace_block(code, brace_start)
    return _parse_js_object_literal(block)

def load_const_parts(constdata_js_path: str | Path) -> Dict[str, Dict[str, Any]]:
    """
    Returns:
      {"head": {...}, "body": {...}, "arm": {...}, "leg": {...}}
    where each category dict is keyed by the source key (e.g., 'a', 'T', ...)
    """
    code = Path(constdata_js_path).read_text(encoding="utf-8", errors="ignore")
    clean = _strip_js_comments(code)
    return {
        "head": _extract_section_dict(clean, "PARTS_HEAD"),
        "body": _extract_section_dict(clean, "PARTS_BODY"),
        "arm":  _extract_section_dict(clean, "PARTS_ARM"),
        "leg":  _extract_section_dict(clean, "PARTS_LEG"),
    }

def load_bland_data(constdata_js_path: str | Path) -> Dict[str, Any]:
    code = Path(constdata_js_path).read_text(encoding="utf-8", errors="ignore")
    clean = _strip_js_comments(code)
    return _extract_section_dict(clean, "BLAND")

def load_rank_param(rank_param_json_path: str | Path) -> Dict[str, Dict[str, float]]:
    payload = json.loads(Path(rank_param_json_path).read_text(encoding="utf-8"))
    rp = payload.get("rank_param", payload)
    out: Dict[str, Dict[str, float]] = {}
    for group, table in rp.items():
        if isinstance(table, dict):
            out[group] = {str(k): float(v) for k, v in table.items()}
    return out

def load_sys_consts(sys_json_path: str | Path) -> Dict[str, float]:
    payload = json.loads(Path(sys_json_path).read_text(encoding="utf-8"))
    c = payload.get("constants", payload)
    # keep only what we use here
    keys = [
        "WEIGHT_PENALTY", "WEIGHT_PENALTY_PER",
        "WALK_MIN", "DASH_MIN",
        "WALK_MAX_HOVER", "WALK_MIN_HOVER", "DASH_MIN_HOVER",
    ]
    return {k: float(c[k]) for k in keys}


# -----------------------------
# Rank param load (constdata -> drawData-like)
# -----------------------------

def rank_param_load_part(part: Dict[str, Any], rank_param: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    """
    Fill param values based on the *field name* (armor/aim/walk/...)
    """
    p = copy.deepcopy(part)
    for field, val in list(p.items()):
        if isinstance(val, dict) and "rank" in val and "param" not in val:
            rk = val.get("rank")
            table = rank_param.get(field)
            if isinstance(rk, str) and isinstance(table, dict) and rk in table:
                val["param"] = float(table[rk])
    return p


# -----------------------------
# Brand (set) bonus
# -----------------------------

def _get_param(obj: Dict[str, Any], field: str) -> float:
    v = obj.get(field)
    if isinstance(v, dict):
        return float(v.get("param", 0.0))
    return float(v or 0.0)

def _set_param(obj: Dict[str, Any], field: str, value: float) -> None:
    if field not in obj or not isinstance(obj[field], dict):
        obj[field] = {}
    obj[field]["param"] = float(value)

def apply_set_bonus(
    *,
    draw: Dict[str, Dict[str, Any]],
    bland_data: Dict[str, Any],
    bonus_rate_percent: float = 100.0,
) -> Dict[str, Any]:
    """
    Port of setDrawdataSetBonus() + addBonusBr* helpers (subset relevant to BR parts).

    draw: {"head": {...}, "body": {...}, "arm": {...}, "leg": {...}}
    Each part dict must include 'blandId' to check set condition.

    Returns info dict: {"applied": bool, "blandId": str|None, "info": str}
    """
    head_id = draw["head"].get("blandId")
    body_id = draw["body"].get("blandId")
    arm_id  = draw["arm"].get("blandId")
    leg_id  = draw["leg"].get("blandId")

    if not (head_id and head_id == body_id == arm_id == leg_id):
        return {"applied": False, "blandId": None, "info": "no bonus"}

    bland_id = str(head_id)
    b = bland_data.get(bland_id)
    if not isinstance(b, dict):
        return {"applied": False, "blandId": bland_id, "info": "brand not found"}

    bonus_obj = b.get("setBonusObj") or []
    info = b.get("setBonusInfo", "")

    def bonus_value(v: float) -> float:
        return float(v) * float(bonus_rate_percent) / 100.0

    for row in bonus_obj:
        if not isinstance(row, dict):
            continue
        param_name = row.get("setBonusParamName")
        val = bonus_value(float(row.get("setBonusValue", 0.0)))

        # Follow simdata.js switch mapping.
        # Note: some bonuses are "time reduction" where JS subtracts.
        if param_name == "armor":
            # JS: bonus/100 then subtract from each part armor.param (damage coefficient)
            dv = val / 100.0
            for cat in ("head", "body", "arm", "leg"):
                _set_param(draw[cat], "armor", _get_param(draw[cat], "armor") - dv)

        elif param_name == "aim":
            _set_param(draw["head"], "aim", _get_param(draw["head"], "aim") + val)
        elif param_name == "sakuteki":
            _set_param(draw["head"], "sakuteki", _get_param(draw["head"], "sakuteki") + val)
        elif param_name == "lockOn":
            _set_param(draw["head"], "lockOn", _get_param(draw["head"], "lockOn") + val)

        elif param_name == "ndefChargeRate":
            # time coefficient reduction
            _set_param(draw["head"], "ndefChargeRate", _get_param(draw["head"], "ndefChargeRate") - val)

        elif param_name == "booster":
            _set_param(draw["body"], "booster", _get_param(draw["body"], "booster") + val)
        elif param_name == "spSupply":
            _set_param(draw["body"], "spSupply", _get_param(draw["body"], "spSupply") + val)
        elif param_name == "ndefCapacity":
            _set_param(draw["body"], "ndefCapacity", _get_param(draw["body"], "ndefCapacity") + val)

        elif param_name == "areaTransport":
            _set_param(draw["body"], "areaTransport", _get_param(draw["body"], "areaTransport") - val)

        elif param_name == "recoilCtrl":
            _set_param(draw["arm"], "recoilCtrl", _get_param(draw["arm"], "recoilCtrl") + val)
        elif param_name == "reload":
            # JS subtracts to shorten time
            _set_param(draw["arm"], "reload", _get_param(draw["arm"], "reload") - val)
        elif param_name == "weaponChange":
            _set_param(draw["arm"], "weaponChange", _get_param(draw["arm"], "weaponChange") + val)

        elif param_name == "walk":
            _set_param(draw["leg"], "walk", _get_param(draw["leg"], "walk") + val)
        elif param_name == "dash":
            _set_param(draw["leg"], "dash", _get_param(draw["leg"], "dash") + val)
        elif param_name == "velocityTimeRate":
            _set_param(draw["leg"], "velocityTimeRate", _get_param(draw["leg"], "velocityTimeRate") - val)
        elif param_name == "velocityTimeSec":
            # JS adds to 'velocity' (sec)
            _set_param(draw["leg"], "velocity", _get_param(draw["leg"], "velocity") + val)

        elif param_name == "loadCapacity":
            # JS adds to leg.loadCapacity and leg.loadCapacityLeftover
            _set_param(draw["leg"], "loadCapacity", _get_param(draw["leg"], "loadCapacity") + val)
            _set_param(draw["leg"], "loadCapacityLeftover", _get_param(draw["leg"], "loadCapacityLeftover") + val)

        # other params exist; extend as needed.

    return {"applied": True, "blandId": bland_id, "info": info}


# -----------------------------
# Base aggregation (raw sum)
# -----------------------------

def calc_parts_base(
    *,
    draw: Dict[str, Dict[str, Any]],
    sysc: Dict[str, float],
    rank_param: Dict[str, Dict[str, float]],
    inside_load_capacity: float = 0.0,
    weight_penalty_per: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Port of setDrawdataBaseParam() subset:
      - armor average
      - weight sum + movement (walk/dash) with overweight penalty + clamp + rank recalculation
    """
    weight_penalty_per = float(weight_penalty_per) if weight_penalty_per is not None else float(sysc["WEIGHT_PENALTY_PER"])

    # armor average of 4 parts
    armor_avg = (
        float(_get_param(draw["head"], "armor"))
        + float(_get_param(draw["body"], "armor"))
        + float(_get_param(draw["arm"], "armor"))
        + float(_get_param(draw["leg"], "armor"))
    ) / 4.0

    # weight sum
    total_weight = (
        float(_get_param(draw["head"], "weight"))
        + float(_get_param(draw["body"], "weight"))
        + float(_get_param(draw["arm"], "weight"))
        + float(_get_param(draw["leg"], "weight"))
    )

    # load capacity = leg + inside
    leg_load = float(_get_param(draw["leg"], "loadCapacity"))
    load_capa = leg_load + float(inside_load_capacity)

    walk = float(_get_param(draw["leg"], "walk"))
    dash = float(_get_param(draw["leg"], "dash"))

    # leg type: hover if walk has type 'hover'
    is_hover = False
    if isinstance(draw["leg"].get("walk"), dict):
        is_hover = (draw["leg"]["walk"].get("type") == "hover")

    left_over = load_capa - total_weight
    penalty = 0.0
    if left_over < 0:
        penalty = (left_over / float(sysc["WEIGHT_PENALTY"])) * (weight_penalty_per / 100.0)

    walk_adj = walk * (1.0 + (penalty / 100.0))
    dash_adj = dash * (1.0 + (penalty / 100.0))

    if is_hover:
        walk_adj = max(float(sysc["WALK_MIN_HOVER"]), min(float(sysc["WALK_MAX_HOVER"]), walk_adj))
        dash_adj = max(float(sysc["DASH_MIN_HOVER"]), dash_adj)
        walk_rank_table = rank_param.get("walk_hover", {})
        dash_rank_table = rank_param.get("dash_hover", rank_param.get("dash", {}))
    else:
        walk_adj = max(float(sysc["WALK_MIN"]), walk_adj)
        dash_adj = max(float(sysc["DASH_MIN"]), dash_adj)
        walk_rank_table = rank_param.get("walk", {})
        dash_rank_table = rank_param.get("dash", {})

    return {
        "armor_avg": {"param": armor_avg, "rank": _get_rank_closest(rank_param.get("armor", {}), armor_avg) if rank_param.get("armor") else None},
        "total_weight": total_weight,
        "load_capacity": load_capa,
        "load_capacity_leftover": left_over,
        "weight_penalty": penalty,
        "walk": {"param": walk_adj, "rank": _get_rank_closest(walk_rank_table, walk_adj) if walk_rank_table else None},
        "dash": {"param": dash_adj, "rank": _get_rank_closest(dash_rank_table, dash_adj) if dash_rank_table else None},
    }


# -----------------------------
# Convenience: build draw parts from constdata
# -----------------------------

def build_draw_parts_from_const(
    *,
    const_parts: Dict[str, Dict[str, Any]],
    rank_param: Dict[str, Dict[str, float]],
    head_key: str,
    body_key: str,
    arm_key: str,
    leg_key: str,
) -> Dict[str, Dict[str, Any]]:
    head = rank_param_load_part(const_parts["head"][head_key], rank_param)
    body = rank_param_load_part(const_parts["body"][body_key], rank_param)
    arm  = rank_param_load_part(const_parts["arm"][arm_key], rank_param)
    leg  = rank_param_load_part(const_parts["leg"][leg_key], rank_param)

    # add loadCapacityLeftover for leg if missing (like DataCommon.dataConv does)
    if "loadCapacity" in leg and isinstance(leg["loadCapacity"], dict):
        lc = float(leg["loadCapacity"].get("param", 0.0))
        w  = float(head.get("weight", {}).get("param", 0.0)) + float(body.get("weight", {}).get("param", 0.0)) + float(arm.get("weight", {}).get("param", 0.0)) + float(leg.get("weight", {}).get("param", 0.0))
        leg.setdefault("loadCapacityLeftover", {})["param"] = lc - w

    return {"head": head, "body": body, "arm": arm, "leg": leg}


if __name__ == "__main__":
    # Example run (edit keys)
    const_parts = load_const_parts("constdata.js")
    bland = load_bland_data("constdata.js")
    rp = load_rank_param("rank_param.json")
    sysc = load_sys_consts("sys_calc_constants.json")

    draw = build_draw_parts_from_const(const_parts=const_parts, rank_param=rp, head_key="a", body_key="a", arm_key="a", leg_key="a")
    info = apply_set_bonus(draw=draw, bland_data=bland, bonus_rate_percent=100)
    base = calc_parts_base(draw=draw, sysc=sysc, rank_param=rp)
    print(json.dumps({"set_bonus": info, "base": base}, ensure_ascii=False, indent=2))
