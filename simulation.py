"""
Border Break シミュレーター - Simulation クラス

各サブモジュールの re-import ハブを兼ねており、テストは
  from simulation import Simulation, Agent, Brain, ...
で動作する。

描画ロジック  → renderer.py  (draw_simulation)
CSV ログ保存  → logger.py    (save_dev_logs)
実行エントリ  → main.py      (main)
"""
from __future__ import annotations  # 前方参照を文字列として遅延評価

import random

import matplotlib.pyplot as plt

from constants import (
    CELL_SIZE_M, MAP_WIDTH_M, MAP_HEIGHT_M, MAP_W, MAP_H,
    BASE_DEPTH, NUM_PLANTS, PLANT_RADIUS_M, PLANT_RADIUS_C,
    AGENT_HP, DPS, HIT_RATE, SEARCH_RANGE_M, SEARCH_RANGE_C,
    LOCKON_RANGE_M, LOCKON_RANGE_C, RESPAWN_STEPS, MOVE_SPEED_MPS, CELLS_PER_STEP,
    CORE_HP, CORE_DMG_PER_KILL, MATCH_TIME_STEPS, DETECTION_STEPS,
    LOCKON_BONUS, DIST_PENALTY_MAX, MISS_FLOOR_PER_SHOT,
    AIM_PARAM_BASE, AIM_SCALE, HIT_RATE_MIN, HIT_RATE_MAX,
    CRUISE_CONSUME_PER_STEP, CRUISE_START_COST, BOOST_REGEN_PER_STEP,
)
from game_types import (
    CELL_COLORS, CellType, ACTION_DELTA, Action, Role, Plant, Core, Map,
)
from brain import Brain, GreedyBaseAttackBrain, PlantCaptureBrain, AggressiveCombatBrain
from agent import (
    _ASSETS_DIR, _ROLE_IMAGE_FILES, _role_image_cache, _get_role_image,
    RoleLoadout, AgentLoadout, Agent,
)
from map_gen import get_base_spawn_points, create_map
from renderer import draw_simulation
from logger import save_dev_logs as _save_dev_logs


