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
| グリッド単位 | 1 マス = 10m × 10m |
| マップサイズ | 縦 500m × 横 100m |
| グリッドサイズ | 50 × 10 セル（`MAP_H=50`, `MAP_W=10`） |
| 向き | 縦型：上端に Base A（チームA）、下端に Base B（チームB） |
| ベース奥行き | 3 セル（30m）。`BASE_DEPTH = 3` |
| プラント数 | 3 個（`NUM_PLANTS = 3`） |
| プラント配置 | ベース間（y=3〜46）を等分割<br>→ y=14（140m）, y=25（250m）, y=35（350m）、すべて x=5（横中央） |
| プラント占拠範囲 | 半径 30m = 3 セル（`PLANT_RADIUS_C = 3.0`） |

---

## ファイル構成

```
BorderBreakシミュレーター/
├── simulation.py        # メイン実装（全ロジック）
├── conftest.py          # pytest パス設定
├── CLAUDE.md            # このファイル
├── tests/
│   ├── __init__.py
│   ├── test_core.py         # Core クラスのテスト（25件）
│   ├── test_plant.py        # Plant クラスのテスト（42件）
│   ├── test_agent.py        # Agent クラスのテスト（48件）
│   ├── test_brain.py                 # Brain / GreedyBaseAttackBrain のテスト（28件）
│   ├── test_plant_capture_brain.py   # PlantCaptureBrain のテスト（25件）
│   ├── test_detection.py             # 被索敵状態のテスト（20件）
│   └── test_simulation.py            # Simulation 戦闘ロジックのテスト（59件）
└── logs/
    └── dev/             # 開発用 CSV ログ出力先
        ├── steps_YYYYMMDD_HHMMSS.csv
        └── events_YYYYMMDD_HHMMSS.csv
```

**テスト合計: 247 件（全件グリーン）**

---

## クラス・型の設計（simulation.py）

### 定数

```python
CELL_SIZE_M    = 10       # 1マス = 10m
MAP_W, MAP_H   = 10, 50
BASE_DEPTH     = 3
NUM_PLANTS     = 3
PLANT_RADIUS_M = 30
PLANT_RADIUS_C = 3.0      # PLANT_RADIUS_M / CELL_SIZE_M

# 戦闘定数（1ステップ = 1秒）
AGENT_HP          = 10_000
DPS               = 3_000   # 射撃成功時のダメージ/ステップ
HIT_RATE          = 0.80
SEARCH_RANGE_M    = 80
SEARCH_RANGE_C    = 8.0     # SEARCH_RANGE_M / CELL_SIZE_M
LOCKON_RANGE_M    = 60
LOCKON_RANGE_C    = 6.0     # LOCKON_RANGE_M / CELL_SIZE_M
RESPAWN_STEPS     = 10
MOVE_SPEED_MPS    = 21.9
CELLS_PER_STEP    = 2       # max(1, round(21.9/10))
MATCH_TIME_STEPS  = 600     # 試合制限時間（10分 × 60秒/ステップ）
DETECTION_STEPS   = 3       # 被索敵状態になるまでの連続索敵ステップ数

# コア定数
CORE_HP           = 266_666
CORE_DMG_PER_KILL = CORE_HP / 160   # ≈ 1,666.67（撃破リスポーン時ペナルティ）
```

### `CellType`（IntEnum）

| 値 | 意味 |
|---|---|
| `EMPTY` | 通路 |
| `OBSTACLE` | 障害物 |
| `PLANT` | プラント中心セル |
| `BASE_A` | チームA ベース（上端 y=0〜2） |
| `BASE_B` | チームB ベース（下端 y=47〜49） |

### `Plant`（dataclass）

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

radius=3 の場合、spawn_y は plant.y ∓ 4（チームA/B）。

### `Core`（dataclass）

- `team`, `hp`, `max_hp`
- `destroyed` プロパティ → `hp <= 0`
- `hp_pct` プロパティ → HP%
- `apply_damage(dmg)` → `max(0, hp - dmg)` にクランプ

### `Map`

- `numpy` の 2D 配列でグリッドを管理
- `is_walkable(x, y)` → 境界内かつ `OBSTACLE` でなければ True

### `Action`（Enum）+ `ACTION_DELTA`

