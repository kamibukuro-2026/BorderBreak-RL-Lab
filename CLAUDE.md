# Border Break シミュレーター — プロジェクト概要

## 目的

ゲーム「Border Break」のマルチエージェントシミュレーションを Python で構築し、
**スコア設定がプレイ体験に与える影響**を分析することを最終目標とする。

---

## ゲームルールの概要

- プレイヤーはブラスト・ランナー（BR）と呼ばれる人型起動兵器に搭乗して戦場に降り立つ
- 試合形式：10 vs 10
- **勝利条件**：敵ベースのコアゲージをゼロにする
  - コアゲージは BR による直接攻撃、または BR の撃破（リスポーン時ペナルティ）で減少
- **プラント**：ベースまでの中間出撃地点。円形範囲内に BR が滞在すると占拠ゲージがたまる。
  最大になると占拠状態となり、陣地として使用可能になる
- **スコア**：ベース攻撃・プラント占拠・味方回復などでポイントが入り、
  試合後のランキングに影響する

---

## マップ仕様（確定済み）

| 項目 | 値 |
|---|---|
| グリッド単位 | 1 マス = 5m × 5m |
| マップサイズ | 縦 500m × 横 100m |
| グリッドサイズ | 100 × 20 セル（`MAP_H=100`, `MAP_W=20`） |
| 向き | 縦型：上端に Base A（チームA）、下端に Base B（チームB） |
| ベース奥行き | 6 セル（30m）。`BASE_DEPTH = 6` |
| プラント数 | 3 個（`NUM_PLANTS = 3`） |
| プラント配置 | ベース間（y=6〜93）を等分割<br>→ y=28（140m）, y=50（250m）, y=71（355m）、すべて x=10（横中央） |
| プラント占拠範囲 | 半径 30m = 6 セル（`PLANT_RADIUS_C = 6.0`） |

---

## ファイル構成

```
BorderBreakシミュレーター/
├── simulation.py              # Simulation クラス + re-import ハブ（テスト後方互換維持）
├── replay.py                  # steps_*.csv からシミュレーション動画を生成（.gif / .mp4）
├── constants.py               # 全ゲーム定数（CELL_SIZE_M, MAP_W, DPS, CORE_HP など）
├── game_types.py              # Enum・Plant・Core・Map クラス（CellType / Action / Role など）
├── brain.py                   # Brain 階層クラス群（Brain / GreedyBaseAttackBrain / PlantCaptureBrain / AggressiveCombatBrain）
├── agent.py                   # Agent クラス + ロール画像アセット読み込み
├── map_gen.py                 # create_map() / get_base_spawn_points()
├── catalog.py                 # パーツ・武器データの読込とインデックス化
├── assemble.py                # 機体アセンブル計算の高レベル API
├── bb_base_and_brand.py       # ベースパラメータ集計・セットボーナス計算
├── bb_brbonus_calcparam_limit.py  # 強化チップ適用・calc params・パラメータ下限
├── bb_calc_movement.py        # 重量ペナルティ・移動速度計算
├── bb_weapon_calc.py          # 武器派生パラメータ計算（DPS・弾倉火力など）
├── bb_full_calc.py            # constdata.js を使う統合エントリ（※要 constdata.js）
├── conftest.py                # pytest パス設定
├── CLAUDE.md                  # このファイル
├── data/
│   ├── weapons_all.json       # 全武器データ（武器種別ごとのネスト構造）
│   ├── rank_param.json        # ランク→数値変換テーブル
│   ├── sys_calc_constants.json  # 重量ペナルティ・速度下限などのシステム定数
│   ├── bland_data.json        # ブランド（セットボーナス）定義
│   ├── parts_param_config.json  # パーツパラメータの上下限設定
│   └── parts_normalized.json  # パーツ正規化データ（パーツ一覧 496件）
├── tests/
│   ├── __init__.py
│   ├── test_core.py                        # Core クラスのテスト（25件）
│   ├── test_plant.py                       # Plant クラスのテスト（42件）
│   ├── test_agent.py                       # Agent クラスのテスト（53件）
│   ├── test_agent_boost.py                 # Agent ブーストパラメータのテスト（15件）
│   ├── test_agent_reload.py                # Agent リロードパラメータのテスト（8件）
│   ├── test_brain.py                       # Brain / GreedyBaseAttackBrain のテスト（28件）
│   ├── test_plant_capture_brain.py         # PlantCaptureBrain のテスト（25件）
│   ├── test_aggressive_combat_brain.py     # AggressiveCombatBrain のテスト（18件）
│   ├── test_detection.py                   # 被索敵状態のテスト（20件）
│   ├── test_hit_fraction.py                # _calc_hit_fraction() のテスト（20件）
│   ├── test_simulation.py                  # Simulation 戦闘ロジックのテスト（64件）
│   ├── test_simulation_boost.py            # Simulation ブースト巡航ロジックのテスト（21件）
│   ├── test_simulation_reload.py           # Simulation リロードロジックのテスト（11件）
│   ├── test_agent_parts.py                 # Agent per-agent パラメータのテスト（44件）
│   ├── test_assemble.py                    # assemble_agent_params のテスト（88件）
│   ├── test_simulation_parts.py            # Simulation + per-agent パラメータ統合テスト（18件）
│   ├── test_weapon_calc.py                 # bb_weapon_calc のテスト（43件）
│   ├── test_bb_base_and_brand.py           # bb_base_and_brand のテスト（41件）
│   ├── test_bb_brbonus_calcparam_limit.py  # bb_brbonus_calcparam_limit のテスト（55件）
│   ├── test_bb_calc_movement.py            # bb_calc_movement のテスト（16件）
│   ├── test_catalog.py                     # catalog のテスト（20件）
│   ├── test_replay.py                      # replay_video() のテスト（5件）
│   └── test_t13_detection_combat.py           # T-13 被索敵戦闘判定のテスト（12件）
└── logs/
    └── dev/             # 開発用 CSV ログ出力先
        ├── steps_YYYYMMDD_HHMMSS.csv
        └── events_YYYYMMDD_HHMMSS.csv
```

