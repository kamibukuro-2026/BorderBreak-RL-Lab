"""Border Break シミュレーター — Agent（ブラスト・ランナー）クラス"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt

from constants import (
    AGENT_HP, DPS, SEARCH_RANGE_C, LOCKON_RANGE_C, CELLS_PER_STEP, CELL_SIZE_M,
)
from game_types import Role, Map

if TYPE_CHECKING:
    from brain import Brain


# ─────────────────────────────────────────
# 機体設定データクラス
# ─────────────────────────────────────────
@dataclass
class RoleLoadout:
    """ロール1枠分の設定（武器 DPS + 行動戦略）"""
    dps  : int
    brain: Brain  # 行動戦略インスタンス


@dataclass
class AgentLoadout:
    """
    1プレイヤー分の機体設定。

    パーツ由来のパラメータ（全ロール共通）と、
    ロールごとの武器・戦略設定を保持する。

    Attributes
    ----------
    max_hp         : 最大HP（装甲パラメータ由来）
    search_range_c : 索敵範囲（セル単位、頭部由来）
    lockon_range_c : ロックオン範囲（セル単位、頭部由来）
    cells_per_step : 1ステップ最大移動セル数（脚部由来）
    roles          : ロール → RoleLoadout の対応表
    """
    max_hp        : int
    search_range_c: float
    lockon_range_c: float
    cells_per_step: int
    roles         : dict[Role, RoleLoadout] = field(default_factory=dict)


# ─────────────────────────────────────────
# ロール別画像アセット
# ─────────────────────────────────────────
_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
_ROLE_IMAGE_FILES: dict[Role, str] = {
    Role.ASSAULT:       'assult.png',
    Role.HEAVY_ASSAULT: 'heavy_assult.png',
    Role.SUPPORT:       'support.png',
    Role.SNIPER:        'sniper.png',
}
_role_image_cache: dict = {}


def _get_role_image(role: Role):
    """ロールに対応する画像配列を返す。読み込み失敗時は None。"""
    if role not in _role_image_cache:
        fname = _ROLE_IMAGE_FILES.get(role)
        try:
            _role_image_cache[role] = plt.imread(
                os.path.join(_ASSETS_DIR, fname)
            )
        except Exception:
            _role_image_cache[role] = None
    return _role_image_cache[role]


# ─────────────────────────────────────────
# エージェント（ブラスト・ランナー）
# ─────────────────────────────────────────
class Agent:
    TEAM_COLORS = {0: "#1a6fb5", 1: "#c0392b"}

    def __init__(self, agent_id: int, x: int, y: int, team: int,
                 brain: Brain | None = None,
                 role: Role = Role.ASSAULT,
                 *,
                 loadout: AgentLoadout | None = None,
                 max_hp: int = AGENT_HP,
                 dps: int = DPS,
                 search_range_c: float = SEARCH_RANGE_C,
                 lockon_range_c: float = LOCKON_RANGE_C,
                 cells_per_step: int = CELLS_PER_STEP):
        self.agent_id       = agent_id
        self.x              = x
        self.y              = y
        self.team           = team          # 0 = チームA, 1 = チームB
        self.role           = role          # 現在のロール
        self.alive          = True
        self.respawn_timer  = 0             # 0=生存中, >0=リスポーン待ちの残ステップ数
        self.detected       = False         # 被索敵状態（True=敵に位置情報を把握されている）
        self.exposure_steps = 0             # 敵の索敵範囲内にいる連続ステップ数
        self.loadout        = loadout       # 機体設定（None なら個別パラメータを直接使用）

        if loadout is not None:
            # loadout 由来のパラメータ（パーツ共通値）
            self.max_hp         = loadout.max_hp
            self.search_range_c = loadout.search_range_c
            self.lockon_range_c = loadout.lockon_range_c
            self.cells_per_step = loadout.cells_per_step
            # 初期ロールの武器・Brain を適用
            if role in loadout.roles:
                role_cfg   = loadout.roles[role]
                self.dps   = role_cfg.dps
                self.brain = role_cfg.brain
            else:
                self.dps   = dps
                self.brain = brain
        else:
            # loadout なし：個別パラメータを直接使用（後方互換）
            self.max_hp         = max_hp
            self.dps            = dps
            self.brain          = brain
            self.search_range_c = search_range_c
            self.lockon_range_c = lockon_range_c
            self.cells_per_step = cells_per_step

        self.hp = self.max_hp  # 現在HP（max_hp で初期化）

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
        """other が索敵範囲（self.search_range_c）内かどうか"""
        return self.dist_cells(other) <= self.search_range_c

    def in_lockon_range(self, other: Agent) -> bool:
        """other がロックオン距離（self.lockon_range_c）内かどうか"""
        return self.dist_cells(other) <= self.lockon_range_c

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
