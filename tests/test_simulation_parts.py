"""
tests/test_simulation_parts.py
Simulation クラスが Agent の per-agent パラメータを使うことを確認するテスト

テスト対象:
  - _resolve_combat()  — agent.dps を DPS として使う
  - _execute_action()  — agent.cells_per_step を CELLS_PER_STEP として使う
  - _update_cores()    — agent.dps を DPS として使う（ベース直接攻撃）
"""
import pytest
from unittest.mock import patch

from simulation import (
    Simulation, Map, Agent, Core, CellType, Action,
    AGENT_HP, DPS, CELLS_PER_STEP,
    MAP_W, MAP_H, BASE_DEPTH,
    create_map,
)

ALWAYS_HIT  = 0.0   # HIT_RATE=0.80 より小さい → 必ず命中
ALWAYS_MISS = 1.0   # HIT_RATE=0.80 以上 → 必ず外れ


# ─────────────────────────────────────────
# テスト用ファクトリ
# ─────────────────────────────────────────
def make_sim(with_bases: bool = False) -> Simulation:
    if with_bases:
        game_map, plants = create_map()
        return Simulation(game_map, plants)
    return Simulation(Map(MAP_W, MAP_H), plants=[])


def add_agent(sim: Simulation, agent_id: int, x: int, y: int,
              team: int, hp: int = AGENT_HP, **kwargs) -> Agent:
    a = Agent(agent_id=agent_id, x=x, y=y, team=team, **kwargs)
    a.hp = hp
    sim.add_agent(a)
    return a


