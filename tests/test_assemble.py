"""
tests/test_assemble.py
assemble_agent_params() のテスト

テスト対象:
  - assemble_agent_params(calc_result) が Agent.__init__ 用の kwargs dict を返す
  - 各フィールドが calc_full() 出力の正しいパスから取得される
  - フィールドが欠損している場合はデフォルト値が使われる
  - 返り値の dict を Agent(**params, ...) に展開できる
"""
import pytest
from assemble import assemble_agent_params
from simulation import Agent, AGENT_HP, DPS, HIT_RATE, SEARCH_RANGE_C, LOCKON_RANGE_C, CELLS_PER_STEP


# ─────────────────────────────────────────
# テスト用の最小 calc_result フィクスチャ
# ─────────────────────────────────────────
def make_calc_result(
    walk_mps: float = 21.9,
    sakuteki_m: float = 80.0,
    lockon_m: float = 60.0,
    dps_per_sec: int = 3000,
    armor_avg_param: float = 1.0,
    aim_param: float = 12.0,
    rate: float = 60.0,
) -> dict:
    """calc_full() 出力と同じ構造を持つ最小の dict を返す"""
    return {
        "base": {
            "armor_avg": {"param": armor_avg_param},
            "walk": {"param": walk_mps},
        },
        "draw": {
            "head": {
                "sakuteki": {"param": sakuteki_m},
                "lockOn":   {"param": lockon_m},
                "aim":      {"param": aim_param},
            },
        },
        "weapons": {
            "main": {"damagePerSec": [dps_per_sec], "rate": rate},
        },
    }


# ─────────────────────────────────────────
# max_hp の抽出テスト
# ─────────────────────────────────────────
class TestAssembleAgentParamsMaxHp:

    def test_armor_coeff_1_0_yields_base_hp(self):
        """armor_avg=1.0（C+ 相当）→ max_hp = 10,000"""
        result = make_calc_result(armor_avg_param=1.0)
        params = assemble_agent_params(result)
        assert params["max_hp"] == 10_000

    def test_armor_coeff_s_rank(self):
        """armor_avg=0.63（S ランク）→ max_hp = round(10000/0.63) = 15,873"""
        result = make_calc_result(armor_avg_param=0.63)
        params = assemble_agent_params(result)
        assert params["max_hp"] == round(10_000 / 0.63)

    def test_armor_coeff_e_minus_rank(self):
        """armor_avg=1.38（E- ランク）→ max_hp = round(10000/1.38) = 7,246"""
        result = make_calc_result(armor_avg_param=1.38)
        params = assemble_agent_params(result)
        assert params["max_hp"] == round(10_000 / 1.38)

    def test_softer_armor_gives_lower_hp(self):
        """armor_avg が大きい（柔らかい）ほど max_hp が小さい"""
        hard = assemble_agent_params(make_calc_result(armor_avg_param=0.63))
        soft = assemble_agent_params(make_calc_result(armor_avg_param=1.25))
        assert hard["max_hp"] > soft["max_hp"]

    def test_max_hp_is_int(self):
        """max_hp は整数型"""
        result = make_calc_result(armor_avg_param=0.9)
        params = assemble_agent_params(result)
        assert isinstance(params["max_hp"], int)

    def test_missing_armor_avg_uses_default(self):
        """base.armor_avg がない → default_max_hp を使う"""
        result = make_calc_result()
        del result["base"]["armor_avg"]
        params = assemble_agent_params(result, default_max_hp=8000)
        assert params["max_hp"] == 8000

    def test_missing_base_uses_default(self):
        """base キー自体がない → default_max_hp を使う"""
        result = make_calc_result()
        del result["base"]
        params = assemble_agent_params(result, default_max_hp=7777)
        assert params["max_hp"] == 7777

    def test_default_max_hp_matches_agent_hp(self):
        """フォールバックはシミュレーター定数 AGENT_HP と一致"""
        result = make_calc_result()
        del result["base"]["armor_avg"]
        params = assemble_agent_params(result)
        assert params["max_hp"] == AGENT_HP