**テスト合計: 692 件（全件グリーン）**

### シミュレーターモジュールの依存関係

```
constants.py        （依存なし）
    ↓
game_types.py       → constants
    ↓
brain.py            → game_types（Agent は TYPE_CHECKING のみ）
    ↓
agent.py            → constants, game_types（Brain は TYPE_CHECKING のみ）

map_gen.py          → constants, game_types

simulation.py       → constants, game_types, brain, agent, map_gen
                      （テスト後方互換のため全シンボルを re-import）

replay.py           → simulation（Simulation, Agent, create_map）
                      （動画生成専用スクリプト。simulation.py の _draw() を再利用）
```

---

## クラス・型の設計

### 定数（constants.py）

```python
CELL_SIZE_M    = 5        # 1マス = 5m
MAP_W, MAP_H   = 20, 100
BASE_DEPTH     = 6
NUM_PLANTS     = 3
PLANT_RADIUS_M = 30
PLANT_RADIUS_C = 6.0      # PLANT_RADIUS_M / CELL_SIZE_M

# 戦闘定数（1ステップ = 1秒）
AGENT_HP          = 10_000
DPS               = 3_000   # 射撃成功時のダメージ/ステップ
HIT_RATE          = 0.64    # ロックオン内実効 ≈ 80%（×LOCKON_BONUS=1.25）
SEARCH_RANGE_M    = 80
SEARCH_RANGE_C    = 16.0    # SEARCH_RANGE_M / CELL_SIZE_M
LOCKON_RANGE_M    = 60
LOCKON_RANGE_C    = 12.0    # LOCKON_RANGE_M / CELL_SIZE_M
RESPAWN_STEPS     = 10
MOVE_SPEED_MPS    = 21.9
CELLS_PER_STEP    = 4       # max(1, round(21.9/5))
MATCH_TIME_STEPS  = 600     # 試合制限時間（10分 × 60秒/ステップ）
DETECTION_STEPS   = 3       # 被索敵状態になるまでの連続索敵ステップ数

# コア定数
CORE_HP           = 266_666
CORE_DMG_PER_KILL = CORE_HP / 160   # ≈ 1,666.67（撃破リスポーン時ペナルティ）
```

### `CellType`（IntEnum）— game_types.py

| 値 | 意味 |
|---|---|
| `EMPTY` | 通路 |
| `OBSTACLE` | 障害物 |
| `PLANT` | プラント中心セル |
| `BASE_A` | チームA ベース（上端 y=0〜5） |
| `BASE_B` | チームB ベース（下端 y=94〜99） |

### `Plant`（dataclass）— game_types.py

- `plant_id`, `x`, `y`, `radius_cells`
- `owner`（-1=中立 / 0=チームA / 1=チームB）
- `capture_gauge`（float, `-CAPTURE_DURABILITY` 〜 `+CAPTURE_DURABILITY`）
- クラス変数 `CAPTURE_DURABILITY = 10`
- クラス変数 `MAX_CAPTURERS = 3`
- `is_in_range(x, y)` → ユークリッド距離 ≤ `radius_cells` で判定
- `get_spawn_points(team)` → 再出撃地点2点を返す

#### プラント再出撃地点の仕様

プラント占拠円から1グリッド外側（自軍ベース方向）、中心 x を挟んで左右対称（x±1）。

| チーム | spawn_y | 左 | 右 |
|---|---|---|---|
| A（ベース上端） | `plant.y - (int(radius) + 1)` | `(plant.x-1, spawn_y)` | `(plant.x+1, spawn_y)` |
| B（ベース下端） | `plant.y + (int(radius) + 1)` | `(plant.x-1, spawn_y)` | `(plant.x+1, spawn_y)` |

radius=6 の場合、spawn_y は plant.y ∓ 7（チームA/B）。

### `Core`（dataclass）— game_types.py

- `team`, `hp`, `max_hp`
- `destroyed` プロパティ → `hp <= 0`
- `hp_pct` プロパティ → HP%
- `apply_damage(dmg)` → `max(0, hp - dmg)` にクランプ

### `Map` — game_types.py

- `numpy` の 2D 配列でグリッドを管理
- `is_walkable(x, y)` → 境界内かつ `OBSTACLE` でなければ True

### `Action`（Enum）+ `ACTION_DELTA` — game_types.py

```python
Action.STAY / MOVE_UP / MOVE_DOWN / MOVE_LEFT / MOVE_RIGHT
ACTION_DELTA: dict[Action, tuple[int, int]]  # (dx, dy)
```

### `Role`（Enum）— game_types.py

| 値 | ロール名 | 説明 |
|---|---|---|
| `ASSAULT` | 突撃型 | **現フェーズのデフォルト。全 BR はこのロールに固定** |
| `HEAVY_ASSAULT` | 重撃型 | 今後実装予定 |
| `SUPPORT` | 支援型 | 今後実装予定 |
| `SNIPER` | 狙撃型 | 今後実装予定 |

> ロールごとの固有パラメータ（HP・移動速度・射程・DPSなど）および
> ロール専用 Brain の実装は今後のフェーズで行う。

### `Brain` / `GreedyBaseAttackBrain` — brain.py

- `Brain`：`decide(agent, map, plants, agents) -> Action` を持つ基底クラス
- `GreedyBaseAttackBrain(target)` — 3状態の貪欲戦略
  1. **ATTACK**（ロックオン内）: `STAY`（射撃は `Simulation` が担当）
  2. **APPROACH**（索敵内・ロックオン外）: 最近接の可視敵へ貪欲移動
  3. **PATROL**（敵なし）: 目標セル（敵ベース）へ貪欲移動
  - `_move_toward(agent, tx, ty, map)`: `|dy|>=|dx|` なら縦優先、障害物はスキップ
