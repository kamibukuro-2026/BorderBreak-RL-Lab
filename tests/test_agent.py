"""
tests/test_agent.py
Agent クラスの単体テスト

テスト対象:
  - Agent の初期状態（hp / max_hp / alive / respawn_timer / brain / pos / pos_m）
  - Agent.role — ロール属性（デフォルト=Role.ASSAULT）
  - Agent.move() および move_up/down/left/right()
  - Agent.dist_cells() — ユークリッド距離
  - Agent.in_search_range() — 索敵範囲（SEARCH_RANGE_C = 8.0）
  - Agent.in_lockon_range() — ロックオン範囲（LOCKON_RANGE_C = 6.0）
"""
import math
import pytest
from simulation import (
    Agent, Map, CellType, Role,
    AGENT_HP, CELL_SIZE_M,
    SEARCH_RANGE_C, LOCKON_RANGE_C,
)


# ─────────────────────────────────────────
# テスト用ファクトリ
# ─────────────────────────────────────────
def make_agent(agent_id=1, x=5, y=25, team=0) -> Agent:
    return Agent(agent_id=agent_id, x=x, y=y, team=team)


def make_map(width=10, height=50) -> Map:
    """全セルが EMPTY のマップ"""
    return Map(width, height)


def make_map_with_obstacle(ox: int, oy: int, width=10, height=50) -> Map:
    """指定セルを OBSTACLE にしたマップ"""
    m = Map(width, height)
    m.set_cell(ox, oy, CellType.OBSTACLE)
    return m


# ─────────────────────────────────────────
# Agent 初期状態
# ─────────────────────────────────────────
class TestAgentInitial:
    def test_initial_hp(self):
        """初期 HP は AGENT_HP"""
        assert make_agent().hp == AGENT_HP

    def test_initial_max_hp(self):
        """max_hp は AGENT_HP"""
        assert make_agent().max_hp == AGENT_HP

    def test_initial_alive(self):
        """生成直後は alive=True"""
        assert make_agent().alive is True

    def test_initial_respawn_timer(self):
        """生成直後は respawn_timer=0"""
        assert make_agent().respawn_timer == 0

    def test_initial_brain_none(self):
        """brain を指定しない場合は None"""
        assert make_agent().brain is None

    def test_initial_team_a(self):
        assert make_agent(team=0).team == 0

    def test_initial_team_b(self):
        assert make_agent(team=1).team == 1

    def test_initial_pos(self):
        """pos プロパティはセル座標タプル"""
        a = make_agent(x=3, y=7)
        assert a.pos == (3, 7)

    def test_initial_pos_m(self):
        """pos_m はセル座標 × CELL_SIZE_M"""
        a = make_agent(x=3, y=7)
        assert a.pos_m == (3 * CELL_SIZE_M, 7 * CELL_SIZE_M)

    def test_initial_pos_m_origin(self):
        """原点のエージェントは pos_m = (0, 0)"""
        a = make_agent(x=0, y=0)
        assert a.pos_m == (0, 0)


