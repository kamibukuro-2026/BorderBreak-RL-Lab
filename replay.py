"""
replay.py — steps_*.csv からシミュレーション動画を生成する。

使い方（Python）:
    from replay import replay_video
    replay_video('logs/dev/steps_20260303_120000.csv', 'sim.gif')
    replay_video('logs/dev/steps_20260303_120000.csv', 'sim.mp4', fps=15)

コマンドライン:
    python replay.py logs/dev/steps_20260303_120000.csv sim.gif
    python replay.py logs/dev/steps_20260303_120000.csv sim.mp4 --fps 15

必要ライブラリ:
    .gif → pip install pillow
    .mp4 → pip install pillow  + FFmpeg（システムインストール）
"""

import csv
import os

import matplotlib
matplotlib.use('Agg')   # ヘッドレス描画（表示不要）
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from simulation import Simulation, Agent, create_map


def replay_video(
    steps_csv: str,
    output_path: str,
    fps: int = 10,
    figsize: tuple[float, float] = (5, 22),
) -> None:
    """steps_*.csv からシミュレーション動画を生成して保存する。

    Parameters
    ----------
    steps_csv : str
        save_dev_logs() で生成した steps_*.csv のパス
    output_path : str
        出力ファイルパス（.gif または .mp4）
    fps : int
        フレームレート（デフォルト 10）
    figsize : tuple[float, float]
        matplotlib の figsize（デフォルト (5, 22)）
    """
    # 1. CSV 読み込み
    with open(steps_csv, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"ステップログが空です: {steps_csv}")

    # 2. エージェント ID 一覧を列名から自動検出（a{id}_x 列を探す）
    agent_ids = sorted({
        int(k[1:k.index('_', 1)])
        for k in rows[0].keys()
        if k.startswith('a') and '_x' in k and k.endswith('_x')
    })
    if not agent_ids:
        raise ValueError(
            "エージェント列 (a{id}_x) が見つかりません。\n"
            "最新版の simulation.py でシミュレーションを実行し直してください。"
        )

    # 3. マップ・プラントを初期化
    game_map, plants = create_map()

    # 4. Simulation インスタンス + テンプレートエージェントを構築
    #    __init__ で cores・plants が初期化されるため _draw() をそのまま利用できる
    sim = Simulation(game_map, plants)
    first_row = rows[0]
    for aid in agent_ids:
        team = int(first_row.get(f'a{aid}_team', 0))
        sim.add_agent(Agent(agent_id=aid, x=0, y=0, team=team))

    # 5. FuncAnimation でフレームを描画
    fig, ax = plt.subplots(figsize=figsize)

    def update(frame_idx: int) -> None:
        ax.clear()
        row = rows[frame_idx]
        sim.step_count = int(row['step'])

        # コアHP
        sim.cores[0].hp = float(row['core_a_hp'])
        sim.cores[1].hp = float(row['core_b_hp'])

        # プラント状態
        for plant in sim.plants:
            pid = plant.plant_id
            plant.owner         = int(row[f'p{pid}_owner'])
            plant.capture_gauge = float(row[f'p{pid}_gauge'])

        # エージェント状態
        for agent in sim.agents:
            aid = agent.agent_id
            agent.x             = int(row[f'a{aid}_x'])
            agent.y             = int(row[f'a{aid}_y'])
            agent.alive         = row[f'a{aid}_alive'] in ('1', 'True', 'true')
            hp_pct              = float(row.get(f'a{aid}_hp_pct', 1.0))
            agent.hp            = int(hp_pct * agent.max_hp)
            agent.respawn_timer = int(float(row.get(f'a{aid}_respawn', 0)))

        sim._draw(ax, f"Step {sim.step_count}")

    anim = FuncAnimation(fig, update, frames=len(rows), interval=1000 // fps)

    # 6. 保存（拡張子で形式を判定）
    ext = os.path.splitext(output_path)[1].lower()
    if ext == '.gif':
        from matplotlib.animation import PillowWriter
        anim.save(output_path, writer=PillowWriter(fps=fps))
    elif ext == '.mp4':
        from matplotlib.animation import FFMpegWriter
        anim.save(output_path, writer=FFMpegWriter(fps=fps, bitrate=1800))
    else:
        raise ValueError(
            f"未対応の形式: {ext!r}（.gif か .mp4 を指定してください）"
        )

    plt.close(fig)
    print(f"動画保存完了: {output_path}  ({len(rows)} フレーム, {fps} fps)")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='BorderBreak シミュレーション動画生成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "例:\n"
            "  python replay.py logs/dev/steps_20260303_120000.csv sim.gif\n"
            "  python replay.py logs/dev/steps_20260303_120000.csv sim.mp4 --fps 15"
        ),
    )
    parser.add_argument('steps_csv', help='steps_*.csv のパス')
    parser.add_argument('output',    help='出力ファイルパス（.gif or .mp4）')
    parser.add_argument('--fps',     type=int, default=10,
                        help='フレームレート（デフォルト: 10）')
    args = parser.parse_args()
    replay_video(args.steps_csv, args.output, fps=args.fps)
