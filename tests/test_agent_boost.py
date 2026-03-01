"""
tests/test_agent_boost.py
Agent のブーストゲージ状態変数テスト

テスト対象:
  - boost_max / boost / boost_regen / walk_cells_per_step / dash_cells_per_step / is_cruising
    の初期値が正しい
  - boost_max=0（デフォルト）時は後方互換
"""
import pytest
from simulation import Agent, CELLS_PER_STEP


# ─────────────────────────────────────────
# デフォルト値テスト
# ─────────────────────────────────────────
class TestAgentBoostDefaults:

    def test_boost_max_default_is_zero(self):
        """boost_max のデフォルトは 0（ブーストシステム無効）"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.boost_max == 0

    def test_boost_default_is_zero(self):
        """boost_max=0 のとき boost=0.0"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.boost == 0.0

    def test_boost_regen_default_is_zero(self):
        """boost_regen のデフォルトは 0.0"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.boost_regen == 0.0

    def test_walk_cells_per_step_default_is_one(self):
        """walk_cells_per_step のデフォルトは 1"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.walk_cells_per_step == 1

    def test_dash_cells_per_step_default_matches_cells_per_step(self):
        """dash_cells_per_step のデフォルトは CELLS_PER_STEP（=2）"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.dash_cells_per_step == CELLS_PER_STEP

    def test_is_cruising_default_is_false(self):
        """is_cruising のデフォルトは False"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.is_cruising is False


# ─────────────────────────────────────────
# boost_max 設定時の初期値
# ─────────────────────────────────────────
class TestAgentBoostInit:

    def test_boost_max_90_sets_boost_to_90(self):
        """boost_max=90 → boost=90.0（フルスタート）"""
        a = Agent(agent_id=1, x=0, y=0, team=0, boost_max=90)
        assert a.boost == 90.0

    def test_boost_max_140_sets_boost_to_140(self):
        """boost_max=140 → boost=140.0"""
        a = Agent(agent_id=1, x=0, y=0, team=0, boost_max=140)
        assert a.boost == 140.0

    def test_boost_max_55_sets_boost_to_55(self):
        """boost_max=55（E- ランク相当）→ boost=55.0"""
        a = Agent(agent_id=1, x=0, y=0, team=0, boost_max=55)
        assert a.boost == 55.0

    def test_boost_is_float(self):
        """boost は float 型"""
        a = Agent(agent_id=1, x=0, y=0, team=0, boost_max=90)
        assert isinstance(a.boost, float)

    def test_boost_regen_set(self):
        """boost_regen を指定するとセットされる"""
        a = Agent(agent_id=1, x=0, y=0, team=0, boost_max=90, boost_regen=15.0)
        assert a.boost_regen == pytest.approx(15.0)

    def test_walk_cells_per_step_set(self):
        """walk_cells_per_step を指定するとセットされる"""
        a = Agent(agent_id=1, x=0, y=0, team=0, walk_cells_per_step=1)
        assert a.walk_cells_per_step == 1

    def test_dash_cells_per_step_set(self):
        """dash_cells_per_step=3 → 3 がセットされる（S ランク脚部相当）"""
        a = Agent(agent_id=1, x=0, y=0, team=0, dash_cells_per_step=3)
        assert a.dash_cells_per_step == 3

    def test_custom_walk_and_dash_cells(self):
        """walk=1, dash=3 を同時に指定できる"""
        a = Agent(agent_id=1, x=0, y=0, team=0,
                  boost_max=100, boost_regen=15.0,
                  walk_cells_per_step=1, dash_cells_per_step=3)
        assert a.walk_cells_per_step == 1
        assert a.dash_cells_per_step == 3

    def test_is_cruising_starts_false(self):
        """boost_max > 0 でも is_cruising は False でスタート"""
        a = Agent(agent_id=1, x=0, y=0, team=0, boost_max=90)
        assert a.is_cruising is False
