"""
Border Break シミュレーター - Step 2
自律移動エージェント: 敵ベースへの貪欲移動
"""
from __future__ import annotations  # 前方参照を文字列として遅延評価

import csv
import os
import random
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from dataclasses import dataclass
from typing import ClassVar
from enum import IntEnum, Enum, auto


# ─────────────────────────────────────────
# マップ定数
# ─────────────────────────────────────────
CELL_SIZE_M    = 10    # 1マスのサイズ（メートル）
MAP_WIDTH_M    = 100   # マップ横幅（メートル）
MAP_HEIGHT_M   = 500   # マップ縦幅（メートル）
MAP_W          = MAP_WIDTH_M  // CELL_SIZE_M   # 10 セル
MAP_H          = MAP_HEIGHT_M // CELL_SIZE_M   # 50 セル
BASE_DEPTH     = 3     # ベースの奥行き（セル）
NUM_PLANTS     = 3     # プラント数
PLANT_RADIUS_M = 30    # プラント占拠範囲（メートル）
PLANT_RADIUS_C = PLANT_RADIUS_M / CELL_SIZE_M  # 3.0 セル


# ─────────────────────────────────────────
# 戦闘定数（1ステップ = 1秒、移動速度 ≈ 10m/s）
# ─────────────────────────────────────────
AGENT_HP       = 10_000  # ブラスト・ランナーの最大HP
DPS            = 3_000   # 毎ステップのダメージ量（射撃成功時）
HIT_RATE       = 0.80    # 命中確率
SEARCH_RANGE_M = 80      # 索敵範囲（メートル）
SEARCH_RANGE_C = SEARCH_RANGE_M / CELL_SIZE_M   # 8.0 セル
LOCKON_RANGE_M = 60      # ロックオン距離（メートル）
LOCKON_RANGE_C = LOCKON_RANGE_M / CELL_SIZE_M   # 6.0 セル
RESPAWN_STEPS  = 10      # 撃破からリスポーンまでのステップ数
MOVE_SPEED_MPS    = 21.9    # 標準BR移動速度（m/s、公式設定値）
CELLS_PER_STEP    = max(1, round(MOVE_SPEED_MPS / CELL_SIZE_M))  # 2 cells/step ≈ 20m/s
CORE_HP           = 266_666          # コアの初期HP（160機撃破でゼロになる値）
CORE_DMG_PER_KILL = CORE_HP / 160    # BR1機撃破→リスポーン時に自チームコアへ入るダメージ（≈1,666.67）
MATCH_TIME_STEPS  = 600              # 試合制限時間（10分 × 60秒/ステップ）


# ─────────────────────────────────────────
# セルの種類
# ─────────────────────────────────────────
class CellType(IntEnum):
    EMPTY    = 0
    OBSTACLE = 1
    PLANT    = 2   # プラント中心セル
    BASE_A   = 3   # チームA ベース（マップ上端）
    BASE_B   = 4   # チームB ベース（マップ下端）


CELL_COLORS = {
    CellType.EMPTY:    "#e8e8e8",
    CellType.OBSTACLE: "#2b2b2b",
    CellType.PLANT:    "#ffe066",
    CellType.BASE_A:   "#6baed6",
    CellType.BASE_B:   "#fc8d59",
}


# ─────────────────────────────────────────
# プラントクラス
# ─────────────────────────────────────────
@dataclass
class Plant:
    OWNER_COLORS: ClassVar[dict] = {
        -1: ("#888888", "中立"),
         0: ("#1a6fb5", "チームA"),
         1: ("#c0392b", "チームB"),
    }
    CAPTURE_DURABILITY: ClassVar[int] = 10  # 占拠完了に必要なゲージ量
    MAX_CAPTURERS     : ClassVar[int] = 3   # 占拠力に上限を与えるBR数

    plant_id     : int
    x            : int
    y            : int
    radius_cells : float = PLANT_RADIUS_C
    owner        : int   = -1
    capture_gauge: float = 0.0

    def get_spawn_points(self, team: int) -> list[tuple[int, int]]:
        """
        team が使用できる再出撃地点を左右2か所返す。

        プラント占拠円から1グリッド外側（自軍ベース方向）に配置し、
        中心 x を挟んで左右対称（x-1, x+1）。

        Team A (team=0): y = self.y - (int(radius_cells) + 1)  ← ベース上側
        Team B (team=1): y = self.y + (int(radius_cells) + 1)  ← ベース下側
        """
        dy = -(int(self.radius_cells) + 1) if team == 0 else (int(self.radius_cells) + 1)
        sy = self.y + dy
        return [(self.x - 1, sy), (self.x + 1, sy)]

    def is_in_range(self, x: int, y: int) -> bool:
        return ((x - self.x) ** 2 + (y - self.y) ** 2) ** 0.5 <= self.radius_cells

    @property
    def pos_m(self) -> tuple[int, int]:
        return (self.x * CELL_SIZE_M, self.y * CELL_SIZE_M)

    def __repr__(self) -> str:
        owner_name = self.OWNER_COLORS[self.owner][1]
        g = self.capture_gauge
        return (f"Plant(id={self.plant_id}, "
                f"pos=({self.pos_m[0]}m, {self.pos_m[1]}m), "
                f"owner={owner_name}, gauge={g:+.0f}/{self.CAPTURE_DURABILITY})")