# ─────────────────────────────────────────
# dps の抽出テスト
# ─────────────────────────────────────────
class TestAssembleAgentParamsDps:

    def test_dps_from_main_weapon(self):
        """main 武器の damagePerSec[0] が dps になる"""
        result = make_calc_result(dps_per_sec=4000)
        params = assemble_agent_params(result)
        assert params["dps"] == 4000

    def test_dps_is_int(self):
        """dps は整数型（float を丸める）"""
        result = make_calc_result(dps_per_sec=3500)
        params = assemble_agent_params(result)
        assert isinstance(params["dps"], int)

    def test_dps_multiple_damage_values_uses_first(self):
        """damagePerSec が複数の場合は最初の要素を使う"""
        result = make_calc_result()
        result["weapons"]["main"]["damagePerSec"] = [5000, 3000, 1000]
        params = assemble_agent_params(result)
        assert params["dps"] == 5000

    def test_missing_weapons_uses_default(self):
        """weapons キーなし → default_dps を使う"""
        result = make_calc_result()
        del result["weapons"]
        params = assemble_agent_params(result, default_dps=9999)
        assert params["dps"] == 9999

    def test_missing_main_slot_uses_default(self):
        """weapons.main がない → default_dps を使う"""
        result = make_calc_result()
        del result["weapons"]["main"]
        params = assemble_agent_params(result, default_dps=1111)
        assert params["dps"] == 1111

    def test_missing_damage_per_sec_uses_default(self):
        """damagePerSec フィールドがない → default_dps を使う"""
        result = make_calc_result()
        del result["weapons"]["main"]["damagePerSec"]
        params = assemble_agent_params(result, default_dps=2222)
        assert params["dps"] == 2222

    def test_default_dps_matches_simulation_constant(self):
        """default_dps 未指定時のフォールバックは DPS（3000）と一致"""
        result = make_calc_result()
        del result["weapons"]
        params = assemble_agent_params(result)
        assert params["dps"] == DPS


# ─────────────────────────────────────────
# search_range_c の抽出テスト
# ─────────────────────────────────────────
class TestAssembleAgentParamsSearchRange:

    def test_search_range_c_from_sakuteki(self):
        """sakuteki=80.0m → search_range_c = 16.0 (80/5)"""
        result = make_calc_result(sakuteki_m=80.0)
        params = assemble_agent_params(result)
        assert params["search_range_c"] == pytest.approx(16.0)

    def test_search_range_c_scaled_by_cell_size(self):
        """sakuteki=120.0m → search_range_c = 24.0"""
        result = make_calc_result(sakuteki_m=120.0)
        params = assemble_agent_params(result)
        assert params["search_range_c"] == pytest.approx(24.0)

    def test_search_range_c_small_value(self):
        """sakuteki=50.0m → search_range_c = 10.0"""
        result = make_calc_result(sakuteki_m=50.0)
        params = assemble_agent_params(result)
        assert params["search_range_c"] == pytest.approx(10.0)

    def test_missing_head_uses_default_search_range(self):
        """draw.head がない → default_search_range_c を使う"""
        result = make_calc_result()
        del result["draw"]["head"]
        params = assemble_agent_params(result, default_search_range_c=7.0)
        assert params["search_range_c"] == pytest.approx(7.0)

    def test_missing_sakuteki_uses_default(self):
        """sakuteki フィールドなし → default_search_range_c を使う"""
        result = make_calc_result()
        del result["draw"]["head"]["sakuteki"]
        params = assemble_agent_params(result, default_search_range_c=5.5)
        assert params["search_range_c"] == pytest.approx(5.5)

    def test_default_search_range_matches_simulation_constant(self):
        """フォールバックはシミュレーター定数 SEARCH_RANGE_C と一致"""
        result = make_calc_result()
        del result["draw"]["head"]["sakuteki"]
        params = assemble_agent_params(result)
        assert params["search_range_c"] == pytest.approx(SEARCH_RANGE_C)


