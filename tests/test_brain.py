"""
tests/test_brain.py
Brain / GreedyBaseAttackBrain の単体テスト

テスト対象:
  - Brain（基底クラス）: decide() は常に STAY
  - GreedyBaseAttackBrain.__init__(): target 属性の格納
  - decide() の 3 状態
      PATROL  : 索敵範囲内に敵なし → 目標（敵ベース）へ貪欲移動
      ATTACK  : ロックオン距離内に敵あり → STAY（射撃は Simulation が担当）
      APPROACH: 索敵範囲内・ロックオン外の敵あり → 最近接敵へ貪欲移動
  - _move_toward() の優先軸・障害物フォールバック・全方向ふさがれ
"""
import pytest
from simulation import (
    Brain, GreedyBaseAttackBrain,
    Agent, Map, CellType, Action,
    SEARCH_RANGE_C, LOCKON_RANGE_C,
)


# ─────────────────────────────────────────
# テスト用ファクトリ / ヘルパー
# ─────────────────────────────────────────
def make_map(width=10, height=50) -> Map:
    """全セルが EMPTY のマップ"""
    return Map(width, height)


def make_agent(agent_id=1, x=5, y=25, team=0, alive=True) -> Agent:
    a = Agent(agent_id=agent_id, x=x, y=y, team=team)
    a.alive = alive
    return a


def make_brain(target=(5, 48)) -> GreedyBaseAttackBrain:
    return GreedyBaseAttackBrain(target=target)


def decide(brain: GreedyBaseAttackBrain, agent: Agent,
           game_map: Map, agents: list[Agent]) -> Action:
    """plants を省略できるラッパー"""
    return brain.decide(agent, game_map, [], agents)


# ─────────────────────────────────────────
# Brain 基底クラス
# ─────────────────────────────────────────
class TestBrainBase:
    def test_base_brain_returns_stay(self):
        """Brain 基底クラスは常に STAY を返す"""
        brain = Brain()
        agent = make_agent()
        m = make_map()
        action = brain.decide(agent, m, [], [agent])
        assert action is Action.STAY


# ─────────────────────────────────────────
# GreedyBaseAttackBrain 初期化
# ─────────────────────────────────────────
class TestGreedyBrainInit:
    def test_target_stored(self):
        """target 属性が正しく格納される"""
        brain = GreedyBaseAttackBrain(target=(5, 48))
        assert brain.target == (5, 48)

    def test_target_any_coordinates(self):
        """任意の座標が格納できる"""
        brain = GreedyBaseAttackBrain(target=(0, 0))
        assert brain.target == (0, 0)


# ─────────────────────────────────────────
# PATROL 状態（敵が索敵範囲外）
# ─────────────────────────────────────────
class TestPatrol:
    """エージェント (5, 25)、ターゲット (5, 48)"""

    def setup_method(self):
        self.m     = make_map()
        self.brain = make_brain(target=(5, 48))
        self.agent = make_agent(x=5, y=25, team=0)

    def _decide(self, agents=None) -> Action:
        return decide(self.brain, self.agent, self.m, agents or [self.agent])

    def test_no_agents_move_toward_target(self):
        """エージェントリストが自分のみ → PATROL → MOVE_DOWN"""
        assert self._decide() is Action.MOVE_DOWN

    def test_dead_enemy_not_counted(self):
        """死亡している敵は索敵対象にならない → PATROL"""
        enemy = make_agent(agent_id=2, x=5, y=28, team=1, alive=False)
        # dist=3 ≤ SEARCH_RANGE_C だが dead
        assert self._decide([self.agent, enemy]) is Action.MOVE_DOWN

    def test_friendly_not_counted(self):
        """同チームは敵ではない → PATROL"""
        friend = make_agent(agent_id=2, x=5, y=28, team=0)
        assert self._decide([self.agent, friend]) is Action.MOVE_DOWN

    def test_enemy_out_of_search_range(self):
        """索敵範囲外(dist > 16)の敵は無視 → PATROL"""
        enemy = make_agent(agent_id=2, x=5, y=42, team=1)  # dist = 17
        assert self._decide([self.agent, enemy]) is Action.MOVE_DOWN

    def test_patrol_move_down_toward_below_target(self):
        """target が下 → MOVE_DOWN"""
        brain = make_brain(target=(5, 30))
        agent = make_agent(x=5, y=25)
        action = decide(brain, agent, self.m, [agent])
        assert action is Action.MOVE_DOWN

    def test_patrol_move_up_toward_above_target(self):
        """target が上 → MOVE_UP"""
        brain = make_brain(target=(5, 20))
        agent = make_agent(x=5, y=25)
        action = decide(brain, agent, self.m, [agent])
        assert action is Action.MOVE_UP

    def test_patrol_move_right_toward_right_target(self):
        """target が右 → MOVE_RIGHT（dy=0, dx>0）"""
        brain = make_brain(target=(8, 25))
        agent = make_agent(x=5, y=25)
        action = decide(brain, agent, self.m, [agent])
        assert action is Action.MOVE_RIGHT

    def test_patrol_move_left_toward_left_target(self):
        """target が左 → MOVE_LEFT（dy=0, dx<0）"""
        brain = make_brain(target=(2, 25))
        agent = make_agent(x=5, y=25)
        action = decide(brain, agent, self.m, [agent])
        assert action is Action.MOVE_LEFT

    def test_patrol_at_target_stay(self):
        """エージェントが target に到達済み → STAY"""
        brain = make_brain(target=(5, 25))
        agent = make_agent(x=5, y=25)
        action = decide(brain, agent, self.m, [agent])
        assert action is Action.STAY


