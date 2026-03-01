"""Border Break シミュレーター — ゲーム定数"""
from __future__ import annotations


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
# 戦闘定数（1ステップ = 1秒）
# ─────────────────────────────────────────
AGENT_HP       = 10_000  # ブラスト・ランナーの最大HP
DPS            = 3_000   # 毎ステップのダメージ量（射撃成功時）
HIT_RATE       = 0.64    # 基本命中率（ロックオン内で×LOCKON_BONUS=1.25 → 実効0.80）
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
DETECTION_STEPS   = 3               # 被索敵状態になるまでの連続索敵ステップ数


# ─────────────────────────────────────────
# T-2: 命中率補正定数（決定論的 DPS 分率モデル）
# ─────────────────────────────────────────
LOCKON_BONUS        = 1.25   # ロックオン範囲内の命中補正係数（hit_fraction を最大25%増）
DIST_PENALTY_MAX    = 0.40   # 索敵限界（search_range_c）での最大距離ペナルティ（40%減）
MISS_FLOOR_PER_SHOT = 0.01   # 1発あたりの最低命中確率（発射レート由来の下限保証）
# aim.param → hit_rate 変換（rank_param.json の B ランク aim=12 を基準点として使用）
AIM_PARAM_BASE = 12.0   # 標準BR相当の aim.param 値（B ランク）
AIM_SCALE      = 0.006  # aim 1点あたりの hit_rate 変化量
HIT_RATE_MIN   = 0.40   # hit_rate の下限
HIT_RATE_MAX   = 1.00   # hit_rate の上限（クランプ）