- `PlantCaptureBrain(target)` — 4状態の占拠優先戦略（`GreedyBaseAttackBrain` のサブクラス）
  1. **ATTACK**（ロックオン内）: `STAY`
  2. **APPROACH**（索敵内・ロックオン外）: 最近接の可視敵へ貪欲移動
  3. **CAPTURE**（敵なし・未占拠プラントあり）: 自チームベースに最も近い未占拠プラントへ
     - チームA（上端ベース）: y 最小の未占拠プラント
     - チームB（下端ベース）: y 最大の未占拠プラント
  4. **PATROL**（全プラント自チーム占拠済みまたはプラントなし）: 敵ベースへ
- `AggressiveCombatBrain(target)` — 4状態の戦闘重視戦略（`GreedyBaseAttackBrain` のサブクラス）
  1. **ATTACK**（ロックオン内）: `STAY`
  2. **APPROACH**（索敵内・ロックオン外）: 最近接の可視敵へ貪欲移動
  3. **HUNT**（索敵範囲外だが `detected=True` の敵がいる）: 味方が発見済みの敵を追撃
     - `enemy.detected == True` → 自チームの誰かが既に捕捉した敵
     - 複数いる場合は最近接を選択
  4. **PATROL**（追跡対象なし）: 敵ベースへ貪欲移動

### `Agent`（ブラスト・ランナー）— agent.py

- `agent_id`, `x`, `y`, `team`, `hp`, `max_hp`, `alive`, `respawn_timer`, `brain`
- `role`（Role, デフォルト `Role.ASSAULT`）: ロール（現フェーズは全員 ASSAULT に固定）
- `detected`（bool, 初期値 False）: 被索敵状態（True=敵に位置情報を把握されている）
- `exposure_steps`（int, 初期値 0）: 敵の索敵範囲内にいる連続ステップ数
- `move(dx, dy, map) -> bool` / `move_up/down/left/right(map)`
- `dist_cells(other)` → ユークリッド距離（セル単位）
- `in_search_range(other)` → `dist_cells <= SEARCH_RANGE_C`
- `in_lockon_range(other)` → `dist_cells <= LOCKON_RANGE_C`
- `pos` プロパティ → `(x, y)`
- `pos_m` プロパティ → メートル座標 `(x*5, y*5)`

### `Simulation` — simulation.py

| メソッド | 説明 |
|---|---|
| `add_agent(agent)` | エージェントを登録 |
| `_log_event(event_type, **kwargs)` | 開発ログにイベントを追記 |
| `_draw(ax, title)` | マップ・プラント・エージェント・コアHPバーを描画 |
| `visualize(title)` | 静止画として `plt.show()` で表示 |
| `_execute_action(agent, action)` | `CELLS_PER_STEP` 分だけ移動（壁で中断） |
| `_calc_hit_fraction(shooter, target)` | 射撃命中率（0〜1）を決定論的に計算。ロックオン内ボーナス・距離ペナルティ・rate_floor を考慮 |
| `_resolve_combat()` | 同時解決で射撃ダメージ適用、撃破判定 |
| `_resolve_time_limit()` | 制限時間到達時の勝敗判定（コアHP比較） |
| `_process_respawns()` | タイマー更新・リスポーン・コアキルペナルティ |
| `_update_plants()` | 占拠ゲージ更新 |
| `_update_cores()` | ベース内敵 BR からのコアダメージ |
| `_update_detection()` | 全エージェントの被索敵状態（detected/exposure_steps）を更新 |
| `run(max_steps, step_delay=0.0, verbose=False)` | アニメーション実行ループ。`step_delay=0`（デフォルト）で GUI 非表示、`verbose=False`（デフォルト）でコンソール出力抑制 |
| `save_dev_logs(base_dir)` | 開発用 CSV ログを保存 |

#### `run()` の1ステップ処理順

```
行動決定（Brain.decide） → _resolve_combat() → _process_respawns()
→ _update_plants() → _update_cores() → _update_detection()
→ スナップショット記録 → 勝敗判定（コア破壊） → 制限時間判定 → 描画
```

### モジュールレベル関数 — map_gen.py

#### `create_map() -> tuple[Map, list[Plant]]`

- Base A/B をグリッドに設定
- `np.linspace(6, 93, 5)[1:-1]` でプラント y 座標を等分割計算

#### `get_base_spawn_points(team: int) -> list[tuple[int, int]]`

ベースの再出撃地点を左右2か所返す。

| チーム | x | y |
|---|---|---|
| A（team=0） | 1, MAP_W-2（= 1, 18） | BASE_DEPTH // 2（= 3） |
| B（team=1） | 1, MAP_W-2（= 1, 18） | MAP_H - BASE_DEPTH // 2 - 1（= 96） |

---

## 占拠ゲージのルール（確定済み）

| 項目 | 値 |
|---|---|
| 各 BR の占拠力 | 1 |
| プラントの占拠耐久値 | 10（`CAPTURE_DURABILITY`） |
| 最大加算BR数 | 3（`MAX_CAPTURERS`）。3機超えても占拠力は3止まり |
| ゲージ範囲 | −10（チームB占拠）〜 +10（チームA占拠） |

```
power_A = min(ゾーン内チームA BR数, 3)
power_B = min(ゾーン内チームB BR数, 3)
net     = power_A - power_B
capture_gauge = clamp(capture_gauge + net, -10, +10)
```

---

## 戦闘ルール（確定済み）

| 項目 | 値 |
|---|---|
| BR の HP | 10,000 |
| 射撃ダメージ/ステップ | 3,000（DPS） |
| 命中率 | 80%（HIT_RATE） |
| 索敵範囲 | 80m = 16セル（SEARCH_RANGE_C） |
| ロックオン範囲 | 60m = 12セル（LOCKON_RANGE_C） |
| リスポーン待機 | 10ステップ（RESPAWN_STEPS） |
| 移動速度 | 21.9m/s ≈ 4セル/ステップ（CELLS_PER_STEP） |

