"""
bb_weapon_calc.py のユニットテスト（30件）
"""
import pytest
from bb_weapon_calc import (
    _parse_int,
    get_damage_num,
    calc_magazine_damage,
    calc_mag_total_damage,
    calc_magazine_sec,
    calc_damage_per_sec,
    apply_weapon_derived_params,
)


# ------------------------------------------------------------------ #
#  _parse_int                                                          #
# ------------------------------------------------------------------ #

class TestParseInt:
    def test_none_returns_zero(self):
        assert _parse_int(None) == 0

    def test_bool_true_returns_one(self):
        assert _parse_int(True) == 1

    def test_bool_false_returns_zero(self):
        assert _parse_int(False) == 0

    def test_int_passthrough(self):
        assert _parse_int(42) == 42

    def test_float_truncated(self):
        assert _parse_int(3.9) == 3

    def test_string_with_comma(self):
        assert _parse_int("1,200") == 1200

    def test_empty_string_returns_zero(self):
        assert _parse_int("") == 0

    def test_invalid_string_returns_zero(self):
        assert _parse_int("abc") == 0

    def test_string_float(self):
        assert _parse_int("25.7") == 25


# ------------------------------------------------------------------ #
#  get_damage_num                                                      #
# ------------------------------------------------------------------ #

class TestGetDamageNum:
    def test_scalar(self):
        assert get_damage_num(1200) == [1200]

    def test_list_of_values(self):
        assert get_damage_num([500, 800]) == [500, 800]

    def test_max_damage_model(self):
        assert get_damage_num({"maxDamage": 2000, "minDamage": 800}) == [2000]

    def test_charge_damage_last_entry(self):
        obj = {"chargeDamage": [300, 600, 1200]}
        assert get_damage_num(obj) == [1200]

    def test_charge_damage_empty_list(self):
        obj = {"chargeDamage": []}
        assert get_damage_num(obj) == [0]

    def test_pellet_model(self):
        obj = {"damageParam": 240, "pellet": 20}
        assert get_damage_num(obj) == [4800]

    def test_pellet_model_missing_pellet(self):
        # pellet が None → _parse_int(None) = 0
        obj = {"damageParam": 240}
        assert get_damage_num(obj) == [0]

    def test_none_scalar(self):
        assert get_damage_num(None) == [0]


# ------------------------------------------------------------------ #
#  calc_magazine_damage                                                #
# ------------------------------------------------------------------ #

class TestCalcMagazineDamage:
    def test_normal(self):
        src = {"damage": 1200, "clip": 10}
        assert calc_magazine_damage(src) == [12000]

    def test_missing_damage_key(self):
        assert calc_magazine_damage({"clip": 10}) is None

    def test_missing_clip_key(self):
        assert calc_magazine_damage({"damage": 1200}) is None

    def test_pellet_model(self):
        src = {"damage": {"damageParam": 200, "pellet": 5}, "clip": 3}
        assert calc_magazine_damage(src) == [3000]  # 200*5=1000, *3=3000

    def test_empty_dict(self):
        assert calc_magazine_damage({}) is None


# ------------------------------------------------------------------ #
#  calc_mag_total_damage                                               #
# ------------------------------------------------------------------ #

class TestCalcMagTotalDamage:
    def test_normal(self):
        src = {"damage": 1200, "clip": 10, "ammo": 4}
        assert calc_mag_total_damage(src) == [48000]

    def test_ammo_zero_treated_as_one(self):
        src = {"damage": 1200, "clip": 10, "ammo": 0}
        assert calc_mag_total_damage(src) == [12000]

    def test_ammo_missing_treated_as_zero_then_one(self):
        src = {"damage": 1200, "clip": 10}
        assert calc_mag_total_damage(src) == [12000]

    def test_missing_damage(self):
        assert calc_mag_total_damage({"clip": 10, "ammo": 4}) is None


# ------------------------------------------------------------------ #
#  calc_magazine_sec                                                   #
# ------------------------------------------------------------------ #