# ─────────────────────────────────────────
# lockon_range_c の抽出テスト
# ─────────────────────────────────────────
class TestAssembleAgentParamsLockonRange:

    def test_lockon_range_c_from_lockon_param(self):
        """lockOn=60.0m → lockon_range_c = 12.0 (60/5)"""
        result = make_calc_result(lockon_m=60.0)
        params = assemble_agent_params(result)
        assert params["lockon_range_c"] == pytest.approx(12.0)

    def test_lockon_range_c_scaled_by_cell_size(self):
        """lockOn=90.0m → lockon_range_c = 18.0"""
        result = make_calc_result(lockon_m=90.0)
        params = assemble_agent_params(result)
        assert params["lockon_range_c"] == pytest.approx(18.0)

    def test_lockon_range_c_small_value(self):
        """lockOn=40.0m → lockon_range_c = 8.0"""
        result = make_calc_result(lockon_m=40.0)
        params = assemble_agent_params(result)
        assert params["lockon_range_c"] == pytest.approx(8.0)

    def test_missing_lockon_uses_default(self):
        """lockOn フィールドなし → default_lockon_range_c を使う"""
        result = make_calc_result()
        del result["draw"]["head"]["lockOn"]
        params = assemble_agent_params(result, default_lockon_range_c=4.5)
        assert params["lockon_range_c"] == pytest.approx(4.5)

    def test_default_lockon_range_matches_simulation_constant(self):
        """フォールバックはシミュレーター定数 LOCKON_RANGE_C と一致"""
        result = make_calc_result()
        del result["draw"]["head"]["lockOn"]
        params = assemble_agent_params(result)
        assert params["lockon_range_c"] == pytest.approx(LOCKON_RANGE_C)


# ─────────────────────────────────────────
# cells_per_step の抽出テスト
# ─────────────────────────────────────────
class TestAssembleAgentParamsCellsPerStep:

    def test_cells_per_step_from_walk_speed(self):
        """walk=21.9m/s → round(21.9/5)=4 → cells_per_step=4"""
        result = make_calc_result(walk_mps=21.9)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 4

    def test_cells_per_step_high_speed(self):
        """walk=31.5m/s → round(31.5/5)=6 → cells_per_step=6"""
        result = make_calc_result(walk_mps=31.5)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 6

    def test_cells_per_step_low_speed(self):
        """walk=14.0m/s → round(14.0/5)=3 → cells_per_step=3"""
        result = make_calc_result(walk_mps=14.0)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 3

    def test_cells_per_step_very_slow_minimum_is_1(self):
        """walk=3.0m/s → round(0.6)=1 → max(1,1)=1 → cells_per_step=1（最低値）"""
        result = make_calc_result(walk_mps=3.0)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 1

    def test_cells_per_step_very_fast(self):
        """walk=45.0m/s → round(45.0/5)=9 → cells_per_step=9"""
        result = make_calc_result(walk_mps=45.0)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 9

    def test_missing_base_walk_uses_default(self):
        """base.walk がない → default_cells_per_step を使う"""
        result = make_calc_result()
        del result["base"]["walk"]
        params = assemble_agent_params(result, default_cells_per_step=3)
        assert params["cells_per_step"] == 3

    def test_default_cells_per_step_matches_simulation_constant(self):
        """フォールバックはシミュレーター定数 CELLS_PER_STEP と一致"""
        result = make_calc_result()
        del result["base"]["walk"]
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == CELLS_PER_STEP


