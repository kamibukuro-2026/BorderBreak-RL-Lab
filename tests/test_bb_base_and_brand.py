"""
bb_base_and_brand.py のユニットテスト（26件）
JS ファイルを必要としない関数群に絞ってテストする。
"""
import pytest
from bb_base_and_brand import (
    _strip_js_comments,
    _extract_brace_block,
    _parse_js_object_literal,
    _get_param,
    _set_param,
    _get_rank_closest,
    rank_param_load_part,
    apply_set_bonus,
    calc_parts_base,
)


# ------------------------------------------------------------------ #
#  _strip_js_comments                                                  #
# ------------------------------------------------------------------ #

class TestStripJsComments:
    def test_line_comment_removed(self):
        src = "var x = 1; // this is a comment\nvar y = 2;"
        result = _strip_js_comments(src)
        assert "//" not in result
        assert "var x = 1;" in result
        assert "var y = 2;" in result

    def test_block_comment_removed(self):
        src = "var a = /* block comment */ 42;"
        result = _strip_js_comments(src)
        assert "block comment" not in result
        assert "42" in result

    def test_url_inside_string_preserved(self):
        # 文字列内の // はコメントとして除去されない
        src = 'var url = "http://example.com";'
        result = _strip_js_comments(src)
        assert "http://example.com" in result

    def test_empty_string(self):
        assert _strip_js_comments("") == ""


# ------------------------------------------------------------------ #
#  _extract_brace_block                                                #
# ------------------------------------------------------------------ #

class TestExtractBraceBlock:
    def test_simple_block(self):
        src = "{ 'key': 1 }"
        block, end = _extract_brace_block(src, 0)
        assert block == "{ 'key': 1 }"
        assert end == len(src)

    def test_nested_braces(self):
        src = "{ 'a': { 'b': 2 } }"
        block, end = _extract_brace_block(src, 0)
        assert block == src
        assert end == len(src)

    def test_no_matching_brace_raises(self):
        with pytest.raises(ValueError):
            _extract_brace_block("{ no close", 0)

    def test_offset_start(self):
        src = "prefix{ 'k': 9 }suffix"
        idx = src.index("{")
        block, _ = _extract_brace_block(src, idx)
        assert block == "{ 'k': 9 }"


# ------------------------------------------------------------------ #
#  _parse_js_object_literal                                            #
# ------------------------------------------------------------------ #

class TestParseJsObjectLiteral:
    def test_null_converted(self):
        result = _parse_js_object_literal("{'key': null}")
        assert result == {"key": None}

    def test_true_false_converted(self):
        result = _parse_js_object_literal("{'a': true, 'b': false}")
        assert result == {"a": True, "b": False}

    def test_trailing_comma_tolerated(self):
        result = _parse_js_object_literal("{'x': 1,}")
        assert result == {"x": 1}

    def test_nested_object(self):
        result = _parse_js_object_literal("{'outer': {'inner': 42}}")
        assert result == {"outer": {"inner": 42}}


# ------------------------------------------------------------------ #
#  _get_param / _set_param                                             #
# ------------------------------------------------------------------ #

class TestGetSetParam:
    def test_get_param_from_dict(self):
        obj = {"armor": {"param": 1.05}}
        assert _get_param(obj, "armor") == pytest.approx(1.05)

    def test_get_param_missing_returns_zero(self):
        assert _get_param({}, "armor") == pytest.approx(0.0)

    def test_get_param_scalar_value(self):
        obj = {"walk": 7.5}
        assert _get_param(obj, "walk") == pytest.approx(7.5)

    def test_set_param_creates_dict(self):
        obj = {}
        _set_param(obj, "aim", 10.0)
        assert obj["aim"] == {"param": 10.0}

    def test_set_param_updates_existing(self):
        obj = {"aim": {"param": 5.0, "rank": "B"}}
        _set_param(obj, "aim", 15.0)
        assert obj["aim"]["param"] == pytest.approx(15.0)
        # rank は保持される
        assert obj["aim"]["rank"] == "B"


