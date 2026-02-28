"""
tests/test_plant_capture_brain.py
PlantCaptureBrain の単体テスト

テスト対象:
  - PlantCaptureBrain.__init__(): target 属性の格納
  - decide() の 4 状態
      ATTACK  : ロックオン距離内に敵あり → STAY
      APPROACH: 索敵範囲内・ロックオン外の敵あり → 最近接敵へ貪欲移動
      CAPTURE : 敵なし・自チーム未占拠プラントあり
                → チームA: y が最小の未占拠プラントへ（上端ベースに近い順）
                → チームB: y が最大の未占拠プラントへ（下端ベースに近い順）
      PATROL  : 全プラントが自チーム占拠済み（またはプラントなし）→ 敵ベースへ
"""
import pytest
from simulation import (
    PlantCaptureBrain,
    GreedyBaseAttackBrain,
    Plant,
    Agent, Map, CellType, Action,
    SEARCH_RANGE_C, LOCKON_RANGE_C,
)


# ─────────────────────────────────────────
# テスト用ファクトリ
# ─────────────────────────────────────────
def make_map(width=10, height=50) -> Map:
    """全セルが EMPTY のマップ"""
    return Map(width, height)


def make_agent(agent_id=1, x=5, y=25, team=0, alive=True) -> Agent:
    a = Agent(agent_id=agent_id, x=x, y=y, team=team)
    a.alive = alive
    return a


def make_brain(target=(5, 48)) -> PlantCaptureBrain:
    return PlantCaptureBrain(target=target)


def make_plants(owners: list[int] | None = None) -> list[Plant]:
    """
    マップ仕様通りの3プラント (x=5, y=14/25/35) を生成。
    owners を指定しない場合は全て中立（owner=-1）。
    owners=[owner_p1, owner_p2, owner_p3] で各プラントの所有者を設定。
    """
    plants = [
        Plant(plant_id=1, x=5, y=14),
        Plant(plant_id=2, x=5, y=25),
        Plant(plant_id=3, x=5, y=35),
    ]
    if owners is not None:
        for p, o in zip(plants, owners):
            p.owner = o
    return plants


def decide(brain: PlantCaptureBrain, agent: Agent,
           game_map: Map, plants: list[Plant],
           agents: list[Agent]) -> Action:
    return brain.decide(agent, game_map, plants, agents)


# ─────────────────────────────────────────
# 初期化
# ─────────────────────────────────────────
class TestPlantCaptureBrainInit:
    def test_target_stored(self):
        """target 属性が正しく格納される"""
        brain = PlantCaptureBrain(target=(5, 48))
        assert brain.target == (5, 48)

    def test_target_any_coordinates(self):
        """任意の座標が格納できる"""
        brain = PlantCaptureBrain(target=(0, 1))
        assert brain.target == (0, 1)

    def test_is_subclass_of_greedy(self):
        """GreedyBaseAttackBrain のサブクラスである（_move_toward を継承）"""
        brain = PlantCaptureBrain(target=(5, 48))
        assert isinstance(brain, GreedyBaseAttackBrain)


# ─────────────────────────────────────────
# ATTACK 状態（ロックオン距離内に敵）
# ─────────────────────────────────────────
class TestPlantCaptureBrainAttack:
    """LOCKON_RANGE_C = 6.0"""

    def setup_method(self):
        self.m      = make_map()
        self.brain  = make_brain(target=(5, 48))
        self.agent  = make_agent(x=5, y=25, team=0)
        self.plants = make_plants()  # 全中立（未占拠）

    def test_stay_when_enemy_in_lockon(self):
        """ロックオン距離内(dist ≤ 6)の敵 → STAY（射撃モード）"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1)  # dist = 5
        action = decide(self.brain, self.agent, self.m, self.plants,
                        [self.agent, enemy])
        assert action is Action.STAY

    def test_stay_at_exact_lockon_boundary(self):
        """ロックオン距離ちょうど(dist = 6) → STAY"""
        enemy = make_agent(agent_id=2, x=5, y=31, team=1)  # dist = 6
        action = decide(self.brain, self.agent, self.m, self.plants,
                        [self.agent, enemy])
        assert action is Action.STAY

    def test_attack_ignores_dead_enemy(self):
        """死亡している敵はロックオン内でも無視 → CAPTURE へ"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, alive=False)
        action = decide(self.brain, self.agent, self.m, self.plants,
                        [self.agent, enemy])
        # 死亡敵は無視 → 未占拠プラントあり → CAPTURE
        # チームA: y最小の未占拠=p1(5,14) → 上へ移動
        assert action is Action.MOVE_UP

    def test_attack_stays_even_with_uncaptured_plants(self):
        """未占拠プラントがあってもロックオン内敵がいれば ATTACK 優先"""
        enemy = make_agent(agent_id=2, x=5, y=29, team=1)  # dist = 4
        action = decide(self.brain, self.agent, self.m, self.plants,
                        [self.agent, enemy])
        assert action is Action.STAY