**同時解決**: `pending_damage` dict で全員分の射撃を計算してから一括適用（相打ちあり）

## コア・勝敗ルール（確定済み）

| 項目 | 値 |
|---|---|
| コア HP | 266,666 |
| 撃破ペナルティ | CORE_HP / 160 ≈ 1,666.67（リスポーン時に自チームコアへ） |
| ベース直接攻撃 | 敵 BR がベース内に滞在 → 毎ステップ DPS（命中率なし） |
| 試合制限時間 | 600ステップ（10分）。`MATCH_TIME_STEPS = 600` |
| 勝利条件① | 敵コア HP が 0 になった瞬間（即時決着） |
| 勝利条件② | 制限時間到達時、自コア HP が多い側の勝利 |
| 引き分け | 制限時間到達時、両コア HP が完全一致 |

---

## リスポーン仕様（確定済み）

### リスポーン位置の優先順

1. **自チームが占拠している最も前線に近いプラント**の再出撃地点
   - チームA：y が最大のプラント（敵ベース側）
   - チームB：y が最小のプラント（敵ベース側）
2. **自チームのベース**の再出撃地点

### 再出撃地点の選択

各リスポーン先には左右2か所の再出撃地点があり、`random.choice()` でランダムに選択する。

### プラント再出撃地点

プラント円（半径6セル）から1グリッド外側（自軍ベース方向）、中心を挟んで左右対称。

### ベース再出撃地点

ベース左端(x=0)から1格(x=1)と右端(x=19)から1格(x=18)の2か所。y はベース中央。

---

## 開発用ログ仕様（CSV）

`sim.save_dev_logs('logs/dev')` で2ファイルを出力。ファイル名はタイムスタンプで一意に識別。

### steps_YYYYMMDD_HHMMSS.csv（1行 = 1ステップ）

| 列 | 内容 |
|---|---|
| `step` | ステップ番号 |
| `core_a_hp` / `core_b_hp` | コアHP |
| `alive_a` / `alive_b` | 生存機数 |
| `p1_owner` 〜 `p3_owner` | プラント所有者（-1/0/1） |
| `p1_gauge` 〜 `p3_gauge` | 占拠ゲージ |
| `a{id}_x` / `a{id}_y` | エージェント座標（セル単位） ※リプレイ動画生成用 |
| `a{id}_alive` | 生存状態（1=生存, 0=撃破） |
| `a{id}_hp_pct` | HP 残量割合（0.0〜1.0） |
| `a{id}_team` | チーム（0=A, 1=B、各ステップで一定） |
| `a{id}_respawn` | リスポーン残時間（0=生存中） |

### events_YYYYMMDD_HHMMSS.csv（1行 = 1イベント）

| `event_type` | 発生元 |
|---|---|
| `hit` | 命中（HP減少・未撃破） |
| `kill` | 撃破 |
| `respawn` | リスポーン（detail に座標） |
| `kill_penalty` | リスポーン時コアペナルティ |
| `plant_capture` | プラント占拠完了 |
| `core_attack` | ベース直接攻撃 |
| `victory` | 勝利（コア破壊） |
| `time_limit` | 制限時間終了（勝利 or 引き分け。agent_team=-1 は引き分け） |

---

## 現在の実装状態

- [x] 2D グリッドマップの生成
- [x] マップ仕様（500m×100m、プラント3個、占拠範囲半径30m）の反映
- [x] Brain / GreedyBaseAttackBrain による自律移動（PATROL / APPROACH / ATTACK 3状態）
- [x] PlantCaptureBrain によるプラント占拠優先戦略（CAPTURE / PATROL / APPROACH / ATTACK 4状態）
- [x] リアルタイムアニメーション（`plt.ion` + `plt.pause`）
- [x] プラント占拠ゲージの増減ロジック（`_update_plants()`）
- [x] 戦闘ロジック（射撃・ダメージ・同時解決・撃破・リスポーン）
- [x] コア HP 管理・ベース攻撃・キルペナルティ・勝敗判定
- [x] HP バー・コアバーの可視化
- [x] 10 vs 10 エージェント配置（`__main__`）
- [x] 開発用 CSV ログ出力（`save_dev_logs()`）
- [x] プラント再出撃地点（`Plant.get_spawn_points(team)`）とリスポーン位置の分散
- [x] ベース再出撃地点（`get_base_spawn_points(team)`）
- [x] 試合制限時間（`MATCH_TIME_STEPS=600`）と時間切れ勝敗判定（`_resolve_time_limit()`）
- [x] 被索敵状態（`Agent.detected` / `Agent.exposure_steps` / `Simulation._update_detection()`）
- [x] AggressiveCombatBrain による戦闘重視戦略（ATTACK / APPROACH / HUNT / PATROL 4状態）
- [x] Role enum（ASSAULT / HEAVY_ASSAULT / SUPPORT / SNIPER）と Agent.role 属性（現フェーズは全員 ASSAULT）
- [x] ユニットテスト 270 件（test_core / test_plant / test_agent / test_brain / test_plant_capture_brain / test_aggressive_combat_brain / test_detection / test_simulation）
- [x] パーツ・武器データ管理モジュール群（catalog / assemble / bb_\* モジュール）の追加
- [x] パーツ・武器計算モジュール群のユニットテスト 174 件（test_weapon_calc / test_bb_base_and_brand / test_bb_brbonus_calcparam_limit / test_bb_calc_movement / test_catalog）
- [x] Agent の per-agent パラメータ（dps / search_range_c / lockon_range_c / cells_per_step）と assemble_agent_params() の実装
- [x] per-agent パラメータのユニットテスト 75 件（test_agent_parts / test_assemble / test_simulation_parts）
- [x] simulation.py を論理単位ごとに5ファイルへ分割（constants / game_types / brain / agent / map_gen）
- [x] AgentLoadout / RoleLoadout データクラスの定義と Agent.loadout パラメータの追加
- [x] T-1: `max_hp` の可変化（body: armor → `実効HP = 基準HP / armor.param`）
- [x] T-2: `hit_rate` の可変化（head: aim → 決定論的 DPS 分率モデルに移行、`_calc_hit_fraction()` 実装）
- [x] T-3: ブースト巡航システムの実装（boost_max / boost_regen / walk_cells_per_step / dash_cells_per_step / is_cruising、assemble_agent_params に4キー追加）
- [x] T-3.5: セルサイズ変更（CELL_SIZE_M: 10m → 5m、MAP 100×20 セル、全定数・テスト更新）
- [x] parts_normalized.json の追加（496 パーツ）
- [x] ブーストテスト 70 件（test_agent_boost / test_simulation_boost / test_assemble 拡張）
- [x] T-4: リロードタイマーの実装（clip / reload_steps / ammo_in_clip / reload_timer、assemble_agent_params に2キー追加）
- [x] リロードテスト 22 件（test_agent_reload / test_simulation_reload / test_assemble 拡張）
- [x] T-5: arm.reloadRate の反映（`reload_steps = round(weapon.reload × reloadRate.param / 100)`）
- [x] T-5 テスト 5 件（test_assemble: TestAssembleReloadRate 追加）
- [x] T-6: weapon precision → hit_rate の反映（独立加算モデル、`data/rank_param.json` に precision テーブル追加）
- [x] T-6 テスト 7 件（test_assemble: TestAssembleAgentParamsPrecision 追加）
- [x] steps_*.csv へのエージェント座標記録（`a{id}_x` / `a{id}_y` / `a{id}_alive` / `a{id}_hp_pct` / `a{id}_team` / `a{id}_respawn`）
- [x] `replay.py` — steps_*.csv からシミュレーション動画を生成（`.gif` / `.mp4` 対応、Pillow 必須）
- [x] `run()` の GUI / コンソール出力デフォルトを OFF に変更（`step_delay=0.0`, `verbose=False`）
- [x] T-13: 被索敵状態に応じた戦闘判定（`target.detected=True` の場合のみ射撃・ATTACK 状態に移行）