# ─────────────────────────────────────────
# シミュレーションクラス
# ─────────────────────────────────────────
class Simulation:
    def __init__(self, game_map: Map, plants: list[Plant]):
        self.game_map   = game_map
        self.plants     = plants
        self.agents: list[Agent] = []
        self.step_count = 0
        self.cores: dict[int, Core] = {0: Core(team=0), 1: Core(team=1)}
        self._step_log:  list[dict] = []   # ステップごとのスナップショット（開発ログ用）
        self._event_log: list[dict] = []   # イベントログ（開発ログ用）

    def add_agent(self, agent: Agent):
        self.agents.append(agent)

    def _log_event(self, event_type: str, **kwargs):
        """構造化イベントを内部ログに追加する（開発ログ用）。"""
        self._event_log.append({
            'step':        self.step_count,
            'event_type':  event_type,
            'agent_id':    kwargs.get('agent_id',    ''),
            'agent_team':  kwargs.get('agent_team',  ''),
            'target_id':   kwargs.get('target_id',   ''),
            'target_team': kwargs.get('target_team', ''),
            'damage':      kwargs.get('damage',      ''),
            'plant_id':    kwargs.get('plant_id',    ''),
            'detail':      kwargs.get('detail',      ''),
        })

    # ── 描画（renderer.py へ委譲） ────────────────────────────────
    def _draw(self, ax, title: str | None = None):
        """ax にマップ・プラント・エージェントを描画する（静的/アニメ共通）。"""
        draw_simulation(self, ax, title)

    def visualize(self, title: str | None = None):
        """現在の状態を静止画として表示する。"""
        fig, ax = plt.subplots(figsize=(7, 22))
        draw_simulation(self, ax, title)
        plt.tight_layout()
        plt.show()

    # ── 占拠ゲージ更新 ────────────────────────────────────────────
    def _update_plants(self) -> list[str]:
        """
        全プラントの占拠ゲージを 1 ステップ分更新する。

        ルール:
          - ゾーン内の各チームの BR 数を集計し、MAX_CAPTURERS で上限をとる。
          - net = power_A - power_B を capture_gauge に加算する。
          - ゲージは [-CAPTURE_DURABILITY, +CAPTURE_DURABILITY] にクランプ。
          - +CAPTURE_DURABILITY 到達 → owner = 0 (チームA)
          - -CAPTURE_DURABILITY 到達 → owner = 1 (チームB)
          - 中間状態（再占拠中）では owner は変化しない。

        Returns: このステップで発生した占拠イベントのメッセージリスト
        """
        events: list[str] = []
        for plant in self.plants:
            count = {0: 0, 1: 0}
            for agent in self.agents:
                if agent.alive and plant.is_in_range(agent.x, agent.y):
                    count[agent.team] += 1

            power_A = min(count[0], plant.MAX_CAPTURERS)
            power_B = min(count[1], plant.MAX_CAPTURERS)
            net = power_A - power_B

            if net == 0:
                continue

            old_owner = plant.owner
            plant.capture_gauge = max(
                -plant.CAPTURE_DURABILITY,
                min(plant.CAPTURE_DURABILITY, plant.capture_gauge + net)
            )

            if plant.capture_gauge >= plant.CAPTURE_DURABILITY and old_owner != 0:
                plant.owner = 0
                events.append(
                    f"  ★★ P{plant.plant_id} がチームA に占拠されました"
                    f"  (gauge={plant.capture_gauge:+.0f})"
                )
                self._log_event('plant_capture', plant_id=plant.plant_id, agent_team=0)
            elif plant.capture_gauge <= -plant.CAPTURE_DURABILITY and old_owner != 1:
                plant.owner = 1
                events.append(
                    f"  ★★ P{plant.plant_id} がチームB に占拠されました"
                    f"  (gauge={plant.capture_gauge:+.0f})"
                )
                self._log_event('plant_capture', plant_id=plant.plant_id, agent_team=1)

        return events

    # ── ベース攻撃（コアダメージ） ────────────────────────────────
    def _update_cores(self) -> list[str]:
        """
        敵ベース内に滞在している BR が、毎ステップ DPS 分のダメージをコアに与える。

        Returns: このステップで発生したコアダメージ・勝利イベントのメッセージリスト
        """
        events: list[str] = []
        base_cell_to_team = {CellType.BASE_A: 0, CellType.BASE_B: 1}

        for agent in self.agents:
            if not agent.alive:
                continue
            cell = self.game_map.get_cell(agent.x, agent.y)
            if cell not in base_cell_to_team:
                continue
            base_owner = base_cell_to_team[cell]
            if agent.team == base_owner:
                continue

            core = self.cores[base_owner]
            if core.destroyed:
                continue

            prev_hp = core.hp
            core.apply_damage(agent.dps)
            lbl = "A" if base_owner == 0 else "B"
            events.append(
                f"  💥 BR{agent.agent_id} が CORE {lbl} を攻撃！"
                f"  -{agent.dps}  → {int(core.hp):,}/{int(core.max_hp):,}"
                f" ({core.hp_pct:.1f}%)"
            )
            self._log_event('core_attack', agent_id=agent.agent_id, agent_team=agent.team,
                            target_team=base_owner, damage=agent.dps)

            if prev_hp > 0 and core.destroyed:
                winner_lbl = "B" if base_owner == 0 else "A"
                events.append(
                    f"\n  {'█'*36}\n"
                    f"  ★ チーム{winner_lbl} の勝利！ CORE {lbl} が破壊されました！\n"
                    f"  {'█'*36}"
                )
                self._log_event('victory', agent_team=1 - base_owner)

        return events

    # ── 被索敵状態の更新 ──────────────────────────────────────────
    def _update_detection(self):
        """
        全エージェントの被索敵状態（detected / exposure_steps）を更新する。

        ルール:
          - 死亡エージェント: exposure_steps=0, detected=False にリセット
          - 生存エージェントが敵の索敵範囲内: exposure_steps += 1
          - 索敵範囲外に出た: exposure_steps = 0
          - ロックオン範囲内に敵がいる、または exposure_steps >= DETECTION_STEPS → detected=True
        """
        for agent in self.agents:
            if not agent.alive:
                agent.exposure_steps = 0
                agent.detected = False
                continue
            enemies = [a for a in self.agents if a.alive and a.team != agent.team]
            in_search = any(e.in_search_range(agent) for e in enemies)
            locked_on = any(e.in_lockon_range(agent) for e in enemies)
            if in_search:
                agent.exposure_steps += 1
            else:
                agent.exposure_steps = 0
            agent.detected = locked_on or agent.exposure_steps >= DETECTION_STEPS

    # ── 制限時間勝敗判定 ──────────────────────────────────────────
    def _resolve_time_limit(self) -> int | None:
        """
        時間切れ時の勝敗を判定する。

        Returns: 勝利チーム番号（0=チームA / 1=チームB）または None（引き分け）
        """
        hp_a = self.cores[0].hp
        hp_b = self.cores[1].hp
        if hp_a > hp_b:
            return 0
        if hp_b > hp_a:
            return 1
        return None

    # ── 命中率計算（決定論的 DPS 分率モデル） ────────────────────
    def _calc_hit_fraction(self, shooter: Agent, target: Agent) -> float:
        """
        shooter から target への hit_fraction（0.0〜1.0）を計算する。

        計算式:
          - ロックオン範囲内: hit_frac = min(1.0, shooter.hit_rate * LOCKON_BONUS)
          - 索敵〜ロックオン範囲: hit_frac = shooter.hit_rate * (1 - t * DIST_PENALTY_MAX)
            （t: ロックオン境界=0、索敵境界=1 の線形補間）
          - rate_floor = 1 - (1 - MISS_FLOOR_PER_SHOT) ** shooter.shots_per_step
          - 最終: max(rate_floor, min(1.0, hit_frac))
        """
        dist = shooter.dist_cells(target)
        if dist <= shooter.lockon_range_c:
            hit_frac = min(1.0, shooter.hit_rate * LOCKON_BONUS)
        else:
            span = shooter.search_range_c - shooter.lockon_range_c
            t = (dist - shooter.lockon_range_c) / span if span > 0 else 1.0
            t = min(1.0, max(0.0, t))
            hit_frac = shooter.hit_rate * (1.0 - t * DIST_PENALTY_MAX)
        rate_floor = 1.0 - (1.0 - MISS_FLOOR_PER_SHOT) ** shooter.shots_per_step
        return max(rate_floor, min(1.0, hit_frac))

    # ── 戦闘ダメージ解決 ──────────────────────────────────────────
    def _resolve_combat(self) -> list[str]:
        """
        ロックオン距離内の敵へ射撃ダメージを適用する（同時解決）。

        処理手順:
          1. 全生存エージェントのロックオン距離内の最近接敵を特定する。
          2. _calc_hit_fraction() で hit_fraction を計算し、damage = int(dps × hit_fraction) を積算。
          3. 全員分を計算し終えてから一括でHP を減算（同ステップ内は互いに相打ちあり）。
          4. HP が 0 以下になったエージェントを撃破状態にし、リスポーンタイマーをセット。

        Returns: このステップで発生した戦闘イベントのメッセージリスト
        """
        events: list[str] = []

        pending_damage: dict[int, int] = {}
        shooters: dict[int, int] = {}
        hit_log: list[tuple[int, int, int, int, int]] = []

        for agent in self.agents:
            if not agent.alive:
                continue

            # T-4: リロードタイマー処理（タイマー中は射撃スキップ）
            if agent.reload_timer > 0:
                agent.reload_timer -= 1
                if agent.reload_timer == 0 and agent.clip > 0:
                    agent.ammo_in_clip = agent.clip
                continue

            # T-13: detected=False の敵は位置不明扱いのため射撃不可
            in_range = [
                a for a in self.agents
                if a.alive and a.team != agent.team
                and agent.in_lockon_range(a) and a.detected
            ]
            if not in_range:
                continue

            target = min(in_range, key=lambda e: agent.dist_cells(e))

            hit_frac = self._calc_hit_fraction(agent, target)
            dmg = int(agent.dps * hit_frac)
            if dmg > 0:
                tid = target.agent_id
                pending_damage[tid] = pending_damage.get(tid, 0) + dmg
                shooters[tid] = agent.agent_id
                hit_log.append((agent.agent_id, agent.team, tid, target.team, dmg))

            # T-4: ammo 消費とリロード開始（clip=0 は無限弾・後方互換）
            if agent.clip > 0:
                agent.ammo_in_clip -= agent.shots_per_step
                if agent.ammo_in_clip <= 0:
                    agent.ammo_in_clip = 0
                    agent.reload_timer = agent.reload_steps

        for agent in self.agents:
            dmg = pending_damage.get(agent.agent_id, 0)
            if dmg == 0:
                continue
            agent.hp -= dmg
            team_str = "A" if agent.team == 0 else "B"
            shooter_str = f"BR{shooters[agent.agent_id]}"
            if agent.hp <= 0:
                agent.hp = 0
                agent.alive = False
                agent.respawn_timer = RESPAWN_STEPS
                events.append(
                    f"  ★★★ {shooter_str} が BR{agent.agent_id}(チーム{team_str}) を撃破！"
                    f"  ({RESPAWN_STEPS}s 後にリスポーン)"
                )
                for sh_id, sh_team, tgt_id, tgt_team, hit_dmg in hit_log:
                    if tgt_id == agent.agent_id:
                        self._log_event('kill', agent_id=sh_id, agent_team=sh_team,
                                        target_id=tgt_id, target_team=tgt_team, damage=hit_dmg)
            else:
                hp_pct = agent.hp / agent.max_hp * 100
                events.append(
                    f"  ⚡ {shooter_str} → BR{agent.agent_id}(チーム{team_str})"
                    f"  -{dmg}  HP: {agent.hp}/{agent.max_hp} ({hp_pct:.0f}%)"
                )
                for sh_id, sh_team, tgt_id, tgt_team, hit_dmg in hit_log:
                    if tgt_id == agent.agent_id:
                        self._log_event('hit', agent_id=sh_id, agent_team=sh_team,
                                        target_id=tgt_id, target_team=tgt_team, damage=hit_dmg)

        return events

    # ── リスポーン処理 ────────────────────────────────────────────
    def _process_respawns(self) -> list[str]:
        """
        撃破されたエージェントのリスポーンタイマーを更新し、
        タイマーが 0 になったエージェントを復活させる。

        Returns: このステップで発生したリスポーンイベントのメッセージリスト
        """
        events: list[str] = []

        for agent in self.agents:
            if agent.alive or agent.respawn_timer <= 0:
                continue

            agent.respawn_timer -= 1

            if agent.respawn_timer == 0:
                friendly = [p for p in self.plants if p.owner == agent.team]
                if friendly:
                    if agent.team == 0:
                        plant = max(friendly, key=lambda p: p.y)
                    else:
                        plant = min(friendly, key=lambda p: p.y)
                    spawn_x, spawn_y = random.choice(plant.get_spawn_points(agent.team))
                    spawn_desc = f"P{plant.plant_id}"
                else:
                    spawn_x, spawn_y = random.choice(get_base_spawn_points(agent.team))
                    spawn_desc = f"Base {'A' if agent.team == 0 else 'B'}"

                agent.x     = spawn_x
                agent.y     = spawn_y
                agent.hp    = agent.max_hp
                agent.alive = True
                if agent.boost_max > 0:
                    agent.boost = float(agent.boost_max)
                    agent.is_cruising = False
                agent.ammo_in_clip = agent.clip
                agent.reload_timer = 0
                team_str = "A" if agent.team == 0 else "B"
                events.append(
                    f"  ★ BR{agent.agent_id}(チーム{team_str}) が {spawn_desc} からリスポーン！"
                )
                self._log_event('respawn', agent_id=agent.agent_id, agent_team=agent.team,
                                detail=f'{spawn_x},{spawn_y}')

                core = self.cores[agent.team]
                core.apply_damage(CORE_DMG_PER_KILL)
                events.append(
                    f"  ↓ CORE {team_str} -キルペナルティ {int(CORE_DMG_PER_KILL):,}"
                    f"  → {int(core.hp):,}/{int(core.max_hp):,}"
                    f" ({core.hp_pct:.1f}%)"
                )
                self._log_event('kill_penalty', agent_id=agent.agent_id, agent_team=agent.team,
                                target_team=agent.team, damage=CORE_DMG_PER_KILL)

        return events

    # ── アクション実行 ────────────────────────────────────────────
    def _get_move_cells(self, agent: Agent) -> int:
        """
        移動時の実際のセル数を返す。

        boost_max=0（デフォルト）: 後方互換モード → cells_per_step を使用。
        boost_max>0: ブーストゲージに応じて dash / walk を切り替える。
        """
        if agent.boost_max == 0:
            return agent.cells_per_step

        cost = CRUISE_CONSUME_PER_STEP
        if not agent.is_cruising:
            cost += CRUISE_START_COST

        if agent.boost >= cost:
            agent.boost = max(0.0, agent.boost - cost)
            agent.is_cruising = True
            return agent.dash_cells_per_step
        else:
            agent.is_cruising = False
            agent.boost = min(float(agent.boost_max),
                              agent.boost + agent.boost_regen)
            return agent.walk_cells_per_step

    def _execute_action(self, agent: Agent, action: Action):
        ddx, ddy = ACTION_DELTA[action]
        if ddx != 0 or ddy != 0:
            cells = self._get_move_cells(agent)
            for _ in range(cells):
                if not agent.move(ddx, ddy, self.game_map):
                    break
        else:
            if agent.boost_max > 0:
                agent.boost = min(float(agent.boost_max),
                                  agent.boost + agent.boost_regen)
                agent.is_cruising = False

    # ── シミュレーション実行（アニメーション） ──────────────────
    def run(self, max_steps: int = 60, step_delay: float = 0.0,
            verbose: bool = False):
        """
        全エージェントを自律移動させ、リアルタイムで描画する。

        Parameters
        ----------
        max_steps  : 最大ステップ数
        step_delay : 1ステップあたりの表示時間（秒）。0 にすると GUI 非表示（デフォルト）。
        verbose    : コンソールへの詳細ログ出力。False にすると全 print を抑制（デフォルト）。
        """
        if verbose:
            print(f"=== シミュレーション開始  max_steps={max_steps} ===\n")

        prev_plant_ids: dict[int, set[int]] = {a.agent_id: set() for a in self.agents}

        if step_delay > 0:
            plt.ion()
            fig, ax = plt.subplots(figsize=(7, 22))
            plt.tight_layout()

        try:
            for _ in range(max_steps):
                all_stayed = True

                for agent in self.agents:
                    if not agent.alive or agent.brain is None:
                        continue
                    action = agent.brain.decide(
                        agent, self.game_map, self.plants, self.agents
                    )
                    self._execute_action(agent, action)
                    if action != Action.STAY:
                        all_stayed = False

                self.step_count += 1

                combat_events  = self._resolve_combat()
                respawn_events = self._process_respawns()
                plant_events   = self._update_plants()
                core_events    = self._update_cores()
                self._update_detection()

                self._step_log.append({
                    'step':      self.step_count,
                    'core_a_hp': round(self.cores[0].hp, 2),
                    'core_b_hp': round(self.cores[1].hp, 2),
                    'alive_a':   sum(1 for a in self.agents if a.alive and a.team == 0),
                    'alive_b':   sum(1 for a in self.agents if a.alive and a.team == 1),
                    **{f'p{p.plant_id}_owner': p.owner          for p in self.plants},
                    **{f'p{p.plant_id}_gauge': round(p.capture_gauge, 1) for p in self.plants},
                    **{f'a{a.agent_id}_x':       a.x                        for a in self.agents},
                    **{f'a{a.agent_id}_y':       a.y                        for a in self.agents},
                    **{f'a{a.agent_id}_alive':   int(a.alive)               for a in self.agents},
                    **{f'a{a.agent_id}_hp_pct':  round(a.hp / a.max_hp, 4) for a in self.agents},
                    **{f'a{a.agent_id}_team':    a.team                     for a in self.agents},
                    **{f'a{a.agent_id}_respawn': a.respawn_timer            for a in self.agents},
                })

                if verbose:
                    for agent in self.agents:
                        if agent.alive:
                            hp_pct = agent.hp / agent.max_hp * 100
                            hp_str = f"HP:{agent.hp}/{agent.max_hp}({hp_pct:.0f}%)"
                            in_plant = [p for p in self.plants
                                        if p.is_in_range(agent.x, agent.y)]
                            current_ids = {p.plant_id for p in in_plant}
                            entered = current_ids - prev_plant_ids[agent.agent_id]
                            exited  = prev_plant_ids[agent.agent_id] - current_ids
                            for pid in entered:
                                print(f"  ★ BR{agent.agent_id} が P{pid} の占拠範囲に進入")
                            for pid in exited:
                                print(f"  ☆ BR{agent.agent_id} が P{pid} の占拠範囲から退出")
                            prev_plant_ids[agent.agent_id] = current_ids
                            zone_str = ""
                            if in_plant:
                                p = in_plant[0]
                                g = p.capture_gauge
                                zone_str = (f"  [P{p.plant_id} ゲージ:"
                                            f" {abs(g):.0f}/{p.CAPTURE_DURABILITY}]")
                            cell_name = self.game_map.get_cell(agent.x, agent.y).name
                            print(f"step {self.step_count:3d} BR{agent.agent_id}: "
                                  f"pos=({agent.pos_m[0]:3d}m,{agent.pos_m[1]:3d}m)"
                                  f"  {hp_str}  cell={cell_name}{zone_str}")
                        else:
                            print(f"step {self.step_count:3d} BR{agent.agent_id}: "
                                  f"DEAD (リスポーン残 {agent.respawn_timer}s)")
                    for msg in combat_events + respawn_events + plant_events + core_events:
                        print(msg)

                winner_team = next(
                    (1 - t for t, c in self.cores.items() if c.destroyed), None
                )
                if winner_team is not None:
                    if not any(e['event_type'] == 'victory' and e['step'] == self.step_count
                               for e in self._event_log):
                        self._log_event('victory', agent_team=winner_team)
                    if verbose:
                        w = "A" if winner_team == 0 else "B"
                        print(f"\n  チーム{w} の勝利！ (step={self.step_count})")
                    if step_delay > 0:
                        ax.clear()
                        self._draw(ax, title=f"★ チーム{'A' if winner_team == 0 else 'B'} の勝利！  Step {self.step_count}")
                        fig.canvas.draw()
                        fig.canvas.flush_events()
                        plt.pause(step_delay * 3)
                    break

                if self.step_count >= MATCH_TIME_STEPS:
                    tl_winner = self._resolve_time_limit()
                    self._log_event('time_limit',
                                    agent_team=tl_winner if tl_winner is not None else -1)
                    if verbose:
                        if tl_winner is not None:
                            w = "A" if tl_winner == 0 else "B"
                            print(f"\n  ⏰ 制限時間！チーム{w} の勝利！"
                                  f"  (CORE A: {int(self.cores[0].hp):,}"
                                  f"  vs  CORE B: {int(self.cores[1].hp):,})")
                        else:
                            print(f"\n  ⏰ 制限時間！引き分け！"
                                  f"  (CORE A: {int(self.cores[0].hp):,}"
                                  f"  vs  CORE B: {int(self.cores[1].hp):,})")
                    if step_delay > 0:
                        ax.clear()
                        result_str = (
                            f"⏰ チーム{'A' if tl_winner == 0 else 'B'} の勝利（時間切れ）"
                            if tl_winner is not None else "⏰ 引き分け（時間切れ）"
                        )
                        self._draw(ax, title=f"{result_str}  Step {self.step_count}")
                        fig.canvas.draw()
                        fig.canvas.flush_events()
                        plt.pause(step_delay * 3)
                    break

                if step_delay > 0:
                    alive = [a for a in self.agents if a.alive]
                    core_str = "  ".join(
                        f"CORE{'A' if t == 0 else 'B'}:{int(c.hp):,}({c.hp_pct:.0f}%)"
                        for t, c in self.cores.items()
                    )
                    pos_str = "  " + "  ".join(
                        f"[BR{a.agent_id}:({a.pos_m[0]}m,{a.pos_m[1]}m)"
                        f" HP:{a.hp * 100 // a.max_hp}%]"
                        for a in alive
                    )
                    ax.clear()
                    self._draw(ax, title=(f"Step {self.step_count}/{max_steps}"
                                          f"  {core_str}" + pos_str))
                    fig.canvas.draw()
                    fig.canvas.flush_events()
                    plt.pause(step_delay)

                no_combat = not any(
                    any(agent.in_lockon_range(e)
                        for e in self.agents if e.alive and e.team != agent.team)
                    for agent in self.agents if agent.alive
                )
                any_respawning = any(a.respawn_timer > 0 for a in self.agents)
                if all_stayed and no_combat and not any_respawning:
                    if verbose:
                        print(f"\n全エージェントが目標到達または停止 "
                              f"(step={self.step_count})")
                    break

        finally:
            if step_delay > 0:
                plt.ioff()

        if verbose:
            print(f"\n=== シミュレーション終了  step={self.step_count} ===")
        if step_delay > 0:
            self.visualize(title=f"最終状態  (step={self.step_count})")

    # ── 開発ログ保存（logger.py へ委譲） ─────────────────────────
    def save_dev_logs(self, base_dir: str = 'logs/dev') -> str:
        """steps_*.csv / events_*.csv を base_dir に保存する。"""
        return _save_dev_logs(self, base_dir)


if __name__ == '__main__':
    from main import main
    main()