class TestCalcMagazineSec:
    def test_scalar_rate(self):
        src = {"clip": 30, "rate": 300}
        result = calc_magazine_sec(src)
        assert abs(result - 6.0) < 1e-9  # 30/300*60 = 6.0

    def test_list_rate(self):
        src = {"clip": 10, "rate": [300, 600]}
        result = calc_magazine_sec(src)
        assert isinstance(result, list)
        assert len(result) == 2
        assert abs(result[0] - 2.0) < 1e-9   # 10/300*60 = 2.0
        assert abs(result[1] - 1.0) < 1e-9   # 10/600*60 = 1.0

    def test_rate_zero_returns_none(self):
        src = {"clip": 10, "rate": 0}
        assert calc_magazine_sec(src) is None

    def test_missing_rate_key(self):
        assert calc_magazine_sec({"clip": 10}) is None

    def test_missing_clip_key(self):
        assert calc_magazine_sec({"rate": 300}) is None

    def test_list_rate_with_zero_entry(self):
        src = {"clip": 10, "rate": [300, 0]}
        result = calc_magazine_sec(src)
        assert isinstance(result, list)
        assert abs(result[0] - 2.0) < 1e-9
        assert result[1] == 0.0  # rate=0 → 0.0


# ------------------------------------------------------------------ #
#  calc_damage_per_sec                                                 #
# ------------------------------------------------------------------ #

class TestCalcDamagePerSec:
    def test_scalar_rate(self):
        src = {"damage": 1200, "rate": 300}
        result = calc_damage_per_sec(src)
        assert result == [6000]  # int(1200 * 300 / 60) = 6000

    def test_list_rate(self):
        src = {"damage": 600, "rate": [300, 600]}
        result = calc_damage_per_sec(src)
        assert result == [3000, 6000]

    def test_rate_zero_returns_none(self):
        src = {"damage": 1200, "rate": 0}
        assert calc_damage_per_sec(src) is None

    def test_missing_damage_key(self):
        assert calc_damage_per_sec({"rate": 300}) is None

    def test_missing_rate_key(self):
        assert calc_damage_per_sec({"damage": 1200}) is None

    def test_list_damage_with_scalar_rate(self):
        src = {"damage": [600, 900], "rate": 300}
        result = calc_damage_per_sec(src)
        assert result == [3000, 4500]


# ------------------------------------------------------------------ #
#  apply_weapon_derived_params                                         #
# ------------------------------------------------------------------ #

class TestApplyWeaponDerivedParams:
    def test_adds_all_four_fields(self):
        w = {"damage": 1200, "clip": 10, "ammo": 4, "rate": 300}
        result = apply_weapon_derived_params(w)
        assert "magazineDamage" in result
        assert "magTotalDamage" in result
        assert "magazineSec" in result
        assert "damagePerSec" in result

    def test_correct_values(self):
        w = {"damage": 1000, "clip": 5, "ammo": 3, "rate": 300}
        apply_weapon_derived_params(w)
        assert w["magazineDamage"] == [5000]
        assert w["magTotalDamage"] == [15000]
        assert abs(w["magazineSec"] - 1.0) < 1e-9
        assert w["damagePerSec"] == [5000]

    def test_missing_fields_not_added(self):
        w = {"damage": 1000}
        apply_weapon_derived_params(w)
        # clip/rate なし → magazineDamage/magazineSec/damagePerSec は追加されない
        assert "magazineDamage" not in w
        assert "magazineSec" not in w
        assert "damagePerSec" not in w

    def test_pellet_with_list_rate(self):
        w = {"damage": {"damageParam": 240, "pellet": 20}, "clip": 1, "ammo": 0, "rate": [60, 120]}
        apply_weapon_derived_params(w)
        # damage = 240*20 = 4800, clip=1 → magazineDamage=[4800]
        assert w["magazineDamage"] == [4800]
        # ammo=0 → treat as 1 → magTotalDamage=[4800]
        assert w["magTotalDamage"] == [4800]
        # magazineSec は list
        assert isinstance(w["magazineSec"], list)
        assert len(w["magazineSec"]) == 2
        # damagePerSec: rate=[60,120], damage=[4800] → [4800, 9600]
        assert w["damagePerSec"] == [4800, 9600]

    def test_returns_same_dict(self):
        w = {"damage": 500, "clip": 10, "ammo": 2, "rate": 100}
        result = apply_weapon_derived_params(w)
        assert result is w