# ------------------------------------------------------------------ #
#  _get_rank_closest                                                   #
# ------------------------------------------------------------------ #

class TestGetRankClosest:
    def test_exact_match(self):
        table = {"S": 0.63, "A": 0.78, "B": 0.90}
        assert _get_rank_closest(table, 0.78) == "A"

    def test_closest_rank(self):
        table = {"A": 0.78, "B": 0.90}
        # 0.80 は B(0.90 diff=0.10) より A(0.78 diff=0.02) に近い
        assert _get_rank_closest(table, 0.80) == "A"

    def test_empty_table_returns_empty_string(self):
        assert _get_rank_closest({}, 1.0) == ""


# ------------------------------------------------------------------ #
#  rank_param_load_part                                                #
# ------------------------------------------------------------------ #

class TestRankParamLoadPart:
    RANK_PARAM = {
        "armor": {"S": 0.63, "A": 0.78, "B": 0.90, "C+": 1.0},
        "aim":   {"S": 37,   "A": 25,   "B": 12,   "C": 0},
    }

    def test_fills_param_from_rank(self):
        part = {"armor": {"rank": "A"}}
        result = rank_param_load_part(part, self.RANK_PARAM)
        assert result["armor"]["param"] == pytest.approx(0.78)

    def test_does_not_overwrite_existing_param(self):
        part = {"armor": {"rank": "A", "param": 0.99}}
        result = rank_param_load_part(part, self.RANK_PARAM)
        # param が既にある場合はスキップ
        assert result["armor"]["param"] == pytest.approx(0.99)

    def test_skips_unknown_rank_key(self):
        part = {"aim": {"rank": "Z"}}
        result = rank_param_load_part(part, self.RANK_PARAM)
        assert "param" not in result["aim"]

    def test_non_rank_field_unchanged(self):
        part = {"name": "テストパーツ", "weight": {"param": 1000}}
        result = rank_param_load_part(part, self.RANK_PARAM)
        assert result["name"] == "テストパーツ"
        assert result["weight"]["param"] == 1000

    def test_deep_copy_does_not_mutate_original(self):
        part = {"armor": {"rank": "A"}}
        rank_param_load_part(part, self.RANK_PARAM)
        # 元の part が変化していないことを確認
        assert "param" not in part["armor"]


# ------------------------------------------------------------------ #
#  apply_set_bonus                                                     #
# ------------------------------------------------------------------ #

def _make_draw(bland_id=None):
    """テスト用のミニマムな draw dict を返す。"""
    def part(bid):
        return {
            "blandId": bid,
            "armor": {"param": 1.0},
            "aim": {"param": 10.0},
            "walk": {"param": 7.0},
            "loadCapacity": {"param": 3000.0},
            "loadCapacityLeftover": {"param": 0.0},
            "booster": {"param": 100.0},
            "ndefCapacity": {"param": 500.0},
            "areaTransport": {"param": 3.0},
        }
    return {
        "head": part(bland_id),
        "body": part(bland_id),
        "arm": part(bland_id),
        "leg": part(bland_id),
    }


BLAND_DATA = {
    "cougar": {
        "name": "クーガー",
        "setBonusObj": [
            {"setBonusParamName": "aim", "setBonusValue": 2},
            {"setBonusParamName": "loadCapacity", "setBonusValue": 150},
        ],
        "setBonusInfo": "射撃補正UP（+2%）、重量耐性UP（+150）",
    },
    "heavyGuard": {
        "name": "ヘヴィーガード",
        "setBonusObj": [
            {"setBonusParamName": "armor", "setBonusValue": 3},
        ],
        "setBonusInfo": "装甲UP（+3%）",
    },
}