## 今後の実装タスク

武器データ・パーツデータの調査結果をもとに、実装すべき項目を優先度順にまとめる。

### フェーズ1: パーツ由来パラメータの反映（優先度：高）

#### T-1. `max_hp` の可変化（body: armor）
- **現状**: `AGENT_HP = 10,000` 固定
- **目標**: body パーツの `armor` ランクを HP に反映する
- `rank_param["armor"]` はHP倍率（S=0.63〜E-=1.38）。基準 HP × armor.param で算出
- `assemble_agent_params()` の出力に `max_hp` を追加
- `AgentLoadout.max_hp` に設定（loadout 対応は実装済み）

#### T-2. `hit_rate` の可変化（head: aim）
- **現状**: `HIT_RATE = 0.80` 固定
- **目標**: head パーツの `aim` ランクを命中率に反映する
- `rank_param["aim"]` の数値の意味（誤差px？確率%？）を確認して変換式を決める
- `AgentLoadout` に `hit_rate: float` フィールドを追加
- `Agent` に `hit_rate` 属性を追加
- `Simulation._resolve_combat()` で `agent.hit_rate` を参照するよう変更

#### T-3. ブースト巡航システム ✅ 実装済み
- walk/dash の2段階移動速度と boost ゲージ管理を実装
- `Agent`: `boost_max`, `boost`, `boost_regen`, `walk_cells_per_step`, `dash_cells_per_step`, `is_cruising` を追加
- `Simulation._get_move_cells()` で巡航判定、`_execute_action()` / `_process_respawns()` を更新
- `assemble_agent_params()` に 4 キー追加（walk_cells_per_step / dash_cells_per_step / boost_max / boost_regen）
- `constants.py` に 3 定数追加（CRUISE_CONSUME_PER_STEP=13.8 / CRUISE_START_COST=12.0 / BOOST_REGEN_PER_STEP=15.0）

#### T-3.5. セルサイズの変更（CELL_SIZE_M: 10m → 5m）✅ 実装済み
- 1セル = 5m に変更し、walk/dash の速度比が 1:2 程度から 1:4 程度に向上
  - 例: dash=21.9m/s → `round(21.9/5) = 4`、walk=6.75m/s → `round(6.75/5) = 1`（walk/dash で 1:4 の差）
- 変更済み定数: `CELL_SIZE_M=5`, `MAP_W=20`, `MAP_H=100`, `BASE_DEPTH=6`, `PLANT_RADIUS_C=6.0`,
  `SEARCH_RANGE_C=16.0`, `LOCKON_RANGE_C=12.0`, `CELLS_PER_STEP=4`, `HIT_RATE=0.64`
- assemble.py ローカル定数（`_CELL_SIZE_M=5` 等）も更新済み
- テスト群の座標・コメント・docstring を全更新（658 件全件グリーン）

### フェーズ2: 武器の射撃サイクル実装（優先度：中）

#### T-4. リロードタイマーの実装 ✅ 実装済み
- `Agent` に `ammo_in_clip: int`・`reload_timer: int` 属性を追加（`clip=0` → 無限弾・後方互換）
- `RoleLoadout` に `clip: int = 0`・`reload_steps: int = 0` を追加
- `Simulation._resolve_combat()`: `reload_timer > 0` → タイマー減算・射撃スキップ、`timer==0` かつ `clip>0` → `ammo_in_clip=clip`（補充）
- 射撃後に `ammo_in_clip -= shots_per_step`、0以下 → `reload_timer = reload_steps`
- `_process_respawns()` でリスポーン時に `ammo_in_clip = clip`, `reload_timer = 0`
- `assemble_agent_params()` に `clip`, `reload_steps` を追加（13キー）