# ─────────────────────────────────────────
# コアクラス
# ─────────────────────────────────────────
@dataclass
class Core:
    """
    各チームのベースに設置されたコア。
    HP がゼロになるとそのチームの敗北。

    ダメージ発生源:
      - 敵 BR がベース内に滞在 → 毎ステップ DPS
      - 自チーム BR が撃破されリスポーン → CORE_DMG_PER_KILL
    """
    team  : int
    hp    : float = float(CORE_HP)
    max_hp: float = float(CORE_HP)

    @property
    def destroyed(self) -> bool:
        return self.hp <= 0

    @property
    def hp_pct(self) -> float:
        return self.hp / self.max_hp * 100

    def apply_damage(self, dmg: float):
        self.hp = max(0.0, self.hp - dmg)


# ─────────────────────────────────────────
# マップクラス
# ─────────────────────────────────────────
class Map:
    def __init__(self, width: int, height: int):
        self.width  = width
        self.height = height
        self.grid   = np.zeros((height, width), dtype=int)

    def set_cell(self, x: int, y: int, cell_type: CellType):
        self.grid[y][x] = int(cell_type)

    def get_cell(self, x: int, y: int) -> CellType:
        return CellType(self.grid[y][x])

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.get_cell(x, y) != CellType.OBSTACLE


# ─────────────────────────────────────────
# 行動定義
# ─────────────────────────────────────────
class Action(Enum):
    STAY       = auto()
    MOVE_UP    = auto()
    MOVE_DOWN  = auto()
    MOVE_LEFT  = auto()
    MOVE_RIGHT = auto()


# アクション → (dx, dy) の対応表
ACTION_DELTA: dict[Action, tuple[int, int]] = {
    Action.STAY:       ( 0,  0),
    Action.MOVE_UP:    ( 0, -1),
    Action.MOVE_DOWN:  ( 0,  1),
    Action.MOVE_LEFT:  (-1,  0),
    Action.MOVE_RIGHT: ( 1,  0),
}


# ─────────────────────────────────────────
# 行動戦略（Brain）
# ─────────────────────────────────────────
class Brain:
    """行動決定ロジックの基底クラス。サブクラスで decide() をオーバーライドする。"""

    def decide(self, agent: Agent, game_map: Map,
               plants: list[Plant], agents: list[Agent]) -> Action:
        del agent, game_map, plants, agents  # サブクラスでオーバーライド想定。基底実装は何もしない。
        return Action.STAY