# ─────────────────────────────────────────
# _resolve_combat() — agent.dps を使うテスト
# ─────────────────────────────────────────
class TestResolveCombatUsesAgentDps:

    def test_custom_dps_deals_custom_damage(self):
        """dps=5000 のエージェントが命中したとき 5000 ダメージ入る"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0, dps=5000, hit_rate=1.0)
        target = add_agent(sim, 2, 0, 5, team=1)        # dist=5 ≤ lockon_range_c(6)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert target.hp == AGENT_HP - 5000

    def test_low_dps_deals_less_damage(self):
        """dps=1000 のエージェントが命中したとき 1000 ダメージ入る"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0, dps=1000, hit_rate=1.0)
        target = add_agent(sim, 2, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert target.hp == AGENT_HP - 1000

    def test_default_dps_deals_dps_constant_damage(self):
        """dps 未指定（デフォルト）のエージェントは DPS 定数分のダメージ"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0, hit_rate=1.0)  # dps=DPS
        target = add_agent(sim, 2, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert target.hp == AGENT_HP - DPS

    def test_two_different_dps_accumulate_separately(self):
        """dps が異なる2エージェントが同じターゲットを攻撃 → 合計ダメージ"""
        sim = make_sim()
        # shooter_a: dps=2000, shooter_b: dps=4000 → 合計 6000
        add_agent(sim, 1, 0, 0, team=0, dps=2000, hit_rate=1.0)
        add_agent(sim, 2, 1, 0, team=0, dps=4000, hit_rate=1.0)
        target = add_agent(sim, 3, 0, 5, team=1)       # 両方にとって lockon 範囲内
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert target.hp == AGENT_HP - 6000

    def test_zero_dps_causes_no_damage(self):
        """dps=0 の場合ダメージなし（HP変化なし）"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0, dps=0)
        target = add_agent(sim, 2, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert target.hp == AGENT_HP

    def test_high_dps_kills_in_one_hit(self):
        """dps=AGENT_HP で1発撃破"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0, dps=AGENT_HP, hit_rate=1.0)
        target = add_agent(sim, 2, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert target.hp == 0
        assert not target.alive

    def test_out_of_lockon_range_dps_not_applied(self):
        """ロックオン範囲外では dps が大きくてもダメージなし"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0, dps=99999)
        target = add_agent(sim, 2, 0, 13, team=1)   # dist=13 > lockon_range_c=12
        sim._resolve_combat()
        assert target.hp == AGENT_HP


# ─────────────────────────────────────────
# _execute_action() — agent.cells_per_step を使うテスト
# ─────────────────────────────────────────
class TestExecuteActionUsesCellsPerStep:

    def test_cells_per_step_1_moves_one_cell(self):
        """cells_per_step=1 のエージェントが MOVE_DOWN → 1セル移動"""
        sim = make_sim()
        a = Agent(agent_id=1, x=5, y=10, team=0, cells_per_step=1)
        sim.add_agent(a)
        sim._execute_action(a, Action.MOVE_DOWN)
        assert a.y == 11

    def test_cells_per_step_3_moves_three_cells(self):
        """cells_per_step=3 のエージェントが MOVE_DOWN → 3セル移動"""
        sim = make_sim()
        a = Agent(agent_id=1, x=5, y=10, team=0, cells_per_step=3)
        sim.add_agent(a)
        sim._execute_action(a, Action.MOVE_DOWN)
        assert a.y == 13

    def test_cells_per_step_default_moves_default_cells(self):
        """デフォルト cells_per_step(2) のエージェントが MOVE_DOWN → 2セル移動"""
        sim = make_sim()
        a = Agent(agent_id=1, x=5, y=10, team=0)      # cells_per_step=CELLS_PER_STEP
        sim.add_agent(a)
        sim._execute_action(a, Action.MOVE_DOWN)
        assert a.y == 10 + CELLS_PER_STEP

    def test_cells_per_step_4_moves_four_cells(self):
        """cells_per_step=4 のエージェントが MOVE_RIGHT → 4セル移動"""
        sim = make_sim()
        a = Agent(agent_id=1, x=0, y=10, team=0, cells_per_step=4)
        sim.add_agent(a)
        sim._execute_action(a, Action.MOVE_RIGHT)
        assert a.x == 4

    def test_cells_per_step_blocked_by_wall(self):
        """cells_per_step=5 でも MAP 境界で止まる"""
        sim = make_sim()
        # x=16 から MOVE_RIGHT → MAP_W=20 なので x=19（境界=19）で止まる
        a = Agent(agent_id=1, x=16, y=10, team=0, cells_per_step=5)
        sim.add_agent(a)
        sim._execute_action(a, Action.MOVE_RIGHT)
        assert a.x == MAP_W - 1   # 最大 x は MAP_W-1=19

    def test_cells_per_step_stay_action_no_movement(self):
        """STAY アクション時は cells_per_step に関わらず移動しない"""
        sim = make_sim()
        a = Agent(agent_id=1, x=5, y=10, team=0, cells_per_step=9)
        sim.add_agent(a)
        sim._execute_action(a, Action.STAY)
        assert a.x == 5
        assert a.y == 10


# ─────────────────────────────────────────
# _update_cores() — agent.dps を使うテスト（ベース直接攻撃）
# ─────────────────────────────────────────
class TestUpdateCoresUsesAgentDps:

    def test_custom_dps_damages_core_by_agent_dps(self):
        """dps=6000 のエージェントが敵ベース内 → コアに 6000 ダメージ"""
        sim = make_sim(with_bases=True)
        # チームA(team=0)のエージェントをチームBのベース(y=94-99)内に配置
        a = Agent(agent_id=1, x=5, y=95, team=0, dps=6000)
        sim.add_agent(a)
        core_b = sim.cores[1]
        prev_hp = core_b.hp
        sim._update_cores()
        assert core_b.hp == prev_hp - 6000

    def test_low_dps_damages_core_less(self):
        """dps=500 のエージェントが敵ベース内 → コアに 500 ダメージ"""
        sim = make_sim(with_bases=True)
        a = Agent(agent_id=1, x=5, y=95, team=0, dps=500)
        sim.add_agent(a)
        core_b = sim.cores[1]
        prev_hp = core_b.hp
        sim._update_cores()
        assert core_b.hp == prev_hp - 500

    def test_default_dps_damages_core_by_dps_constant(self):
        """dps 未指定（デフォルト）では DPS 定数分コアへダメージ"""
        sim = make_sim(with_bases=True)
        a = Agent(agent_id=1, x=5, y=95, team=0)    # dps=DPS
        sim.add_agent(a)
        core_b = sim.cores[1]
        prev_hp = core_b.hp
        sim._update_cores()
        assert core_b.hp == prev_hp - DPS

    def test_multiple_agents_different_dps_accumulate(self):
        """異なる dps の2エージェントがベース内 → それぞれのダメージが加算"""
        sim = make_sim(with_bases=True)
        # team=0 の2エージェントがチームBベース内: dps=2000 + dps=3000 = 5000
        a1 = Agent(agent_id=1, x=4, y=95, team=0, dps=2000)
        a2 = Agent(agent_id=2, x=5, y=94, team=0, dps=3000)
        sim.add_agent(a1)
        sim.add_agent(a2)
        core_b = sim.cores[1]
        prev_hp = core_b.hp
        sim._update_cores()
        assert core_b.hp == prev_hp - 5000

    def test_team_b_agent_custom_dps_damages_core_a(self):
        """チームBエージェント(dps=4000)がチームAベース内 → コアAに 4000 ダメージ"""
        sim = make_sim(with_bases=True)
        # チームAのベースはy=0-5
        b = Agent(agent_id=2, x=5, y=1, team=1, dps=4000)
        sim.add_agent(b)
        core_a = sim.cores[0]
        prev_hp = core_a.hp
        sim._update_cores()
        assert core_a.hp == prev_hp - 4000
