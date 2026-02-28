"""
bb_brbonus_calcparam_limit.py のユニットテスト（37件）
"""
import pytest
from bb_brbonus_calcparam_limit import (
    _to_float,
    _get_param,
    _set_param,
    _ensure_inside,
    _normalize_chip_key,
    add_bonus_br_armor,
    add_bonus_br_aim,
    add_bonus_br_sakuteki,
    add_bonus_br_lockon,
    add_bonus_br_ndef_charge_rate,
    add_bonus_br_booster,
    add_bonus_br_area_transport,
    add_bonus_br_recoil_ctrl,
    add_bonus_br_reload_rate,
    add_bonus_br_weapon_change,
    add_bonus_br_walk,
    add_bonus_br_dash,
    add_bonus_br_load_capacity,
    apply_br_bonus_chips,
    calc_param_ndef_charge,
    calc_param_step,
    calc_param_velocity,
    calc_draw_param,
    apply_parts_param_limits,
)


# ------------------------------------------------------------------ #
#  ヘルパー：ミニマム draw dict                                        #
# ------------------------------------------------------------------ #

def _draw(head=None, body=None, arm=None, leg=None):
    def _p(**kw):
        return {k: {"param": v} for k, v in kw.items()}
    return {
        "head": head or _p(armor=1.0, aim=10.0, sakuteki=200.0, lockOn=100.0, ndefChargeRate=100.0),
        "body": body or _p(armor=1.0, booster=100.0, spSupply=1.0, ndefCapacity=500.0, areaTransport=3.0),
        "arm":  arm  or _p(armor=1.0, recoilCtrl=50.0, reloadRate=1.2, weaponChange=0.5),
        "leg":  leg  or _p(armor=1.0, walk=7.0, dash=17.0, loadCapacity=3200.0, loadCapacityLeftover=0.0),
    }


# ------------------------------------------------------------------ #
#  _to_float                                                           #
# ------------------------------------------------------------------ #

class TestToFloat:
    def test_none_returns_zero(self):
        assert _to_float(None) == 0.0

    def test_int(self):
        assert _to_float(5) == 5.0

    def test_float_passthrough(self):
        assert _to_float(3.14) == pytest.approx(3.14)

    def test_string_with_comma(self):
        assert _to_float("1,200") == pytest.approx(1200.0)

    def test_empty_string(self):
        assert _to_float("") == 0.0

    def test_invalid_string(self):
        assert _to_float("abc") == 0.0


# ------------------------------------------------------------------ #
#  _get_param / _set_param                                            #
# ------------------------------------------------------------------ #

class TestGetSetParam:
    def test_get_from_dict(self):
        assert _get_param({"x": {"param": 5.0}}, "x") == pytest.approx(5.0)

    def test_get_missing_returns_zero(self):
        assert _get_param({}, "x") == 0.0

    def test_get_scalar(self):
        assert _get_param({"x": 7}, "x") == pytest.approx(7.0)

    def test_set_creates_entry(self):
        obj = {}
        _set_param(obj, "aim", 20.0)
        assert obj["aim"]["param"] == pytest.approx(20.0)

    def test_set_updates_existing(self):
        obj = {"aim": {"param": 10.0}}
        _set_param(obj, "aim", 15.0)
        assert obj["aim"]["param"] == pytest.approx(15.0)


# ------------------------------------------------------------------ #
#  _ensure_inside                                                      #
# ------------------------------------------------------------------ #

class TestEnsureInside:
    def test_creates_br_inside_if_missing(self):
        d = {"head": {}}
        inside = _ensure_inside(d)
        assert "br_inside" in d
        assert inside is d["br_inside"]

    def test_returns_existing_br_inside(self):
        existing = {"foo": "bar"}
        d = {"br_inside": existing}
        inside = _ensure_inside(d)
        assert inside is existing


# ------------------------------------------------------------------ #
#  add_bonus_br_armor                                                  #
# ------------------------------------------------------------------ #

class TestAddBonusBrArmor:
    def test_all_four_parts_reduced(self):
        d = _draw()
        add_bonus_br_armor(d, 60)
        # bonus=60 → bonus_val=0.60, each armor 1.0 - 0.60 = 0.40
        for cat in ("head", "body", "arm", "leg"):
            assert d[cat]["armor"]["param"] == pytest.approx(0.40)

    def test_from_zero_goes_negative(self):
        d = _draw(
            head={"armor": {"param": 0.0}},
            body={"armor": {"param": 0.0}},
            arm={"armor": {"param": 0.0}},
            leg={"armor": {"param": 0.0}},
        )
        add_bonus_br_armor(d, 30)
        for cat in ("head", "body", "arm", "leg"):
            assert d[cat]["armor"]["param"] == pytest.approx(-0.30)


# ------------------------------------------------------------------ #
#  サイド別チップ関数                                                   #
# ------------------------------------------------------------------ #

