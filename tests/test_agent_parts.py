"""
tests/test_agent_parts.py
Agent クラスの per-agent パラメータ（パーツ由来）のテスト

テスト対象:
  - Agent の dps / search_range_c / lockon_range_c / cells_per_step 属性
  - デフォルト値がグローバル定数と一致すること（後方互換性）
  - カスタム値を渡したとき正しくインスタンス変数に格納されること
  - in_search_range / in_lockon_range がインスタンス変数を使うこと
"""
import pytest
from simulation import (
    Agent,
    DPS, HIT_RATE, SEARCH_RANGE_C, LOCKON_RANGE_C, CELLS_PER_STEP,
)


# ─────────────────────────────────────────
# テスト用ファクトリ
# ─────────────────────────────────────────
def make_agent(agent_id=1, x=5, y=25, team=0, **kwargs) -> Agent:
    return Agent(agent_id=agent_id, x=x, y=y, team=team, **kwargs)


# ─────────────────────────────────────────
# デフォルト値テスト（後方互換性）
# ─────────────────────────────────────────
class TestAgentPerAgentParamDefaults:
    def test_dps_default(self):
        """dps のデフォルトは グローバル定数 DPS"""
        assert make_agent().dps == DPS

    def test_search_range_c_default(self):
        """search_range_c のデフォルトは SEARCH_RANGE_C"""
        assert make_agent().search_range_c == SEARCH_RANGE_C

    def test_lockon_range_c_default(self):
        """lockon_range_c のデフォルトは LOCKON_RANGE_C"""
        assert make_agent().lockon_range_c == LOCKON_RANGE_C

    def test_cells_per_step_default(self):
        """cells_per_step のデフォルトは CELLS_PER_STEP"""
        assert make_agent().cells_per_step == CELLS_PER_STEP


# ─────────────────────────────────────────
# カスタム値テスト
# ─────────────────────────────────────────
class TestAgentPerAgentParamCustom:
    def test_custom_dps(self):
        """dps にカスタム値を渡せる"""
        a = make_agent(dps=5000)
        assert a.dps == 5000

    def test_custom_dps_zero_is_allowed(self):
        """dps=0 も受け付ける"""
        a = make_agent(dps=0)
        assert a.dps == 0

    def test_custom_search_range_c(self):
        """search_range_c にカスタム値を渡せる"""
        a = make_agent(search_range_c=12.0)
        assert a.search_range_c == 12.0

    def test_custom_search_range_c_float(self):
        """search_range_c は float 精度で保持される"""
        a = make_agent(search_range_c=7.5)
        assert a.search_range_c == pytest.approx(7.5)

    def test_custom_lockon_range_c(self):
        """lockon_range_c にカスタム値を渡せる"""
        a = make_agent(lockon_range_c=4.0)
        assert a.lockon_range_c == 4.0

    def test_custom_lockon_range_c_float(self):
        """lockon_range_c は float 精度で保持される"""
        a = make_agent(lockon_range_c=5.5)
        assert a.lockon_range_c == pytest.approx(5.5)

    def test_custom_cells_per_step(self):
        """cells_per_step にカスタム値を渡せる"""
        a = make_agent(cells_per_step=3)
        assert a.cells_per_step == 3

    def test_custom_cells_per_step_one(self):
        """cells_per_step=1 も有効"""
        a = make_agent(cells_per_step=1)
        assert a.cells_per_step == 1

    def test_all_params_combined(self):
        """4つ全部同時に指定できる"""
        a = make_agent(dps=4000, search_range_c=10.0, lockon_range_c=5.0, cells_per_step=3)
        assert a.dps == 4000
        assert a.search_range_c == 10.0
        assert a.lockon_range_c == 5.0
        assert a.cells_per_step == 3