# ─────────────────────────────────────────
# Agent.move() / move_up/down/left/right()
# ─────────────────────────────────────────
class TestAgentMove:

    def test_move_walkable_returns_true(self):
        """空きセルへの移動は True を返す"""
        m = make_map()
        a = make_agent(x=5, y=5)
        assert a.move(0, 1, m) is True

    def test_move_walkable_updates_pos(self):
        """移動成功時に座標が更新される"""
        m = make_map()
        a = make_agent(x=5, y=5)
        a.move(1, 0, m)
        assert a.pos == (6, 5)

    def test_move_out_of_bounds_returns_false(self):
        """マップ外への移動は False を返す"""
        m = make_map(width=10, height=50)
        a = make_agent(x=0, y=0)
        assert a.move(-1, 0, m) is False

    def test_move_out_of_bounds_stays(self):
        """マップ外への移動では座標が変わらない"""
        m = make_map(width=10, height=50)
        a = make_agent(x=0, y=0)
        a.move(-1, 0, m)
        assert a.pos == (0, 0)

    def test_move_obstacle_returns_false(self):
        """OBSTACLE セルへの移動は False を返す"""
        m = make_map_with_obstacle(6, 5)
        a = make_agent(x=5, y=5)
        assert a.move(1, 0, m) is False

    def test_move_obstacle_stays(self):
        """OBSTACLE セルへの移動では座標が変わらない"""
        m = make_map_with_obstacle(6, 5)
        a = make_agent(x=5, y=5)
        a.move(1, 0, m)
        assert a.pos == (5, 5)

    def test_move_up_decreases_y(self):
        """move_up は y を 1 減らす"""
        m = make_map()
        a = make_agent(x=5, y=5)
        a.move_up(m)
        assert a.pos == (5, 4)

    def test_move_down_increases_y(self):
        """move_down は y を 1 増やす"""
        m = make_map()
        a = make_agent(x=5, y=5)
        a.move_down(m)
        assert a.pos == (5, 6)

    def test_move_left_decreases_x(self):
        """move_left は x を 1 減らす"""
        m = make_map()
        a = make_agent(x=5, y=5)
        a.move_left(m)
        assert a.pos == (4, 5)

    def test_move_right_increases_x(self):
        """move_right は x を 1 増やす"""
        m = make_map()
        a = make_agent(x=5, y=5)
        a.move_right(m)
        assert a.pos == (6, 5)

    def test_move_up_at_top_boundary(self):
        """y=0 でさらに上は False"""
        m = make_map()
        a = make_agent(x=5, y=0)
        assert a.move_up(m) is False
        assert a.pos == (5, 0)

    def test_move_down_at_bottom_boundary(self):
        """y=height-1 でさらに下は False"""
        m = make_map(height=50)
        a = make_agent(x=5, y=49)
        assert a.move_down(m) is False
        assert a.pos == (5, 49)

    def test_move_left_at_left_boundary(self):
        """x=0 でさらに左は False"""
        m = make_map()
        a = make_agent(x=0, y=5)
        assert a.move_left(m) is False
        assert a.pos == (0, 5)

    def test_move_right_at_right_boundary(self):
        """x=width-1 でさらに右は False"""
        m = make_map(width=10)
        a = make_agent(x=9, y=5)
        assert a.move_right(m) is False
        assert a.pos == (9, 5)

    def test_multiple_moves_accumulate(self):
        """複数回の移動が累積される"""
        m = make_map()
        a = make_agent(x=3, y=3)
        a.move_right(m)
        a.move_right(m)
        a.move_down(m)
        assert a.pos == (5, 4)


# ─────────────────────────────────────────
# Agent.dist_cells()
# ─────────────────────────────────────────
class TestDistCells:

    def _pair(self, x1, y1, x2, y2):
        return make_agent(x=x1, y=y1), make_agent(x=x2, y=y2)

    def test_same_position(self):
        """同じ座標なら距離 = 0"""
        a, b = self._pair(5, 5, 5, 5)
        assert a.dist_cells(b) == pytest.approx(0.0)

    def test_horizontal(self):
        """水平方向 5 セル"""
        a, b = self._pair(0, 0, 5, 0)
        assert a.dist_cells(b) == pytest.approx(5.0)

    def test_vertical(self):
        """垂直方向 7 セル"""
        a, b = self._pair(0, 0, 0, 7)
        assert a.dist_cells(b) == pytest.approx(7.0)

    def test_diagonal_3_4_5(self):
        """3-4-5 直角三角形 → 距離 = 5"""
        a, b = self._pair(0, 0, 3, 4)
        assert a.dist_cells(b) == pytest.approx(5.0)

    def test_symmetry(self):
        """a→b と b→a の距離は等しい"""
        a, b = self._pair(2, 3, 7, 10)
        assert a.dist_cells(b) == pytest.approx(b.dist_cells(a))

    def test_unit_diagonal(self):
        """斜め 1 マス → √2"""
        a, b = self._pair(0, 0, 1, 1)
        assert a.dist_cells(b) == pytest.approx(math.sqrt(2))

    def test_negative_displacement(self):
        """dx/dy が負でも正しい距離"""
        a, b = self._pair(5, 5, 2, 1)
        assert a.dist_cells(b) == pytest.approx(5.0)  # 3-4-5


# ─────────────────────────────────────────
# Agent.in_search_range()
# ─────────────────────────────────────────
class TestInSearchRange:
    """SEARCH_RANGE_C = 8.0"""

    def _pair(self, x1, y1, x2, y2):
        return make_agent(x=x1, y=y1), make_agent(x=x2, y=y2)

    def test_search_range_constant(self):
        assert SEARCH_RANGE_C == 8.0

    def test_same_position_in_range(self):
        """同一位置は範囲内"""
        a, b = self._pair(5, 5, 5, 5)
        assert a.in_search_range(b)

    def test_boundary_exact_in_range(self):
        """距離ちょうど 8.0 → 範囲内（≤ で判定）"""
        a, b = self._pair(0, 0, 8, 0)    # dist = 8.0
        assert a.in_search_range(b)

    def test_just_outside_range(self):
        """距離 9 → 範囲外"""
        a, b = self._pair(0, 0, 9, 0)    # dist = 9.0
        assert not a.in_search_range(b)

    def test_diagonal_inside(self):
        """斜め (4, 4) → dist = √32 ≈ 5.66 → 範囲内"""
        a, b = self._pair(0, 0, 4, 4)
        assert a.in_search_range(b)

    def test_far_outside(self):
        """遠距離 (0, 20) → 範囲外"""
        a, b = self._pair(0, 0, 0, 20)
        assert not a.in_search_range(b)

    def test_symmetry(self):
        """a→b と b→a の結果は等しい"""
        a, b = self._pair(0, 0, 6, 0)
        assert a.in_search_range(b) == b.in_search_range(a)


