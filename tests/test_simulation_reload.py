"""
tests/test_simulation_reload.py
Simulation のリロードタイマーロジックテスト

テスト対象:
  - _resolve_combat(): reload_timer > 0 のとき射撃しない / タイマー減算 / ammo 消費 / リロード開始
  - _process_respawns(): リスポーン時に ammo_in_clip = clip / reload_timer = 0 にリセット
  - clip=0（デフォルト）時の後方互換（リロードなし・無限弾）
"""
import pytest
from simulation import (
    Simulation, Agent, Map,
    AGENT_HP, DPS, RESPAWN_STEPS, MAP_W, MAP_H,
)


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────
def make_sim() -> Simulation:
    """全 EMPTY の最小 Simulation を返す。"""
    return Simulation(Map(MAP_W, MAP_H), plants=[])


def add_agent(sim: Simulation, agent_id: int, x: int, y: int,
              team: int, **kwargs) -> Agent:
    a = Agent(agent_id=agent_id, x=x, y=y, team=team, **kwargs)
    sim.add_agent(a)
    return a


def kill_agent(agent: Agent, timer: int = RESPAWN_STEPS) -> None:
    agent.alive = False
    agent.hp = 0
    agent.respawn_timer = timer


# ─────────────────────────────────────────
# リロードタイマーによる射撃スキップ
# ─────────────────────────────────────────
class TestResolveCombatReloadTimer:

    def test_no_shoot_when_reload_timer_positive(self):
        """reload_timer=1 のシューターは射撃しない（敵に被弾なし）"""
        sim = make_sim()
        shooter = add_agent(sim, 1, 0, 0, team=0,
                            clip=30, reload_steps=3)
        shooter.ammo_in_clip = 0   # リロード中（弾切れ）状態を再現
        shooter.reload_timer = 1
        enemy = add_agent(sim, 2, 0, 5, team=1)  # ロックオン範囲内

        hp_before = enemy.hp
        sim._resolve_combat()

        assert enemy.hp == hp_before

    def test_reload_timer_decrements_each_step(self):
        """reload_timer=3 → _resolve_combat() 後に 2 になる"""
        sim = make_sim()
        shooter = add_agent(sim, 1, 0, 0, team=0, clip=30)
        shooter.reload_timer = 3
        # 敵なしでも timer は減算される
        add_agent(sim, 2, 0, 5, team=1)

        sim._resolve_combat()

        assert shooter.reload_timer == 2

    def test_shoot_when_reload_timer_zero(self):
        """reload_timer=0 かつ ammo あり → 通常射撃（敵に被弾する）"""
        sim = make_sim()
        add_agent(sim, 1, 0, 0, team=0,
                  clip=30)  # ammo_in_clip=30（clip と同値で自動初期化）、reload_timer=0（デフォルト）
        enemy = add_agent(sim, 2, 0, 5, team=1)
        enemy.detected = True

        hp_before = enemy.hp
        sim._resolve_combat()

        assert enemy.hp < hp_before  # ダメージが入った

    def test_ammo_refilled_when_timer_reaches_zero(self):
        """reload_timer=1 → _resolve_combat() 後に timer=0 かつ ammo_in_clip=clip に補充される"""
        sim = make_sim()
        shooter = add_agent(sim, 1, 0, 0, team=0,
                            clip=30, reload_steps=3)
        shooter.ammo_in_clip = 0   # リロード中（弾切れ）状態を再現
        shooter.reload_timer = 1
        add_agent(sim, 2, 0, 5, team=1)

        sim._resolve_combat()

        assert shooter.reload_timer == 0
        assert shooter.ammo_in_clip == 30  # clip と同値に補充


