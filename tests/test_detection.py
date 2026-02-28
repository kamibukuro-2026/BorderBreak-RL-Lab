"""
tests/test_detection.py
エージェントの被索敵状態（detected / exposure_steps）の単体テスト

テスト対象:
  - Agent の初期属性: detected=False, exposure_steps=0
  - Simulation._update_detection() の挙動
      - 索敵範囲外の敵 / 死亡敵 / 同チーム → 変化なし
      - 索敵範囲内1〜2ステップ: exposure_steps 増加, detected=False
      - 索敵範囲内3ステップ到達: detected=True
      - 範囲外に出ると: exposure_steps=0, detected=False
      - ロックオン: 即座に detected=True（exposure_steps に関わらず）
      - 死亡エージェント: exposure_steps=0, detected=False にリセット

定数（SEARCH_RANGE_C=8.0, LOCKON_RANGE_C=6.0, DETECTION_STEPS=3）
エージェント固定位置 (5, 25) に対する敵配置:
  SEARCH_ONLY: (5, 32)  dist=7  索敵範囲内・ロックオン外
  LOCKON_POS : (5, 30)  dist=5  ロックオン範囲内
  OUT_OF_POS : (5, 34)  dist=9  索敵範囲外
"""
import pytest
from simulation import (
    Agent, Map, Simulation,
    DETECTION_STEPS,
    MAP_W, MAP_H,
)


# ─────────────────────────────────────────
# テスト用ファクトリ
# ─────────────────────────────────────────
def make_map() -> Map:
    return Map(MAP_W, MAP_H)


def make_agent(agent_id=1, x=5, y=25, team=0, alive=True) -> Agent:
    a = Agent(agent_id=agent_id, x=x, y=y, team=team)
    a.alive = alive
    return a


def make_sim(*agents) -> Simulation:
    sim = Simulation(make_map(), [])
    for a in agents:
        sim.add_agent(a)
    return sim


# ─────────────────────────────────────────
# Agent 初期属性
# ─────────────────────────────────────────
class TestAgentDetectionInit:
    def test_detected_initial_false(self):
        """初期状態の detected は False"""
        assert make_agent().detected is False

    def test_exposure_steps_initial_zero(self):
        """初期状態の exposure_steps は 0"""
        assert make_agent().exposure_steps == 0


# ─────────────────────────────────────────
# 脅威なし → 変化なし
# ─────────────────────────────────────────
class TestUpdateDetectionNoThreat:
    def test_no_agents_no_change(self):
        """エージェントのみ（敵なし）→ 変化なし"""
        agent = make_agent()
        sim   = make_sim(agent)
        sim._update_detection()
        assert agent.detected is False
        assert agent.exposure_steps == 0

    def test_ally_in_range_does_not_trigger(self):
        """同チームが索敵範囲内でも変化なし"""
        agent = make_agent(1, x=5, y=25, team=0)
        ally  = make_agent(2, x=5, y=32, team=0)   # dist=7, 同チーム
        sim   = make_sim(agent, ally)
        sim._update_detection()
        assert agent.detected is False
        assert agent.exposure_steps == 0

    def test_enemy_out_of_search_range_no_change(self):
        """索敵範囲外(dist=9)の敵は検知しない"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=34, team=1)   # dist=9 > 8
        sim   = make_sim(agent, enemy)
        sim._update_detection()
        assert agent.detected is False
        assert agent.exposure_steps == 0

    def test_dead_enemy_does_not_trigger(self):
        """死亡している敵は検知に使わない"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=30, team=1, alive=False)  # LO内だが死亡
        sim   = make_sim(agent, enemy)
        sim._update_detection()
        assert agent.detected is False
        assert agent.exposure_steps == 0


# ─────────────────────────────────────────
# 索敵範囲内（ロックオン外）の連続ステップ
# ─────────────────────────────────────────
class TestUpdateDetectionSearchRange:
    """エージェント(5,25)、敵(5,32) dist=7: 索敵範囲内・ロックオン外"""

    def setup_method(self):
        self.agent = make_agent(1, x=5, y=25, team=0)
        self.enemy = make_agent(2, x=5, y=32, team=1)  # dist=7
        self.sim   = make_sim(self.agent, self.enemy)

    def test_one_step_exposure_increments_not_detected(self):
        """1ステップ目: exposure_steps=1, detected=False"""
        self.sim._update_detection()
        assert self.agent.exposure_steps == 1
        assert self.agent.detected is False

    def test_two_steps_exposure_increments_not_detected(self):
        """2ステップ目: exposure_steps=2, detected=False"""
        self.sim._update_detection()
        self.sim._update_detection()
        assert self.agent.exposure_steps == 2
        assert self.agent.detected is False

    def test_three_steps_triggers_detection(self):
        """DETECTION_STEPS（3）ステップ目: detected=True"""
        for _ in range(DETECTION_STEPS):
            self.sim._update_detection()
        assert self.agent.exposure_steps == DETECTION_STEPS
        assert self.agent.detected is True

    def test_beyond_threshold_keeps_detected(self):
        """しきい値超過後も detected=True 継続"""
        for _ in range(DETECTION_STEPS + 2):
            self.sim._update_detection()
        assert self.agent.detected is True