class TestApplySetBonus:
    def test_no_bonus_mismatched_ids(self):
        draw = _make_draw("cougar")
        draw["body"]["blandId"] = "other"
        result = apply_set_bonus(draw=draw, bland_data=BLAND_DATA)
        assert result["applied"] is False

    def test_no_bonus_all_none(self):
        draw = _make_draw(None)
        result = apply_set_bonus(draw=draw, bland_data=BLAND_DATA)
        assert result["applied"] is False

    def test_brand_not_found_in_data(self):
        draw = _make_draw("unknown_brand")
        result = apply_set_bonus(draw=draw, bland_data=BLAND_DATA)
        assert result["applied"] is False
        assert result["blandId"] == "unknown_brand"

    def test_aim_bonus_applied_to_head(self):
        draw = _make_draw("cougar")
        apply_set_bonus(draw=draw, bland_data=BLAND_DATA)
        assert draw["head"]["aim"]["param"] == pytest.approx(12.0)  # 10 + 2
        # 他のパーツの aim は変化しない
        assert draw["body"].get("aim", {}).get("param", 10.0) == pytest.approx(10.0)

    def test_load_capacity_bonus_applied_to_leg(self):
        draw = _make_draw("cougar")
        apply_set_bonus(draw=draw, bland_data=BLAND_DATA)
        assert draw["leg"]["loadCapacity"]["param"] == pytest.approx(3150.0)
        assert draw["leg"]["loadCapacityLeftover"]["param"] == pytest.approx(150.0)

    def test_armor_bonus_subtracts_from_all_parts(self):
        draw = _make_draw("heavyGuard")
        apply_set_bonus(draw=draw, bland_data=BLAND_DATA)
        # armor bonus=3 → val=3, /100=0.03, 各パーツ armor 1.0 - 0.03 = 0.97
        for cat in ("head", "body", "arm", "leg"):
            assert draw[cat]["armor"]["param"] == pytest.approx(0.97)

    def test_bonus_rate_percent_halved(self):
        draw = _make_draw("cougar")
        apply_set_bonus(draw=draw, bland_data=BLAND_DATA, bonus_rate_percent=50.0)
        # aim bonus = 2 * 50% = 1
        assert draw["head"]["aim"]["param"] == pytest.approx(11.0)

    def test_returns_applied_true_with_info(self):
        draw = _make_draw("cougar")
        result = apply_set_bonus(draw=draw, bland_data=BLAND_DATA)
        assert result["applied"] is True
        assert result["blandId"] == "cougar"
        assert "info" in result


# ------------------------------------------------------------------ #
#  calc_parts_base                                                     #
# ------------------------------------------------------------------ #

SYSC = {
    "WEIGHT_PENALTY": 10.0,
    "WEIGHT_PENALTY_PER": 25.0,
    "WALK_MIN": 3.15,
    "DASH_MIN": 10.5,
    "WALK_MAX_HOVER": 14.7,
    "WALK_MIN_HOVER": 4.2,
    "DASH_MIN_HOVER": 8.4,
}

RANK_PARAM = {
    "armor": {"S": 0.63, "A": 0.78, "B": 0.90, "C+": 1.0, "C": 1.05},
    "walk":  {"S": 14.0, "A": 10.5, "B": 8.4, "C": 6.3},
    "dash":  {"S": 35.0, "A": 28.0, "B": 21.0, "C": 14.0},
}


def _make_base_draw(walk=7.0, dash=17.0, load_capacity=3200, weights=(800, 800, 800, 800),
                    armors=(1.0, 1.0, 1.0, 1.0), is_hover=False):
    leg_walk = {"param": walk, "type": "hover"} if is_hover else {"param": walk}
    return {
        "head": {"armor": {"param": armors[0]}, "weight": {"param": weights[0]}},
        "body": {"armor": {"param": armors[1]}, "weight": {"param": weights[1]}},
        "arm":  {"armor": {"param": armors[2]}, "weight": {"param": weights[2]}},
        "leg":  {
            "armor": {"param": armors[3]},
            "weight": {"param": weights[3]},
            "walk": leg_walk,
            "dash": {"param": dash},
            "loadCapacity": {"param": load_capacity},
        },
    }