#### T-5. arm: reloadRate の反映 ✅ 実装済み
- `rank_param["reloadRate"]` でパーセント値（S-=59.5% 〜 C-=100% 〜 E-=140%）を取得
- `reload_steps = round(weapon.reload × reloadRate.param / 100)` で調整
- `assemble_agent_params()` で `draw.arm.reloadRate.param` を参照（欠損時は 100.0 でフォールバック）

#### T-6. precision → hit_rate の武器側反映 ✅ 実装済み
- 武器の `precision` ランクを hit_rate に独立加算
  - `hit_rate = clamp(0.64 + (aim-12)×0.006 + (prec-12)×0.006, 0.40, 1.00)`
  - aim 欠損時は `default_hit_rate` を起点に precision のみ加算（後方互換維持）
  - リスト型 precision（スイッチ武器）は先頭値を使用
- `data/rank_param.json` に precision テーブル追加（aim と同値、B=12 が基準）

### フェーズ3: 弾切れと補給（優先度：中〜低）

#### T-7. ammo（総弾倉数）の実装
- **前提**: T-4 実装後
- **現状**: 弾切れなし
- **目標**: ammo 個の弾倉を使い切ったら射撃不能になる
- `Agent` に `mag_count: int` 属性を追加
- リロード完了時に mag_count -= 1、0 になったら「弾切れ」状態
- 弾切れ時の Brain の行動を決定（Brain に弾切れ状態を渡す必要あり）
- リスポーン時に mag_count をフルに補充

### フェーズ4: 補助武器の実装（優先度：中）← T-8 の前提

#### T-12. 補助武器（Sub Weapon）の実装
- **前提**: T-8（ロール選択）を意味のあるものにするための先行タスク
- **ロールごとの補助武器:**

| ロール | 補助武器 |
|---|---|
| ASSAULT | 近接武器（メレー）|
| HEAVY_ASSAULT | 近接武器 + 妨害補助アイテム（選択制） |
| SUPPORT | 索敵装備 または 弾薬補給装置（選択制） |
| SNIPER | 妨害補助アイテム または 索敵装備（選択制） |

- `SubWeaponType` Enum を `game_types.py` に追加（`MELEE` / `JAMMER` / `SCANNER` / `AMMO_PACK` など）
- `RoleLoadout` に `sub_weapon: SubWeaponType` フィールドを追加
- 補助武器の効果をシミュレーション内で処理（Brain の使用判断含む）
- Brain に補助武器使用状態（`USE_SUB` など）を追加

### フェーズ5: ロール選択戦略の実装（優先度：中）

#### T-8. リスポーン時のロール選択
- **前提**: T-12（補助武器）実装後
- **現状**: AgentLoadout.roles は定義済みだがリスポーン時にロールが変わらない
- **目標**: リスポーン時に AgentLoadout.roles から次ロールを選んで適用する
- ロール選択戦略インターフェースを決定（例: `RoleSelector` 基底クラス）
  - `FixedRoleSelector(role)`: 常に同じロール（現状維持）
  - `RandomRoleSelector(weights)`: ロールごとの出現率で選択
  - `StateBasedRoleSelector(...)`: 戦況によって選択（将来）
- `_process_respawns()` でリスポーン時にロール選択 → `agent.role`, `agent.dps`, `agent.brain`, `agent.hit_rate` を更新
- `AgentLoadout` にロール選択戦略（`role_selector`）フィールドを追加

### フェーズ6: 高度な戦闘仕様（優先度：中）

#### T-13. 被索敵状態に応じた戦闘判定 ✅ 実装済み
- `Simulation._resolve_combat()`: `in_range` フィルターに `a.detected` を追加（未検出の敵は射撃不可）
- 全 Brain クラスの ATTACK 条件に `nearest.detected` を追加（`GreedyBaseAttackBrain` / `PlantCaptureBrain` / `AggressiveCombatBrain`）
- テスト: `test_t13_detection_combat.py` 12件追加

#### T-14. 戦況イベントによる戦略切り替え
- **目標**: プラント占拠・敵撃破などのイベント発生時に Brain の戦略を動的に切り替える
- **実装方針:**
  - `Brain.on_event(event_type, game_state)` コールバックインターフェースを追加
  - `Simulation._log_event()` 内でイベント発生時に関連エージェントの `brain.on_event()` を呼ぶ
  - または `Brain.decide()` が試合状態（プラント制圧状況・コア残HP等）を参照して自律判断
  - 例: プラントが全占拠 → 攻撃優先 Brain に切り替え、自コアが危機域 → 防衛 Brain に切り替え
- **前提**: T-8（ロール選択）実装後に最も効果的

### フェーズ7: 高度なパラメータ（優先度：低）

#### T-9. スペシャル武器（SP ゲージ）の実装
- body: `spSupply`（SP回復速度）と武器の `spCharge`/`spReboot` の管理
  - ※ `booster` パラメータはブースト容量（T-3で実装済み）、SP とは別系統
- スペシャル武器専用の Brain 状態（`USE_SPECIAL`）が必要

#### T-10. 爆発・範囲ダメージの実装
- `radius` フィールドを持つ武器（グレネード、榴弾砲等）の範囲内全エージェントへのダメージ計算

#### T-11. 積載量チェック（leg: loadCapacity）
- 現在は重量超過ペナルティを計算していない
- cells_per_step のペナルティとして表現可能

### タスク依存関係