# ─────────────────────────────────────────
# ammo 消費とリロード開始
# ─────────────────────────────────────────
class TestAmmoDecrement:

    def test_ammo_decrements_by_shots_per_step_on_shoot(self):
        """1ステップの射撃で ammo_in_clip が shots_per_step 分だけ減少する"""
        sim = make_sim()
        shooter = add_agent(sim, 1, 0, 0, team=0,
                            clip=30, shots_per_step=1)  # ammo_in_clip=30（自動）
        enemy = add_agent(sim, 2, 0, 5, team=1)
        enemy.detected = True

        sim._resolve_combat()

        assert shooter.ammo_in_clip == 29  # 30 - 1

    def test_reload_timer_set_when_ammo_exhausted(self):
        """clip=1 かつ shots_per_step=1 → 1発撃ったあと reload_timer=reload_steps になる"""
        sim = make_sim()
        shooter = add_agent(sim, 1, 0, 0, team=0,
                            clip=1, reload_steps=5, shots_per_step=1)  # ammo_in_clip=1（自動）
        enemy = add_agent(sim, 2, 0, 5, team=1)
        enemy.detected = True

        sim._resolve_combat()

        assert shooter.reload_timer == 5

    def test_ammo_zero_when_reload_starts(self):
        """リロード開始直後は ammo_in_clip == 0"""
        sim = make_sim()
        shooter = add_agent(sim, 1, 0, 0, team=0,
                            clip=1, reload_steps=5, shots_per_step=1)  # ammo_in_clip=1（自動）
        enemy = add_agent(sim, 2, 0, 5, team=1)
        enemy.detected = True

        sim._resolve_combat()

        assert shooter.ammo_in_clip == 0

    def test_clip_zero_no_reload_no_ammo_track(self):
        """clip=0（デフォルト・無限弾）→ リロード発生しない、ammo_in_clip は 0 のまま"""
        sim = make_sim()
        shooter = add_agent(sim, 1, 0, 0, team=0)  # clip=0（デフォルト）
        enemy = add_agent(sim, 2, 0, 5, team=1)
        enemy.detected = True

        hp_before = enemy.hp
        sim._resolve_combat()

        assert shooter.reload_timer == 0       # リロードは発生しない
        assert shooter.ammo_in_clip == 0       # ammo_in_clip は変化しない
        assert enemy.hp < hp_before            # 射撃は行われた（無限弾）


# ─────────────────────────────────────────
# リスポーン時のリセット
# ─────────────────────────────────────────
class TestProcessRespawnReload:

    def test_ammo_refilled_on_respawn(self):
        """リスポーン後 ammo_in_clip は clip（満タン）にリセットされる"""
        sim = make_sim()
        agent = add_agent(sim, 1, 5, 10, team=0, clip=30)
        agent.ammo_in_clip = 0  # 弾切れ状態で撃破
        kill_agent(agent, timer=RESPAWN_STEPS)

        for _ in range(RESPAWN_STEPS):
            sim._process_respawns()

        assert agent.alive
        assert agent.ammo_in_clip == 30  # clip と同値

    def test_reload_timer_reset_on_respawn(self):
        """リスポーン後 reload_timer は 0 にリセットされる"""
        sim = make_sim()
        agent = add_agent(sim, 1, 5, 10, team=0, clip=30, reload_steps=5)
        kill_agent(agent, timer=RESPAWN_STEPS)
        agent.reload_timer = 5  # リロード中状態で撃破

        for _ in range(RESPAWN_STEPS):
            sim._process_respawns()

        assert agent.alive
        assert agent.reload_timer == 0

    def test_clip_zero_ammo_stays_zero_on_respawn(self):
        """clip=0（無限弾）のエージェントはリスポーン後も ammo_in_clip=0"""
        sim = make_sim()
        agent = add_agent(sim, 1, 5, 10, team=0)  # clip=0（デフォルト）
        kill_agent(agent, timer=RESPAWN_STEPS)

        for _ in range(RESPAWN_STEPS):
            sim._process_respawns()

        assert agent.alive
        assert agent.ammo_in_clip == 0