# ─────────────────────────────────────────
# APPROACH 状態（索敵範囲内・ロックオン外）
# ─────────────────────────────────────────
class TestPlantCaptureBrainApproach:
    """6 < dist ≤ 8 の敵に向かって移動"""

    def setup_method(self):
        self.m      = make_map()
        self.brain  = make_brain(target=(5, 48))
        self.agent  = make_agent(x=5, y=25, team=0)
        self.plants = make_plants()  # 全中立

    def test_approach_moves_toward_enemy_below(self):
        """索敵内・ロックオン外の敵が下 → MOVE_DOWN"""
        enemy = make_agent(agent_id=2, x=5, y=32, team=1)  # dist = 7
        action = decide(self.brain, self.agent, self.m, self.plants,
                        [self.agent, enemy])
        assert action is Action.MOVE_DOWN

    def test_approach_moves_toward_enemy_above(self):
        """索敵内・ロックオン外の敵が上 → MOVE_UP"""
        enemy = make_agent(agent_id=2, x=5, y=18, team=1)  # dist = 7
        action = decide(self.brain, self.agent, self.m, self.plants,
                        [self.agent, enemy])
        assert action is Action.MOVE_UP

    def test_approach_prioritized_over_capture(self):
        """未占拠プラントがあっても索敵範囲内の敵には APPROACH"""
        enemy = make_agent(agent_id=2, x=5, y=32, team=1)  # dist = 7
        action = decide(self.brain, self.agent, self.m, self.plants,
                        [self.agent, enemy])
        # CAPTURE(p1 が上)より APPROACH(敵は下)が優先 → 敵方向に MOVE_DOWN
        assert action is Action.MOVE_DOWN

    def test_approach_outside_search_range_falls_to_capture(self):
        """索敵範囲外(dist > 8)の敵は無視 → CAPTURE へ"""
        enemy = make_agent(agent_id=2, x=5, y=34, team=1)  # dist = 9
        action = decide(self.brain, self.agent, self.m, self.plants,
                        [self.agent, enemy])
        # 敵無視 → チームA: y最小の未占拠=p1(5,14) → MOVE_UP
        assert action is Action.MOVE_UP


