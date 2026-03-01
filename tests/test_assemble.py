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
from simulation import Agent, AGENT_HP, DPS, SEARCH_RANGE_C, LOCKON_RANGE_C, CELLS_PER_STEP


# ─────────────────────────────────────────
# テスト用の最小 calc_result フィクスチャ
# ─────────────────────────────────────────
def make_calc_result(
    walk_mps: float = 21.9,
    sakuteki_m: float = 80.0,
    lockon_m: float = 60.0,
    dps_per_sec: int = 3000,
    armor_avg_param: float = 1.0,
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
            },
        },
        "weapons": {
            "main": {"damagePerSec": [dps_per_sec]},
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
        """sakuteki=80.0m → search_range_c = 8.0 (80/10)"""
        result = make_calc_result(sakuteki_m=80.0)
        params = assemble_agent_params(result)
        assert params["search_range_c"] == pytest.approx(8.0)

    def test_search_range_c_scaled_by_cell_size(self):
        """sakuteki=120.0m → search_range_c = 12.0"""
        result = make_calc_result(sakuteki_m=120.0)
        params = assemble_agent_params(result)
        assert params["search_range_c"] == pytest.approx(12.0)

    def test_search_range_c_small_value(self):
        """sakuteki=50.0m → search_range_c = 5.0"""
        result = make_calc_result(sakuteki_m=50.0)
        params = assemble_agent_params(result)
        assert params["search_range_c"] == pytest.approx(5.0)

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
        """lockOn=60.0m → lockon_range_c = 6.0 (60/10)"""
        result = make_calc_result(lockon_m=60.0)
        params = assemble_agent_params(result)
        assert params["lockon_range_c"] == pytest.approx(6.0)

    def test_lockon_range_c_scaled_by_cell_size(self):
        """lockOn=90.0m → lockon_range_c = 9.0"""
        result = make_calc_result(lockon_m=90.0)
        params = assemble_agent_params(result)
        assert params["lockon_range_c"] == pytest.approx(9.0)

    def test_lockon_range_c_small_value(self):
        """lockOn=40.0m → lockon_range_c = 4.0"""
        result = make_calc_result(lockon_m=40.0)
        params = assemble_agent_params(result)
        assert params["lockon_range_c"] == pytest.approx(4.0)

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
        """walk=21.9m/s → round(21.9/10)=2 → cells_per_step=2"""
        result = make_calc_result(walk_mps=21.9)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 2

    def test_cells_per_step_high_speed(self):
        """walk=31.5m/s → round(31.5/10)=3 → cells_per_step=3"""
        result = make_calc_result(walk_mps=31.5)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 3

    def test_cells_per_step_low_speed(self):
        """walk=14.0m/s → round(14.0/10)=1 → cells_per_step=1"""
        result = make_calc_result(walk_mps=14.0)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 1

    def test_cells_per_step_very_slow_minimum_is_1(self):
        """walk=3.0m/s → round(0.3)=0 → max(1,0)=1 → cells_per_step=1（最低値）"""
        result = make_calc_result(walk_mps=3.0)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 1

    def test_cells_per_step_very_fast(self):
        """walk=45.0m/s → round(4.5)=4 → cells_per_step=4"""
        result = make_calc_result(walk_mps=45.0)
        params = assemble_agent_params(result)
        assert params["cells_per_step"] == 4

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
        """5つの必須キーが含まれる"""
        result = make_calc_result()
        params = assemble_agent_params(result)
        assert "max_hp" in params
        assert "dps" in params
        assert "search_range_c" in params
        assert "lockon_range_c" in params
        assert "cells_per_step" in params

    def test_no_extra_keys(self):
        """余分なキーが含まれない"""
        result = make_calc_result()
        params = assemble_agent_params(result)
        assert set(params.keys()) == {"max_hp", "dps", "search_range_c", "lockon_range_c", "cells_per_step"}

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

    def test_fully_missing_result_all_defaults(self):
        """空の dict → 全フィールドがデフォルト値"""
        params = assemble_agent_params({})
        assert params["max_hp"] == AGENT_HP
        assert params["dps"] == DPS
        assert params["search_range_c"] == SEARCH_RANGE_C
        assert params["lockon_range_c"] == LOCKON_RANGE_C
        assert params["cells_per_step"] == CELLS_PER_STEP

    def test_custom_defaults_are_used_when_fields_missing(self):
        """カスタム default 値が欠損時に正しく使われる"""
        params = assemble_agent_params(
            {},
            default_max_hp=9999,
            default_dps=1234,
            default_search_range_c=11.0,
            default_lockon_range_c=7.5,
            default_cells_per_step=4,
        )
        assert params["max_hp"] == 9999
        assert params["dps"] == 1234
        assert params["search_range_c"] == pytest.approx(11.0)
        assert params["lockon_range_c"] == pytest.approx(7.5)
        assert params["cells_per_step"] == 4