class GreedyBaseAttackBrain(Brain):
    """
    敵ベースへ向かいながら、敵を検知したら戦闘を行う貪欲戦略。

    行動状態（優先順）:
      1. ATTACK  : ロックオン距離（LOCKON_RANGE_C）内に敵がいる
                   → STAY（足を止めて射撃。ダメージ適用は Simulation が担当）
      2. APPROACH: 索敵範囲（SEARCH_RANGE_C）内に敵がいる
                   → 最も近い敵へ貪欲移動
      3. PATROL  : 敵が視界外
                   → 目標（敵ベース）へ貪欲移動
    """

    def __init__(self, target: tuple[int, int]):
        """
        Parameters
        ----------
        target : (x, y) セル座標  ← 敵ベース中心など
        """
        self.target = target

    def decide(self, agent: Agent, game_map: Map,
               plants: list[Plant], agents: list[Agent]) -> Action:
        del plants  # 現バージョンでは未使用

        # 生存している敵エージェントを列挙
        enemies = [a for a in agents if a.alive and a.team != agent.team]
        visible = [e for e in enemies if agent.in_search_range(e)]

        if visible:
            nearest = min(visible, key=lambda e: agent.dist_cells(e))

            # 状態1 ATTACK: ロックオン距離内 → 足を止めて射撃
            if agent.in_lockon_range(nearest):
                return Action.STAY

            # 状態2 APPROACH: 索敵範囲内 → 最も近い敵へ接近
            return self._move_toward(agent, nearest.x, nearest.y, game_map)

        # 状態3 PATROL: 敵なし → 敵ベースへ直進
        return self._move_toward(agent, *self.target, game_map)

    def _move_toward(self, agent: Agent, tx: int, ty: int, game_map: Map) -> Action:
        """指定座標 (tx, ty) に向かう貪欲移動アクションを返す。"""
        dy = ty - agent.y
        dx = tx - agent.x

        if dx == 0 and dy == 0:
            return Action.STAY

        candidates: list[Action] = []
        if abs(dy) >= abs(dx):
            if dy > 0: candidates.append(Action.MOVE_DOWN)
            if dy < 0: candidates.append(Action.MOVE_UP)
            if dx > 0: candidates.append(Action.MOVE_RIGHT)
            if dx < 0: candidates.append(Action.MOVE_LEFT)
        else:
            if dx > 0: candidates.append(Action.MOVE_RIGHT)
            if dx < 0: candidates.append(Action.MOVE_LEFT)
            if dy > 0: candidates.append(Action.MOVE_DOWN)
            if dy < 0: candidates.append(Action.MOVE_UP)

        for action in candidates:
            ddx, ddy = ACTION_DELTA[action]
            if game_map.is_walkable(agent.x + ddx, agent.y + ddy):
                return action

        return Action.STAY  # 全方向ふさがれた場合


class PlantCaptureBrain(GreedyBaseAttackBrain):
    """
    プラント占拠を優先しながら、敵を検知したら戦闘を行う戦略。

    行動状態（優先順）:
      1. ATTACK  : ロックオン距離（LOCKON_RANGE_C）内に敵がいる
                   → STAY（足を止めて射撃）
      2. APPROACH: 索敵範囲（SEARCH_RANGE_C）内・ロックオン外に敵がいる
                   → 最も近い敵へ貪欲移動
      3. CAPTURE : 敵が視界外・自チーム未占拠プラントがある
                   → 自チームのベースに最も近い未占拠プラントへ貪欲移動
                   （チームA: y が最小のプラント、チームB: y が最大のプラント）
      4. PATROL  : 全プラントが自チーム占拠済み（またはプラントなし）
                   → 目標（敵ベース）へ貪欲移動
    """

    def decide(self, agent: Agent, game_map: Map,
               plants: list[Plant], agents: list[Agent]) -> Action:
        # 生存している敵エージェントを列挙
        enemies = [a for a in agents if a.alive and a.team != agent.team]
        visible = [e for e in enemies if agent.in_search_range(e)]

        if visible:
            nearest = min(visible, key=lambda e: agent.dist_cells(e))

            # 状態1 ATTACK: ロックオン距離内 → 足を止めて射撃
            if agent.in_lockon_range(nearest):
                return Action.STAY

            # 状態2 APPROACH: 索敵範囲内 → 最も近い敵へ接近
            return self._move_toward(agent, nearest.x, nearest.y, game_map)

        # 状態3 CAPTURE: 自チームが占拠していないプラントを探す
        uncaptured = [p for p in plants if p.owner != agent.team]
        if uncaptured:
            # 自チームのベースに最も近い未占拠プラントを選択
            if agent.team == 0:
                target_plant = min(uncaptured, key=lambda p: p.y)  # 上端ベース → y最小
            else:
                target_plant = max(uncaptured, key=lambda p: p.y)  # 下端ベース → y最大
            return self._move_toward(agent, target_plant.x, target_plant.y, game_map)

        # 状態4 PATROL: 全プラント占拠済み → 敵ベースへ直進
        return self._move_toward(agent, *self.target, game_map)