# ─────────────────────────────────────────
# CAPTURE 状態（敵なし・未占拠プラントあり）
# ─────────────────────────────────────────
class TestPlantCaptureBrainCapture:
    """
    プラント配置: p1(5,14), p2(5,25), p3(5,35)
    チームA ベース: y=0-2（上端）→ y が小さいプラントが近い
    チームB ベース: y=47-49（下端）→ y が大きいプラントが近い
    """

    def setup_method(self):
        self.m = make_map()

    def _decide(self, agent: Agent, plants: list[Plant]) -> Action:
        brain = PlantCaptureBrain(target=(5, 48) if agent.team == 0 else (5, 1))
        return brain.decide(agent, self.m, plants, [agent])

    # ── チームA ─────────────────────────────────────────────
    def test_team_a_targets_closest_plant_from_top_all_neutral(self):
        """チームA・全プラント中立 → y最小の p1(5,14) へ → MOVE_UP"""
        agent = make_agent(x=5, y=25, team=0)
        action = self._decide(agent, make_plants())  # owners=全て-1
        assert action is Action.MOVE_UP

    def test_team_a_skips_own_captured_plant(self):
        """チームA・p1 が自チーム占拠済み → 次に y が小さい p2(5,25) へ"""
        agent = make_agent(x=5, y=10, team=0)  # p2(y=25) は下
        # owners=[0, -1, -1]: p1が自チーム、p2/p3が中立
        action = self._decide(agent, make_plants(owners=[0, -1, -1]))
        assert action is Action.MOVE_DOWN

    def test_team_a_targets_enemy_occupied_plant(self):
        """チームA・p1 が敵（チームB）占拠 → p1 は未占拠扱い → p1(5,14) へ"""
        agent = make_agent(x=5, y=25, team=0)
        # owners=[1, -1, -1]: p1が敵チーム、p2/p3が中立
        action = self._decide(agent, make_plants(owners=[1, -1, -1]))
        # y最小の未占拠はp1(y=14)（敵占拠も未占拠扱い） → MOVE_UP
        assert action is Action.MOVE_UP

    def test_team_a_all_own_captured_patrol(self):
        """チームA・全プラントが自チーム占拠済み → PATROL（敵ベース下へ）"""
        agent = make_agent(x=5, y=25, team=0)
        # owners=[0, 0, 0]: 全て自チーム
        action = self._decide(agent, make_plants(owners=[0, 0, 0]))
        # PATROL → target=(5,48) → MOVE_DOWN
        assert action is Action.MOVE_DOWN

    def test_team_a_two_own_one_uncaptured(self):
        """チームA・p1,p2 が自チーム占拠済み、p3(5,35) が中立 → p3 へ"""
        agent = make_agent(x=5, y=25, team=0)
        # owners=[0, 0, -1]: p1/p2が自チーム、p3が中立
        action = self._decide(agent, make_plants(owners=[0, 0, -1]))
        # 未占拠はp3(y=35) → MOVE_DOWN
        assert action is Action.MOVE_DOWN

    # ── チームB ─────────────────────────────────────────────
    def test_team_b_targets_closest_plant_from_bottom_all_neutral(self):
        """チームB・全プラント中立 → y最大の p3(5,35) へ → MOVE_UP"""
        agent = make_agent(x=5, y=45, team=1)  # p3(y=35)は上
        brain = PlantCaptureBrain(target=(5, 1))
        action = brain.decide(agent, self.m, make_plants(), [agent])
        assert action is Action.MOVE_UP

    def test_team_b_skips_own_captured_plant(self):
        """チームB・p3 が自チーム占拠済み → 次に y が大きい p2(5,25) へ"""
        agent = make_agent(x=5, y=40, team=1)  # p2(y=25)は上
        # owners=[-1, -1, 1]: p1/p2が中立、p3が自チーム
        brain = PlantCaptureBrain(target=(5, 1))
        action = brain.decide(agent, self.m, make_plants(owners=[-1, -1, 1]), [agent])
        assert action is Action.MOVE_UP

    def test_team_b_all_own_captured_patrol(self):
        """チームB・全プラントが自チーム占拠済み → PATROL（敵ベース上へ）"""
        agent = make_agent(x=5, y=25, team=1)
        brain = PlantCaptureBrain(target=(5, 1))
        # owners=[1, 1, 1]: 全て自チーム
        action = brain.decide(agent, self.m, make_plants(owners=[1, 1, 1]), [agent])
        # PATROL → target=(5,1) → MOVE_UP
        assert action is Action.MOVE_UP

    # ── プラントなし ────────────────────────────────────────
    def test_empty_plants_falls_to_patrol(self):
        """プラントリストが空 → PATROL（敵ベースへ）"""
        agent = make_agent(x=5, y=25, team=0)
        brain = PlantCaptureBrain(target=(5, 48))
        action = brain.decide(agent, self.m, [], [agent])
        assert action is Action.MOVE_DOWN

    # ── プラント上に到達済み ─────────────────────────────────
    def test_agent_on_uncaptured_plant_stays(self):
        """エージェントがターゲットプラントの中心と同座標 → STAY"""
        # チームA: y最小の未占拠=p1(5,14)、エージェントも(5,14)
        agent = make_agent(x=5, y=14, team=0)
        brain = PlantCaptureBrain(target=(5, 48))
        # p1が中立（未占拠）のまま
        action = brain.decide(agent, self.m, make_plants(), [agent])
        # _move_toward で dx=0, dy=0 → STAY
        assert action is Action.STAY


# ─────────────────────────────────────────
# PATROL 状態（全プラント占拠済みまたはリストなし）
# ─────────────────────────────────────────
class TestPlantCaptureBrainPatrol:
    """全プラントが自チーム占拠済みのとき敵ベースへ向かう"""

    def setup_method(self):
        self.m = make_map()

    def test_team_a_patrol_toward_enemy_base(self):
        """チームA・全占拠済み → target(5,48) へ → MOVE_DOWN"""
        agent = make_agent(x=5, y=25, team=0)
        brain = PlantCaptureBrain(target=(5, 48))
        action = brain.decide(agent, self.m,
                               make_plants(owners=[0, 0, 0]), [agent])
        assert action is Action.MOVE_DOWN

    def test_team_b_patrol_toward_enemy_base(self):
        """チームB・全占拠済み → target(5,1) へ → MOVE_UP"""
        agent = make_agent(x=5, y=25, team=1)
        brain = PlantCaptureBrain(target=(5, 1))
        action = brain.decide(agent, self.m,
                               make_plants(owners=[1, 1, 1]), [agent])
        assert action is Action.MOVE_UP

    def test_patrol_no_plants(self):
        """プラントなし → PATROL（敵ベースへ）"""
        agent = make_agent(x=5, y=25, team=0)
        brain = PlantCaptureBrain(target=(5, 48))
        action = brain.decide(agent, self.m, [], [agent])
        assert action is Action.MOVE_DOWN

    def test_patrol_target_direction_horizontal(self):
        """target が横方向 → MOVE_RIGHT"""
        agent = make_agent(x=2, y=25, team=0)
        brain = PlantCaptureBrain(target=(8, 25))
        action = brain.decide(agent, self.m,
                               make_plants(owners=[0, 0, 0]), [agent])
        assert action is Action.MOVE_RIGHT
