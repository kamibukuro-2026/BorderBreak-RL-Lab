"""
tests/test_aggressive_combat_brain.py
AggressiveCombatBrain の単体テスト

テスト対象:
  - AggressiveCombatBrain.__init__(): target 属性の格納
  - decide() の 4 状態
      ATTACK  : ロックオン距離内に敵あり → STAY
      APPROACH: 索敵範囲内・ロックオン外の敵あり → 最近接敵へ貪欲移動
      HUNT    : 索敵範囲外だが detected=True の敵がいる
                → 最近接 detected 敵へ貪欲移動
      PATROL  : 追跡対象なし → 目標（敵ベース）へ貪欲移動
"""
import pytest
from simulation import (
    AggressiveCombatBrain,
    GreedyBaseAttackBrain,
    Agent, Map, Action,
    SEARCH_RANGE_C, LOCKON_RANGE_C,
)


# ─────────────────────────────────────────
# テスト用ファクトリ
# ─────────────────────────────────────────
def make_map(width=10, height=50) -> Map:
    """全セルが EMPTY のマップ"""
    return Map(width, height)


def make_agent(agent_id=1, x=5, y=25, team=0, alive=True,
               detected=False) -> Agent:
    a = Agent(agent_id=agent_id, x=x, y=y, team=team)
    a.alive = alive
    a.detected = detected
    return a


def make_brain(target=(5, 48)) -> AggressiveCombatBrain:
    return AggressiveCombatBrain(target=target)


def decide(brain: AggressiveCombatBrain, agent: Agent,
           game_map: Map, agents: list[Agent]) -> Action:
    """plants を省略できるラッパー"""
    return brain.decide(agent, game_map, [], agents)


# ─────────────────────────────────────────
# 初期化
# ─────────────────────────────────────────
class TestAggressiveCombatBrainInit:
    def test_target_stored(self):
        """target 属性が正しく格納される"""
        brain = AggressiveCombatBrain(target=(5, 48))
        assert brain.target == (5, 48)

    def test_is_subclass_of_greedy(self):
        """GreedyBaseAttackBrain のサブクラスである（_move_toward を継承）"""
        brain = AggressiveCombatBrain(target=(5, 48))
        assert isinstance(brain, GreedyBaseAttackBrain)


# ─────────────────────────────────────────
# ATTACK 状態（ロックオン距離内に敵）
# ─────────────────────────────────────────
class TestAggressiveCombatBrainAttack:
    """LOCKON_RANGE_C = 12.0"""

    def setup_method(self):
        self.m     = make_map()
        self.brain = make_brain(target=(5, 48))
        self.agent = make_agent(x=5, y=25, team=0)

    def test_stay_when_enemy_in_lockon(self):
        """ロックオン距離内(dist=5)の敵 → STAY（射撃モード）"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1)  # dist=5
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.STAY

    def test_stay_at_exact_lockon_boundary(self):
        """ロックオン距離ちょうど(dist=12) → STAY"""
        enemy = make_agent(agent_id=2, x=5, y=37, team=1)  # dist=12
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.STAY

    def test_attack_ignores_dead_enemy_in_lockon(self):
        """ロックオン距離内でも dead の敵は無視 → PATROL（敵なし扱い）"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, alive=False)
        # 死亡 + 非detected → PATROL → target(5,48) は下
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.MOVE_DOWN


# ─────────────────────────────────────────
# APPROACH 状態（索敵範囲内・ロックオン外）
# ─────────────────────────────────────────
class TestAggressiveCombatBrainApproach:
    """12 < dist ≤ 16 の敵に向かって移動"""

    def setup_method(self):
        self.m     = make_map()
        self.brain = make_brain(target=(5, 48))
        self.agent = make_agent(x=5, y=25, team=0)

    def test_approach_moves_toward_enemy_below(self):
        """索敵内・ロックオン外の敵が下(dist=13) → MOVE_DOWN"""
        enemy = make_agent(agent_id=2, x=5, y=38, team=1)  # dist=13
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.MOVE_DOWN

    def test_approach_moves_toward_enemy_above(self):
        """索敵内・ロックオン外の敵が上(dist=13) → MOVE_UP"""
        enemy = make_agent(agent_id=2, x=5, y=12, team=1)  # dist=13
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.MOVE_UP

    def test_approach_prioritized_over_hunt(self):
        """索敵内の敵がいれば detected 敵より APPROACH が優先"""
        visible = make_agent(agent_id=2, x=5, y=38, team=1)      # dist=13, 索敵内
        hunted  = make_agent(agent_id=3, x=5, y=5,   team=1,
                             detected=True)                        # dist=20, 範囲外 detected
        # visible が索敵内なので APPROACH → MOVE_DOWN（visibleは下方向）
        action = decide(self.brain, self.agent, self.m,
                        [self.agent, visible, hunted])
        assert action is Action.MOVE_DOWN