# ─────────────────────────────────────────
# エージェント（ブラスト・ランナー）
# ─────────────────────────────────────────
class Agent:
    TEAM_COLORS = {0: "#1a6fb5", 1: "#c0392b"}

    def __init__(self, agent_id: int, x: int, y: int, team: int,
                 brain: Brain | None = None):
        self.agent_id      = agent_id
        self.x             = x
        self.y             = y
        self.team          = team          # 0 = チームA, 1 = チームB
        self.hp            = AGENT_HP      # 現在HP
        self.max_hp        = AGENT_HP      # 最大HP（HP バー表示用）
        self.alive         = True
        self.respawn_timer = 0             # 0=生存中, >0=リスポーン待ちの残ステップ数
        self.brain         = brain         # 行動戦略（None なら手動操作）

    def move(self, dx: int, dy: int, game_map: Map) -> bool:
        nx, ny = self.x + dx, self.y + dy
        if game_map.is_walkable(nx, ny):
            self.x, self.y = nx, ny
            return True
        return False

    def move_up(self,    m: Map) -> bool: return self.move( 0, -1, m)
    def move_down(self,  m: Map) -> bool: return self.move( 0,  1, m)
    def move_left(self,  m: Map) -> bool: return self.move(-1,  0, m)
    def move_right(self, m: Map) -> bool: return self.move( 1,  0, m)

    def dist_cells(self, other: Agent) -> float:
        """他エージェントとのユークリッド距離（セル単位）"""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

    def in_search_range(self, other: Agent) -> bool:
        """other が索敵範囲（SEARCH_RANGE_C）内かどうか"""
        return self.dist_cells(other) <= SEARCH_RANGE_C

    def in_lockon_range(self, other: Agent) -> bool:
        """other がロックオン距離（LOCKON_RANGE_C）内かどうか"""
        return self.dist_cells(other) <= LOCKON_RANGE_C

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)

    @property
    def pos_m(self) -> tuple[int, int]:
        return (self.x * CELL_SIZE_M, self.y * CELL_SIZE_M)

    def __repr__(self) -> str:
        status = (f"DEAD(残{self.respawn_timer}s)" if not self.alive
                  else f"hp={self.hp}/{self.max_hp}")
        return (f"Agent(id={self.agent_id}, team={self.team}, "
                f"pos={self.pos_m}m, {status})")


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
            core.apply_damage(DPS)
            lbl      = "A" if base_owner == 0 else "B"
            events.append(
                f"  💥 BR{agent.agent_id} が CORE {lbl} を攻撃！"
                f"  -{DPS}  → {int(core.hp):,}/{int(core.max_hp):,}"
                f" ({core.hp_pct:.1f}%)"
            )
            self._log_event('core_attack', agent_id=agent.agent_id, agent_team=agent.team,
                            target_team=base_owner, damage=DPS)

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

    # ── 戦闘ダメージ解決 ──────────────────────────────────
    def _resolve_combat(self) -> list[str]:
        """
        ロックオン距離内の敵へ射撃ダメージを適用する（同時解決）。

        処理手順:
          1. 全生存エージェントのロックオン距離内の最近接敵を特定する。
          2. HIT_RATE の確率で命中判定し、命中なら DPS をペンディングダメージに積算。
          3. 全員分を計算し終えてから一括でHP を減算（同ステップ内は互いに相打ちあり）。
          4. HP が 0 以下になったエージェントを撃破状態にし、リスポーンタイマーをセット。

        Returns: このステップで発生した戦闘イベントのメッセージリスト
        """
        events: list[str] = []

        # フェーズ1: 全エージェントの射撃を計算（ダメージ量を積算）
        pending_damage: dict[int, int] = {}              # agent_id → 被ダメージ合計
        shooters: dict[int, int] = {}                    # target.agent_id → shooter.agent_id（ログ用）
        hit_log: list[tuple[int, int, int, int]] = []    # (shooter_id, shooter_team, target_id, target_team)

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

            # 命中判定
            if random.random() < HIT_RATE:
                tid = target.agent_id
                pending_damage[tid] = pending_damage.get(tid, 0) + DPS
                shooters[tid] = agent.agent_id   # 最後に命中させたシューターを記録
                hit_log.append((agent.agent_id, agent.team, tid, target.team))

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
                for sh_id, sh_team, tgt_id, tgt_team in hit_log:
                    if tgt_id == agent.agent_id:
                        self._log_event('kill', agent_id=sh_id, agent_team=sh_team,
                                        target_id=tgt_id, target_team=tgt_team, damage=DPS)
            else:
                hp_pct = agent.hp / agent.max_hp * 100
                events.append(
                    f"  ⚡ {shooter_str} → BR{agent.agent_id}(チーム{team_str})"
                    f"  -{dmg}  HP: {agent.hp}/{agent.max_hp} ({hp_pct:.0f}%)"
                )
                for sh_id, sh_team, tgt_id, tgt_team in hit_log:
                    if tgt_id == agent.agent_id:
                        self._log_event('hit', agent_id=sh_id, agent_team=sh_team,
                                        target_id=tgt_id, target_team=tgt_team, damage=DPS)

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
                agent.hp     = AGENT_HP
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
            # CELLS_PER_STEP 分だけ同方向に移動（壁に当たったら中断）
            for _ in range(CELLS_PER_STEP):
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
# ベース再出撃地点
# ─────────────────────────────────────────
def get_base_spawn_points(team: int) -> list[tuple[int, int]]:
    """
    ベースの再出撃地点を左右2か所返す。

    x: ベース左端(x=0)から1グリッド(x=1)、右端(x=MAP_W-1)から1グリッド(x=MAP_W-2)
    y: ベース中央
      Team A (team=0): y = BASE_DEPTH // 2              (= 1)
      Team B (team=1): y = MAP_H - BASE_DEPTH // 2 - 1  (= 48)
    """
    y = BASE_DEPTH // 2 if team == 0 else MAP_H - BASE_DEPTH // 2 - 1
    return [(1, y), (MAP_W - 2, y)]


