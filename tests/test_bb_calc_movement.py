"""
bb_calc_movement.py のユニットテスト（16件）
"""
import pytest
from bb_calc_movement import get_rank_closest, set_weight_penalty, SysConsts


# ------------------------------------------------------------------ #
#  テスト用フィクスチャ                                                #
# ------------------------------------------------------------------ #

SYSC = SysConsts(
    WEIGHT_PENALTY=10.0,
    WALK_MIN=3.15,
    DASH_MIN=10.5,
    WALK_MIN_HOVER=4.2,
    WALK_MAX_HOVER=14.7,
    DASH_MIN_HOVER=8.4,
)

RANK_PARAM = {
    "walk": {
        "S": 14.0,
        "A": 10.5,
        "B": 8.4,
        "C+": 7.35,
        "C": 6.3,
        "D": 4.2,
    },
    "dash": {
        "S": 35.0,
        "A": 28.0,
        "B": 21.0,
        "C": 14.0,
        "D": 10.5,
    },
    "walk_hover": {
        "S": 14.7,
        "A": 12.6,
        "B": 10.5,
        "C": 7.35,
    },
    "dash_hover": {
        "S": 28.0,
        "A": 21.0,
        "B": 14.0,
        "C": 8.4,
    },
}


# ------------------------------------------------------------------ #
#  get_rank_closest                                                    #
# ------------------------------------------------------------------ #

class TestGetRankClosest:
    def test_exact_match(self):
        table = {"A": 10.5, "B": 8.4, "C": 6.3}
        assert get_rank_closest(table, 8.4) == "B"

    def test_closest_of_two(self):
        table = {"A": 10.0, "B": 8.0}
        # 9.5 → A(diff=0.5) vs B(diff=1.5) → A
        assert get_rank_closest(table, 9.5) == "A"

    def test_exactly_midpoint_picks_one(self):
        # 9.0 → A(diff=1.0) vs B(diff=1.0) — どちらか（実装依存）、クラッシュしないことを確認
        table = {"A": 10.0, "B": 8.0}
        result = get_rank_closest(table, 9.0)
        assert result in ("A", "B")

    def test_empty_table_returns_empty_string(self):
        assert get_rank_closest({}, 5.0) == ""

    def test_single_entry(self):
        assert get_rank_closest({"C": 6.3}, 999.0) == "C"


# ------------------------------------------------------------------ #
#  set_weight_penalty                                                  #
# ------------------------------------------------------------------ #

class TestSetWeightPenalty:
    def test_no_overweight_no_penalty(self):
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=3200, weight=3000,
            weight_penalty_per=25.0,
            walk=6.3, dash=14.0, is_hover=False,
        )
        assert result["weight_penalty"] == pytest.approx(0.0)
        assert result["loadcapacity_leftover"] == pytest.approx(200.0)
        assert result["walk"]["param"] == pytest.approx(6.3)
        assert result["dash"]["param"] == pytest.approx(14.0)

    def test_overweight_reduces_speed(self):
        # leftover = 3200 - 3600 = -400
        # penalty = (-400 / 10) * (25 / 100) = -40 * 0.25 = -10.0
        # walk_adj = 7.35 * (1 + (-10.0/100)) = 7.35 * 0.90 = 6.615
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=3200, weight=3600,
            weight_penalty_per=25.0,
            walk=7.35, dash=17.0, is_hover=False,
        )
        assert result["weight_penalty"] == pytest.approx(-10.0)
        assert result["walk"]["param"] < 7.35
        assert result["dash"]["param"] < 17.0

    def test_walk_clamped_to_walk_min(self):
        # 極端な過積載 → WALK_MIN でクランプ
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=100, weight=5000,
            weight_penalty_per=25.0,
            walk=4.0, dash=12.0, is_hover=False,
        )
        assert result["walk"]["param"] >= SYSC.WALK_MIN

    def test_dash_clamped_to_dash_min(self):
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=100, weight=5000,
            weight_penalty_per=25.0,
            walk=4.0, dash=12.0, is_hover=False,
        )
        assert result["dash"]["param"] >= SYSC.DASH_MIN

    def test_hover_walk_clamped_to_min_hover(self):
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=100, weight=5000,
            weight_penalty_per=25.0,
            walk=5.0, dash=9.0, is_hover=True,
        )
        assert result["walk"]["param"] >= SYSC.WALK_MIN_HOVER

    def test_hover_walk_clamped_to_max_hover(self):
        # 軽すぎ・高速脚 → WALK_MAX_HOVER でクランプ
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=9999, weight=100,
            weight_penalty_per=25.0,
            walk=20.0, dash=30.0, is_hover=True,
        )
        assert result["walk"]["param"] == pytest.approx(SYSC.WALK_MAX_HOVER)

    def test_hover_dash_clamped_to_min_hover(self):
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=100, weight=5000,
            weight_penalty_per=25.0,
            walk=5.0, dash=6.0, is_hover=True,
        )
        assert result["dash"]["param"] >= SYSC.DASH_MIN_HOVER

    def test_hover_uses_hover_rank_tables(self):
        # hover 時は walk_hover / dash_hover テーブルを使う
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=3200, weight=3000,
            weight_penalty_per=25.0,
            walk=7.35, dash=14.0, is_hover=True,
        )
        # walk_hover テーブルで closest rank を探す → "C" (7.35)
        assert result["walk"]["rank"] == "C"

    def test_normal_uses_walk_rank_table(self):
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=3200, weight=3000,
            weight_penalty_per=25.0,
            walk=6.3, dash=14.0, is_hover=False,
        )
        # walk テーブルで 6.3 → "C"
        assert result["walk"]["rank"] == "C"

    def test_empty_rank_table_gives_none(self):
        result = set_weight_penalty(
            sysc=SYSC, rank_param={},
            load_capa=3200, weight=3000,
            weight_penalty_per=25.0,
            walk=6.3, dash=14.0, is_hover=False,
        )
        assert result["walk"]["rank"] is None
        assert result["dash"]["rank"] is None

    def test_weight_and_leftover_in_result(self):
        result = set_weight_penalty(
            sysc=SYSC, rank_param=RANK_PARAM,
            load_capa=3200, weight=3100,
            weight_penalty_per=25.0,
            walk=6.3, dash=14.0, is_hover=False,
        )
        assert result["weight"] == pytest.approx(3100.0)
        assert result["loadcapacity_leftover"] == pytest.approx(100.0)
