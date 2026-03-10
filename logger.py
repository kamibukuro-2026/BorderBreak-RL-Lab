"""
logger.py — Simulation の CSV ログ保存ロジック

Simulation クラスから切り出した開発ログ保存コードを提供する。
`save_dev_logs(sim, base_dir)` を呼ぶことで steps_*.csv / events_*.csv を出力できる。
"""
from __future__ import annotations
from typing import TYPE_CHECKING

import csv
import os
from datetime import datetime

if TYPE_CHECKING:
    from simulation import Simulation


def save_dev_logs(sim: Simulation, base_dir: str = 'logs/dev') -> str:
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

    # steps CSV
    steps_path = os.path.join(base_dir, f'steps_{ts}.csv')
    if sim._step_log:
        fieldnames = list(sim._step_log[0].keys())
        with open(steps_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sim._step_log)

    # events CSV
    events_path = os.path.join(base_dir, f'events_{ts}.csv')
    if sim._event_log:
        fieldnames = ['step', 'event_type', 'agent_id', 'agent_team',
                      'target_id', 'target_team', 'damage', 'plant_id', 'detail']
        with open(events_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sim._event_log)

    print(f"\n開発ログ保存完了  [{base_dir}]")
    print(f"  steps  : steps_{ts}.csv  ({len(sim._step_log)} rows)")
    print(f"  events : events_{ts}.csv  ({len(sim._event_log)} rows)")
    return ts
