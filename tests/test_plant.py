"""
tests/test_plant.py
Plant クラスおよび Simulation._update_plants() の単体テスト

テスト対象:
  - Plant.is_in_range()
  - Plant の初期状態（owner / capture_gauge / pos_m）
  - Plant クラス変数（CAPTURE_DURABILITY / MAX_CAPTURERS）
  - Simulation._update_plants() のゲージ更新ロジック
  - Simulation._update_plants() の占拠完了・オーナー変更
"""
import math
import pytest
from simulation import (
    Plant, Map, Agent, Simulation,
    PLANT_RADIUS_C, CELL_SIZE_M,
    MAP_W, MAP_H,
    create_map,
)


# ─────────────────────────────────────────
# テスト用ファクトリ
# ─────────────────────────────────────────
def make_plant(plant_id=1, x=5, y=25, radius=PLANT_RADIUS_C) -> Plant:
    return Plant(plant_id=plant_id, x=x, y=y, radius_cells=radius)


def make_sim(plant: Plant) -> Simulation:
    """プラント1個を持つ最小 Simulation（マップは全 EMPTY）"""
    return Simulation(Map(MAP_W, MAP_H), plants=[plant])


def add_agent(sim: Simulation, agent_id: int, x: int, y: int, team: int) -> Agent:
    """エージェントを作成して sim に登録し返す"""
    a = Agent(agent_id=agent_id, x=x, y=y, team=team)
    sim.add_agent(a)
    return a


# ─────────────────────────────────────────
# Plant クラス変数・初期状態
# ─────────────────────────────────────────
class TestPlantInitial:
    def test_default_owner_neutral(self):
        """初期オーナーは中立（-1）"""
        assert make_plant().owner == -1

    def test_default_capture_gauge_zero(self):
        """初期ゲージは 0.0"""
        assert make_plant().capture_gauge == 0.0

    def test_capture_durability_is_10(self):
        assert Plant.CAPTURE_DURABILITY == 10

    def test_max_capturers_is_3(self):
        assert Plant.MAX_CAPTURERS == 3

    def test_pos_m(self):
        """pos_m はセル座標 × CELL_SIZE_M"""
        plant = make_plant(x=5, y=25)
        assert plant.pos_m == (5 * CELL_SIZE_M, 25 * CELL_SIZE_M)

    def test_pos_m_origin(self):
        plant = make_plant(x=0, y=0)
        assert plant.pos_m == (0, 0)


# ─────────────────────────────────────────
# Plant.is_in_range()
# ─────────────────────────────────────────
class TestPlantIsInRange:
    """プラント中心 (5, 25)、半径 6.0 セルで確認"""

    def setup_method(self):
        self.plant = make_plant(x=5, y=25)

    def test_center_is_in_range(self):
        """中心セル自身は範囲内"""
        assert self.plant.is_in_range(5, 25)

    def test_boundary_vertical_top(self):
        """真上 6セル = 半径ちょうど → 範囲内"""
        assert self.plant.is_in_range(5, 19)   # dist = 6.0

    def test_boundary_vertical_bottom(self):
        """真下 6セル = 半径ちょうど → 範囲内"""
        assert self.plant.is_in_range(5, 31)   # dist = 6.0

    def test_boundary_horizontal_right(self):
        """真右 6セル → 範囲内"""
        assert self.plant.is_in_range(11, 25)   # dist = 6.0

    def test_boundary_horizontal_left(self):
        """真左 6セル → 範囲内"""
        assert self.plant.is_in_range(-1, 25)   # dist = 6.0

    def test_just_outside_vertical(self):
        """真上 7セル → 範囲外"""
        assert not self.plant.is_in_range(5, 18)  # dist = 7.0

    def test_just_outside_horizontal(self):
        """真右 7セル → 範囲外"""
        assert not self.plant.is_in_range(12, 25)  # dist = 7.0

    def test_diagonal_inside(self):
        """斜め (2,2) → dist = √8 ≈ 2.83 → 範囲内"""
        assert self.plant.is_in_range(7, 27)

    def test_diagonal_outside(self):
        """斜め (7,1) → dist = √50 ≈ 7.07 → 範囲外"""
        assert not self.plant.is_in_range(12, 26)

    def test_far_away(self):
        """遠距離は範囲外"""
        assert not self.plant.is_in_range(5, 10)  # dist = 15


