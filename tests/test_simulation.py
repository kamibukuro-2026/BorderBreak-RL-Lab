"""
tests/test_simulation.py
Simulation クラスの戦闘・リスポーン・コアダメージロジックの単体テスト

テスト対象:
  - Simulation._resolve_combat()
      同時解決・命中/外れ・撃破・複数シューター・最近接選択
  - Simulation._process_respawns()
      タイマーカウントダウン・リスポーン位置（ベース/プラント）・コアペナルティ
  - Simulation._update_cores()
      ベース滞在ダメージ・自チームベース無効・破壊済みスキップ・勝利イベント
"""
import pytest
from unittest.mock import patch

import random as _random

from simulation import (
    Simulation, Map, Agent, Plant, Core, CellType,
    AGENT_HP, DPS, RESPAWN_STEPS, CORE_DMG_PER_KILL,
    MAP_W, MAP_H, BASE_DEPTH, PLANT_RADIUS_C,
    MATCH_TIME_STEPS,
    create_map, get_base_spawn_points,
)

# random.random() の戻り値を固定するための定数
ALWAYS_HIT  = 0.0   # HIT_RATE=0.80 より小さい → 必ず命中
ALWAYS_MISS = 1.0   # HIT_RATE=0.80 以上 → 必ず外れ


# ─────────────────────────────────────────
# テスト用ファクトリ / ヘルパー
# ─────────────────────────────────────────
def make_sim(with_bases: bool = False) -> Simulation:
    """
    with_bases=False : 全 EMPTY の最小マップ
    with_bases=True  : create_map() でベースセルを含むフルマップ
    """
    if with_bases:
        game_map, plants = create_map()
        return Simulation(game_map, plants)
    return Simulation(Map(MAP_W, MAP_H), plants=[])


def add_agent(sim: Simulation, agent_id: int, x: int, y: int,
              team: int, hp: int = AGENT_HP) -> Agent:
    a = Agent(agent_id=agent_id, x=x, y=y, team=team)
    a.hp = hp
    sim.add_agent(a)
    return a


def kill_agent(agent: Agent, timer: int = RESPAWN_STEPS):
    """エージェントを撃破状態にする"""
    agent.alive = False
    agent.hp = 0
    agent.respawn_timer = timer