# ─────────────────────────────────────────
# ATTACK 状態（ロックオン距離内に敵）
# ─────────────────────────────────────────
class TestAttack:
    """LOCKON_RANGE_C = 12.0"""

    def setup_method(self):
        self.m     = make_map()
        self.brain = make_brain(target=(5, 48))
        self.agent = make_agent(x=5, y=25, team=0)

    def test_stay_when_enemy_in_lockon(self):
        """ロックオン距離内(dist ≤ 12)の敵 → STAY（射撃モード）"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1)  # dist = 5
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.STAY

    def test_stay_when_enemy_at_exact_lockon_boundary(self):
        """ロックオン距離ちょうど(dist = 12) → STAY"""
        enemy = make_agent(agent_id=2, x=5, y=37, team=1)  # dist = 12
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.STAY

    def test_attack_ignores_dead_enemy_in_lockon_distance(self):
        """ロックオン距離内でも dead の敵は無視 → PATROL"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, alive=False)
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        # 敵なし扱い → PATROL → MOVE_DOWN (target は下)
        assert action is Action.MOVE_DOWN

    def test_attack_chooses_nearest_when_multiple_enemies(self):
        """複数敵のうち最近接がロックオン内ならATTACK→STAY"""
        near  = make_agent(agent_id=2, x=5, y=30, team=1)  # dist = 5
        far   = make_agent(agent_id=3, x=5, y=40, team=1)  # dist = 15, search境界内
        action = decide(self.brain, self.agent, self.m,
                        [self.agent, near, far])
        assert action is Action.STAY


# ─────────────────────────────────────────
# APPROACH 状態（索敵内・ロックオン外）
# ─────────────────────────────────────────
class TestApproach:
    """12 < dist ≤ 16 の敵に向かって移動"""

    def setup_method(self):
        self.m     = make_map()
        self.brain = make_brain(target=(5, 48))
        self.agent = make_agent(x=5, y=25, team=0)

    def test_approach_moves_toward_enemy_below(self):
        """索敵内・ロックオン外の敵が下 → MOVE_DOWN"""
        enemy = make_agent(agent_id=2, x=5, y=38, team=1)  # dist = 13
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.MOVE_DOWN

    def test_approach_moves_toward_enemy_above(self):
        """索敵内・ロックオン外の敵が上 → MOVE_UP"""
        enemy = make_agent(agent_id=2, x=5, y=12, team=1)  # dist = 13
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.MOVE_UP

    def test_approach_targets_nearest_enemy(self):
        """複数の可視敵がいる場合、最近接の敵へ向かう"""
        # APPROACH ゾーン: 12 < dist ≤ 16
        m = make_map()
        agent = make_agent(x=5, y=25, team=0)
        en13 = make_agent(agent_id=10, x=5, y=38, team=1)   # dist = 13 (nearest)
        en15 = make_agent(agent_id=11, x=5, y=40, team=1)   # dist = 15
        action = decide(self.brain, agent, m, [agent, en13, en15])
        # nearest = en13 (dist=13) → 下 → MOVE_DOWN
        assert action is Action.MOVE_DOWN

    def test_approach_not_triggered_outside_search(self):
        """索敵範囲外(dist=17)の敵には APPROACH しない → PATROL"""
        enemy = make_agent(agent_id=2, x=5, y=42, team=1)  # dist = 17 > 16
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.MOVE_DOWN   # PATROL モードでターゲット方向