```
T-1（armor→max_hp）       ✅ 実装済み
T-2（aim→hit_rate）       ✅ 実装済み
T-3（ブースト巡航）        ✅ 実装済み
T-3.5（セルサイズ変更）    ✅ 実装済み
T-4（リロード）            ✅ 実装済み ← T-5, T-7 の前提
T-5（reloadRate反映）     ✅ 実装済み
T-6（precision→hit_rate） ✅ 実装済み
T-7（ammo弾切れ）         T-4 の後
T-8（ロール選択）          T-12 の後（T-2, T-4 実装後に効果大）
T-9（スペシャル）          T-8 の後
T-10（範囲ダメージ）       独立
T-11（積載量）             独立
T-12（補助武器）           独立 ← T-8 の前提
T-13（被索敵戦闘）         ✅ 実装済み
T-14（戦略切り替え）       T-8 の後（戦況反応型 Brain はロール切り替えと組み合わせて使う）
```

### 推奨実装順

| 順序 | タスク | 理由 |
|---|---|---|
| ✅ | T-1 armor → max_hp | 装甲差がロール間の基本差として最重要 |
| ✅ | T-2 aim → hit_rate | 命中率固定がシミュレーション精度に影響大 |
| ✅ | T-3 ブースト巡航 | 実ゲームの移動の大半はダッシュ。速度差の再現 |
| ✅ | T-3.5 セルサイズ変更 | 10m→5m で walk/dash の速度分解能が向上 |
| ✅ | T-4 リロードタイマー | 武器スペックの差を最もよく反映できる |
| ✅ | T-5 reloadRate 反映 | T-4 があれば追加コスト小 |
| ✅ | T-6 precision → hit_rate | aim と precision の相乗効果でロール差が明確化 |
| 1 | T-12 補助武器 | ロール別サブ武器の定義。T-8（ロール選択）の直接前提 |
| 2 | T-8 ロール選択戦略 | T-12 実装後に複数ロール混成が意味を持つ |
| ✅ | T-13 被索敵戦闘 | 被索敵状態の活用で戦略的深度が増す |
| 4 | T-14 戦略切り替え | 戦況反応型 Brain でシミュレーション展開が多様化 |
| 5 | T-7 ammo 弾切れ | T-4 があれば追加コスト小 |
| 6 | T-10, T-11 | 状況に応じて |
| 後 | T-9 スペシャル | 実装コスト高、優先度は最終段階 |

### 上位目標

- [ ] スコア計算（占拠・撃破・回復ポイント）の実装
- [ ] スコアパラメータを変えた複数回シミュレーションの比較・分析
- [x] `parts_normalized.json` の追加（パーツ一覧 496件）

---

## 実行方法

```bash
cd BorderBreakシミュレーター
python simulation.py
```

1. 初期状態の静止画が表示される（閉じると次へ）
2. アニメーション実行（0.10秒/ステップ、最大600ステップ＝10分）
   - 各チーム 10 機が `GreedyBaseAttackBrain` で自律行動
   - 索敵範囲 80m 内に敵を発見 → 接近、ロックオン範囲 60m 内 → 停止して射撃
3. 終了条件
   - どちらかのコアが 0 → 即時勝利表示
   - 600ステップ到達 → コア残HP比較で勝敗（引き分けあり）
4. 終了後 `logs/dev/` に CSV ログを保存

### リプレイ動画の生成

`save_dev_logs()` で保存した `steps_*.csv` から動画を生成できる。

```bash
# GIF 生成（要: pip install pillow）
python replay.py logs/dev/steps_YYYYMMDD_HHMMSS.csv sim.gif

# MP4 生成（要: pip install pillow + FFmpeg システムインストール）
python replay.py logs/dev/steps_YYYYMMDD_HHMMSS.csv sim.mp4 --fps 15

# 解像度指定（デフォルト 640×480）
python replay.py logs/dev/steps_YYYYMMDD_HHMMSS.csv sim.gif --output-size 1280x960

# 完了メッセージを出力する場合
python replay.py logs/dev/steps_YYYYMMDD_HHMMSS.csv sim.gif --verbose
```

Python から直接呼ぶ場合:

```python
from replay import replay_video
replay_video('logs/dev/steps_YYYYMMDD_HHMMSS.csv', 'sim.gif', fps=10)
replay_video('logs/dev/steps_YYYYMMDD_HHMMSS.csv', 'sim.gif',
             output_size=(1280, 960), verbose=True)
```

> **注意**: エージェント列（`a{id}_x` 等）を含む最新フォーマットの steps_*.csv が必要。
> 旧フォーマットの CSV を渡すと `ValueError` が発生する。

### `run()` のオプション

| パラメータ | デフォルト | 説明 |
|---|---|---|
| `step_delay` | `0.0` | ステップ間の表示時間（秒）。`0` で GUI 非表示 |
| `verbose` | `False` | `True` でコンソールへの詳細ログを有効化 |

### `replay_video()` のオプション

| パラメータ | デフォルト | 説明 |
|---|---|---|
| `fps` | `10` | フレームレート |
| `output_size` | `(640, 480)` | 出力解像度（幅, 高さ）ピクセル。マップは中央配置・余白は黒 |
| `verbose` | `False` | `True` で完了メッセージをコンソールに出力 |

```python
# GUI 表示あり + コンソールログあり（python simulation.py の挙動）
sim.run(max_steps=600, step_delay=0.10, verbose=True)

# GUI なし + ログなし（テスト・バッチ実行向け。デフォルト）
sim.run(max_steps=600)
```

### テスト実行

```bash
python -m pytest tests/ -v
```

---

## パーツ・武器計算モジュール群の設計

### モジュール依存関係

```
bb_calc_movement.py          (依存なし)
bb_base_and_brand.py         → bb_calc_movement (_get_rank_closest を再利用)
bb_brbonus_calcparam_limit.py  (依存なし)
bb_weapon_calc.py              (依存なし)
catalog.py                     (依存なし)
assemble.py  → catalog / bb_base_and_brand / bb_brbonus_calcparam_limit / bb_weapon_calc
               ※ simulation.py → assemble.py の循環 import は禁止
               ※ _CELL_SIZE_M = 10 を assemble.py ローカル定数として定義（constants.py を import しない）
bb_full_calc.py → bb_base_and_brand / bb_brbonus_calcparam_limit / bb_weapon_calc
                  （※ constdata.js が必要。ファイルが存在しない場合は calc_full_assemble 呼び出し時にエラー）
```