# ─────────────────────────────────────────
# 既存パラメータへの無影響確認
# ─────────────────────────────────────────
class TestAgentMaxHpKwarg:
    """max_hp キーワード引数のテスト"""

    def test_default_max_hp_equals_agent_hp(self):
        """max_hp 未指定時のデフォルトは AGENT_HP"""
        from simulation import AGENT_HP
        a = make_agent()
        assert a.max_hp == AGENT_HP

    def test_custom_max_hp_is_stored(self):
        """max_hp を指定するとその値が格納される"""
        a = make_agent(max_hp=15000)
        assert a.max_hp == 15000

    def test_custom_max_hp_initializes_hp(self):
        """max_hp を指定すると hp も同値で初期化される"""
        a = make_agent(max_hp=8000)
        assert a.hp == 8000

    def test_low_max_hp(self):
        """max_hp=7246（E- 装甲相当）を指定できる"""
        a = make_agent(max_hp=7246)
        assert a.max_hp == 7246
        assert a.hp == 7246

    def test_high_max_hp(self):
        """max_hp=15873（S 装甲相当）を指定できる"""
        a = make_agent(max_hp=15873)
        assert a.max_hp == 15873

    def test_max_hp_does_not_affect_other_attrs(self):
        """max_hp を変えても dps / team / role などは変わらない"""
        from simulation import DPS, Role
        a = make_agent(max_hp=12000)
        assert a.dps == DPS
        assert a.team == 0
        assert a.role == Role.ASSAULT


class TestAgentPerAgentParamNoSideEffects:
    def test_custom_params_do_not_affect_hp(self):
        """カスタム dps は hp/max_hp に影響しない"""
        from simulation import AGENT_HP
        a = make_agent(dps=9999)
        assert a.hp == AGENT_HP
        assert a.max_hp == AGENT_HP

    def test_custom_params_do_not_affect_alive(self):
        """カスタムパラメータは alive に影響しない"""
        a = make_agent(dps=9999, cells_per_step=5)
        assert a.alive is True

    def test_custom_params_do_not_affect_team(self):
        """カスタムパラメータは team に影響しない"""
        a = make_agent(team=1, dps=1000)
        assert a.team == 1


# ─────────────────────────────────────────
# in_search_range がインスタンス変数を使うテスト
# ─────────────────────────────────────────
class TestInSearchRangeUsesInstanceVar:
    def test_extended_range_detects_far_agent(self):
        """search_range_c=10.0 の索敵者は距離9.0の敵を検知できる"""
        # (0,0) と (9,0) → dist=9.0
        a = make_agent(agent_id=1, x=0, y=0, team=0, search_range_c=10.0)
        b = make_agent(agent_id=2, x=9, y=0, team=1)
        assert a.in_search_range(b)  # 10.0 >= 9.0

    def test_default_range_cannot_detect_far_agent(self):
        """デフォルト(8.0)では距離9.0の敵を検知できない"""
        a = make_agent(agent_id=1, x=0, y=0, team=0)  # search_range_c=8.0
        b = make_agent(agent_id=2, x=9, y=0, team=1)
        assert not a.in_search_range(b)  # 8.0 < 9.0

    def test_narrow_range_cannot_detect_within_default(self):
        """search_range_c=5.0 では距離6.0の敵を検知できない"""
        a = make_agent(agent_id=1, x=0, y=0, team=0, search_range_c=5.0)
        b = make_agent(agent_id=2, x=6, y=0, team=1)
        assert not a.in_search_range(b)  # 5.0 < 6.0

    def test_search_range_exactly_at_boundary(self):
        """search_range_c と距離が完全一致するとき True（以下）"""
        a = make_agent(agent_id=1, x=0, y=0, team=0, search_range_c=6.0)
        b = make_agent(agent_id=2, x=6, y=0, team=1)
        assert a.in_search_range(b)  # dist=6.0, range=6.0 → True

    def test_search_range_does_not_affect_other_agent(self):
        """索敵者の search_range_c は相手の範囲に影響しない"""
        # a は広い search_range_c=10.0, b はデフォルト
        a = make_agent(agent_id=1, x=0, y=0, team=0, search_range_c=10.0)
        b = make_agent(agent_id=2, x=9, y=0, team=1)
        # a から b は検知できるが、b から a は距離9.0でデフォルト8.0では検知できない
        assert a.in_search_range(b)
        assert not b.in_search_range(a)