class TestSideChipFunctions:
    def test_aim_added_to_head(self):
        d = _draw()
        add_bonus_br_aim(d, 5)
        assert d["head"]["aim"]["param"] == pytest.approx(15.0)

    def test_sakuteki_added_to_head(self):
        d = _draw()
        add_bonus_br_sakuteki(d, 20)
        assert d["head"]["sakuteki"]["param"] == pytest.approx(220.0)

    def test_lockon_added_to_head(self):
        d = _draw()
        add_bonus_br_lockon(d, 10)
        assert d["head"]["lockOn"]["param"] == pytest.approx(110.0)

    def test_ndef_charge_rate_subtracted_from_head(self):
        d = _draw()
        add_bonus_br_ndef_charge_rate(d, 10)
        assert d["head"]["ndefChargeRate"]["param"] == pytest.approx(90.0)

    def test_booster_added_to_body(self):
        d = _draw()
        add_bonus_br_booster(d, 10)
        assert d["body"]["booster"]["param"] == pytest.approx(110.0)

    def test_area_transport_subtracted_from_body(self):
        d = _draw()
        add_bonus_br_area_transport(d, 0.5)
        assert d["body"]["areaTransport"]["param"] == pytest.approx(2.5)

    def test_recoil_ctrl_added_to_arm(self):
        d = _draw()
        add_bonus_br_recoil_ctrl(d, 5)
        assert d["arm"]["recoilCtrl"]["param"] == pytest.approx(55.0)

    def test_reload_rate_subtracted_from_arm(self):
        d = _draw()
        add_bonus_br_reload_rate(d, 0.1)
        assert d["arm"]["reloadRate"]["param"] == pytest.approx(1.1)

    def test_weapon_change_added_to_arm(self):
        d = _draw()
        add_bonus_br_weapon_change(d, 0.1)
        assert d["arm"]["weaponChange"]["param"] == pytest.approx(0.6)

    def test_walk_added_to_leg(self):
        d = _draw()
        add_bonus_br_walk(d, 0.45)
        assert d["leg"]["walk"]["param"] == pytest.approx(7.45)

    def test_dash_added_to_leg(self):
        d = _draw()
        add_bonus_br_dash(d, 1.0)
        assert d["leg"]["dash"]["param"] == pytest.approx(18.0)

    def test_load_capacity_updates_both(self):
        d = _draw()
        add_bonus_br_load_capacity(d, 150)
        assert d["leg"]["loadCapacity"]["param"] == pytest.approx(3350.0)
        assert d["leg"]["loadCapacityLeftover"]["param"] == pytest.approx(150.0)


# ------------------------------------------------------------------ #
#  _normalize_chip_key                                                 #
# ------------------------------------------------------------------ #

class TestNormalizeChipKey:
    def test_already_normalized(self):
        assert _normalize_chip_key("BASE_ARMOR_I") == "BASE_ARMOR_I"

    def test_kebab_to_upper_snake(self):
        key = _normalize_chip_key("base-armor-i")
        assert "_" in key
        assert key == key.upper()

    def test_whitespace_stripped(self):
        result = _normalize_chip_key("  BASE_ARMOR_I  ")
        assert result == "BASE_ARMOR_I"


# ------------------------------------------------------------------ #
#  apply_br_bonus_chips                                                #
# ------------------------------------------------------------------ #

class TestApplyBrBonusChips:
    def test_known_chip_applied(self):
        d = _draw()
        chips = {"BASE_ARMOR_I": {"chipBonusValue": 60}}
        apply_br_bonus_chips(draw=d, chip_reinforcement_br=chips)
        for cat in ("head", "body", "arm", "leg"):
            assert d[cat]["armor"]["param"] == pytest.approx(0.40)

    def test_unknown_chip_does_nothing(self):
        d = _draw()
        chips = {"UNKNOWN_CHIP_XYZ": {"chipBonusValue": 999}}
        # 例外なく処理を終え、draw は変化しない
        apply_br_bonus_chips(draw=d, chip_reinforcement_br=chips)
        assert d["head"]["aim"]["param"] == pytest.approx(10.0)

    def test_empty_chips_does_nothing(self):
        d = _draw()
        apply_br_bonus_chips(draw=d, chip_reinforcement_br={})
        assert d["leg"]["walk"]["param"] == pytest.approx(7.0)

    def test_nested_param_chip_bonus(self):
        d = _draw()
        chips = {"WALK_I": {"chipBonusValue": {"param": 0.5}}}
        apply_br_bonus_chips(draw=d, chip_reinforcement_br=chips)
        assert d["leg"]["walk"]["param"] == pytest.approx(7.5)


# ------------------------------------------------------------------ #
#  calc_param_ndef_charge                                              #
# ------------------------------------------------------------------ #

