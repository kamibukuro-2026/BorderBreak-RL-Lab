"""
Border Break シミュレーター - Step 2
自律移動エージェント: 敵ベースへの貪欲移動
"""
from __future__ import annotations  # 前方参照を文字列として遅延評価

import csv
import os
import random
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.patches as patches

from constants import (
    CELL_SIZE_M, MAP_WIDTH_M, MAP_HEIGHT_M, MAP_W, MAP_H,
    BASE_DEPTH, NUM_PLANTS, PLANT_RADIUS_M, PLANT_RADIUS_C,
    AGENT_HP, DPS, HIT_RATE, SEARCH_RANGE_M, SEARCH_RANGE_C,
    LOCKON_RANGE_M, LOCKON_RANGE_C, RESPAWN_STEPS, MOVE_SPEED_MPS, CELLS_PER_STEP,
    CORE_HP, CORE_DMG_PER_KILL, MATCH_TIME_STEPS, DETECTION_STEPS,
    LOCKON_BONUS, DIST_PENALTY_MAX, MISS_FLOOR_PER_SHOT,
    AIM_PARAM_BASE, AIM_SCALE, HIT_RATE_MIN, HIT_RATE_MAX,
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

    # ── 共通描画ロジック ──────────────────────────────────
    def _draw(self, ax, title: str | None = None):
        """ax にマップ・プラント・エージェントを描画する（静的/アニメ共通）。"""
        m = self.game_map

        # セル描画
        for y in range(m.height):
            for x in range(m.width):
                ct    = m.get_cell(x, y)
                color = CELL_COLORS[ct]
                ax.add_patch(patches.Rectangle(
                    (x, y), 1, 1,
                    linewidth=0.25, edgecolor="#bbbbbb", facecolor=color
                ))

        # ベースラベル + コアHPバー
        # レイアウト（y軸は上が 0、下が MAP_H）:
        #   BASE_A (y=0~3): y=0.5 に "BASE A" ラベル、y=1.5 にコアHPバー
        #   BASE_B (y=47~50): y=47.5 にコアHPバー、y=49.5 に "BASE B" ラベル
        core_cfg = [
            (0, 0.5,          1.5,   "#0d3a60", "#1a6fb5"),   # (team, label_y, bar_y, text_col, fill_col)
            (1, m.height-0.5, m.height-2.5, "#7a1500", "#c0392b"),
        ]
        for c_team, lbl_y, bar_y, txt_col, fill_col in core_cfg:
            core = self.cores[c_team]
            lbl  = "A" if c_team == 0 else "B"

            # ベースラベル
            ax.text(m.width / 2, lbl_y, f"BASE {lbl}",
                    ha="center", va="center",
                    fontsize=9, color=txt_col, fontweight="bold", zorder=4)

            # コアHPバー（背景）
            bar_w, bar_h = m.width - 1.0, 0.45
            bar_x0 = 0.5
            bar_top = bar_y - bar_h / 2
            ax.add_patch(patches.Rectangle(
                (bar_x0, bar_top), bar_w, bar_h,
                facecolor="#333333", edgecolor="#888888",
                linewidth=0.5, zorder=8
            ))
            # コアHPバー（フィル）
            hp_ratio   = core.hp / core.max_hp
            bar_color  = fill_col if hp_ratio > 0.30 else "#e74c3c"
            ax.add_patch(patches.Rectangle(
                (bar_x0, bar_top), hp_ratio * bar_w, bar_h,
                facecolor=bar_color, linewidth=0, zorder=9
            ))
            # コアHP テキスト
            ax.text(
                m.width / 2, bar_y,
                f"CORE {lbl}  {int(core.hp):,} / {int(core.max_hp):,}"
                f"  ({hp_ratio * 100:.1f}%)",
                ha="center", va="center",
                fontsize=6.5, color="white", fontweight="bold", zorder=10
            )

        # プラント：占拠範囲（半透明円 + 破線縁）+ 中心マーカー
        for plant in self.plants:
            owner_color = plant.OWNER_COLORS[plant.owner][0]
            cx, cy = plant.x + 0.5, plant.y + 0.5

            ax.add_patch(plt.Circle((cx, cy), plant.radius_cells,
                         color=owner_color, alpha=0.15, zorder=2))
            ax.add_patch(plt.Circle((cx, cy), plant.radius_cells,
                         fill=False, edgecolor=owner_color,
                         linewidth=1.5, linestyle="--", zorder=3))
            ax.add_patch(plt.Circle((cx, cy), 0.42,
                         color=owner_color, zorder=4))
            ax.text(cx, cy, f"P{plant.plant_id}",
                    ha="center", va="center",
                    fontsize=8, color="white", fontweight="bold", zorder=5)
            # y座標をメートルで右側に表示
            ax.text(cx + plant.radius_cells + 0.15, cy,
                    f"{plant.pos_m[1]}m",
                    ha="left", va="center", fontsize=6.5, color="#555555", zorder=5)

            # ── 占拠ゲージバー（中心円の直下） ──
            bar_w  = 2.0   # バー全長（セル単位）、中心から ±1.0
            bar_h  = 0.22
            bar_x0 = cx - bar_w / 2
            bar_y  = cy + 0.60  # 中心円（r=0.42）の下に配置

            # 背景（グレー）
            ax.add_patch(patches.Rectangle(
                (bar_x0, bar_y), bar_w, bar_h,
                facecolor="#cccccc", edgecolor="#888888",
                linewidth=0.5, zorder=5
            ))
            # 進捗フィル（ゲージ量に比例した幅）
            if plant.capture_gauge != 0:
                ratio      = abs(plant.capture_gauge) / plant.CAPTURE_DURABILITY
                fill_color = (Agent.TEAM_COLORS[0] if plant.capture_gauge > 0
                              else Agent.TEAM_COLORS[1])
                ax.add_patch(patches.Rectangle(
                    (bar_x0, bar_y), ratio * bar_w, bar_h,
                    facecolor=fill_color, linewidth=0, zorder=6
                ))
            # ゲージ数値テキスト
            ax.text(
                cx, bar_y + bar_h / 2,
                f"{abs(int(plant.capture_gauge))}/{plant.CAPTURE_DURABILITY}",
                ha="center", va="center",
                fontsize=5.5, color="white", fontweight="bold", zorder=7
            )

        # エージェント（生存）
        for agent in self.agents:
            if not agent.alive:
                continue
            color = Agent.TEAM_COLORS[agent.team]
            cx_a, cy_a = agent.x + 0.5, agent.y + 0.5
            img = _get_role_image(agent.role)
            if img is not None:
                # チームカラーのリングを背面に描画
                ax.add_patch(plt.Circle((cx_a, cy_a), 0.44,
                                        color=color, zorder=5, linewidth=0))
                # ロール画像（inverted y-axis: extent=[left,right,bottom,top]）
                r = 0.38
                ax.imshow(img,
                          extent=[cx_a - r, cx_a + r, cy_a + r, cy_a - r],
                          zorder=6, interpolation='bilinear')
            else:
                ax.add_patch(plt.Circle((cx_a, cy_a), 0.38, color=color, zorder=6))
            ax.text(cx_a, cy_a, str(agent.agent_id),
                    ha="center", va="center",
                    fontsize=8, color="white", fontweight="bold", zorder=7)

            # HP バー（エージェント円の下：y が大きいほど下に表示される）
            hp_ratio = agent.hp / agent.max_hp
            bar_w  = 0.80
            bar_h  = 0.13
            bar_x0 = cx_a - bar_w / 2
            bar_y  = cy_a + 0.43   # 円(r=0.38)の下端より少し下
            # 背景（暗灰色）
            ax.add_patch(patches.Rectangle(
                (bar_x0, bar_y), bar_w, bar_h,
                facecolor="#444444", linewidth=0, zorder=7
            ))
            # HP フィル（HP 残量に比例）
            fill_color = "#2ecc71" if hp_ratio > 0.5 else "#e74c3c"
            ax.add_patch(patches.Rectangle(
                (bar_x0, bar_y), hp_ratio * bar_w, bar_h,
                facecolor=fill_color, linewidth=0, zorder=8
            ))

        # 死亡エージェント（× マーカー＋リスポーン残時間）
        for agent in self.agents:
            if agent.alive:
                continue
            cx_a, cy_a = agent.x + 0.5, agent.y + 0.5
            ax.plot(cx_a, cy_a, "x",
                    color="#888888", markersize=10, markeredgewidth=2,
                    zorder=6, alpha=0.55)
            ax.text(cx_a, cy_a + 0.55, f"{agent.respawn_timer}s",
                    ha="center", va="center",
                    fontsize=5.5, color="#888888", zorder=7)

        # 軸設定
        ax.set_xlim(0, m.width)
        ax.set_ylim(0, m.height)
        ax.set_aspect("equal")
        ax.invert_yaxis()  # y=0 を上（Base A 側）

        x_ticks = range(0, m.width + 1, 2)
        ax.set_xticks(x_ticks)
        ax.set_xticklabels([f"{x * CELL_SIZE_M}m" for x in x_ticks], fontsize=7)

        y_ticks = range(0, m.height + 1, 5)
        ax.set_yticks(y_ticks)
        ax.set_yticklabels([f"{y * CELL_SIZE_M}m" for y in y_ticks], fontsize=7)

        ax.set_xlabel("横（m）", fontsize=8)
        ax.set_ylabel("縦（m）", fontsize=8)

        ax.set_title(
            title or f"Border Break Simulation  (step={self.step_count})",
            fontsize=11, pad=10
        )

        # 凡例
        legend_items = [
            patches.Patch(color=CELL_COLORS[CellType.BASE_A], label="Base A (チームA)"),
            patches.Patch(color=CELL_COLORS[CellType.BASE_B], label="Base B (チームB)"),
            patches.Patch(color=CELL_COLORS[CellType.PLANT],  label="Plant 中心セル"),
            patches.Patch(color="#888888", alpha=0.4,
                          label=f"Plant 占拠範囲 (r={PLANT_RADIUS_M}m)"),
            patches.Patch(color=Agent.TEAM_COLORS[0], label="BR チームA"),
            patches.Patch(color=Agent.TEAM_COLORS[1], label="BR チームB"),
        ]
        ax.legend(handles=legend_items, loc="upper right",
                  fontsize=7, framealpha=0.9)

    def visualize(self, title: str | None = None):
        """現在の状態を静止画として表示する。"""
        fig, ax = plt.subplots(figsize=(7, 22))
        self._draw(ax, title=title)
        plt.tight_layout()
        plt.show()

    # ── 占拠ゲージ更新 ──────────────────────────────────
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
            # ゾーン内BR数を集計
            count = {0: 0, 1: 0}
            for agent in self.agents:
                if agent.alive and plant.is_in_range(agent.x, agent.y):
                    count[agent.team] += 1

            # 有効占拠力（MAX_CAPTURERSで上限）
            power_A = min(count[0], plant.MAX_CAPTURERS)
            power_B = min(count[1], plant.MAX_CAPTURERS)
            net = power_A - power_B

            if net == 0:
                continue  # 均衡 or 無人 → ゲージ変化なし

            old_owner = plant.owner
            plant.capture_gauge = max(
                -plant.CAPTURE_DURABILITY,
                min(plant.CAPTURE_DURABILITY, plant.capture_gauge + net)
            )

            # 占拠完了判定（ゲージが上限に達した時のみ owner を更新）
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

    # ── ベース攻撃（コアダメージ）────────────────────────
    def _update_cores(self) -> list[str]:
        """
        敵ベース内に滞在している BR が、毎ステップ DPS 分のダメージをコアに与える。
        （命中率なし：コアは固定目標のため確実に命中）

        ダメージ対応:
          チームA の BR が BASE_B 内 → チームB のコアへ DPS ダメージ
          チームB の BR が BASE_A 内 → チームA のコアへ DPS ダメージ

        Returns: このステップで発生したコアダメージ・勝利イベントのメッセージリスト
        """
        events: list[str] = []

        # ベースセル → コア所有チームの対応
        base_cell_to_team = {
            CellType.BASE_A: 0,
            CellType.BASE_B: 1,
        }

        for agent in self.agents:
            if not agent.alive:
                continue
            cell = self.game_map.get_cell(agent.x, agent.y)
            if cell not in base_cell_to_team:
                continue
            base_owner = base_cell_to_team[cell]
            if agent.team == base_owner:
                continue   # 自チームのベースには攻撃しない

            core = self.cores[base_owner]
            if core.destroyed:
                continue   # すでに破壊済み

            prev_hp  = core.hp
            core.apply_damage(agent.dps)
            lbl      = "A" if base_owner == 0 else "B"
            events.append(
                f"  💥 BR{agent.agent_id} が CORE {lbl} を攻撃！"
                f"  -{agent.dps}  → {int(core.hp):,}/{int(core.max_hp):,}"
                f" ({core.hp_pct:.1f}%)"
            )
            self._log_event('core_attack', agent_id=agent.agent_id, agent_team=agent.team,
                            target_team=base_owner, damage=agent.dps)

            # 破壊判定（この攻撃でゼロになった）
            if prev_hp > 0 and core.destroyed:
                winner_lbl = "B" if base_owner == 0 else "A"
                events.append(
                    f"\n  {'█'*36}\n"
                    f"  ★ チーム{winner_lbl} の勝利！ CORE {lbl} が破壊されました！\n"
                    f"  {'█'*36}"
                )
                self._log_event('victory', agent_team=1 - base_owner)

        return events

    # ── 被索敵状態の更新 ──────────────────────────────────
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

    # ── 制限時間勝敗判定 ──────────────────────────────────
    def _resolve_time_limit(self) -> int | None:
        """
        時間切れ時の勝敗を判定する。

        コアゲージ（残HP）が多い方のチームを勝利とする。
        HP が等しい場合は引き分け（None）。

        Returns: 勝利チーム番号（0=チームA / 1=チームB）または None（引き分け）
        """
        hp_a = self.cores[0].hp
        hp_b = self.cores[1].hp
        if hp_a > hp_b:
            return 0
        if hp_b > hp_a:
            return 1
        return None

    # ── 命中率計算（決定論的 DPS 分率モデル） ───────────────
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

    # ── 戦闘ダメージ解決 ──────────────────────────────────
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

        # フェーズ1: 全エージェントの射撃を計算（ダメージ量を積算）
        pending_damage: dict[int, int] = {}                      # agent_id → 被ダメージ合計
        shooters: dict[int, int] = {}                            # target.agent_id → shooter.agent_id（ログ用）
        hit_log: list[tuple[int, int, int, int, int]] = []       # (shooter_id, shooter_team, target_id, target_team, damage)

        for agent in self.agents:
            if not agent.alive:
                continue

            # ロックオン距離内の敵を抽出し最近接を選ぶ
            in_range = [
                a for a in self.agents
                if a.alive and a.team != agent.team and agent.in_lockon_range(a)
            ]
            if not in_range:
                continue

            target = min(in_range, key=lambda e: agent.dist_cells(e))

            # 決定論的ダメージ計算（hit_fraction × dps）
            hit_frac = self._calc_hit_fraction(agent, target)
            dmg = int(agent.dps * hit_frac)
            if dmg > 0:
                tid = target.agent_id
                pending_damage[tid] = pending_damage.get(tid, 0) + dmg
                shooters[tid] = agent.agent_id   # 最後にダメージを与えたシューターを記録
                hit_log.append((agent.agent_id, agent.team, tid, target.team, dmg))

        # フェーズ2: 一括ダメージ適用
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

    # ── リスポーン処理 ────────────────────────────────────
    def _process_respawns(self) -> list[str]:
        """
        撃破されたエージェントのリスポーンタイマーを更新し、
        タイマーが 0 になったエージェントを復活させる。

        リスポーン位置（優先順）:
          1. 自チームが占拠している最も前線に近いプラント
          2. 自チームのベース中心

        Returns: このステップで発生したリスポーンイベントのメッセージリスト
        """
        events: list[str] = []

        for agent in self.agents:
            if agent.alive or agent.respawn_timer <= 0:
                continue

            agent.respawn_timer -= 1

            if agent.respawn_timer == 0:
                # リスポーン位置を決定
                friendly = [p for p in self.plants if p.owner == agent.team]
                if friendly:
                    # 前線（敵ベースに近い）プラントを優先
                    if agent.team == 0:
                        plant = max(friendly, key=lambda p: p.y)   # チームA は y 大＝前線
                    else:
                        plant = min(friendly, key=lambda p: p.y)   # チームB は y 小＝前線
                    spawn_x, spawn_y = random.choice(plant.get_spawn_points(agent.team))
                    spawn_desc = f"P{plant.plant_id}"
                else:
                    spawn_x, spawn_y = random.choice(get_base_spawn_points(agent.team))
                    spawn_desc = f"Base {'A' if agent.team == 0 else 'B'}"

                agent.x      = spawn_x
                agent.y      = spawn_y
                agent.hp     = agent.max_hp   # loadout.max_hp またはデフォルト AGENT_HP
                agent.alive  = True
                team_str = "A" if agent.team == 0 else "B"
                events.append(
                    f"  ★ BR{agent.agent_id}(チーム{team_str}) が {spawn_desc} からリスポーン！"
                )
                self._log_event('respawn', agent_id=agent.agent_id, agent_team=agent.team,
                                detail=f'{spawn_x},{spawn_y}')

                # 撃破ペナルティ: 自チームのコアへ CORE_DMG_PER_KILL ダメージ
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

    # ── アクション実行 ───────────────────────────────────
    def _execute_action(self, agent: Agent, action: Action):
        ddx, ddy = ACTION_DELTA[action]
        if ddx != 0 or ddy != 0:
            # agent.cells_per_step 分だけ同方向に移動（壁に当たったら中断）
            for _ in range(agent.cells_per_step):
                if not agent.move(ddx, ddy, self.game_map):
                    break

    # ── シミュレーション実行（アニメーション） ──────────────
    def run(self, max_steps: int = 60, step_delay: float = 0.15,
            verbose: bool = True):
        """
        全エージェントを自律移動させ、リアルタイムで描画する。

        Parameters
        ----------
        max_steps  : 最大ステップ数
        step_delay : 1ステップあたりの表示時間（秒）。0 にすると描画スキップ。
        verbose    : コンソールへの詳細ログ出力
        """
        print(f"=== シミュレーション開始  max_steps={max_steps} ===\n")

        # プラント進入状態の追跡（agent_id → プラントIDセット）
        prev_plant_ids: dict[int, set[int]] = {a.agent_id: set() for a in self.agents}

        plt.ion()
        fig, ax = plt.subplots(figsize=(7, 22))
        plt.tight_layout()

        try:
            for _ in range(max_steps):
                all_stayed = True  # 全員 STAY（移動なし）フラグ

                # ── 行動フェーズ ──
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

                # ── 戦闘ダメージ解決 ──
                combat_events = self._resolve_combat()

                # ── リスポーン処理（コアキルペナルティもここで適用） ──
                respawn_events = self._process_respawns()

                # ── 占拠ゲージ更新 ──
                plant_events = self._update_plants()

                # ── ベース攻撃（コアダメージ） ──
                core_events = self._update_cores()

                # ── 被索敵状態更新 ──
                self._update_detection()

                # ── ステップスナップショット（開発ログ用） ──
                self._step_log.append({
                    'step':      self.step_count,
                    'core_a_hp': round(self.cores[0].hp, 2),
                    'core_b_hp': round(self.cores[1].hp, 2),
                    'alive_a':   sum(1 for a in self.agents if a.alive and a.team == 0),
                    'alive_b':   sum(1 for a in self.agents if a.alive and a.team == 1),
                    **{f'p{p.plant_id}_owner': p.owner          for p in self.plants},
                    **{f'p{p.plant_id}_gauge': round(p.capture_gauge, 1) for p in self.plants},
                })

                # ── ログ出力 ──
                if verbose:
                    for agent in self.agents:
                        # 生存エージェントの位置・HP 表示
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

                    # 各種イベントを表示
                    for msg in combat_events + respawn_events + plant_events + core_events:
                        print(msg)

                # ── 勝敗判定（コア破壊） ──
                winner_team = next(
                    (1 - t for t, c in self.cores.items() if c.destroyed), None
                )
                if winner_team is not None:
                    # victory イベントがまだ記録されていない場合（kill_penalty 経由の勝利）に追記
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

                # ── 制限時間判定 ──
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

                # ── 描画更新 ──
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

                # ── 早期終了判定 ──
                # 全員 STAY かつ、ロックオン中の敵がいない かつ リスポーン待ちもいない
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
            plt.ioff()

        # 最終状態を表示
        print(f"\n=== シミュレーション終了  step={self.step_count} ===")
        self.visualize(title=f"最終状態  (step={self.step_count})")


    # ── 開発ログ保存 ─────────────────────────────────────
    def save_dev_logs(self, base_dir: str = 'logs/dev') -> str:
        """
        開発用 CSV ログを base_dir に保存する。

        出力ファイル（タイムスタンプで一意に識別）:
          steps_YYYYMMDD_HHMMSS.csv   ステップごとのスナップショット
          events_YYYYMMDD_HHMMSS.csv  各種イベント（命中・撃破・リスポーン等）

        イベント種別 (event_type):
          hit          命中（HP 減少、未撃破）
          kill         撃破
          respawn      リスポーン
          kill_penalty リスポーン時のコアペナルティ
          plant_capture プラント占拠完了
          core_attack  ベース直接攻撃
          victory      勝利（コア破壊）
          time_limit   制限時間終了（勝利 or 引き分け、agent_team=-1 は引き分け）

        Returns: タイムスタンプ文字列 (YYYYMMDD_HHMMSS)
        """
        os.makedirs(base_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        # ── steps CSV ──────────────────────────────────────────────
        steps_path = os.path.join(base_dir, f'steps_{ts}.csv')
        if self._step_log:
            fieldnames = list(self._step_log[0].keys())
            with open(steps_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self._step_log)

        # ── events CSV ─────────────────────────────────────────────
        events_path = os.path.join(base_dir, f'events_{ts}.csv')
        if self._event_log:
            fieldnames = ['step', 'event_type', 'agent_id', 'agent_team',
                          'target_id', 'target_team', 'damage', 'plant_id', 'detail']
            with open(events_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self._event_log)

        print(f"\n開発ログ保存完了  [{base_dir}]")
        print(f"  steps  : steps_{ts}.csv  ({len(self._step_log)} rows)")
        print(f"  events : events_{ts}.csv  ({len(self._event_log)} rows)")
        return ts


# ─────────────────────────────────────────
# メイン
# ─────────────────────────────────────────
if __name__ == "__main__":
    random.seed(42)   # 再現性のためにシードを固定

    game_map, plants = create_map()

    print("=== Border Break シミュレーター（10 vs 10）===")
    print(f"マップ    : {MAP_WIDTH_M}m × {MAP_HEIGHT_M}m  ({MAP_W}×{MAP_H} セル、1マス={CELL_SIZE_M}m)")
    print(f"プラント  : {NUM_PLANTS}個、占拠範囲 半径{PLANT_RADIUS_M}m")
    for p in plants:
        print(f"  {p}")

    # ─────────────────────────────────────────
    # 10 vs 10 エージェント配置
    #
    # チームA (team=0): Base A 出口行（y=2）に x=0..9 の 10 機
    # チームB (team=1): Base B 出口行（y=47）に x=0..9 の 10 機
    # 各機の戦略はシミュレーション開始時にランダムで決定する
    # ─────────────────────────────────────────
    NUM_AGENTS  = 10          # 1チームあたりの機数
    START_Y_A   = BASE_DEPTH - 1          # y = 2  (Base A 出口)
    START_Y_B   = MAP_H - BASE_DEPTH      # y = 47 (Base B 出口)
    target_a    = (MAP_W // 2, MAP_H - BASE_DEPTH // 2 - 1)   # (5, 48)
    target_b    = (MAP_W // 2, BASE_DEPTH // 2)                # (5, 1)

    BRAIN_CLASSES = [GreedyBaseAttackBrain, PlantCaptureBrain, AggressiveCombatBrain]

    sim = Simulation(game_map, plants)

    print(f"\n--- チームA  {NUM_AGENTS}機  (Base A y={START_Y_A})  → target {target_a} ---")
    for i in range(NUM_AGENTS):
        brain_cls = random.choice(BRAIN_CLASSES)
        agent = Agent(
            agent_id=i + 1,
            x=i, y=START_Y_A,
            team=0,
            brain=brain_cls(target=target_a),
        )
        sim.add_agent(agent)
        print(f"  BR{agent.agent_id:>2}: ({agent.x}, {agent.y})  [{brain_cls.__name__}]")

    print(f"\n--- チームB  {NUM_AGENTS}機  (Base B y={START_Y_B})  → target {target_b} ---")
    for i in range(NUM_AGENTS):
        brain_cls = random.choice(BRAIN_CLASSES)
        agent = Agent(
            agent_id=NUM_AGENTS + i + 1,
            x=i, y=START_Y_B,
            team=1,
            brain=brain_cls(target=target_b),
        )
        sim.add_agent(agent)
        print(f"  BR{agent.agent_id:>2}: ({agent.x}, {agent.y})  [{brain_cls.__name__}]")

    print()

    # 初期状態の確認
    sim.visualize(title="初期状態（10 vs 10）")

    # 自律移動シミュレーション実行
    sim.run(max_steps=MATCH_TIME_STEPS, step_delay=0.10)

    # 開発ログを CSV に保存
    sim.save_dev_logs()
