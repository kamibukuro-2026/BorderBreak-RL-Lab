"""
tests/test_replay.py
replay.py の replay_video() 関数のテスト

テスト対象:
  - replay_video(): steps_*.csv から動画を生成する
  - 旧フォーマット CSV（エージェント列なし）は ValueError を返す
  - 未対応の拡張子は ValueError を返す
  - 空の CSV は ValueError を返す

Pillow が未インストールの環境では GIF 書き出しテストをスキップ。
"""
import csv
import os

import pytest
import matplotlib
matplotlib.use('Agg')

# Pillow がなければ GIF 書き出しテストをスキップ
PIL = pytest.importorskip('PIL', reason='Pillow が未インストール')

from replay import replay_video
from simulation import Simulation, Agent, create_map, AGENT_HP


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────

def _make_steps_csv(path: str, n_agents: int = 2, n_steps: int = 3) -> str:
    """replay_video() が読める最小限の steps_*.csv を生成して path に保存する。"""
    game_map, plants = create_map()
    sim = Simulation(game_map, plants)
    for aid in range(1, n_agents + 1):
        team = 0 if aid <= n_agents // 2 else 1
        sim.add_agent(Agent(agent_id=aid, x=10, y=10 if team == 0 else 90, team=team))
    sim.run(max_steps=n_steps, step_delay=0, verbose=False)
    sim.save_dev_logs(os.path.dirname(path))

    # save_dev_logs が生成した最新の steps_*.csv を探して path へコピー
    log_dir = os.path.dirname(path)
    files = sorted(
        [f for f in os.listdir(log_dir) if f.startswith('steps_') and f.endswith('.csv')],
        reverse=True,
    )
    import shutil
    shutil.copy(os.path.join(log_dir, files[0]), path)
    return path


def _make_old_format_csv(path: str) -> str:
    """エージェント列を含まない旧フォーマット CSV を生成する（後方互換テスト用）。"""
    rows = [
        {'step': 1, 'core_a_hp': 266666, 'core_b_hp': 266666,
         'alive_a': 2, 'alive_b': 2,
         'p1_owner': -1, 'p1_gauge': 0.0,
         'p2_owner': -1, 'p2_gauge': 0.0,
         'p3_owner': -1, 'p3_gauge': 0.0},
    ]
    fieldnames = list(rows[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


# ─────────────────────────────────────────
# replay_video() の正常系テスト
# ─────────────────────────────────────────
class TestReplayVideoGif:

    def test_creates_gif_file(self, tmp_path):
        """replay_video() が .gif ファイルを生成する"""
        steps_csv = _make_steps_csv(str(tmp_path / 'steps.csv'))
        output = str(tmp_path / 'sim.gif')
        replay_video(steps_csv, output, fps=5)
        assert os.path.exists(output), ".gif ファイルが生成されていない"

    def test_gif_file_has_nonzero_size(self, tmp_path):
        """.gif ファイルのサイズが 0 より大きい"""
        steps_csv = _make_steps_csv(str(tmp_path / 'steps.csv'))
        output = str(tmp_path / 'sim.gif')
        replay_video(steps_csv, output, fps=5)
        assert os.path.getsize(output) > 0


# ─────────────────────────────────────────
# replay_video() のエラー系テスト
# ─────────────────────────────────────────
class TestReplayVideoErrors:

    def test_raises_for_unsupported_extension(self, tmp_path):
        """未対応の拡張子（.avi）は ValueError"""
        steps_csv = _make_steps_csv(str(tmp_path / 'steps.csv'))
        with pytest.raises(ValueError, match="未対応の形式"):
            replay_video(steps_csv, str(tmp_path / 'sim.avi'), fps=5)

    def test_raises_for_missing_agent_columns(self, tmp_path):
        """エージェント列がない旧フォーマット CSV は ValueError"""
        old_csv = _make_old_format_csv(str(tmp_path / 'old.csv'))
        with pytest.raises(ValueError, match="エージェント列"):
            replay_video(old_csv, str(tmp_path / 'sim.gif'), fps=5)

    def test_raises_for_empty_csv(self, tmp_path):
        """空の CSV（ヘッダーのみ）は ValueError"""
        empty_csv = str(tmp_path / 'empty.csv')
        with open(empty_csv, 'w', newline='', encoding='utf-8') as f:
            f.write('step,core_a_hp\n')   # ヘッダーだけ
        with pytest.raises(ValueError, match="空"):
            replay_video(empty_csv, str(tmp_path / 'sim.gif'), fps=5)