class TestCalcParamNdefCharge:
    def test_no_ndef_charge_returns_none(self):
        assert calc_param_ndef_charge({}) is None

    def test_without_rate_uses_default_100(self):
        src = {"ndefCharge": {"param": 6.0, "rank": "C"}}
        result = calc_param_ndef_charge(src)
        # rate=100 → 6.0 * (100/100) = 6.0
        assert result["param"] == pytest.approx(6.0)

    def test_with_rate_applies_factor(self):
        src = {
            "ndefCharge": {"param": 6.0, "rank": "C"},
            "ndefChargeRate": {"param": 80},
        }
        result = calc_param_ndef_charge(src)
        # 6.0 * (80/100) = 4.8
        assert result["param"] == pytest.approx(4.8)

    def test_preserves_rank(self):
        src = {"ndefCharge": {"param": 6.0, "rank": "B"}}
        result = calc_param_ndef_charge(src)
        assert result["rank"] == "B"


# ------------------------------------------------------------------ #
#  calc_param_step                                                     #
# ------------------------------------------------------------------ #

class TestCalcParamStep:
    def test_no_booster_returns_none(self):
        assert calc_param_step({}) is None

    def test_step_boost_cost_zero_uses_default(self):
        # stepBoostCost が 0 のとき: int(0) は falsy なので条件分岐に入らず
        # step_boost_default（=12.0）がそのまま使われる
        src = {"booster": {"param": 120}, "stepBoostCost": {"param": 0}}
        result = calc_param_step(src, step_boost_default=12.0)
        assert result is not None
        assert result["param"] == 10  # 120 / 12 = 10

    def test_exact_division(self):
        src = {"booster": {"param": 120}}
        result = calc_param_step(src, step_boost_default=12.0)
        assert result["param"] == 10  # 120/12 = 10

    def test_ceil_on_remainder(self):
        src = {"booster": {"param": 125}}
        result = calc_param_step(src, step_boost_default=12.0)
        # 125/12 = 10.41... → 11
        assert result["param"] == 11


# ------------------------------------------------------------------ #
#  calc_param_velocity                                                 #
# ------------------------------------------------------------------ #

class TestCalcParamVelocity:
    def test_no_velocity_returns_none(self):
        assert calc_param_velocity({}) is None

    def test_without_rate_uses_100(self):
        src = {"velocity": {"param": 1.8}}
        result = calc_param_velocity(src)
        assert result["param"] == pytest.approx(1.8)

    def test_with_rate(self):
        src = {"velocity": {"param": 2.0}, "velocityTimeRate": {"param": 90}}
        result = calc_param_velocity(src)
        # 2.0 * (90/100) = 1.8
        assert result["param"] == pytest.approx(1.8)

    def test_preserves_rank(self):
        src = {"velocity": {"param": 2.0, "rank": "A"}}
        result = calc_param_velocity(src)
        assert result["rank"] == "A"


# ------------------------------------------------------------------ #
#  calc_draw_param                                                     #
# ------------------------------------------------------------------ #

class TestCalcDrawParam:
    def test_head_updates_ndef_charge(self):
        src = {"ndefCharge": {"param": 6.0, "rank": "C"}, "ndefChargeRate": {"param": 80}}
        calc_draw_param(src, "head")
        assert src["ndefCharge"]["param"] == pytest.approx(4.8)

    def test_body_updates_step(self):
        src = {"booster": {"param": 120}}
        calc_draw_param(src, "body", sysdata_step_boost=12.0)
        assert src["step"]["param"] == 10

    def test_leg_updates_velocity(self):
        src = {"velocity": {"param": 2.0}, "velocityTimeRate": {"param": 90}}
        calc_draw_param(src, "leg")
        assert src["velocity"]["param"] == pytest.approx(1.8)

    def test_arm_does_nothing(self):
        src = {"reloadRate": {"param": 1.2}}
        calc_draw_param(src, "arm")
        assert "step" not in src
        assert "ndefCharge" not in src

    def test_case_insensitive_parts_type(self):
        src = {"booster": {"param": 120}}
        calc_draw_param(src, "BODY", sysdata_step_boost=12.0)
        assert "step" in src


# ------------------------------------------------------------------ #
#  apply_parts_param_limits                                            #
# ------------------------------------------------------------------ #

class TestApplyPartsParamLimits:
    def test_area_transport_below_min_clamped(self):
        d = _draw()
        d["body"]["areaTransport"]["param"] = 1.5
        apply_parts_param_limits(d, {"areaTransport": 2.0})
        assert d["body"]["areaTransport"]["param"] == pytest.approx(2.0)

    def test_area_transport_above_min_unchanged(self):
        d = _draw()
        d["body"]["areaTransport"]["param"] = 3.5
        apply_parts_param_limits(d, {"areaTransport": 2.0})
        assert d["body"]["areaTransport"]["param"] == pytest.approx(3.5)

    def test_no_limit_key_does_nothing(self):
        d = _draw()
        d["body"]["areaTransport"]["param"] = 1.0
        apply_parts_param_limits(d, {})
        assert d["body"]["areaTransport"]["param"] == pytest.approx(1.0)

    def test_body_missing_area_transport_no_error(self):
        d = _draw(body={"booster": {"param": 100.0}})
        apply_parts_param_limits(d, {"areaTransport": 2.0})
        # body に areaTransport がなくてもエラーにならない