# ─────────────────────────────────────────
# 返り値の構造と Agent への展開テスト
# ─────────────────────────────────────────
class TestAssembleAgentParamsStructure:

    def test_returns_dict(self):
        """返り値は dict"""
        result = make_calc_result()
        params = assemble_agent_params(result)
        assert isinstance(params, dict)

    def test_has_required_keys(self):
        """13の必須キーが含まれる（T-4: clip / reload_steps を追加）"""
        result = make_calc_result()
        params = assemble_agent_params(result)
        assert "max_hp" in params
        assert "dps" in params
        assert "search_range_c" in params
        assert "lockon_range_c" in params
        assert "cells_per_step" in params
        assert "hit_rate" in params
        assert "shots_per_step" in params
        assert "walk_cells_per_step" in params
        assert "dash_cells_per_step" in params
        assert "boost_max" in params
        assert "boost_regen" in params
        assert "clip" in params
        assert "reload_steps" in params

    def test_no_extra_keys(self):
        """余分なキーが含まれない（T-4: 13キー）"""
        result = make_calc_result()
        params = assemble_agent_params(result)
        assert set(params.keys()) == {
            "max_hp", "dps", "search_range_c", "lockon_range_c",
            "cells_per_step", "hit_rate", "shots_per_step",
            "walk_cells_per_step", "dash_cells_per_step",
            "boost_max", "boost_regen",
            "clip", "reload_steps",
        }

    def test_params_can_be_spread_into_agent(self):
        """返り値を Agent(**params, ...) に展開できる"""
        result = make_calc_result()
        params = assemble_agent_params(result)
        agent = Agent(agent_id=1, x=5, y=25, team=0, **params)
        assert agent.max_hp == params["max_hp"]
        assert agent.dps == params["dps"]
        assert agent.search_range_c == params["search_range_c"]
        assert agent.lockon_range_c == params["lockon_range_c"]
        assert agent.cells_per_step == params["cells_per_step"]
        assert agent.hit_rate == pytest.approx(params["hit_rate"])
        assert agent.shots_per_step == params["shots_per_step"]
        assert agent.walk_cells_per_step == params["walk_cells_per_step"]
        assert agent.dash_cells_per_step == params["dash_cells_per_step"]
        assert agent.boost_max == params["boost_max"]
        assert agent.boost_regen == pytest.approx(params["boost_regen"])
        assert agent.clip == params["clip"]
        assert agent.reload_steps == params["reload_steps"]

    def test_fully_missing_result_all_defaults(self):
        """空の dict → 全フィールドがデフォルト値"""
        params = assemble_agent_params({})
        assert params["max_hp"] == AGENT_HP
        assert params["dps"] == DPS
        assert params["search_range_c"] == SEARCH_RANGE_C
        assert params["lockon_range_c"] == LOCKON_RANGE_C
        assert params["cells_per_step"] == CELLS_PER_STEP
        assert params["hit_rate"] == pytest.approx(HIT_RATE)
        assert params["shots_per_step"] == 1

    def test_custom_defaults_are_used_when_fields_missing(self):
        """カスタム default 値が欠損時に正しく使われる"""
        params = assemble_agent_params(
            {},
            default_max_hp=9999,
            default_dps=1234,
            default_search_range_c=11.0,
            default_lockon_range_c=7.5,
            default_cells_per_step=4,
            default_hit_rate=0.70,
            default_shots_per_step=3,
        )
        assert params["max_hp"] == 9999
        assert params["dps"] == 1234
        assert params["search_range_c"] == pytest.approx(11.0)
        assert params["lockon_range_c"] == pytest.approx(7.5)
        assert params["cells_per_step"] == 4
        assert params["hit_rate"] == pytest.approx(0.70)
        assert params["shots_per_step"] == 3


