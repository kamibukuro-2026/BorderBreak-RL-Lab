"""
tests/test_t13_detection_combat.py
T-13: 被索敵状態に応じた戦闘判定のテスト

仕様:
  - target.detected=True の場合のみ射撃可能
    （ロックオン範囲内でも detected=False の敵には射撃しない）
  - Brain.decide() の ATTACK 状態も detected=True の敵がいる場合のみ STAY
  - detected=False の敵はロックオン範囲内でも「位置不明」扱い → APPROACH へフォールバック
"""
import pytest

from simulation import (
    Simulation, Map, Agent,
    GreedyBaseAttackBrain, PlantCaptureBrain, AggressiveCombatBrain,
    Action, Plant,
    AGENT_HP, DPS, LOCKON_RANGE_C, SEARCH_RANGE_C,
    MAP_W, MAP_H,
)


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────
def make_sim() -> Simulation:
    return Simulation(Map(MAP_W, MAP_H), plants=[])


def add_agent(sim: Simulation, agent_id: int, x: int, y: int,
              team: int, detected: bool = False, hp: int | None = None,
              **kwargs) -> Agent:
    a = Agent(agent_id=agent_id, x=x, y=y, team=team, **kwargs)
    a.detected = detected
    if hp is not None:
        a.hp = hp
    sim.add_agent(a)
    return a


def make_agent(agent_id=1, x=5, y=25, team=0,
               detected=False, **kwargs) -> Agent:
    a = Agent(agent_id=agent_id, x=x, y=y, team=team, **kwargs)
    a.detected = detected
    return a


def make_brain_greedy(target=(5, 95)) -> GreedyBaseAttackBrain:
    return GreedyBaseAttackBrain(target=target)


def make_brain_plant(target=(5, 95)) -> PlantCaptureBrain:
    return PlantCaptureBrain(target=target)


def make_brain_aggressive(target=(5, 95)) -> AggressiveCombatBrain:
    return AggressiveCombatBrain(target=target)


def decide(brain, agent, game_map, agents, plants=None):
    return brain.decide(agent, game_map, plants or [], agents)


# ─────────────────────────────────────────
# _resolve_combat() — detected=False の敵への射撃禁止
# ─────────────────────────────────────────
class TestResolveCombatDetection:

    def test_undetected_target_not_shot_in_lockon_range(self):
        """ロックオン範囲内でも detected=False の敵にはダメージを与えない"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0, hit_rate=1.0)
        target = add_agent(sim, 2, 0, 5, team=1, detected=False)   # dist=5 ≤ lockon
        sim._resolve_combat()
        assert target.hp == AGENT_HP

    def test_detected_target_shot_in_lockon_range(self):
        """detected=True の敵はロックオン範囲内で通常ダメージを受ける"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0, hit_rate=1.0)
        target = add_agent(sim, 2, 0, 5, team=1, detected=True)    # dist=5 ≤ lockon
        sim._resolve_combat()
        assert target.hp == AGENT_HP - DPS

    def test_both_undetected_no_mutual_damage(self):
        """双方 detected=False → 互いにダメージなし"""
        sim = make_sim()
        a = add_agent(sim, 1, 0, 0, team=0, hit_rate=1.0, detected=False)
        b = add_agent(sim, 2, 0, 5, team=1, hit_rate=1.0, detected=False)
        sim._resolve_combat()
        assert a.hp == AGENT_HP
        assert b.hp == AGENT_HP

    def test_asymmetric_detection(self):
        """A が B を検出済み（b.detected=True）、B は A 未検出（a.detected=False）
        → B はダメージを受け、A はダメージを受けない"""
        sim = make_sim()
        a = add_agent(sim, 1, 0, 0, team=0, hit_rate=1.0, detected=False)
        b = add_agent(sim, 2, 0, 5, team=1, hit_rate=1.0, detected=True)
        sim._resolve_combat()
        assert b.hp < AGENT_HP    # A が B を射撃
        assert a.hp == AGENT_HP   # B は A を射撃できない

    def test_undetected_target_cannot_be_killed(self):
        """detected=False の敵には HP が1でも撃破できない"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0, hit_rate=1.0)
        target = add_agent(sim, 2, 0, 5, team=1, detected=False, hp=1)
        target.hp = 1
        sim._resolve_combat()
        assert target.alive is True
        assert target.hp == 1


# ─────────────────────────────────────────
# GreedyBaseAttackBrain — ATTACK 状態に detected 条件を追加
# ─────────────────────────────────────────
class TestGreedyBrainAttackDetection:

    def setup_method(self):
        self.m     = Map(MAP_W, MAP_H)
        self.brain = make_brain_greedy(target=(5, 95))
        self.agent = make_agent(agent_id=1, x=5, y=25, team=0)

    def test_no_attack_when_enemy_undetected_in_lockon(self):
        """ロックオン範囲内でも detected=False の敵 → STAY しない（APPROACH へ）"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, detected=False)  # dist=5
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is not Action.STAY

    def test_attack_when_enemy_detected_in_lockon(self):
        """detected=True かつロックオン範囲内 → STAY（射撃モード）"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, detected=True)   # dist=5
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.STAY

    def test_undetected_in_lockon_falls_back_to_approach(self):
        """detected=False の敵がロックオン範囲内 → APPROACH（接近して索敵を試みる）"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, detected=False)  # dist=5, search内
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        # ロックオン外敵として扱われ APPROACH に落ちる
        assert action is Action.MOVE_DOWN  # enemy は下方向 (y=30 > y=25)


# ─────────────────────────────────────────
# PlantCaptureBrain — ATTACK 状態に detected 条件を追加
# ─────────────────────────────────────────
class TestPlantBrainAttackDetection:

    def setup_method(self):
        self.m      = Map(MAP_W, MAP_H)
        self.brain  = make_brain_plant(target=(5, 95))
        self.agent  = make_agent(agent_id=1, x=5, y=25, team=0)

    def test_no_attack_when_enemy_undetected_in_lockon(self):
        """ロックオン範囲内でも detected=False → STAY しない"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, detected=False)
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is not Action.STAY

    def test_attack_when_enemy_detected_in_lockon(self):
        """detected=True かつロックオン範囲内 → STAY"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, detected=True)
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.STAY


# ─────────────────────────────────────────
# AggressiveCombatBrain — ATTACK 状態に detected 条件を追加
# ─────────────────────────────────────────
class TestAggressiveBrainAttackDetection:

    def setup_method(self):
        self.m     = Map(MAP_W, MAP_H)
        self.brain = make_brain_aggressive(target=(5, 95))
        self.agent = make_agent(agent_id=1, x=5, y=25, team=0)

    def test_no_attack_when_enemy_undetected_in_lockon(self):
        """ロックオン範囲内でも detected=False → STAY しない"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, detected=False)
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is not Action.STAY

    def test_attack_when_enemy_detected_in_lockon(self):
        """detected=True かつロックオン範囲内 → STAY"""
        enemy = make_agent(agent_id=2, x=5, y=30, team=1, detected=True)
        action = decide(self.brain, self.agent, self.m, [self.agent, enemy])
        assert action is Action.STAY