# ─────────────────────────────────────────
# in_lockon_range がインスタンス変数を使うテスト
# ─────────────────────────────────────────
class TestInLockonRangeUsesInstanceVar:
    def test_extended_range_lockons_far_agent(self):
        """lockon_range_c=7.0 のエージェントは距離7.0の敵をロックオンできる"""
        a = make_agent(agent_id=1, x=0, y=0, team=0, lockon_range_c=7.0)
        b = make_agent(agent_id=2, x=7, y=0, team=1)
        assert a.in_lockon_range(b)  # 7.0 >= 7.0

    def test_default_range_cannot_lockon_far_agent(self):
        """デフォルト(6.0)では距離7.0の敵をロックオンできない"""
        a = make_agent(agent_id=1, x=0, y=0, team=0)  # lockon_range_c=6.0
        b = make_agent(agent_id=2, x=7, y=0, team=1)
        assert not a.in_lockon_range(b)  # 6.0 < 7.0

    def test_narrow_lockon_cannot_reach_within_default(self):
        """lockon_range_c=4.0 では距離5.0の敵をロックオンできない"""
        a = make_agent(agent_id=1, x=0, y=0, team=0, lockon_range_c=4.0)
        b = make_agent(agent_id=2, x=5, y=0, team=1)
        assert not a.in_lockon_range(b)  # 4.0 < 5.0

    def test_lockon_range_exactly_at_boundary(self):
        """lockon_range_c と距離が完全一致するとき True（以下）"""
        a = make_agent(agent_id=1, x=0, y=0, team=0, lockon_range_c=5.0)
        b = make_agent(agent_id=2, x=5, y=0, team=1)
        assert a.in_lockon_range(b)  # dist=5.0, range=5.0 → True

    def test_lockon_range_does_not_affect_other_agent(self):
        """ロックオン側の lockon_range_c は相手の範囲に影響しない"""
        a = make_agent(agent_id=1, x=0, y=0, team=0, lockon_range_c=7.0)
        b = make_agent(agent_id=2, x=7, y=0, team=1)
        assert a.in_lockon_range(b)
        assert not b.in_lockon_range(a)


# ─────────────────────────────────────────
# hit_rate のテスト
# ─────────────────────────────────────────
class TestAgentHitRateKwarg:

    def test_default_hit_rate_equals_constant(self):
        """hit_rate 未指定のデフォルトは HIT_RATE 定数と一致"""
        a = make_agent()
        assert a.hit_rate == HIT_RATE

    def test_custom_hit_rate_is_stored(self):
        """カスタム hit_rate が保存される"""
        a = make_agent(hit_rate=0.95)
        assert a.hit_rate == pytest.approx(0.95)

    def test_low_hit_rate_is_stored(self):
        """低い hit_rate (0.40) も保存される"""
        a = make_agent(hit_rate=0.40)
        assert a.hit_rate == pytest.approx(0.40)

    def test_hit_rate_one_is_stored(self):
        """hit_rate=1.0 も保存される"""
        a = make_agent(hit_rate=1.0)
        assert a.hit_rate == pytest.approx(1.0)

    def test_hit_rate_zero_is_stored(self):
        """hit_rate=0.0 も保存される"""
        a = make_agent(hit_rate=0.0)
        assert a.hit_rate == pytest.approx(0.0)

    def test_hit_rate_does_not_affect_hp(self):
        """hit_rate は hp/max_hp に影響しない"""
        from simulation import AGENT_HP
        a = make_agent(hit_rate=0.60)
        assert a.hp == AGENT_HP
        assert a.max_hp == AGENT_HP

    def test_hit_rate_does_not_affect_team(self):
        """hit_rate は team に影響しない"""
        a = make_agent(team=1, hit_rate=0.75)
        assert a.team == 1


# ─────────────────────────────────────────
# shots_per_step のテスト
# ─────────────────────────────────────────
class TestAgentShotsPerStepKwarg:

    def test_default_shots_per_step_is_one(self):
        """shots_per_step 未指定のデフォルトは 1"""
        a = make_agent()
        assert a.shots_per_step == 1

    def test_custom_shots_per_step_is_stored(self):
        """カスタム shots_per_step が保存される"""
        a = make_agent(shots_per_step=3)
        assert a.shots_per_step == 3

    def test_shots_per_step_high_value(self):
        """shots_per_step=10 も保存される"""
        a = make_agent(shots_per_step=10)
        assert a.shots_per_step == 10

    def test_shots_per_step_does_not_affect_hp(self):
        """shots_per_step は hp に影響しない"""
        from simulation import AGENT_HP
        a = make_agent(shots_per_step=5)
        assert a.hp == AGENT_HP

    def test_all_new_params_combined(self):
        """hit_rate と shots_per_step を同時に指定できる"""
        a = make_agent(hit_rate=0.90, shots_per_step=4)
        assert a.hit_rate == pytest.approx(0.90)
        assert a.shots_per_step == 4