# ─────────────────────────────────────────
# hit_rate の抽出テスト
# ─────────────────────────────────────────
class TestAssembleAgentParamsHitRate:

    def test_aim_param_12_gives_default_hit_rate(self):
        """aim.param=12 (B ランク) → hit_rate = HIT_RATE=0.64（デフォルト命中率）"""
        result = make_calc_result(aim_param=12.0)
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(HIT_RATE)

    def test_high_aim_gives_higher_hit_rate(self):
        """aim.param=37 (S ランク) → hit_rate = 0.64 + (37-12)*0.006 = 0.79"""
        result = make_calc_result(aim_param=37.0)
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(HIT_RATE + (37.0 - 12.0) * 0.006)

    def test_low_aim_gives_lower_hit_rate(self):
        """aim.param=-24 (E ランク) → hit_rate = 0.64 + (-24-12)*0.006 = 0.424"""
        result = make_calc_result(aim_param=-24.0)
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(HIT_RATE + (-24.0 - 12.0) * 0.006)

    def test_hit_rate_clamped_at_max_1_0(self):
        """aim が非常に高い → hit_rate は 1.0 でクランプ"""
        result = make_calc_result(aim_param=200.0)
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(1.0)

    def test_hit_rate_clamped_at_min_0_4(self):
        """aim が非常に低い → hit_rate は 0.40 でクランプ"""
        result = make_calc_result(aim_param=-1000.0)
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(0.40)

    def test_missing_aim_uses_default_hit_rate(self):
        """draw.head.aim がない → default_hit_rate を使う"""
        result = make_calc_result()
        del result["draw"]["head"]["aim"]
        params = assemble_agent_params(result, default_hit_rate=0.65)
        assert params["hit_rate"] == pytest.approx(0.65)

    def test_missing_head_uses_default_hit_rate(self):
        """draw.head がない → default_hit_rate を使う"""
        result = make_calc_result()
        del result["draw"]["head"]
        params = assemble_agent_params(result, default_hit_rate=0.55)
        assert params["hit_rate"] == pytest.approx(0.55)

    def test_default_hit_rate_matches_hit_rate_constant(self):
        """フォールバックはシミュレーター定数 HIT_RATE と一致"""
        result = make_calc_result()
        del result["draw"]["head"]["aim"]
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(HIT_RATE)

    def test_hit_rate_is_float(self):
        """hit_rate は float 型"""
        result = make_calc_result(aim_param=12.0)
        params = assemble_agent_params(result)
        assert isinstance(params["hit_rate"], float)


# ─────────────────────────────────────────
# T-6: weapon precision による hit_rate 補正テスト
# ─────────────────────────────────────────
def make_calc_result_with_precision(precision: str = "B", **kwargs) -> dict:
    """weapons.main.precision を持つ calc_result を返す"""
    result = make_calc_result(**kwargs)
    result["weapons"]["main"]["precision"] = precision
    return result


class TestAssembleAgentParamsPrecision:

    def test_precision_b_no_change(self):
        """precision=B（基準）→ hit_rate 変化なし（0.64）"""
        result = make_calc_result_with_precision("B", aim_param=12.0)
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(HIT_RATE)

    def test_precision_high_rank_increases_hit_rate(self):
        """precision=S(param=37) → hit_rate = 0.64 + (37-12)*0.006 = 0.79"""
        result = make_calc_result_with_precision("S", aim_param=12.0)
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(HIT_RATE + (37 - 12) * 0.006)

    def test_precision_low_rank_decreases_hit_rate(self):
        """precision=E(param=-24) → hit_rate = 0.64 + (-24-12)*0.006 = 0.424"""
        result = make_calc_result_with_precision("E", aim_param=12.0)
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(HIT_RATE + (-24 - 12) * 0.006)

    def test_aim_and_precision_both_contribute(self):
        """aim=B+(param=16) + precision=A(param=25) → 両方の補正が加算"""
        result = make_calc_result_with_precision("A", aim_param=16.0)
        params = assemble_agent_params(result)
        expected = HIT_RATE + (16 - 12) * 0.006 + (25 - 12) * 0.006
        assert params["hit_rate"] == pytest.approx(expected)

    def test_precision_missing_acts_as_b_rank(self):
        """precision 未設定 → B ランク相当（prec_bonus=0）、aim のみ有効"""
        result = make_calc_result(aim_param=16.0)
        params = assemble_agent_params(result)
        expected = HIT_RATE + (16 - 12) * 0.006
        assert params["hit_rate"] == pytest.approx(expected)

    def test_precision_list_uses_first_value(self):
        """precision がリスト → 先頭値を使用"""
        result = make_calc_result(aim_param=12.0)
        result["weapons"]["main"]["precision"] = ["S", "C"]
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(HIT_RATE + (37 - 12) * 0.006)

    def test_hit_rate_clamped_at_max_with_both(self):
        """aim が非常に高い + precision=S → 上限 1.0 にクランプ"""
        result = make_calc_result_with_precision("S", aim_param=200.0)
        params = assemble_agent_params(result)
        assert params["hit_rate"] == pytest.approx(1.0)