# ─────────────────────────────────────────
# 範囲外に出ると状態リセット
# ─────────────────────────────────────────
class TestUpdateDetectionReset:
    def test_exposure_resets_when_enemy_leaves_search_range(self):
        """敵が索敵範囲外に移動すると exposure_steps=0"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=32, team=1)   # dist=7
        sim   = make_sim(agent, enemy)
        sim._update_detection()                     # exposure_steps=1
        enemy.y = 34                                # dist=9 → 範囲外
        sim._update_detection()
        assert agent.exposure_steps == 0
        assert agent.detected is False

    def test_detected_clears_after_three_steps_then_enemy_leaves(self):
        """3ステップ検知後に敵が範囲外へ → detected=False"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=32, team=1)
        sim   = make_sim(agent, enemy)
        for _ in range(DETECTION_STEPS):
            sim._update_detection()
        assert agent.detected is True
        enemy.y = 34                                # 範囲外
        sim._update_detection()
        assert agent.detected is False
        assert agent.exposure_steps == 0

    def test_exposure_restarts_from_zero_after_gap(self):
        """範囲外を1ステップ挟むと exposure_steps が 1 から再カウント"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=32, team=1)
        sim   = make_sim(agent, enemy)
        sim._update_detection()                     # exposure_steps=1
        sim._update_detection()                     # exposure_steps=2
        enemy.y = 34                                # 範囲外
        sim._update_detection()                     # exposure_steps=0
        enemy.y = 32                                # 再び範囲内
        sim._update_detection()                     # exposure_steps=1（再スタート）
        assert agent.exposure_steps == 1
        assert agent.detected is False


# ─────────────────────────────────────────
# ロックオン → 即座に detected=True
# ─────────────────────────────────────────
class TestUpdateDetectionLockon:
    def test_lockon_triggers_detected_immediately(self):
        """ロックオン範囲内(dist=5)の敵がいると1ステップで detected=True"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=30, team=1)   # dist=5 ≤ 6
        sim   = make_sim(agent, enemy)
        sim._update_detection()
        assert agent.detected is True

    def test_lockon_triggers_at_exact_boundary(self):
        """ロックオン境界ちょうど(dist=6) → detected=True"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=31, team=1)   # dist=6 = LOCKON_RANGE_C
        sim   = make_sim(agent, enemy)
        sim._update_detection()
        assert agent.detected is True

    def test_lockon_increments_exposure_steps_too(self):
        """ロックオン範囲内は索敵範囲内でもあるので exposure_steps もインクリメント"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=30, team=1)   # dist=5
        sim   = make_sim(agent, enemy)
        sim._update_detection()
        assert agent.exposure_steps == 1
        assert agent.detected is True

    def test_detected_clears_when_lockon_moves_to_search_only_below_threshold(self):
        """ロックオン解除（索敵内・LO外）でexposure_stepsがしきい値未満なら detected=False"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=30, team=1)   # dist=5, LO内
        sim   = make_sim(agent, enemy)
        sim._update_detection()                     # exposure_steps=1, detected=True
        enemy.y = 32                                # dist=7, 索敵内・LO外
        sim._update_detection()                     # exposure_steps=2, locked_on=False
        assert agent.exposure_steps == 2
        assert agent.detected is False              # 2 < DETECTION_STEPS


# ─────────────────────────────────────────
# 死亡エージェントの状態管理
# ─────────────────────────────────────────
class TestUpdateDetectionDeadAgent:
    def test_dead_agent_detected_is_false(self):
        """死亡エージェントはロックオン内の敵がいても detected=False"""
        agent = make_agent(1, x=5, y=25, team=0, alive=False)
        enemy = make_agent(2, x=5, y=30, team=1)   # LO内
        sim   = make_sim(agent, enemy)
        sim._update_detection()
        assert agent.detected is False

    def test_dead_agent_exposure_steps_reset(self):
        """死亡エージェントの exposure_steps は 0 にリセット"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=32, team=1)
        sim   = make_sim(agent, enemy)
        sim._update_detection()                     # exposure_steps=1
        sim._update_detection()                     # exposure_steps=2
        agent.alive = False
        sim._update_detection()
        assert agent.exposure_steps == 0
        assert agent.detected is False

    def test_detected_state_clears_on_death(self):
        """3ステップ検知後に死亡 → detected=False, exposure_steps=0"""
        agent = make_agent(1, x=5, y=25, team=0)
        enemy = make_agent(2, x=5, y=32, team=1)
        sim   = make_sim(agent, enemy)
        for _ in range(DETECTION_STEPS):
            sim._update_detection()
        assert agent.detected is True
        agent.alive = False
        sim._update_detection()
        assert agent.detected is False
        assert agent.exposure_steps == 0