# ─────────────────────────────────────────
# _update_plants() — ゲージ更新ロジック
# ─────────────────────────────────────────
class TestUpdatePlantsGauge:

    def test_no_agents_gauge_unchanged(self):
        """エージェントなし → ゲージ変化なし"""
        plant = make_plant()
        sim = make_sim(plant)
        sim._update_plants()
        assert plant.capture_gauge == 0.0

    def test_team_a_alone_gauge_increases_by_1(self):
        """チームA 1機のみ → +1"""
        plant = make_plant()
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=0)
        sim._update_plants()
        assert plant.capture_gauge == 1.0

    def test_team_b_alone_gauge_decreases_by_1(self):
        """チームB 1機のみ → -1"""
        plant = make_plant()
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=1)
        sim._update_plants()
        assert plant.capture_gauge == -1.0

    def test_equal_teams_1v1_gauge_unchanged(self):
        """1v1 → net=0 → ゲージ変化なし"""
        plant = make_plant()
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=0)
        add_agent(sim, 2, 5, 25, team=1)
        sim._update_plants()
        assert plant.capture_gauge == 0.0

    def test_2v1_net_plus_1(self):
        """チームA 2機 vs チームB 1機 → net=1 → +1"""
        plant = make_plant()
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=0)
        add_agent(sim, 2, 5, 25, team=0)
        add_agent(sim, 3, 5, 25, team=1)
        sim._update_plants()
        assert plant.capture_gauge == 1.0

    def test_3v0_net_plus_3(self):
        """チームA 3機のみ → net=3 → +3"""
        plant = make_plant()
        sim = make_sim(plant)
        for i in range(3):
            add_agent(sim, i + 1, 5, 25, team=0)
        sim._update_plants()
        assert plant.capture_gauge == 3.0

    def test_max_capturers_4_equals_3(self):
        """4機と3機の1ステップ後ゲージは同じ（MAX_CAPTURERS=3 上限）"""
        plant3 = make_plant()
        sim3 = make_sim(plant3)
        for i in range(3):
            add_agent(sim3, i + 1, 5, 25, team=0)
        sim3._update_plants()

        plant4 = make_plant()
        sim4 = make_sim(plant4)
        for i in range(4):
            add_agent(sim4, i + 1, 5, 25, team=0)
        sim4._update_plants()

        assert plant3.capture_gauge == plant4.capture_gauge

    def test_dead_agent_not_counted(self):
        """dead エージェントは占拠力にカウントされない"""
        plant = make_plant()
        sim = make_sim(plant)
        a = add_agent(sim, 1, 5, 25, team=0)
        a.alive = False
        sim._update_plants()
        assert plant.capture_gauge == 0.0

    def test_out_of_range_agent_not_counted(self):
        """範囲外エージェントはカウントされない"""
        plant = make_plant(x=5, y=25)
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 10, team=0)   # dist=15 > 3
        sim._update_plants()
        assert plant.capture_gauge == 0.0

    def test_returns_list(self):
        """戻り値は list"""
        plant = make_plant()
        sim = make_sim(plant)
        assert isinstance(sim._update_plants(), list)

    def test_no_event_before_capture(self):
        """占拠完了前はイベントリストが空"""
        plant = make_plant()
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=0)
        events = sim._update_plants()   # gauge=1、まだ占拠完了せず
        assert events == []