# ─────────────────────────────────────────
# shots_per_step の抽出テスト
# ─────────────────────────────────────────
class TestAssembleAgentParamsShotsPerStep:

    def test_rate_60_gives_shots_per_step_1(self):
        """rate=60 → round(60/60)=1 → shots_per_step=1"""
        result = make_calc_result(rate=60.0)
        params = assemble_agent_params(result)
        assert params["shots_per_step"] == 1

    def test_rate_120_gives_shots_per_step_2(self):
        """rate=120 → round(120/60)=2 → shots_per_step=2"""
        result = make_calc_result(rate=120.0)
        params = assemble_agent_params(result)
        assert params["shots_per_step"] == 2

    def test_rate_180_gives_shots_per_step_3(self):
        """rate=180 → round(180/60)=3 → shots_per_step=3"""
        result = make_calc_result(rate=180.0)
        params = assemble_agent_params(result)
        assert params["shots_per_step"] == 3

    def test_rate_very_low_minimum_is_1(self):
        """rate=10 → round(10/60)=0 → max(1,0)=1（最低値）"""
        result = make_calc_result(rate=10.0)
        params = assemble_agent_params(result)
        assert params["shots_per_step"] == 1

    def test_missing_rate_uses_default(self):
        """weapons.main.rate がない → default_shots_per_step を使う"""
        result = make_calc_result()
        del result["weapons"]["main"]["rate"]
        params = assemble_agent_params(result, default_shots_per_step=4)
        assert params["shots_per_step"] == 4

    def test_missing_weapons_uses_default_shots(self):
        """weapons キーなし → default_shots_per_step を使う"""
        result = make_calc_result()
        del result["weapons"]
        params = assemble_agent_params(result, default_shots_per_step=2)
        assert params["shots_per_step"] == 2

    def test_default_shots_per_step_is_one(self):
        """フォールバックのデフォルトは 1"""
        result = make_calc_result()
        del result["weapons"]["main"]["rate"]
        params = assemble_agent_params(result)
        assert params["shots_per_step"] == 1

    def test_shots_per_step_is_int(self):
        """shots_per_step は整数型"""
        result = make_calc_result(rate=60.0)
        params = assemble_agent_params(result)
        assert isinstance(params["shots_per_step"], int)


# ─────────────────────────────────────────
# walk_cells_per_step / dash_cells_per_step の抽出テスト
# ─────────────────────────────────────────
def make_calc_result_with_dash(
    walk_mps: float = 21.9,
    dash_mps: float | None = None,
    booster_param: float | None = None,
    **kwargs,
) -> dict:
    """dash / body.booster フィールドを追加した calc_result を返す"""
    base = make_calc_result(walk_mps=walk_mps, **kwargs)
    if dash_mps is not None:
        base["base"]["dash"] = {"param": dash_mps}
    if booster_param is not None:
        base.setdefault("draw", {}).setdefault("body", {})
        base["draw"]["body"]["booster"] = {"param": booster_param}
    return base


