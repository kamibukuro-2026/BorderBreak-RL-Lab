"""Border Break シミュレーター — マップ・プラント生成関数"""
from __future__ import annotations

import numpy as np

from constants import MAP_W, MAP_H, BASE_DEPTH, NUM_PLANTS
from game_types import Map, CellType, Plant


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
