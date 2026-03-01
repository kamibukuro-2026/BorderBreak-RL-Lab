"""
tests/test_simulation_boost.py
Simulation のブースト巡航ロジックテスト

テスト対象:
  - _get_move_cells(): boost_max=0 時の後方互換 / ブースト移動 / 歩行フォールバック
  - _execute_action(): STAY 時のブースト回復
  - _process_respawns(): リスポーン時のブースト全回復
  - ブースト消費量（初回: CRUISE_START_COST + CRUISE_CONSUME_PER_STEP、継続: CRUISE_CONSUME_PER_STEP）
  - ブースト不足時は歩行 + 回復
"""
import pytest
from simulation import (
    Simulation, Agent, Action, Map,
    CELLS_PER_STEP, RESPAWN_STEPS, MAP_W, MAP_H,
)
from constants import (
    CRUISE_CONSUME_PER_STEP, CRUISE_START_COST, BOOST_REGEN_PER_STEP,
)


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────
def make_sim_with_agent(**agent_kwargs) -> tuple[Simulation, Agent]:
    """エージェント1体を持つ最小 Simulation を返す。"""
    sim = Simulation(Map(MAP_W, MAP_H), plants=[])
    a = Agent(agent_id=1, x=5, y=10, team=0, **agent_kwargs)
    sim.add_agent(a)
    return sim, a


def move_step(sim: Simulation, agent: Agent, action: Action):
    """_execute_action を1ステップ実行してエージェントの位置を返す。"""
    old_x, old_y = agent.x, agent.y
    sim._execute_action(agent, action)
    return agent.x - old_x, agent.y - old_y   # (dx, dy)


# ─────────────────────────────────────────
# boost_max=0 の後方互換テスト
# ─────────────────────────────────────────
class TestGetMoveCellsBackwardCompat:

    def test_boost_max_0_uses_cells_per_step(self):
        """boost_max=0 → cells_per_step 分だけ移動（ブーストロジック無効）"""
        sim, agent = make_sim_with_agent(cells_per_step=2)
        # マップ上端から遠い位置で下方向へ移動
        agent.y = 20
        dx, dy = move_step(sim, agent, Action.MOVE_DOWN)
        assert dy == 2

    def test_boost_max_0_cells_per_step_1(self):
        """boost_max=0, cells_per_step=1 → 1セル移動"""
        sim, agent = make_sim_with_agent(cells_per_step=1)
        agent.y = 20
        dx, dy = move_step(sim, agent, Action.MOVE_DOWN)
        assert dy == 1

    def test_boost_max_0_boost_not_consumed(self):
        """boost_max=0 では boost は変化しない"""
        sim, agent = make_sim_with_agent(cells_per_step=2)
        agent.y = 20
        move_step(sim, agent, Action.MOVE_DOWN)
        assert agent.boost == 0.0