class TestAssembleWalkDashCells:

    def test_walk_cells_from_walk_speed(self):
        """walk=6.75m/s → round(6.75/10)=1 → walk_cells_per_step=1"""
        result = make_calc_result_with_dash(walk_mps=6.75, dash_mps=21.9)
        params = assemble_agent_params(result)
        assert params["walk_cells_per_step"] == 1

    def test_walk_cells_very_slow_minimum_is_1(self):
        """walk=3.0m/s → round(0.3)=0 → max(1,0)=1"""
        result = make_calc_result_with_dash(walk_mps=3.0, dash_mps=21.9)
        params = assemble_agent_params(result)
        assert params["walk_cells_per_step"] == 1

    def test_dash_cells_c_minus_rank(self):
        """dash=21.9m/s → round(21.9/5)=4 → dash_cells_per_step=4（C- ランク相当）"""
        result = make_calc_result_with_dash(walk_mps=6.75, dash_mps=21.9)
        params = assemble_agent_params(result)
        assert params["dash_cells_per_step"] == 4

    def test_dash_cells_s_rank(self):
        """dash=28.5m/s → round(28.5/5)=6 → dash_cells_per_step=6（S ランク相当）"""
        result = make_calc_result_with_dash(walk_mps=10.125, dash_mps=28.5)
        params = assemble_agent_params(result)
        assert params["dash_cells_per_step"] == 6

    def test_missing_dash_falls_back_to_cells_per_step(self):
        """base.dash がない → cells_per_step の値を使う"""
        result = make_calc_result(walk_mps=21.9)  # dash なし
        params = assemble_agent_params(result)
        # cells_per_step = round(21.9/5) = 4
        assert params["dash_cells_per_step"] == params["cells_per_step"]

    def test_missing_walk_uses_default_walk_cells(self):
        """base.walk がない → default_walk_cells_per_step を使う"""
        result = make_calc_result_with_dash(walk_mps=6.75, dash_mps=21.9)
        del result["base"]["walk"]
        params = assemble_agent_params(result, default_walk_cells_per_step=2)
        assert params["walk_cells_per_step"] == 2

    def test_walk_cells_is_int(self):
        """walk_cells_per_step は整数型"""
        result = make_calc_result_with_dash(walk_mps=6.75, dash_mps=21.9)
        params = assemble_agent_params(result)
        assert isinstance(params["walk_cells_per_step"], int)

    def test_dash_cells_is_int(self):
        """dash_cells_per_step は整数型"""
        result = make_calc_result_with_dash(walk_mps=6.75, dash_mps=21.9)
        params = assemble_agent_params(result)
        assert isinstance(params["dash_cells_per_step"], int)


# ─────────────────────────────────────────
# boost_max の抽出テスト
# ─────────────────────────────────────────
class TestAssembleBoostMax:

    def test_boost_max_from_booster_param(self):
        """draw.body.booster.param=90.0 → boost_max=90"""
        result = make_calc_result_with_dash(booster_param=90.0)
        params = assemble_agent_params(result)
        assert params["boost_max"] == 90

    def test_boost_max_s_rank(self):
        """draw.body.booster.param=140.0 → boost_max=140（S ランク相当）"""
        result = make_calc_result_with_dash(booster_param=140.0)
        params = assemble_agent_params(result)
        assert params["boost_max"] == 140

    def test_boost_max_e_minus_rank(self):
        """draw.body.booster.param=55.0 → boost_max=55（E- ランク相当）"""
        result = make_calc_result_with_dash(booster_param=55.0)
        params = assemble_agent_params(result)
        assert params["boost_max"] == 55

    def test_missing_booster_uses_default(self):
        """draw.body.booster がない → default_boost_max を使う"""
        result = make_calc_result()
        params = assemble_agent_params(result, default_boost_max=80)
        assert params["boost_max"] == 80

    def test_missing_booster_default_is_zero(self):
        """booster なし・default 未指定 → boost_max=0（後方互換）"""
        result = make_calc_result()
        params = assemble_agent_params(result)
        assert params["boost_max"] == 0

    def test_boost_max_is_int(self):
        """boost_max は整数型"""
        result = make_calc_result_with_dash(booster_param=90.0)
        params = assemble_agent_params(result)
        assert isinstance(params["boost_max"], int)


# ─────────────────────────────────────────
# boost_regen の計算テスト
# ─────────────────────────────────────────
class TestAssembleBoostRegen:

    def test_boost_regen_nonzero_when_boost_max_positive(self):
        """boost_max > 0 → boost_regen = BOOST_REGEN_PER_STEP（15.0）"""
        result = make_calc_result_with_dash(booster_param=90.0)
        params = assemble_agent_params(result)
        from constants import BOOST_REGEN_PER_STEP
        assert params["boost_regen"] == pytest.approx(BOOST_REGEN_PER_STEP)

    def test_boost_regen_zero_when_boost_max_zero(self):
        """boost_max=0 → boost_regen=0.0（後方互換）"""
        result = make_calc_result()
        params = assemble_agent_params(result)
        assert params["boost_regen"] == pytest.approx(0.0)

    def test_boost_regen_is_float(self):
        """boost_regen は float 型"""
        result = make_calc_result_with_dash(booster_param=90.0)
        params = assemble_agent_params(result)
        assert isinstance(params["boost_regen"], float)