# ─────────────────────────────────────────
# _move_toward() の優先軸・障害物フォールバック
# ─────────────────────────────────────────
class TestMoveToward:
    """
    _move_toward() を間接的に decide() 経由でテストする。
    エージェントを PATROL 状態（敵なし）にして target の方向を検証。
    """

    def _patrol_action(self, ax, ay, tx, ty, obstacle=None) -> Action:
        """エージェント(ax,ay)・ターゲット(tx,ty)で decide() を呼ぶ。"""
        m = make_map()
        if obstacle:
            ox, oy = obstacle
            m.set_cell(ox, oy, CellType.OBSTACLE)
        agent = make_agent(x=ax, y=ay, team=0)
        brain = make_brain(target=(tx, ty))
        return decide(brain, agent, m, [agent])

    # ── 優先軸の確認 ──────────────────────────────────────
    def test_vertical_priority_when_dy_gt_dx(self):
        """|dy| > |dx| → 縦方向優先"""
        # (5,25) → target (6,30): dy=5, dx=1 → 縦優先 → MOVE_DOWN
        action = self._patrol_action(5, 25, 6, 30)
        assert action is Action.MOVE_DOWN

    def test_horizontal_priority_when_dx_gt_dy(self):
        """|dx| > |dy| → 横方向優先"""
        # (5,25) → target (9,26): dy=1, dx=4 → 横優先 → MOVE_RIGHT
        action = self._patrol_action(5, 25, 9, 26)
        assert action is Action.MOVE_RIGHT

    def test_equal_priority_vertical_first(self):
        """|dy| == |dx| → 縦優先（abs(dy) >= abs(dx) の条件）"""
        # (5,25) → target (8,28): dy=3, dx=3 → 縦優先 → MOVE_DOWN
        action = self._patrol_action(5, 25, 8, 28)
        assert action is Action.MOVE_DOWN

    def test_target_up_and_right_vertical_first(self):
        """|dy|=4 > |dx|=1 → MOVE_UP"""
        # (5,25) → target (6,21): dy=-4, dx=1 → 縦優先 → MOVE_UP
        action = self._patrol_action(5, 25, 6, 21)
        assert action is Action.MOVE_UP

    # ── 障害物フォールバック ──────────────────────────────
    def test_obstacle_fallback_to_secondary_direction(self):
        """第1候補が OBSTACLE → 第2候補（横）に移動"""
        # (5,25) → target (6,26): dy=1, dx=1 → 縦優先 [DOWN, RIGHT]
        # (5,26) を OBSTACLE にすると DOWN が blocked → RIGHT を選択
        action = self._patrol_action(5, 25, 6, 26, obstacle=(5, 26))
        assert action is Action.MOVE_RIGHT

    def test_obstacle_fallback_vertical_when_horizontal_blocked(self):
        """横方向優先だが横が OBSTACLE → 縦にフォールバック"""
        # (5,25) → target (9,26): dy=1, dx=4 → 横優先 [RIGHT, DOWN]
        # (6,25) を OBSTACLE にすると RIGHT が blocked → DOWN を選択
        action = self._patrol_action(5, 25, 9, 26, obstacle=(6, 25))
        assert action is Action.MOVE_DOWN

    def test_all_directions_blocked_returns_stay(self):
        """候補方向がすべて OBSTACLE → STAY"""
        # (5,25) → target (5,26): dy=1, dx=0 → candidates=[DOWN]
        # (5,26) を OBSTACLE → 全ブロック → STAY
        action = self._patrol_action(5, 25, 5, 26, obstacle=(5, 26))
        assert action is Action.STAY

    def test_out_of_bounds_treated_as_blocked(self):
        """マップ境界外の移動は is_walkable=False → 次候補へ"""
        # (0,25) → target (-1, 26): dx=-1, dy=1 → |dy|>=|dx| → [DOWN, LEFT]
        # LEFT は x=-1 → out of bounds → DOWN を選択
        m = make_map(width=10, height=50)
        agent = make_agent(x=0, y=25, team=0)
        brain = make_brain(target=(0, 26))   # 純粋に下へ
        # 境界外フォールバックを確認: target を左下に設定
        brain2 = GreedyBaseAttackBrain(target=(-1, 26))
        # (-1,26): dy=1, dx=-1 → |dy|=|dx| → 縦優先 [DOWN, LEFT]
        # LEFT → x=-1 → out of bounds → DOWN
        action = brain2.decide(agent, m, [], [agent])
        assert action is Action.MOVE_DOWN