class TestCalcPartsBase:
    def test_no_overweight_no_penalty(self):
        # total_weight=3200, load_capacity=3200 → leftover=0 → penalty=0
        draw = _make_base_draw(walk=7.0, dash=17.0, load_capacity=3200,
                               weights=(800, 800, 800, 800))
        base = calc_parts_base(draw=draw, sysc=SYSC, rank_param=RANK_PARAM)
        assert base["weight_penalty"] == pytest.approx(0.0)
        assert base["walk"]["param"] == pytest.approx(7.0)
        assert base["dash"]["param"] == pytest.approx(17.0)

    def test_overweight_reduces_speed(self):
        # total=3600, load_capacity=3200 → leftover=-400
        # penalty = (-400/10) * (25/100) = -1.0 (%)
        # walk_adj = 7.0 * (1 + (-1.0/100)) = 7.0 * 0.99 = 6.93
        draw = _make_base_draw(walk=7.0, dash=17.0, load_capacity=3200,
                               weights=(900, 900, 900, 900))
        base = calc_parts_base(draw=draw, sysc=SYSC, rank_param=RANK_PARAM)
        assert base["weight_penalty"] < 0
        assert base["walk"]["param"] < 7.0
        assert base["dash"]["param"] < 17.0

    def test_walk_clamped_to_min(self):
        # 極端な過積載 → walk が WALK_MIN でクランプ
        draw = _make_base_draw(walk=4.0, dash=12.0, load_capacity=100,
                               weights=(2000, 2000, 2000, 2000))
        base = calc_parts_base(draw=draw, sysc=SYSC, rank_param=RANK_PARAM)
        assert base["walk"]["param"] >= SYSC["WALK_MIN"]
        assert base["dash"]["param"] >= SYSC["DASH_MIN"]

    def test_armor_average_correct(self):
        draw = _make_base_draw(armors=(0.63, 0.78, 0.90, 1.0))
        base = calc_parts_base(draw=draw, sysc=SYSC, rank_param=RANK_PARAM)
        expected = (0.63 + 0.78 + 0.90 + 1.0) / 4.0
        assert base["armor_avg"]["param"] == pytest.approx(expected)

    def test_hover_walk_clamped_to_max(self):
        # ホバー脚: walk=20 (MAX_HOVER=14.7 超) → 14.7 にクランプ
        draw = _make_base_draw(walk=20.0, dash=17.0, load_capacity=5000,
                               weights=(100, 100, 100, 100), is_hover=True)
        base = calc_parts_base(draw=draw, sysc=SYSC, rank_param=RANK_PARAM)
        assert base["walk"]["param"] == pytest.approx(SYSC["WALK_MAX_HOVER"])

    def test_hover_walk_clamped_to_min(self):
        draw = _make_base_draw(walk=2.0, dash=6.0, load_capacity=100,
                               weights=(2000, 2000, 2000, 2000), is_hover=True)
        base = calc_parts_base(draw=draw, sysc=SYSC, rank_param=RANK_PARAM)
        assert base["walk"]["param"] >= SYSC["WALK_MIN_HOVER"]
        assert base["dash"]["param"] >= SYSC["DASH_MIN_HOVER"]

    def test_inside_load_capacity_added(self):
        draw = _make_base_draw(load_capacity=3000, weights=(800, 800, 800, 800))
        base_without = calc_parts_base(draw=draw, sysc=SYSC, rank_param=RANK_PARAM,
                                       inside_load_capacity=0.0)
        base_with = calc_parts_base(draw=draw, sysc=SYSC, rank_param=RANK_PARAM,
                                    inside_load_capacity=500.0)
        assert base_with["load_capacity"] - base_without["load_capacity"] == pytest.approx(500.0)

    def test_rank_none_when_table_empty(self):
        draw = _make_base_draw()
        base = calc_parts_base(draw=draw, sysc=SYSC, rank_param={})
        assert base["armor_avg"]["rank"] is None
        assert base["walk"]["rank"] is None
        assert base["dash"]["rank"] is None