# ─────────────────────────────────────────
# T-4: clip / reload_steps の抽出テスト
# ─────────────────────────────────────────
class TestAssembleReload:

    def test_clip_extracted_from_weapon(self):
        """weapons.main.clip=30 → params["clip"]=30"""
        result = make_calc_result()
        result["weapons"]["main"]["clip"] = 30
        params = assemble_agent_params(result)
        assert params["clip"] == 30

    def test_reload_steps_extracted_from_weapon(self):
        """weapons.main.reload=2.5 → params["reload_steps"]=round(2.5)=2"""
        result = make_calc_result()
        result["weapons"]["main"]["reload"] = 2.5
        params = assemble_agent_params(result)
        assert params["reload_steps"] == 2

    def test_clip_zero_when_weapon_data_missing(self):
        """weapons.main に clip がない → clip=0（後方互換・無限弾）"""
        result = make_calc_result()
        params = assemble_agent_params(result)
        assert params["clip"] == 0
        assert params["reload_steps"] == 0


# ─────────────────────────────────────────
# T-5: arm.reloadRate による reload_steps 調整テスト
# ─────────────────────────────────────────
def make_calc_result_with_reload_rate(
    reload_val: float = 2.0,
    reload_rate_param: float = 100.0,
    **kwargs,
) -> dict:
    """draw.arm.reloadRate.param を持つ calc_result を返す"""
    result = make_calc_result(**kwargs)
    result["weapons"]["main"]["reload"] = reload_val
    result["draw"]["arm"] = {"reloadRate": {"param": reload_rate_param}}
    return result


class TestAssembleReloadRate:

    def test_reload_rate_100_no_change(self):
        """reloadRate.param=100（C-ランク）→ reload_steps 変化なし"""
        result = make_calc_result_with_reload_rate(reload_val=2.5, reload_rate_param=100.0)
        params = assemble_agent_params(result)
        assert params["reload_steps"] == round(2.5 * 100.0 / 100)  # 2

    def test_reload_rate_b_rank_shortens(self):
        """reloadRate.param=82（Bランク）→ round(2.5 × 0.82) = 2"""
        result = make_calc_result_with_reload_rate(reload_val=2.5, reload_rate_param=82.0)
        params = assemble_agent_params(result)
        assert params["reload_steps"] == round(2.5 * 82.0 / 100)  # 2

    def test_reload_rate_s_minus_shortens_significantly(self):
        """reloadRate.param=59.5（S-ランク）→ round(2.0 × 0.595) = 1"""
        result = make_calc_result_with_reload_rate(reload_val=2.0, reload_rate_param=59.5)
        params = assemble_agent_params(result)
        assert params["reload_steps"] == round(2.0 * 59.5 / 100)  # 1

    def test_reload_rate_e_minus_extends(self):
        """reloadRate.param=140（E-ランク）→ round(2.0 × 1.40) = 3"""
        result = make_calc_result_with_reload_rate(reload_val=2.0, reload_rate_param=140.0)
        params = assemble_agent_params(result)
        assert params["reload_steps"] == round(2.0 * 140.0 / 100)  # 3

    def test_reload_rate_missing_arm_backward_compat(self):
        """arm フィールドが欠損 → reload_rate=100%（後方互換）"""
        result = make_calc_result()
        result["weapons"]["main"]["reload"] = 2.0
        # draw.arm なし → デフォルト 100.0 適用
        params = assemble_agent_params(result)
        assert params["reload_steps"] == 2  # round(2.0 × 1.00)