# ─────────────────────────────────────────
# Agent.in_lockon_range()
# ─────────────────────────────────────────
class TestInLockonRange:
    """LOCKON_RANGE_C = 6.0"""

    def _pair(self, x1, y1, x2, y2):
        return make_agent(x=x1, y=y1), make_agent(x=x2, y=y2)

    def test_lockon_range_constant(self):
        assert LOCKON_RANGE_C == 6.0

    def test_same_position_in_lockon(self):
        """同一位置はロックオン範囲内"""
        a, b = self._pair(5, 5, 5, 5)
        assert a.in_lockon_range(b)

    def test_boundary_exact_in_lockon(self):
        """距離ちょうど 6.0 → ロックオン範囲内（≤ で判定）"""
        a, b = self._pair(0, 0, 6, 0)    # dist = 6.0
        assert a.in_lockon_range(b)

    def test_just_outside_lockon(self):
        """距離 7 → ロックオン範囲外"""
        a, b = self._pair(0, 0, 7, 0)    # dist = 7.0
        assert not a.in_lockon_range(b)

    def test_diagonal_inside_lockon(self):
        """斜め (3, 3) → dist = √18 ≈ 4.24 → ロックオン範囲内"""
        a, b = self._pair(0, 0, 3, 3)
        assert a.in_lockon_range(b)

    def test_lockon_implies_search(self):
        """ロックオン範囲内ならば必ず索敵範囲内（ロックオン ⊆ 索敵）"""
        a, b = self._pair(0, 0, 5, 0)    # dist = 5.0, lockon=True
        assert a.in_lockon_range(b)
        assert a.in_search_range(b)

    def test_search_not_lockon(self):
        """索敵範囲内でもロックオン範囲外になる距離が存在する"""
        a, b = self._pair(0, 0, 7, 0)    # dist = 7.0: search=True(7≤8), lockon=False(7>6)
        assert a.in_search_range(b)
        assert not a.in_lockon_range(b)

    def test_outside_both_ranges(self):
        """索敵範囲外ならロックオン範囲外でもある"""
        a, b = self._pair(0, 0, 9, 0)    # dist = 9.0
        assert not a.in_search_range(b)
        assert not a.in_lockon_range(b)

    def test_symmetry(self):
        """a→b と b→a の結果は等しい"""
        a, b = self._pair(0, 0, 5, 0)
        assert a.in_lockon_range(b) == b.in_lockon_range(a)


# ─────────────────────────────────────────
# Role 属性
# ─────────────────────────────────────────
class TestAgentRole:
    """
    Agent.role — ロール属性のテスト。
    現フェーズでは全エージェントが Assault に固定されている。
    """

    def test_default_role_is_assault(self):
        """デフォルトロールは Role.ASSAULT"""
        assert make_agent().role is Role.ASSAULT

    def test_role_can_be_set_to_heavy_assault(self):
        """role=Role.HEAVY_ASSAULT を指定できる"""
        a = Agent(agent_id=1, x=5, y=25, team=0, role=Role.HEAVY_ASSAULT)
        assert a.role is Role.HEAVY_ASSAULT

    def test_role_can_be_set_to_support(self):
        """role=Role.SUPPORT を指定できる"""
        a = Agent(agent_id=1, x=5, y=25, team=0, role=Role.SUPPORT)
        assert a.role is Role.SUPPORT

    def test_role_can_be_set_to_sniper(self):
        """role=Role.SNIPER を指定できる"""
        a = Agent(agent_id=1, x=5, y=25, team=0, role=Role.SNIPER)
        assert a.role is Role.SNIPER

    def test_role_enum_has_four_members(self):
        """Role enum は Assault / HeavyAssault / Support / Sniper の4種類"""
        assert len(Role) == 4
        assert Role.ASSAULT in Role
        assert Role.HEAVY_ASSAULT in Role
        assert Role.SUPPORT in Role
        assert Role.SNIPER in Role
