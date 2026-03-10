"""
renderer.py — Simulation の描画ロジック

Simulation クラスから切り出した matplotlib 描画コードを提供する。
`draw_simulation(sim, ax, title)` を呼ぶことで、マップ・プラント・
エージェント・コア HP バーを ax に描画できる。
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import matplotlib.patches as patches

from constants import CELL_SIZE_M, PLANT_RADIUS_M
from game_types import CELL_COLORS, CellType
from agent import Agent, _get_role_image

if TYPE_CHECKING:
    from simulation import Simulation


def draw_simulation(sim: Simulation, ax, title: str | None = None) -> None:
    """sim の現在状態を ax に描画する（静的/アニメ共通）。"""
    m = sim.game_map

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
    core_cfg = [
        (0, 0.5,          1.5,            "#0d3a60", "#1a6fb5"),
        (1, m.height-0.5, m.height-2.5,   "#7a1500", "#c0392b"),
    ]
    for c_team, lbl_y, bar_y, txt_col, fill_col in core_cfg:
        core = sim.cores[c_team]
        lbl  = "A" if c_team == 0 else "B"

        ax.text(m.width / 2, lbl_y, f"BASE {lbl}",
                ha="center", va="center",
                fontsize=9, color=txt_col, fontweight="bold", zorder=4)

        bar_w, bar_h = m.width - 1.0, 0.45
        bar_x0 = 0.5
        bar_top = bar_y - bar_h / 2
        ax.add_patch(patches.Rectangle(
            (bar_x0, bar_top), bar_w, bar_h,
            facecolor="#333333", edgecolor="#888888",
            linewidth=0.5, zorder=8
        ))
        hp_ratio  = core.hp / core.max_hp
        bar_color = fill_col if hp_ratio > 0.30 else "#e74c3c"
        ax.add_patch(patches.Rectangle(
            (bar_x0, bar_top), hp_ratio * bar_w, bar_h,
            facecolor=bar_color, linewidth=0, zorder=9
        ))
        ax.text(
            m.width / 2, bar_y,
            f"CORE {lbl}  {int(core.hp):,} / {int(core.max_hp):,}"
            f"  ({hp_ratio * 100:.1f}%)",
            ha="center", va="center",
            fontsize=6.5, color="white", fontweight="bold", zorder=10
        )

    # プラント：占拠範囲（半透明円 + 破線縁）+ 中心マーカー + ゲージバー
    for plant in sim.plants:
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
        ax.text(cx + plant.radius_cells + 0.15, cy,
                f"{plant.pos_m[1]}m",
                ha="left", va="center", fontsize=6.5, color="#555555", zorder=5)

        # 占拠ゲージバー（中心円の直下）
        bar_w  = 2.0
        bar_h  = 0.22
        bar_x0 = cx - bar_w / 2
        bar_y  = cy + 0.60

        ax.add_patch(patches.Rectangle(
            (bar_x0, bar_y), bar_w, bar_h,
            facecolor="#cccccc", edgecolor="#888888",
            linewidth=0.5, zorder=5
        ))
        if plant.capture_gauge != 0:
            ratio      = abs(plant.capture_gauge) / plant.CAPTURE_DURABILITY
            fill_color = (Agent.TEAM_COLORS[0] if plant.capture_gauge > 0
                          else Agent.TEAM_COLORS[1])
            ax.add_patch(patches.Rectangle(
                (bar_x0, bar_y), ratio * bar_w, bar_h,
                facecolor=fill_color, linewidth=0, zorder=6
            ))
        ax.text(
            cx, bar_y + bar_h / 2,
            f"{abs(int(plant.capture_gauge))}/{plant.CAPTURE_DURABILITY}",
            ha="center", va="center",
            fontsize=5.5, color="white", fontweight="bold", zorder=7
        )

    # エージェント（生存）
    for agent in sim.agents:
        if not agent.alive:
            continue
        color = Agent.TEAM_COLORS[agent.team]
        cx_a, cy_a = agent.x + 0.5, agent.y + 0.5
        img = _get_role_image(agent.role)
        if img is not None:
            ax.add_patch(plt.Circle((cx_a, cy_a), 0.44,
                                    color=color, zorder=5, linewidth=0))
            r = 0.38
            ax.imshow(img,
                      extent=[cx_a - r, cx_a + r, cy_a + r, cy_a - r],
                      zorder=6, interpolation='bilinear')
        else:
            ax.add_patch(plt.Circle((cx_a, cy_a), 0.38, color=color, zorder=6))
        ax.text(cx_a, cy_a, str(agent.agent_id),
                ha="center", va="center",
                fontsize=8, color="white", fontweight="bold", zorder=7)

        # HP バー
        hp_ratio = agent.hp / agent.max_hp
        bar_w  = 0.80
        bar_h  = 0.13
        bar_x0 = cx_a - bar_w / 2
        bar_y  = cy_a + 0.43
        ax.add_patch(patches.Rectangle(
            (bar_x0, bar_y), bar_w, bar_h,
            facecolor="#444444", linewidth=0, zorder=7
        ))
        fill_color = "#2ecc71" if hp_ratio > 0.5 else "#e74c3c"
        ax.add_patch(patches.Rectangle(
            (bar_x0, bar_y), hp_ratio * bar_w, bar_h,
            facecolor=fill_color, linewidth=0, zorder=8
        ))

    # 死亡エージェント（× マーカー + リスポーン残時間）
    for agent in sim.agents:
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
    ax.invert_yaxis()

    x_ticks = range(0, m.width + 1, 2)
    ax.set_xticks(x_ticks)
    ax.set_xticklabels([f"{x * CELL_SIZE_M}m" for x in x_ticks], fontsize=7)

    y_ticks = range(0, m.height + 1, 5)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([f"{y * CELL_SIZE_M}m" for y in y_ticks], fontsize=7)

    ax.set_xlabel("横（m）", fontsize=8)
    ax.set_ylabel("縦（m）", fontsize=8)

    ax.set_title(
        title or f"Border Break Simulation  (step={sim.step_count})",
        fontsize=11, pad=10
    )

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
