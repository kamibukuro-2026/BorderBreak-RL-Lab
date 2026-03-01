"""Border Break シミュレーター — ゲーム基本型（Enum・Plant・Core・Map）"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import ClassVar
from enum import IntEnum, Enum, auto

from constants import CELL_SIZE_M, PLANT_RADIUS_C, CORE_HP


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
# ロール定義
# ─────────────────────────────────────────
class Role(Enum):
    """BR（ブラスト・ランナー）のロール。"""
    ASSAULT       = auto()   # 突撃型（現フェーズではデフォルト）
    HEAVY_ASSAULT = auto()   # 重撃型
    SUPPORT       = auto()   # 支援型
    SNIPER        = auto()   # 狙撃型