# ─────────────────────────────────────────
# _resolve_combat()
# ─────────────────────────────────────────
class TestResolveCombat:

    def test_returns_list(self):
        """戻り値は list"""
        assert isinstance(make_sim()._resolve_combat(), list)

    def test_no_agents_no_events(self):
        """エージェントなし → イベントなし"""
        assert make_sim()._resolve_combat() == []

    def test_out_of_lockon_range_no_damage(self):
        """ロックオン距離外（dist > 6）では射撃されない"""
        sim = make_sim()
        a = add_agent(sim, 1, 0,  0, team=0)
        b = add_agent(sim, 2, 0, 10, team=1)   # dist = 10 > LOCKON_RANGE_C=6
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert a.hp == AGENT_HP
        assert b.hp == AGENT_HP

    def test_always_hit_reduces_hp(self):
        """命中時に DPS 分 HP が減る"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        b = add_agent(sim, 2, 0, 5, team=1)   # dist = 5 ≤ 6
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert b.hp == AGENT_HP - DPS

    def test_always_miss_no_damage(self):
        """外れ時は HP 変化なし"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        b = add_agent(sim, 2, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_MISS):
            sim._resolve_combat()
        assert b.hp == AGENT_HP

    def test_dead_agent_does_not_shoot(self):
        """撃破済みエージェントは射撃しない"""
        sim = make_sim()
        a = add_agent(sim, 1, 0, 0, team=0)
        kill_agent(a)
        b = add_agent(sim, 2, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert b.hp == AGENT_HP

    def test_dead_agent_not_targeted(self):
        """撃破済みエージェントはターゲットにならない"""
        sim = make_sim()
        shooter = add_agent(sim, 1, 0, 0, team=0)
        dead_e  = add_agent(sim, 2, 0, 3, team=1)
        kill_agent(dead_e)                         # dist=3, dead
        live_e  = add_agent(sim, 3, 0, 5, team=1)  # dist=5, alive
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert dead_e.hp == 0        # dead のまま変化なし
        assert live_e.hp < AGENT_HP  # alive が撃たれる

    def test_same_team_no_damage(self):
        """同チームには射撃しない（フレンドリーファイアなし）"""
        sim = make_sim()
        a = add_agent(sim, 1, 0, 0, team=0)
        b = add_agent(sim, 2, 0, 5, team=0)   # 同チーム
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert a.hp == AGENT_HP
        assert b.hp == AGENT_HP

    def test_kill_sets_alive_false(self):
        """HP ≤ 0 → alive=False"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        b = add_agent(sim, 2, 0, 5, team=1, hp=DPS)   # 1 発で撃破される HP
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert b.alive is False

    def test_kill_sets_respawn_timer(self):
        """撃破時に respawn_timer = RESPAWN_STEPS"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        b = add_agent(sim, 2, 0, 5, team=1, hp=DPS)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert b.respawn_timer == RESPAWN_STEPS

    def test_kill_hp_clamped_to_zero(self):
        """オーバーキルでも HP は 0 で止まる（負にならない）"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        b = add_agent(sim, 2, 0, 5, team=1, hp=1)   # DPS=3000 で大幅超過
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert b.hp == 0

    def test_simultaneous_resolution_both_can_die(self):
        """同ステップ内で互いに撃破し合える（同時解決）"""
        sim = make_sim()
        a = add_agent(sim, 1, 0, 0, team=0, hp=DPS)
        b = add_agent(sim, 2, 0, 5, team=1, hp=DPS)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert a.alive is False
        assert b.alive is False

    def test_targets_nearest_enemy(self):
        """複数の敵がいる場合、最近接の敵をターゲットにする"""
        # shooter(0) at (0,0) | near(1) at (0,3) dist=3 | far_(1) at (0,5) dist=5
        # near/far_ は同チームなので互いに撃たない
        # near → shooter、far_ → shooter、shooter → near（最近接）
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        near  = add_agent(sim, 2, 0, 3, team=1)
        far_  = add_agent(sim, 3, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert near.hp == AGENT_HP - DPS   # 最近接が狙われる
        assert far_.hp == AGENT_HP         # 遠い方は被弾しない

    def test_multiple_shooters_accumulate_damage(self):
        """2 人が同じターゲットを命中 → 2×DPS の累積ダメージ"""
        # s1(0) at (0,0), s2(0) at (0,1), target(1) at (0,5)
        # target: dist(s1)=5, dist(s2)=4 → target は s2 を狙う
        # s1 と s2 はともに target を狙う → target が 2×DPS
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        add_agent(sim, 2, 0, 1, team=0)
        target = add_agent(sim, 3, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            sim._resolve_combat()
        assert target.hp == AGENT_HP - DPS * 2

    def test_event_returned_on_hit(self):
        """命中時にイベントリストが空でない"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        add_agent(sim, 2, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            events = sim._resolve_combat()
        assert len(events) > 0

    def test_kill_event_contains_kill_word(self):
        """撃破イベントに「撃破」が含まれる"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        add_agent(sim, 2, 0, 5, team=1, hp=DPS)
        with patch('simulation.random.random', return_value=ALWAYS_HIT):
            events = sim._resolve_combat()
        assert any("撃破" in e for e in events)

    def test_no_events_when_all_miss(self):
        """全弾外れ → イベントなし"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0)
        add_agent(sim, 2, 0, 5, team=1)
        with patch('simulation.random.random', return_value=ALWAYS_MISS):
            events = sim._resolve_combat()
        assert events == []


# ─────────────────────────────────────────
# _process_respawns()
# ─────────────────────────────────────────
class TestProcessRespawns:

    def test_returns_list(self):
        """戻り値は list"""
        assert isinstance(make_sim()._process_respawns(), list)

    def test_alive_agent_not_touched(self):
        """生存エージェントは処理されない"""
        sim = make_sim()
        a = add_agent(sim, 1, 5, 25, team=0)
        sim._process_respawns()
        assert a.alive is True
        assert a.respawn_timer == 0

    def test_dead_agent_timer_at_zero_skipped(self):
        """alive=False かつ timer=0 → 条件 timer<=0 により処理されない"""
        sim = make_sim()
        a = add_agent(sim, 1, 5, 25, team=0)
        a.alive = False
        a.respawn_timer = 0
        sim._process_respawns()
        assert a.alive is False   # 状態は変わらない

    def test_timer_decrements_each_step(self):
        """毎ステップ respawn_timer が 1 ずつ減る"""
        sim = make_sim()
        a = add_agent(sim, 1, 5, 25, team=0)
        kill_agent(a, timer=5)
        sim._process_respawns()
        assert a.respawn_timer == 4

    def test_no_respawn_while_timer_positive(self):
        """timer > 0 の間はリスポーンしない"""
        sim = make_sim()
        a = add_agent(sim, 1, 5, 25, team=0)
        kill_agent(a, timer=2)
        sim._process_respawns()   # timer: 2 → 1
        assert a.alive is False

    def test_respawn_when_timer_reaches_zero(self):
        """timer=1 → 1 ステップでタイマーが 0 になりリスポーン"""
        sim = make_sim()
        a = add_agent(sim, 1, 5, 25, team=0)
        kill_agent(a, timer=1)
        sim._process_respawns()
        assert a.alive is True

    def test_respawn_hp_restored(self):
        """リスポーン後 HP は AGENT_HP に回復"""
        sim = make_sim()
        a = add_agent(sim, 1, 5, 25, team=0)
        kill_agent(a, timer=1)
        sim._process_respawns()
        assert a.hp == AGENT_HP

    def test_respawn_at_base_team_a_y_coordinate(self):
        """友軍プラントなし → チームA は Base A 中心（y = BASE_DEPTH//2）にリスポーン"""
        sim = make_sim()   # plants=[] → 友軍プラントなし
        a = add_agent(sim, 1, 5, 25, team=0)
        kill_agent(a, timer=1)
        sim._process_respawns()
        assert a.y == BASE_DEPTH // 2   # = 1

    def test_respawn_at_base_team_b_y_coordinate(self):
        """友軍プラントなし → チームB は Base B 中心（y = MAP_H - BASE_DEPTH//2 - 1）にリスポーン"""
        sim = make_sim()
        b = add_agent(sim, 2, 5, 25, team=1)
        kill_agent(b, timer=1)
        sim._process_respawns()
        assert b.y == MAP_H - BASE_DEPTH // 2 - 1   # = 48

    def test_respawn_x_at_base_spawn_point(self):
        """ベースリスポーン後の x 座標はベース再出撃地点のいずれか（x=1 または x=MAP_W-2）"""
        sim = make_sim()
        a = add_agent(sim, 1, 0, 0, team=0)
        kill_agent(a, timer=1)
        sim._process_respawns()
        assert a.x in {1, MAP_W - 2}

    def test_respawn_at_friendly_plant(self):
        """自チーム占拠プラントがある場合はそのプラントの再出撃地点にリスポーン"""
        plant = Plant(plant_id=1, x=5, y=25, radius_cells=PLANT_RADIUS_C)
        plant.owner = 0   # チームA 所有
        sim = Simulation(Map(MAP_W, MAP_H), plants=[plant])
        a = Agent(agent_id=1, x=0, y=0, team=0)
        kill_agent(a, timer=1)
        sim.add_agent(a)
        sim._process_respawns()
        assert (a.x, a.y) in plant.get_spawn_points(team=0)

    def test_respawn_prefers_frontline_plant_team_a(self):
        """チームA は y が最大（敵ベース側）のプラントを優先し、その再出撃地点にリスポーン"""
        p1 = Plant(1, x=5, y=14, radius_cells=PLANT_RADIUS_C); p1.owner = 0
        p2 = Plant(2, x=5, y=35, radius_cells=PLANT_RADIUS_C); p2.owner = 0
        sim = Simulation(Map(MAP_W, MAP_H), plants=[p1, p2])
        a = Agent(agent_id=1, x=0, y=0, team=0)
        kill_agent(a, timer=1)
        sim.add_agent(a)
        sim._process_respawns()
        assert (a.x, a.y) in p2.get_spawn_points(team=0)   # p2(y=35) が前線

    def test_respawn_prefers_frontline_plant_team_b(self):
        """チームB は y が最小（敵ベース側）のプラントを優先し、その再出撃地点にリスポーン"""
        p1 = Plant(1, x=5, y=14, radius_cells=PLANT_RADIUS_C); p1.owner = 1
        p2 = Plant(2, x=5, y=35, radius_cells=PLANT_RADIUS_C); p2.owner = 1
        sim = Simulation(Map(MAP_W, MAP_H), plants=[p1, p2])
        b = Agent(agent_id=2, x=0, y=49, team=1)
        kill_agent(b, timer=1)
        sim.add_agent(b)
        sim._process_respawns()
        assert (b.x, b.y) in p1.get_spawn_points(team=1)   # p1(y=14) が前線

    def test_core_damage_applied_on_respawn(self):
        """リスポーン時に自チームのコアへ CORE_DMG_PER_KILL のダメージ"""
        sim = make_sim()
        a = add_agent(sim, 1, 5, 25, team=0)
        kill_agent(a, timer=1)
        initial_hp = sim.cores[0].hp
        sim._process_respawns()
        assert sim.cores[0].hp == pytest.approx(initial_hp - CORE_DMG_PER_KILL)

    def test_core_damage_only_own_team(self):
        """チームA がリスポーン → チームA コアのみ減少、チームB コアは不変"""
        sim = make_sim()
        a = add_agent(sim, 1, 5, 25, team=0)
        kill_agent(a, timer=1)
        b_hp_before = sim.cores[1].hp
        sim._process_respawns()
        assert sim.cores[1].hp == b_hp_before

    def test_multiple_steps_to_respawn(self):
        """RESPAWN_STEPS 回のステップで確実にリスポーンする"""
        sim = make_sim()
        a = add_agent(sim, 1, 5, 25, team=0)
        kill_agent(a, timer=RESPAWN_STEPS)
        for _ in range(RESPAWN_STEPS):
            sim._process_respawns()
        assert a.alive is True


# ─────────────────────────────────────────
# _update_cores()
# ─────────────────────────────────────────
class TestUpdateCores:

    def test_returns_list(self):
        """戻り値は list"""
        sim = make_sim(with_bases=True)
        assert isinstance(sim._update_cores(), list)

    def test_no_agents_no_damage(self):
        """エージェントなし → コアダメージなし"""
        sim = make_sim(with_bases=True)
        hp0, hp1 = sim.cores[0].hp, sim.cores[1].hp
        sim._update_cores()
        assert sim.cores[0].hp == hp0
        assert sim.cores[1].hp == hp1

    def test_team_a_in_base_b_damages_team_b_core(self):
        """チームA が BASE_B（y=47）に滞在 → チームB コアに DPS"""
        sim = make_sim(with_bases=True)
        add_agent(sim, 1, 5, 47, team=0)   # BASE_B セル
        initial = sim.cores[1].hp
        sim._update_cores()
        assert sim.cores[1].hp == pytest.approx(initial - DPS)

    def test_team_b_in_base_a_damages_team_a_core(self):
        """チームB が BASE_A（y=1）に滞在 → チームA コアに DPS"""
        sim = make_sim(with_bases=True)
        add_agent(sim, 2, 5, 1, team=1)    # BASE_A セル
        initial = sim.cores[0].hp
        sim._update_cores()
        assert sim.cores[0].hp == pytest.approx(initial - DPS)

    def test_friendly_in_own_base_no_damage(self):
        """自チームが自ベースにいても自コアはダメージなし"""
        sim = make_sim(with_bases=True)
        add_agent(sim, 1, 5, 1, team=0)    # BASE_A にチームA
        initial = sim.cores[0].hp
        sim._update_cores()
        assert sim.cores[0].hp == initial

    def test_dead_agent_in_enemy_base_no_damage(self):
        """撃破済みエージェントはベース内でもダメージを与えない"""
        sim = make_sim(with_bases=True)
        a = add_agent(sim, 1, 5, 47, team=0)
        kill_agent(a)
        initial = sim.cores[1].hp
        sim._update_cores()
        assert sim.cores[1].hp == initial

    def test_empty_cell_no_damage(self):
        """EMPTY セルにいるエージェントはダメージを与えない"""
        sim = make_sim(with_bases=True)
        add_agent(sim, 1, 5, 25, team=0)   # EMPTY セル（プラント付近）
        initial = sim.cores[1].hp
        sim._update_cores()
        assert sim.cores[1].hp == initial

    def test_destroyed_core_no_further_damage(self):
        """破壊済みコアはそれ以上ダメージを受けない（0 のまま）"""
        sim = make_sim(with_bases=True)
        sim.cores[1].hp = 0.0              # 事前に破壊済み
        add_agent(sim, 1, 5, 47, team=0)
        sim._update_cores()
        assert sim.cores[1].hp == 0.0

    def test_multiple_attackers_accumulate_damage(self):
        """同ベース内に 2 人いる → 2×DPS の累積ダメージ"""
        sim = make_sim(with_bases=True)
        add_agent(sim, 1, 5, 47, team=0)
        add_agent(sim, 2, 5, 48, team=0)
        initial = sim.cores[1].hp
        sim._update_cores()
        assert sim.cores[1].hp == pytest.approx(initial - DPS * 2)

    def test_events_returned_on_attack(self):
        """攻撃時はイベントリストが空でない"""
        sim = make_sim(with_bases=True)
        add_agent(sim, 1, 5, 47, team=0)
        events = sim._update_cores()
        assert len(events) > 0

    def test_no_events_when_no_attack(self):
        """攻撃なし → イベントリスト空"""
        sim = make_sim(with_bases=True)
        events = sim._update_cores()
        assert events == []

    def test_victory_event_on_core_destruction(self):
        """コア破壊ステップで勝利メッセージが返る"""
        sim = make_sim(with_bases=True)
        sim.cores[1].hp = DPS              # あと 1 撃で破壊
        add_agent(sim, 1, 5, 47, team=0)
        events = sim._update_cores()
        assert sim.cores[1].destroyed
        assert any("勝利" in e for e in events)

    def test_no_victory_event_when_core_survives(self):
        """コアが生き残っている間は勝利メッセージが出ない"""
        sim = make_sim(with_bases=True)
        add_agent(sim, 1, 5, 47, team=0)   # 1 発では破壊されない初期 HP
        events = sim._update_cores()
        assert not any("勝利" in e for e in events)


# ─────────────────────────────────────────
# get_base_spawn_points()
# ─────────────────────────────────────────
class TestBaseSpawnPoints:
    """get_base_spawn_points() の単体テスト"""

    def test_returns_two_points_per_team(self):
        """各チームに2か所返す"""
        for team in [0, 1]:
            assert len(get_base_spawn_points(team)) == 2

    def test_team_a_points_are_in_base_a(self):
        """Team A の再出撃地点は BASE_A セル"""
        game_map, _ = create_map()
        for x, y in get_base_spawn_points(0):
            assert game_map.get_cell(x, y) == CellType.BASE_A

    def test_team_b_points_are_in_base_b(self):
        """Team B の再出撃地点は BASE_B セル"""
        game_map, _ = create_map()
        for x, y in get_base_spawn_points(1):
            assert game_map.get_cell(x, y) == CellType.BASE_B

    def test_x_positions_1_from_each_edge(self):
        """x=1（左端から1格）と x=MAP_W-2（右端から1格）"""
        for team in [0, 1]:
            xs = sorted(x for x, _ in get_base_spawn_points(team))
            assert xs[0] == 1
            assert xs[1] == MAP_W - 2


# ─────────────────────────────────────────
# _process_respawns() — 新再出撃地点を使うか
# ─────────────────────────────────────────
class TestRespawnUsesNewSpawnPoints:
    """更新後の _process_respawns() がスポーン地点を正しく使うか"""

    def test_respawn_at_base_lands_on_base_spawn_point(self):
        """友軍プラントなし → ベース再出撃地点のいずれかにリスポーン"""
        sim = make_sim()   # plants=[]
        a = add_agent(sim, 1, 5, 25, team=0)
        kill_agent(a, timer=1)
        sim._process_respawns()
        assert (a.x, a.y) in get_base_spawn_points(team=0)

    def test_respawn_at_plant_lands_on_plant_spawn_point(self):
        """友軍プラントあり → そのプラントの再出撃地点のいずれかにリスポーン"""
        plant = Plant(plant_id=1, x=5, y=25, radius_cells=PLANT_RADIUS_C)
        plant.owner = 0
        sim = Simulation(Map(MAP_W, MAP_H), plants=[plant])
        a = Agent(agent_id=1, x=0, y=0, team=0)
        kill_agent(a, timer=1)
        sim.add_agent(a)
        sim._process_respawns()
        assert (a.x, a.y) in plant.get_spawn_points(team=0)

    def test_respawn_randomness_uses_both_sides(self):
        """十分な試行で左右どちらの再出撃地点も出現する"""
        plant = Plant(plant_id=1, x=5, y=25, radius_cells=PLANT_RADIUS_C)
        plant.owner = 0
        positions = set()
        for seed in range(30):
            _random.seed(seed)
            sim = Simulation(Map(MAP_W, MAP_H), plants=[plant])
            a = Agent(agent_id=1, x=0, y=0, team=0)
            kill_agent(a, timer=1)
            sim.add_agent(a)
            sim._process_respawns()
            positions.add((a.x, a.y))
        assert len(positions) > 1, "左右両方の再出撃地点が使われること"


# ─────────────────────────────────────────
# _resolve_time_limit()
# ─────────────────────────────────────────
class TestResolveTimeLimit:
    """試合制限時間勝敗判定の単体テスト"""

    def test_match_time_steps_is_600(self):
        """MATCH_TIME_STEPS = 600（10分 × 60秒）"""
        assert MATCH_TIME_STEPS == 600

    def test_team_a_wins_when_core_a_has_more_hp(self):
        """コアA HP > コアB HP → チームA（0）勝利"""
        sim = make_sim()
        sim.cores[0].hp = 200_000
        sim.cores[1].hp = 100_000
        assert sim._resolve_time_limit() == 0

    def test_team_b_wins_when_core_b_has_more_hp(self):
        """コアB HP > コアA HP → チームB（1）勝利"""
        sim = make_sim()
        sim.cores[0].hp = 100_000
        sim.cores[1].hp = 200_000
        assert sim._resolve_time_limit() == 1

    def test_draw_when_cores_have_equal_hp(self):
        """コアHP 完全一致 → 引き分け（None）"""
        sim = make_sim()
        sim.cores[0].hp = 150_000
        sim.cores[1].hp = 150_000
        assert sim._resolve_time_limit() is None

    def test_draw_when_both_cores_at_full_hp(self):
        """両コア満HP（試合開始直後想定）→ 引き分け"""
        sim = make_sim()
        assert sim._resolve_time_limit() is None

    def test_returns_int_or_none(self):
        """戻り値は int（0 or 1）または None"""
        sim = make_sim()
        result = sim._resolve_time_limit()
        assert result is None or result in (0, 1)