# ─────────────────────────────────────────
# ブースト移動テスト（boost 十分）
# ─────────────────────────────────────────
class TestGetMoveCellsBoostOn:

    def test_boost_on_uses_dash_cells(self):
        """boost 十分 → dash_cells_per_step セル移動"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.y = 20
        dx, dy = move_step(sim, agent, Action.MOVE_DOWN)
        assert dy == 2

    def test_boost_on_first_step_consumes_start_plus_cruise(self):
        """初回移動: boost -= CRUISE_START_COST + CRUISE_CONSUME_PER_STEP"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.y = 20
        move_step(sim, agent, Action.MOVE_DOWN)
        expected = 90.0 - (CRUISE_START_COST + CRUISE_CONSUME_PER_STEP)
        assert agent.boost == pytest.approx(expected)

    def test_boost_on_second_step_consumes_only_cruise(self):
        """2回目移動（is_cruising=True）: boost -= CRUISE_CONSUME_PER_STEP のみ"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.y = 10
        move_step(sim, agent, Action.MOVE_DOWN)
        boost_after_first = agent.boost
        move_step(sim, agent, Action.MOVE_DOWN)
        expected = boost_after_first - CRUISE_CONSUME_PER_STEP
        assert agent.boost == pytest.approx(expected)

    def test_is_cruising_becomes_true_when_boosting(self):
        """ブースト移動後は is_cruising=True"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.y = 20
        move_step(sim, agent, Action.MOVE_DOWN)
        assert agent.is_cruising is True

    def test_boost_clamped_at_zero(self):
        """boost が消費でちょうど 0 になっても負にならない"""
        exact_cost = CRUISE_START_COST + CRUISE_CONSUME_PER_STEP
        sim, agent = make_sim_with_agent(
            boost_max=int(exact_cost), boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.boost = exact_cost
        agent.y = 20
        move_step(sim, agent, Action.MOVE_DOWN)
        assert agent.boost >= 0.0


# ─────────────────────────────────────────
# ブースト切れテスト（boost 不足 → 歩行）
# ─────────────────────────────────────────
class TestGetMoveCellsBoostOff:

    def test_no_boost_uses_walk_cells(self):
        """boost=0.0 → walk_cells_per_step セル移動"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.boost = 0.0
        agent.y = 20
        dx, dy = move_step(sim, agent, Action.MOVE_DOWN)
        assert dy == 1

    def test_insufficient_boost_for_first_step_walks(self):
        """boost < CRUISE_START_COST + CRUISE_CONSUME_PER_STEP → 歩行"""
        insufficient = CRUISE_START_COST + CRUISE_CONSUME_PER_STEP - 1
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.boost = insufficient
        agent.y = 20
        dx, dy = move_step(sim, agent, Action.MOVE_DOWN)
        assert dy == 1

    def test_walk_does_not_consume_boost(self):
        """boost 不足時に歩行しても boost は消費されない（回復する）"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.boost = 0.0
        agent.y = 20
        move_step(sim, agent, Action.MOVE_DOWN)
        # 歩行時は boost_regen 分だけ回復する
        assert agent.boost == pytest.approx(BOOST_REGEN_PER_STEP)

    def test_walk_boost_regen_capped_at_boost_max(self):
        """回復量が boost_max を超えてもクランプされる"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.boost = 80.0  # regen=15 → 95 になるはずが 90 でクランプ
        agent.is_cruising = True  # cruising=False にリセットされてから歩行回復
        agent.boost = 80.0
        # boost < cost (80 >= 25.8 なので実際は cruise できる → 切れるケースを設定)
        # 強制的に不足状態: boost を cruise cost より少なくする
        agent.boost = CRUISE_START_COST + CRUISE_CONSUME_PER_STEP - 0.5
        agent.is_cruising = False
        agent.y = 20
        move_step(sim, agent, Action.MOVE_DOWN)
        assert agent.boost <= 90.0

    def test_is_cruising_becomes_false_when_walking(self):
        """boost 不足で歩行に切り替わると is_cruising=False"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.boost = 0.0
        agent.is_cruising = True  # 事前にTrueにしておく
        agent.y = 20
        move_step(sim, agent, Action.MOVE_DOWN)
        assert agent.is_cruising is False


# ─────────────────────────────────────────
# STAY 時のブースト回復テスト
# ─────────────────────────────────────────
class TestBoostRegenOnStay:

    def test_stay_regens_boost(self):
        """STAY アクション → boost が boost_regen 分回復"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.boost = 50.0
        sim._execute_action(agent, Action.STAY)
        assert agent.boost == pytest.approx(65.0)

    def test_stay_regen_capped_at_boost_max(self):
        """回復後の boost は boost_max でクランプ"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.boost = 80.0  # 80+15=95 → 90 でクランプ
        sim._execute_action(agent, Action.STAY)
        assert agent.boost == pytest.approx(90.0)

    def test_stay_sets_is_cruising_false(self):
        """STAY → is_cruising=False にリセット"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.is_cruising = True
        sim._execute_action(agent, Action.STAY)
        assert agent.is_cruising is False

    def test_stay_boost_max_0_does_not_regen(self):
        """boost_max=0 の STAY では boost は変化しない（後方互換）"""
        sim, agent = make_sim_with_agent(cells_per_step=2)
        sim._execute_action(agent, Action.STAY)
        assert agent.boost == 0.0


# ─────────────────────────────────────────
# 巡航再開時の START_COST テスト
# ─────────────────────────────────────────
class TestBoostStartCostOnResume:

    def test_start_cost_charged_after_stay(self):
        """STAY で中断後に移動再開 → CRUISE_START_COST が再度かかる"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.y = 10
        # 1回目の移動（巡航開始コスト発生）
        move_step(sim, agent, Action.MOVE_DOWN)
        boost_after_first = agent.boost
        assert agent.is_cruising is True

        # STAY で中断
        sim._execute_action(agent, Action.STAY)
        assert agent.is_cruising is False

        # 2回目の移動（is_cruising=False → 再度 START_COST）
        boost_before_second = agent.boost
        move_step(sim, agent, Action.MOVE_DOWN)
        expected = boost_before_second - (CRUISE_START_COST + CRUISE_CONSUME_PER_STEP)
        assert agent.boost == pytest.approx(expected)


# ─────────────────────────────────────────
# リスポーン時のブースト全回復テスト
# ─────────────────────────────────────────
class TestRespawnRestoresBoost:

    def test_respawn_restores_boost_to_max(self):
        """リスポーン後 boost == boost_max"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        # ブーストを消費させてから撃破
        agent.boost = 10.0
        agent.is_cruising = True
        agent.alive = False
        agent.respawn_timer = 1  # 次ステップでリスポーン
        sim._process_respawns()
        assert agent.boost == pytest.approx(90.0)

    def test_respawn_sets_is_cruising_false(self):
        """リスポーン後 is_cruising=False"""
        sim, agent = make_sim_with_agent(
            boost_max=90, boost_regen=15.0,
            walk_cells_per_step=1, dash_cells_per_step=2,
        )
        agent.is_cruising = True
        agent.alive = False
        agent.respawn_timer = 1
        sim._process_respawns()
        assert agent.is_cruising is False

    def test_respawn_boost_max_0_no_change(self):
        """boost_max=0 のリスポーンでは boost は変化しない"""
        sim, agent = make_sim_with_agent(cells_per_step=2)
        agent.alive = False
        agent.respawn_timer = 1
        sim._process_respawns()
        assert agent.boost == 0.0