```python
Action.STAY / MOVE_UP / MOVE_DOWN / MOVE_LEFT / MOVE_RIGHT
ACTION_DELTA: dict[Action, tuple[int, int]]  # (dx, dy)
```

### `Brain` / `GreedyBaseAttackBrain`

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

### `Agent`（ブラスト・ランナー）

- `agent_id`, `x`, `y`, `team`, `hp`, `max_hp`, `alive`, `respawn_timer`, `brain`
- `detected`（bool, 初期値 False）: 被索敵状態（True=敵に位置情報を把握されている）
- `exposure_steps`（int, 初期値 0）: 敵の索敵範囲内にいる連続ステップ数
- `move(dx, dy, map) -> bool` / `move_up/down/left/right(map)`
- `dist_cells(other)` → ユークリッド距離（セル単位）
- `in_search_range(other)` → `dist_cells <= SEARCH_RANGE_C`
- `in_lockon_range(other)` → `dist_cells <= LOCKON_RANGE_C`
- `pos` プロパティ → `(x, y)`
- `pos_m` プロパティ → メートル座標 `(x*10, y*10)`

### `Simulation`

| メソッド | 説明 |
|---|---|
| `add_agent(agent)` | エージェントを登録 |
| `_log_event(event_type, **kwargs)` | 開発ログにイベントを追記 |
| `_draw(ax, title)` | マップ・プラント・エージェント・コアHPバーを描画 |
| `visualize(title)` | 静止画として `plt.show()` で表示 |
| `_execute_action(agent, action)` | `CELLS_PER_STEP` 分だけ移動（壁で中断） |
| `_resolve_combat()` | 同時解決で射撃ダメージ適用、撃破判定 |
| `_resolve_time_limit()` | 制限時間到達時の勝敗判定（コアHP比較） |
| `_process_respawns()` | タイマー更新・リスポーン・コアキルペナルティ |
| `_update_plants()` | 占拠ゲージ更新 |
| `_update_cores()` | ベース内敵 BR からのコアダメージ |
| `_update_detection()` | 全エージェントの被索敵状態（detected/exposure_steps）を更新 |
| `run(max_steps, step_delay, verbose)` | アニメーション実行ループ |
| `save_dev_logs(base_dir)` | 開発用 CSV ログを保存 |

#### `run()` の1ステップ処理順

```
行動決定（Brain.decide） → _resolve_combat() → _process_respawns()
→ _update_plants() → _update_cores() → _update_detection()
→ スナップショット記録 → 勝敗判定（コア破壊） → 制限時間判定 → 描画
```

### モジュールレベル関数

#### `create_map() -> tuple[Map, list[Plant]]`

- Base A/B をグリッドに設定
- `np.linspace(3, 46, 5)[1:-1]` でプラント y 座標を等分割計算

#### `get_base_spawn_points(team: int) -> list[tuple[int, int]]`

ベースの再出撃地点を左右2か所返す。

| チーム | x | y |
|---|---|---|
| A（team=0） | 1, MAP_W-2（= 1, 8） | BASE_DEPTH // 2（= 1） |
| B（team=1） | 1, MAP_W-2（= 1, 8） | MAP_H - BASE_DEPTH // 2 - 1（= 48） |

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
| 索敵範囲 | 80m = 8セル（SEARCH_RANGE_C） |
| ロックオン範囲 | 60m = 6セル（LOCKON_RANGE_C） |
| リスポーン待機 | 10ステップ（RESPAWN_STEPS） |
| 移動速度 | 21.9m/s ≈ 2セル/ステップ（CELLS_PER_STEP） |

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

プラント円（半径3セル）から1グリッド外側（自軍ベース方向）、中心を挟んで左右対称。

### ベース再出撃地点

ベース左端(x=0)から1格(x=1)と右端(x=9)から1格(x=8)の2か所。y はベース中央。

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
- [x] ユニットテスト 247 件（test_core / test_plant / test_agent / test_brain / test_plant_capture_brain / test_detection / test_simulation）

## 未実装・次ステップ候補

- [ ] 行動戦略の多様化（プラント占拠専従・役割分担）
- [ ] スコア計算（占拠・撃破・回復ポイント）
- [ ] スコアパラメータを変えた複数回シミュレーション比較・分析

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

### テスト実行

```bash
python -m pytest tests/ -v
```

## 依存ライブラリ

```
numpy >= 1.26
matplotlib >= 3.10
```