# ─────────────────────────────────────────
# HUNT 状態（索敵範囲外・detected=True の敵）
# ─────────────────────────────────────────
class TestAggressiveCombatBrainHunt:
    """
    索敵範囲 SEARCH_RANGE_C = 16.0 セル
    エージェント位置: (5, 25)

    detected=True の敵がいれば HUNT（索敵範囲外でも追う）
    """

    def setup_method(self):
        self.m     = make_map()
        self.brain = make_brain(target=(5, 48))
        self.agent = make_agent(x=5, y=25, team=0)

    def _decide(self, agents):
        return decide(self.brain, self.agent, self.m, agents)

    def test_hunt_moves_toward_detected_enemy_below(self):
        """索敵外・detected 敵が下(dist=17) → HUNT → MOVE_DOWN"""
        enemy = make_agent(agent_id=2, x=5, y=42, team=1,
                           detected=True)   # dist=17 > 16
        action = self._decide([self.agent, enemy])
        assert action is Action.MOVE_DOWN

    def test_hunt_moves_toward_detected_enemy_above(self):
        """索敵外・detected 敵が上(dist=17) → HUNT → MOVE_UP"""
        enemy = make_agent(agent_id=2, x=5, y=8, team=1,
                           detected=True)   # dist=17 > 16
        action = self._decide([self.agent, enemy])
        assert action is Action.MOVE_UP

    def test_hunt_ignores_non_detected_enemy_outside_range(self):
        """索敵外・detected=False の敵は無視 → PATROL"""
        enemy = make_agent(agent_id=2, x=5, y=42, team=1,
                           detected=False)  # dist=17, 非detected
        action = self._decide([self.agent, enemy])
        assert action is Action.MOVE_DOWN  # PATROL → target(5,48) 方向

    def test_hunt_ignores_dead_detected_enemy(self):
        """死亡している detected 敵は無視 → PATROL"""
        enemy = make_agent(agent_id=2, x=5, y=10, team=1,
                           alive=False, detected=True)  # dead + detected
        # dead なので HUNT 対象外 → PATROL → target(5,48) は下
        action = self._decide([self.agent, enemy])
        assert action is Action.MOVE_DOWN

    def test_hunt_targets_nearest_when_multiple_detected(self):
        """複数 detected 敵のうち最近接を追う"""
        near = make_agent(agent_id=2, x=5, y=42, team=1,
                          detected=True)   # dist=17 > 16（下）
        far  = make_agent(agent_id=3, x=5, y=5,  team=1,
                          detected=True)   # dist=20 > 16（上）
        # near の方が近い → 下へ MOVE_DOWN
        action = self._decide([self.agent, near, far])
        assert action is Action.MOVE_DOWN

    def test_hunt_detected_in_search_range_handled_as_approach(self):
        """detected=True でも索敵範囲内（APPROACH ゾーン）なら APPROACH として処理される"""
        # dist=13 は APPROACH ゾーン → visible に入る → APPROACH（detected 参照前に分岐）
        enemy = make_agent(agent_id=2, x=5, y=38, team=1,
                           detected=True)  # dist=13, APPROACH ゾーン
        action = self._decide([self.agent, enemy])
        # APPROACH ゾーンなので APPROACH → MOVE_DOWN
        assert action is Action.MOVE_DOWN

    def test_hunt_not_triggered_when_visible_enemy_exists(self):
        """索敵内に敵がいれば、別の detected 敵は HUNT されない（APPROACH が優先）"""
        visible_enemy  = make_agent(agent_id=2, x=5, y=38, team=1)       # dist=13, APPROACH ゾーン
        detected_enemy = make_agent(agent_id=3, x=5, y=5,   team=1,
                                    detected=True)                          # dist=20, 索敵外
        # 索敵内の visible_enemy が優先 → APPROACH → MOVE_DOWN
        action = self._decide([self.agent, visible_enemy, detected_enemy])
        assert action is Action.MOVE_DOWN


# ─────────────────────────────────────────
# PATROL 状態（追跡対象なし）
# ─────────────────────────────────────────
class TestAggressiveCombatBrainPatrol:
    """索敵内の敵も detected 敵もいない場合は target へ直進"""

    def setup_method(self):
        self.m = make_map()

    def test_patrol_when_no_enemies(self):
        """エージェントが自分のみ → PATROL → target 方向"""
        agent = make_agent(x=5, y=25, team=0)
        brain = make_brain(target=(5, 48))
        action = decide(brain, agent, self.m, [agent])
        assert action is Action.MOVE_DOWN  # target は下

    def test_patrol_ignores_non_detected_out_of_range(self):
        """索敵外かつ detected=False の敵は無視 → PATROL"""
        agent = make_agent(x=5, y=25, team=0)
        enemy = make_agent(agent_id=2, x=5, y=42, team=1,
                           detected=False)  # dist=17 > 16, 非detected
        brain = make_brain(target=(5, 48))
        action = decide(brain, agent, self.m, [agent, enemy])
        assert action is Action.MOVE_DOWN  # PATROL → target(5,48) 方向

    def test_patrol_direction_toward_target(self):
        """target が上方向のとき PATROL は MOVE_UP"""
        agent = make_agent(x=5, y=25, team=1)
        brain = make_brain(target=(5, 1))   # チームB 想定：target は上
        action = decide(brain, agent, self.m, [agent])
        assert action is Action.MOVE_UP
