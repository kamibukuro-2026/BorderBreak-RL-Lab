\
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json


@dataclass(frozen=True)
class LoadoutKeys:
    """Part keys are the original per-category IDs (e.g., 'a', 'T', ...)."""
    head: str
    body: str
    arm: str
    leg: str


@dataclass(frozen=True)
class WeaponRef:
    """Weapon selection by dataset key + item key (e.g., dataset='WEAPON_AS_MAIN', key='a')."""
    dataset: str
    key: str


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class Catalog:
    """
    Loads and indexes:
      - parts_normalized.json (flat list)
      - weapons_all.json (nested by dataset)
      - sys_calc_constants.json, rank_param.json, bland_data.json, parts_param_config.json

    Data files are expected under bb_assemble/data/.
    """

    def __init__(self, data_dir: str | Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
        self._parts: Dict[str, Any] = {}
        self._weapons: Dict[str, Dict[str, Any]] = {}
        self._rank_param: Dict[str, Any] = {}
        self._sys: Dict[str, Any] = {}
        self._bland: Dict[str, Any] = {}
        self._param_limits: Dict[str, Any] = {}

        self._parts_by_cat_key: Dict[str, Dict[str, Any]] = {"head": {}, "body": {}, "arm": {}, "leg": {}}
        self._parts_by_name: Dict[str, List[str]] = {"head": {}, "body": {}, "arm": {}, "leg": {}}
        self._weapons_by_dataset_key: Dict[str, Dict[str, Any]] = {}
        self._weapons_by_name: Dict[str, List[Tuple[str, str]]] = {}

        self._load_all()

    def _load_all(self) -> None:
        parts_path = self.data_dir / "parts_normalized.json"
        weapons_path = self.data_dir / "weapons_all.json"
        rank_path = self.data_dir / "rank_param.json"
        sys_path = self.data_dir / "sys_calc_constants.json"
        bland_path = self.data_dir / "bland_data.json"
        limits_path = self.data_dir / "parts_param_config.json"

        if parts_path.exists():
            payload = _read_json(parts_path)
            parts_list = payload["parts"] if isinstance(payload, dict) and "parts" in payload else payload
            for p in parts_list:
                cat = p.get("category")
                src_key = p.get("source_key")
                if cat in self._parts_by_cat_key and isinstance(src_key, str):
                    self._parts_by_cat_key[cat][src_key] = p
                    nm = (p.get("name") or "").strip()
                    if nm:
                        self._parts_by_name[cat].setdefault(nm, []).append(src_key)

        if weapons_path.exists():
            payload = _read_json(weapons_path)
            weapons = payload.get("weapons", payload)
            if isinstance(weapons, dict):
                self._weapons_by_dataset_key = {}
                for dataset, items in weapons.items():
                    if isinstance(items, dict):
                        self._weapons_by_dataset_key[dataset] = items
                        for key, w in items.items():
                            nm = (w.get("name") or "").strip() if isinstance(w, dict) else ""
                            if nm:
                                self._weapons_by_name.setdefault(nm, []).append((dataset, key))

        if rank_path.exists():
            self._rank_param = _read_json(rank_path).get("rank_param", {})
        if sys_path.exists():
            self._sys = _read_json(sys_path).get("constants", {})
        if bland_path.exists():
            self._bland = _read_json(bland_path).get("bland", {})
        if limits_path.exists():
            self._param_limits = _read_json(limits_path).get("param_limits", {})

    # ---------- parts lookup ----------
    def list_parts(self, category: str) -> List[Tuple[str, str]]:
        """Return list of (key, name) for category in head/body/arm/leg."""
        cat = category.lower()
        out = []
        for k, p in self._parts_by_cat_key.get(cat, {}).items():
            out.append((k, p.get("name", "")))
        return out

    def get_part(self, category: str, key: str) -> Dict[str, Any]:
        cat = category.lower()
        try:
            return self._parts_by_cat_key[cat][key]
        except KeyError:
            raise KeyError(f"Part not found: category={category} key={key}")

    def find_part_keys_by_name(self, category: str, name: str) -> List[str]:
        cat = category.lower()
        return list(self._parts_by_name.get(cat, {}).get(name, []))

    # ---------- weapons lookup ----------
    def list_weapon_datasets(self) -> List[str]:
        return sorted(self._weapons_by_dataset_key.keys())

    def list_weapons(self, dataset: str) -> List[Tuple[str, str]]:
        """Return list of (key, name) for a dataset like WEAPON_AS_MAIN."""
        items = self._weapons_by_dataset_key.get(dataset, {})
        out = []
        for k, w in items.items():
            nm = w.get("name", "") if isinstance(w, dict) else ""
            out.append((k, nm))
        return out

    def get_weapon(self, dataset: str, key: str) -> Dict[str, Any]:
        try:
            return self._weapons_by_dataset_key[dataset][key]
        except KeyError:
            raise KeyError(f"Weapon not found: dataset={dataset} key={key}")

    def find_weapons_by_name(self, name: str) -> List[WeaponRef]:
        return [WeaponRef(d, k) for d, k in self._weapons_by_name.get(name, [])]

    # ---------- system tables ----------
    @property
    def rank_param(self) -> Dict[str, Any]:
        return self._rank_param

    @property
    def sys_consts(self) -> Dict[str, Any]:
        return self._sys

    @property
    def bland(self) -> Dict[str, Any]:
        return self._bland

    @property
    def param_limits(self) -> Dict[str, Any]:
        return self._param_limits