# ─────────────────────────────────────────
# _update_plants() — 占拠完了・オーナー変更
# ─────────────────────────────────────────
class TestUpdatePlantsOwnership:

    def _sim_a_capturing(self) -> tuple[Simulation, Plant]:
        """チームA が 1機で占拠中のシム"""
        plant = make_plant()
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=0)
        return sim, plant

    def test_owner_stays_neutral_after_9_steps(self):
        """9ステップ時点ではまだ中立（-1）"""
        sim, plant = self._sim_a_capturing()
        for _ in range(9):
            sim._update_plants()
        assert plant.owner == -1
        assert plant.capture_gauge == 9.0

    def test_owner_changes_to_a_at_step_10(self):
        """10ステップでチームA(0)が占拠"""
        sim, plant = self._sim_a_capturing()
        for _ in range(10):
            sim._update_plants()
        assert plant.owner == 0

    def test_gauge_clamps_at_positive_max(self):
        """11ステップ以降もゲージは +10 を超えない"""
        sim, plant = self._sim_a_capturing()
        for _ in range(15):
            sim._update_plants()
        assert plant.capture_gauge == Plant.CAPTURE_DURABILITY

    def test_owner_changes_to_b_at_minus_10(self):
        """-10到達でチームB(1)が占拠"""
        plant = make_plant()
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=1)
        for _ in range(10):
            sim._update_plants()
        assert plant.owner == 1

    def test_gauge_clamps_at_negative_max(self):
        """チームB占拠後もゲージは -10 を下回らない"""
        plant = make_plant()
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=1)
        for _ in range(15):
            sim._update_plants()
        assert plant.capture_gauge == -Plant.CAPTURE_DURABILITY

    def test_capture_event_returned_on_completion(self):
        """占拠完了ステップでイベントメッセージが返る"""
        sim, plant = self._sim_a_capturing()
        events = []
        for _ in range(10):
            events = sim._update_plants()
        # 10ステップ目のイベントにチームA占拠メッセージが含まれる
        assert any("チームA" in e for e in events)

    def test_no_duplicate_event_on_already_captured(self):
        """既にチームA占拠済みのプラントに再度チームAがいてもイベントなし"""
        plant = make_plant()
        plant.owner = 0
        plant.capture_gauge = float(Plant.CAPTURE_DURABILITY)
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=0)
        events = sim._update_plants()   # gauge は 10 のままで owner も変わらない
        assert events == []

    def test_recapture_b_takes_a_plant(self):
        """チームAが占拠したプラントをチームBが奪還する（20ステップ）"""
        plant = make_plant()
        plant.owner = 0
        plant.capture_gauge = float(Plant.CAPTURE_DURABILITY)   # +10（チームA占拠済み）
        sim = make_sim(plant)
        add_agent(sim, 1, 5, 25, team=1)   # チームBが1機滞在

        # +10 → 0 に10ステップ、0 → -10 にさらに10ステップ = 計20ステップ
        for _ in range(20):
            sim._update_plants()

        assert plant.owner == 1
        assert plant.capture_gauge == -Plant.CAPTURE_DURABILITY

# ─────────────────────────────────────────
# Plant.get_spawn_points()
# ─────────────────────────────────────────
class TestPlantSpawnPoints:
    """プラント再出撃地点の単体テスト"""

    def setup_method(self):
        self.plant = make_plant(x=5, y=25)   # radius=6.0

    def test_returns_two_points_per_team(self):
        """各チームに2か所の再出撃地点を返す"""
        assert len(self.plant.get_spawn_points(0)) == 2
        assert len(self.plant.get_spawn_points(1)) == 2

    def test_team_a_spawn_y_is_above_circle(self):
        """Team A → y = plant.y - (int(radius) + 1)"""
        expected_y = self.plant.y - int(self.plant.radius_cells) - 1  # 25-4=21
        for _, y in self.plant.get_spawn_points(0):
            assert y == expected_y

    def test_team_b_spawn_y_is_below_circle(self):
        """Team B → y = plant.y + (int(radius) + 1)"""
        expected_y = self.plant.y + int(self.plant.radius_cells) + 1  # 25+4=29
        for _, y in self.plant.get_spawn_points(1):
            assert y == expected_y

    def test_spawn_points_symmetric_around_center_x(self):
        """左右の x が plant.x に対して対称"""
        for team in [0, 1]:
            (x1, _), (x2, _) = self.plant.get_spawn_points(team)
            assert x1 + x2 == 2 * self.plant.x   # 4+6 == 10

    def test_spawn_points_are_outside_circle(self):
        """再出撃地点はプラント占拠円の外側"""
        for team in [0, 1]:
            for x, y in self.plant.get_spawn_points(team):
                dist = math.dist((x, y), (self.plant.x, self.plant.y))
                assert dist > self.plant.radius_cells

    def test_all_plants_spawn_points_in_bounds(self):
        """全プラント × 全チームの再出撃地点がマップ範囲内"""
        game_map, plants = create_map()
        for plant in plants:
            for team in [0, 1]:
                for x, y in plant.get_spawn_points(team):
                    assert game_map.in_bounds(x, y), (
                        f"out of bounds: plant={plant.plant_id} team={team} ({x},{y})"
                    )


    def test_multiple_plants_updated_independently(self):
        """複数プラントが独立して更新される"""
        plant1 = make_plant(plant_id=1, x=5, y=14)
        plant2 = make_plant(plant_id=2, x=5, y=35)
        sim = Simulation(Map(MAP_W, MAP_H), plants=[plant1, plant2])
        # plant1 にはチームA、plant2 にはチームB を配置
        sim.add_agent(Agent(1, 5, 14, team=0))
        sim.add_agent(Agent(2, 5, 35, team=1))

        sim._update_plants()

        assert plant1.capture_gauge == 1.0    # チームA が +1
        assert plant2.capture_gauge == -1.0   # チームB が -1