# ─────────────────────────────────────────
# マップ・プラント生成
# ─────────────────────────────────────────
def create_map() -> tuple[Map, list[Plant]]:
    """
    縦500m × 横100m (50×10 セル) のマップを生成する。

    レイアウト:
      y =  0 〜  2 : Base A（チームA、上端）
      y = 47 〜 49 : Base B（チームB、下端）

    プラント（NUM_PLANTS=3）:
      ベース間（y=3〜46）を等分割した位置に配置
      横中央（x=5, 50m）に設置
      占拠範囲: 半径 30m = 3 セル

    プラント位置:
      linspace(3, 46, 5)[1:-1] → y = 14 (140m), 25 (250m), 35 (350m)
    """
    game_map = Map(MAP_W, MAP_H)

    # Base A（上端 BASE_DEPTH 行）
    for y in range(BASE_DEPTH):
        for x in range(MAP_W):
            game_map.set_cell(x, y, CellType.BASE_A)

    # Base B（下端 BASE_DEPTH 行）
    for y in range(MAP_H - BASE_DEPTH, MAP_H):
        for x in range(MAP_W):
            game_map.set_cell(x, y, CellType.BASE_B)

    # プラント位置：ベース間を等分割
    inner_top = BASE_DEPTH               # y = 3
    inner_bot = MAP_H - BASE_DEPTH - 1   # y = 46
    plant_ys = [
        int(y + 0.5)
        for y in np.linspace(inner_top, inner_bot, NUM_PLANTS + 2)[1:-1]
    ]
    plant_x = MAP_W // 2  # 横中央 x = 5

    plants: list[Plant] = []
    for i, py in enumerate(plant_ys):
        game_map.set_cell(plant_x, py, CellType.PLANT)
        plants.append(Plant(plant_id=i + 1, x=plant_x, y=py))

    return game_map, plants


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
    # 全機が GreedyBaseAttackBrain で敵ベース中心を目標にする
    # ─────────────────────────────────────────
    NUM_AGENTS  = 10          # 1チームあたりの機数
    START_Y_A   = BASE_DEPTH - 1          # y = 2  (Base A 出口)
    START_Y_B   = MAP_H - BASE_DEPTH      # y = 47 (Base B 出口)
    target_a    = (MAP_W // 2, MAP_H - BASE_DEPTH // 2 - 1)   # (5, 48)
    target_b    = (MAP_W // 2, BASE_DEPTH // 2)                # (5, 1)

    sim = Simulation(game_map, plants)

    print(f"\n--- チームA  {NUM_AGENTS}機  (Base A y={START_Y_A})  → target {target_a} ---")
    for i in range(NUM_AGENTS):
        agent = Agent(
            agent_id=i + 1,
            x=i, y=START_Y_A,
            team=0,
            brain=GreedyBaseAttackBrain(target=target_a),
        )
        sim.add_agent(agent)
        print(f"  BR{agent.agent_id:>2}: ({agent.x}, {agent.y})")

    print(f"\n--- チームB  {NUM_AGENTS}機  (Base B y={START_Y_B})  → target {target_b} ---")
    for i in range(NUM_AGENTS):
        agent = Agent(
            agent_id=NUM_AGENTS + i + 1,
            x=i, y=START_Y_B,
            team=1,
            brain=GreedyBaseAttackBrain(target=target_b),
        )
        sim.add_agent(agent)
        print(f"  BR{agent.agent_id:>2}: ({agent.x}, {agent.y})")

    print()

    # 初期状態の確認
    sim.visualize(title="初期状態（10 vs 10）")

    # 自律移動シミュレーション実行
    sim.run(max_steps=MATCH_TIME_STEPS, step_delay=0.10)

    # 開発ログを CSV に保存
    sim.save_dev_logs()
