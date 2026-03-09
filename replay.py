"""
replay.py — steps_*.csv からシミュレーション動画を生成する。

使い方（Python）:
    from replay import replay_video
    replay_video('logs/dev/steps_20260303_120000.csv', 'sim.gif')
    replay_video('logs/dev/steps_20260303_120000.csv', 'sim.mp4', fps=15)
    replay_video('logs/dev/steps_20260303_120000.csv', 'sim.gif',
                 output_size=(1280, 960), verbose=True)

コマンドライン:
    python replay.py logs/dev/steps_20260303_120000.csv sim.gif
    python replay.py logs/dev/steps_20260303_120000.csv sim.mp4 --fps 15
    python replay.py logs/dev/steps_20260303_120000.csv sim.gif --output-size 1280x960
    python replay.py logs/dev/steps_20260303_120000.csv sim.gif --verbose

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

from simulation import Simulation, Agent, create_map, MAP_W, MAP_H


# 出力解像度に使う固定 DPI
_OUTPUT_DPI = 100


def replay_video(
    steps_csv: str,
    output_path: str,
    fps: int = 10,
    output_size: tuple[int, int] = (640, 480),
    verbose: bool = False,
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
    output_size : tuple[int, int]
        出力解像度（幅, 高さ）ピクセル（デフォルト (640, 480)）。
        マップ（縦長）は中央配置され、余白は黒で埋められる。
    verbose : bool
        True のとき完了メッセージをコンソールに出力（デフォルト False）
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

    # 5. Figure を output_size (pixels) で生成、背景黒
    w_px, h_px = output_size
    fig = plt.figure(
        figsize=(w_px / _OUTPUT_DPI, h_px / _OUTPUT_DPI),
        dpi=_OUTPUT_DPI,
    )
    fig.patch.set_facecolor('black')

    # マップ（MAP_W × MAP_H セル）をアスペクト比を保ちつつ中央配置
    # MAP_W=20, MAP_H=100 → 縦長（aspect 0.2）
    map_aspect = MAP_W / MAP_H          # 幅÷高さ
    map_px_h = float(h_px)
    map_px_w = map_px_h * map_aspect
    if map_px_w > w_px:                 # 横方向に収まらない場合は横基準にスケール
        map_px_w = float(w_px)
        map_px_h = map_px_w / map_aspect
    left_frac   = (w_px - map_px_w) / 2 / w_px
    bottom_frac = (h_px - map_px_h) / 2 / h_px
    ax = fig.add_axes([
        left_frac,
        bottom_frac,
        map_px_w / w_px,
        map_px_h / h_px,
    ])

    # 6. FuncAnimation でフレームを描画
    def update(frame_idx: int) -> None:
        ax.clear()
        ax.set_facecolor('black')
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

    # 7. 保存（拡張子で形式を判定）
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
    if verbose:
        print(f"動画保存完了: {output_path}  ({len(rows)} フレーム, {fps} fps, {w_px}×{h_px}px)")


if __name__ == '__main__':
    import argparse

    def _parse_output_size(s: str) -> tuple[int, int]:
        """'640x480' → (640, 480)"""
        parts = s.lower().split('x')
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(f"'WxH' 形式で指定してください（例: 640x480）: {s!r}")
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            raise argparse.ArgumentTypeError(f"整数値で指定してください: {s!r}")

    parser = argparse.ArgumentParser(
        description='BorderBreak シミュレーション動画生成',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "例:\n"
            "  python replay.py logs/dev/steps_20260303_120000.csv sim.gif\n"
            "  python replay.py logs/dev/steps_20260303_120000.csv sim.mp4 --fps 15\n"
            "  python replay.py logs/dev/steps_20260303_120000.csv sim.gif --output-size 1280x960\n"
            "  python replay.py logs/dev/steps_20260303_120000.csv sim.gif --verbose"
        ),
    )
    parser.add_argument('steps_csv',  help='steps_*.csv のパス')
    parser.add_argument('output',     help='出力ファイルパス（.gif or .mp4）')
    parser.add_argument('--fps',      type=int, default=10,
                        help='フレームレート（デフォルト: 10）')
    parser.add_argument('--output-size', type=_parse_output_size, default=(640, 480),
                        metavar='WxH',
                        help='出力解像度（デフォルト: 640x480）')
    parser.add_argument('--verbose',  action='store_true',
                        help='完了メッセージをコンソールに出力する')
    args = parser.parse_args()
    replay_video(
        args.steps_csv,
        args.output,
        fps=args.fps,
        output_size=args.output_size,
        verbose=args.verbose,
    )