### `catalog.py` — `Catalog` クラス

`data/` ディレクトリ以下の JSON ファイルを読み込み、パーツ・武器・定数テーブルを提供する。

| メソッド / プロパティ | 説明 |
|---|---|
| `list_parts(category)` | カテゴリ（head/body/arm/leg）のパーツ一覧 `[(key, name)]` |
| `get_part(category, key)` | 指定パーツの dict を返す（なければ KeyError） |
| `find_part_keys_by_name(category, name)` | 名前でパーツキーを検索 |
| `list_weapon_datasets()` | 武器データセット名の一覧（ソート済み） |
| `list_weapons(dataset)` | データセット内の武器一覧 `[(key, name)]` |
| `get_weapon(dataset, key)` | 指定武器の dict を返す（なければ KeyError） |
| `find_weapons_by_name(name)` | 名前で武器を検索、`[WeaponRef]` を返す |
| `rank_param` | ランク→数値テーブル（`data/rank_param.json`） |
| `sys_consts` | システム定数（`data/sys_calc_constants.json`） |
| `bland` | ブランドセットボーナス定義（`data/bland_data.json`） |
| `param_limits` | パラメータ下限設定（`data/parts_param_config.json`） |

> `data/parts_normalized.json` は現時点では存在しないため、パーツ検索系は空を返す。

### `bb_calc_movement.py` — 移動速度・重量ペナルティ

| 関数 | 説明 |
|---|---|
| `get_rank_closest(const_data, param)` | 数値に最も近いランク文字列を返す |
| `set_weight_penalty(...)` | 積載超過ペナルティを walk/dash に適用、MIN/MAX でクランプ、ランク再計算 |

`SysConsts` dataclass: `WEIGHT_PENALTY`, `WALK_MIN`, `DASH_MIN`, `WALK_MIN_HOVER`, `WALK_MAX_HOVER`, `DASH_MIN_HOVER`

### `bb_base_and_brand.py` — ベース集計・セットボーナス

| 関数 | 説明 |
|---|---|
| `_strip_js_comments(code)` | JS ソースからコメントを除去 |
| `_extract_brace_block(s, start_idx)` | `{...}` ブロックを抽出 |
| `_parse_js_object_literal(block)` | JS オブジェクトリテラルを Python dict に変換 |
| `load_const_parts(path)` | `constdata.js` からパーツ定義を読み込む |
| `load_bland_data(path)` | `constdata.js` からブランド定義を読み込む |
| `load_rank_param(path)` | `rank_param.json` を読み込む |
| `rank_param_load_part(part, rank_param)` | `{"rank": "C+"}` → `{"rank": "C+", "param": 1.0}` に変換 |
| `apply_set_bonus(draw, bland_data, bonus_rate_percent)` | 全4パーツが同一 `blandId` の場合にセットボーナスを適用 |
| `calc_parts_base(draw, sysc, rank_param, ...)` | 装甲平均・総重量・walk/dash（ペナルティ適用済み）を集計 |
| `build_draw_parts_from_const(...)` | `constdata.js` のパーツデータから draw 構造体を構築 |
| `_get_rank_closest` | `bb_calc_movement.get_rank_closest` の再エクスポート |

### `bb_brbonus_calcparam_limit.py` — 強化チップ・calc params

| 関数群 | 説明 |
|---|---|
| `add_bonus_br_armor(draw, bonus)` 他 | 個別チップ効果を draw に適用（加算・減算） |
| `apply_br_bonus_chips(draw, chip_reinforcement_br)` | チップ設定を一括適用（`CHIP_HANDLERS` テーブルで dispatch） |
| `calc_param_ndef_charge(src)` | DEF 回復時間の計算（`ndefCharge * ndefChargeRate / 100`） |
| `calc_param_step(src, step_boost_default)` | ブースター容量からステップ数を計算（切り上げ） |
| `calc_param_velocity(src)` | 加速到達時間の計算（`velocity * velocityTimeRate / 100`） |
| `calc_draw_param(src, parts_type, ...)` | head/body/leg に対応した calc_param を dispatch |
| `apply_parts_param_limits(draw, param_limits)` | `areaTransport >= 2.0` などのパラメータ下限を適用 |

### `bb_weapon_calc.py` — 武器派生パラメータ

| 関数 | 説明 |
|---|---|
| `get_damage_num(damage_obj)` | damage フィールドを `list[int]` に正規化（scalar / list / maxDamage / chargeDamage / pellet モデル対応） |
| `calc_magazine_damage(src)` | 弾倉火力 = damage × clip |
| `calc_mag_total_damage(src)` | 総火力 = damage × clip × ammo（ammo=0 は 1 扱い） |
| `calc_magazine_sec(src)` | 弾倉持続時間 = clip / rate × 60 |
| `calc_damage_per_sec(src)` | 秒間火力 = damage × rate / 60 |
| `apply_weapon_derived_params(dst)` | 上記4種を dst dict に追加（in-place）、同じ dict を返す |

### `assemble.py` — 高レベル API

| 関数 | 説明 |
|---|---|
| `calc_loadout(catalog, keys, ...)` | パーツキーを受け取り、セットボーナス・チップ・基本パラメータを一括計算 |
| `calc_weapon(catalog, ref)` | 武器の派生パラメータを計算した dict を返す |
| `calc_full(catalog, keys, weapons, ...)` | `calc_loadout` + 武器計算をまとめた統合エントリ |

---

## 依存ライブラリ

```
numpy >= 1.26
matplotlib >= 3.10
pillow >= 10.0    # replay.py で .gif / .mp4 生成に必要（pip install pillow）
```

> `.mp4` 出力には Pillow に加えて FFmpeg のシステムインストールが必要。
