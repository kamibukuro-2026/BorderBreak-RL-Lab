# Border Break シミュレーター

アーケードゲーム「Border Break」のマルチエージェントシミュレーター。
**スコア設定がプレイ体験に与える影響**を分析することを最終目標として、Python で構築しています。

---

## 概要

10 vs 10 のブラスト・ランナー（BR）が自律行動し、敵コアの破壊を目指す戦場をシミュレートします。
エージェントの行動戦略を差し替えることで、様々な戦術がゲームの結果に与える影響を定量的に評価できます。

```
BASE A（チームA）
   ↕  140m
  [P1]   ← プラント1
   ↕  110m
  [P2]   ← プラント2（中央）
   ↕  100m
  [P3]   ← プラント3
   ↕  140m
BASE B（チームB）
```

---

## 特徴

- **リアルタイム可視化** — matplotlib のアニメーションでエージェントの動きをステップごとに描画
- **リプレイ動画生成** — `replay.py` で `steps_*.csv` から `.gif` / `.mp4` 動画を生成可能
- **プラグイン可能な Brain** — `Brain.decide()` を実装するだけで新しい戦略を追加可能
- **同時解決戦闘** — 全エージェントの射撃を一括計算してから適用（相打ちあり）
- **CSV ログ出力** — ステップ・イベントの2種類のログを自動保存、分析に利用可能
- **パーツ・武器データ管理** — 実際のゲームデータを基にした機体パラメータ計算（セットボーナス・強化チップ・重量ペナルティ・武器派生パラメータ）
- **673 件のユニットテスト** — TDD で開発、全件グリーン

---

## ゲームルール

| 項目 | 内容 |
|---|---|
| 試合形式 | 10 vs 10 |
| 勝利条件 | 敵コア HP をゼロにする（即時決着）|
| 時間切れ | 600ステップ（10分）経過後、コア残HP が多い側の勝利 |
| コアへのダメージ源 | 敵BR のベース侵入（毎ステップ DPS）、BR 撃破ペナルティ（リスポーン時） |
| プラント | ゾーン内に滞在すると占拠ゲージが蓄積、占拠後は前線リスポーン地点として利用可能 |

---

## マップ仕様

| 項目 | 値 |
|---|---|
| グリッド単位 | 1 マス = 5m × 5m |
| マップサイズ | 縦 500m × 横 100m（100 × 20 セル） |
| ベース奥行き | 30m（6 セル） |
| プラント数 | 3 個（y = 140m / 250m / 355m、横中央） |
| プラント占拠範囲 | 半径 30m（6 セル） |

---

## 戦闘パラメータ

| パラメータ | 値 |
|---|---|
| BR HP | 10,000 |
| DPS（ダメージ/ステップ） | 3,000 |
| 命中率 | 64%（ロックオン内実効 ≈ 80%） |
| 索敵範囲 | 80m（16 セル） |
| ロックオン範囲 | 60m（12 セル） |
| 移動速度 | 21.9 m/s ≈ 4 セル/ステップ |
| リスポーン待機 | 10 ステップ |
| コア HP | 266,666（160 機撃破でゼロ） |
| 撃破ペナルティ | 約 1,666.67（自チームコアへ） |

---

## インストール

Python 3.12 以上を推奨します。

```bash
pip install numpy matplotlib

# リプレイ動画生成を使う場合（.gif / .mp4）
pip install pillow
# .mp4 出力には FFmpeg のシステムインストールも必要
```

---

## 使い方

### シミュレーション実行

```bash
python simulation.py
```

1. 初期状態の静止画が表示される（ウィンドウを閉じると開始）
2. アニメーション実行（0.10 秒/ステップ、最大 600 ステップ）
3. 終了後、`logs/dev/` に CSV ログを保存

### リプレイ動画の生成

```bash
# GIF 形式（要 Pillow）
python replay.py logs/dev/steps_YYYYMMDD_HHMMSS.csv sim.gif

# MP4 形式（要 Pillow + FFmpeg）
python replay.py logs/dev/steps_YYYYMMDD_HHMMSS.csv sim.mp4 --fps 15
```

Python スクリプトから呼ぶ場合：

```python
from replay import replay_video
replay_video('logs/dev/steps_YYYYMMDD_HHMMSS.csv', 'sim.gif', fps=10)
```

### テスト実行

```bash
python -m pytest tests/ -v
```

---

## ファイル構成

```
BorderBreakシミュレーター/
├── constants.py                      # 全ゲーム定数（CELL_SIZE_M, MAP_W, DPS, CORE_HP など）
├── game_types.py                     # CellType / Action / Role / Plant / Core / Map
├── brain.py                          # Brain / GreedyBaseAttackBrain / PlantCaptureBrain / AggressiveCombatBrain
├── agent.py                          # Agent クラス
├── map_gen.py                        # create_map() / get_base_spawn_points()
├── simulation.py                     # Simulation クラス（re-import ハブ）
├── replay.py                         # steps_*.csv から動画を生成（.gif / .mp4）
├── catalog.py                        # パーツ・武器データの読込とインデックス化
├── assemble.py                       # 機体アセンブル計算の高レベル API
├── bb_base_and_brand.py              # ベースパラメータ集計・セットボーナス計算
├── bb_brbonus_calcparam_limit.py     # 強化チップ適用・calc params・パラメータ下限
├── bb_calc_movement.py               # 重量ペナルティ・移動速度計算
├── bb_weapon_calc.py                 # 武器派生パラメータ計算（DPS・弾倉火力など）
├── bb_full_calc.py                   # constdata.js を使う統合エントリ
├── conftest.py                       # pytest パス設定
├── README.md                         # このファイル
├── CLAUDE.md                         # 設計仕様書（Claude Code 用）
├── .gitignore
├── data/
│   ├── weapons_all.json              # 全武器データ
│   ├── rank_param.json               # ランク→数値変換テーブル
│   ├── sys_calc_constants.json       # システム定数
│   ├── bland_data.json               # ブランドセットボーナス定義
│   ├── parts_param_config.json       # パーツパラメータの上下限設定
│   └── parts_normalized.json         # パーツ正規化データ（496件）
├── tests/
│   ├── test_core.py                  # Core クラスのテスト（25件）
│   ├── test_plant.py                 # Plant クラスのテスト（42件）
│   ├── test_agent.py                 # Agent クラスのテスト（53件）
│   ├── test_agent_boost.py           # Agent ブーストパラメータのテスト（20件）
│   ├── test_agent_reload.py          # Agent リロードパラメータのテスト（8件）
│   ├── test_brain.py                 # GreedyBaseAttackBrain のテスト（28件）
│   ├── test_plant_capture_brain.py   # PlantCaptureBrain のテスト（25件）
│   ├── test_aggressive_combat_brain.py  # AggressiveCombatBrain のテスト（18件）
│   ├── test_detection.py             # 被索敵状態のテスト（20件）
│   ├── test_simulation.py            # Simulation 戦闘ロジックのテスト（64件）
│   ├── test_simulation_boost.py      # Simulation ブースト巡航ロジックのテスト（23件）
│   ├── test_simulation_reload.py     # Simulation リロードロジックのテスト（11件）
│   ├── test_agent_parts.py           # Agent per-agent パラメータのテスト（25件）
│   ├── test_assemble.py              # assemble_agent_params のテスト（81件）
│   ├── test_simulation_parts.py      # Simulation + per-agent パラメータ統合テスト（20件）
│   ├── test_weapon_calc.py           # bb_weapon_calc のテスト（44件）
│   ├── test_bb_base_and_brand.py     # bb_base_and_brand のテスト（41件）
│   ├── test_bb_brbonus_calcparam_limit.py  # bb_brbonus_calcparam_limit のテスト（37件）
│   ├── test_bb_calc_movement.py      # bb_calc_movement のテスト（16件）
│   ├── test_catalog.py               # catalog のテスト（16件）
│   └── test_replay.py                # replay_video() のテスト（5件）
└── logs/
    └── dev/                          # 開発用 CSV ログ出力先
        ├── steps_YYYYMMDD_HHMMSS.csv
        └── events_YYYYMMDD_HHMMSS.csv
```

---

## Brain（行動戦略）

新しい戦略は `Brain.decide()` をオーバーライドして実装します。

```python
class Brain:
    def decide(self, agent: Agent, game_map: Map,
               plants: list[Plant], agents: list[Agent]) -> Action:
        return Action.STAY
```

### 実装済みの戦略

#### `GreedyBaseAttackBrain(target)`

敵ベースへ直行しながら、接敵したら戦闘を優先する。

| 状態 | 条件 | 行動 |
|---|---|---|
| ATTACK | ロックオン範囲（60m）内に敵 | STAY（射撃） |
| APPROACH | 索敵範囲（80m）内に敵 | 最近接の敵へ移動 |
| PATROL | 敵なし | 敵ベースへ移動 |

#### `PlantCaptureBrain(target)`

プラント占拠を優先しながら、接敵したら戦闘を行う。

| 状態 | 条件 | 行動 |
|---|---|---|
| ATTACK | ロックオン範囲（60m）内に敵 | STAY（射撃） |
| APPROACH | 索敵範囲（80m）内に敵 | 最近接の敵へ移動 |
| CAPTURE | 敵なし・未占拠プラントあり | 自チームベースに最も近い未占拠プラントへ移動 |
| PATROL | 敵なし・全プラント占拠済み | 敵ベースへ移動 |

---

## CSV ログ仕様

### `steps_YYYYMMDD_HHMMSS.csv`（1行 = 1ステップ）

| 列 | 内容 |
|---|---|
| `step` | ステップ番号 |
| `core_a_hp` / `core_b_hp` | コア残 HP |
| `alive_a` / `alive_b` | 生存機数 |
| `p1_owner` 〜 `p3_owner` | プラント所有者（-1=中立 / 0=A / 1=B） |
| `p1_gauge` 〜 `p3_gauge` | 占拠ゲージ値 |
| `a{id}_x` / `a{id}_y` | エージェント座標（セル単位）|
| `a{id}_alive` | 生存状態（1=生存, 0=撃破） |
| `a{id}_hp_pct` | HP 残量割合（0.0〜1.0） |
| `a{id}_team` | チーム（0=A, 1=B） |
| `a{id}_respawn` | リスポーン残時間 |

### `events_YYYYMMDD_HHMMSS.csv`（1行 = 1イベント）

| `event_type` | 内容 |
|---|---|
| `hit` | 命中（HP 減少・未撃破） |
| `kill` | 撃破 |
| `respawn` | リスポーン（`detail` に座標） |
| `kill_penalty` | リスポーン時のコアペナルティ |
| `plant_capture` | プラント占拠完了 |
| `core_attack` | ベース直接攻撃 |
| `victory` | 勝利（コア破壊） |
| `time_limit` | 制限時間終了（`agent_team=-1` は引き分け） |

---

## パーツ・武器計算 API

実際のゲームデータを用いた機体パラメータ計算ができます。

```python
from catalog import Catalog, LoadoutKeys, WeaponRef
from assemble import calc_full

catalog = Catalog()  # data/ ディレクトリから自動読み込み

# 武器の派生パラメータを計算
ref = WeaponRef(dataset="WEAPON_AS_MAIN", key="a")
weapon = calc_full(catalog, LoadoutKeys("a","a","a","a"), weapons={"main": ref})
# weapon["weapons"]["main"]["magazineDamage"]  → 弾倉火力
# weapon["weapons"]["main"]["damagePerSec"]    → 秒間火力
```

---

## 今後の予定

武器データ・パーツデータの調査にもとづき、以下の順序で実装を進める予定です。

### フェーズ1: パーツ由来パラメータの反映

| タスク | 状態 | 内容 |
|---|---|---|
| T-1 `max_hp` の可変化 | ✅ 完了 | body の `armor` ランクを BR の最大 HP に反映 |
| T-2 `hit_rate` の可変化 | ✅ 完了 | head の `aim` ランクを命中率に反映（決定論的 DPS 分率モデル） |
| T-3 ブースト巡航システム | ✅ 完了 | walk/dash 2段階速度 + boost ゲージ管理の実装 |
| T-3.5 セルサイズ変更 | ✅ 完了 | `CELL_SIZE_M: 10m → 5m` — walk/dash の速度比が 1:4 程度に向上 |

### フェーズ2: 武器の射撃サイクル実装（優先度：中）

| タスク | 状態 | 内容 |
|---|---|---|
| T-4 リロードタイマー | ✅ 完了 | 弾倉（clip）→ 射撃 → リロード（reload_steps）のサイクルを実装。`clip=0` で後方互換 |
| T-5 reloadRate 反映 | ✅ 完了 | arm の `reloadRate` ランク（%）をリロード時間に乗算。S-=59.5%〜E-=140%（T-4 の後） |
| T-6 precision 反映 | 未着手 | 武器の `precision` ランクを命中率に反映（T-2 の後） |

### フェーズ3: 弾切れと補給（優先度：中〜低）

| タスク | 内容 |
|---|---|
| T-7 ammo 弾切れ | 総弾倉数（ammo）を使い切ったら射撃不能。リスポーン時に補充（T-4 の後） |

### フェーズ4: ロール選択戦略（優先度：中）

| タスク | 内容 |
|---|---|
| T-8 リスポーン時ロール選択 | `AgentLoadout.roles` からリスポーン時に次ロールを選択する戦略クラスの実装 |

### フェーズ5: 高度な機能（優先度：低）

| タスク | 内容 |
|---|---|
| T-9 スペシャル武器 | SP ゲージ管理（body: spSupply）と spCharge / spReboot の実装 |
| T-10 範囲ダメージ | グレネード・榴弾砲など `radius` を持つ武器の爆発範囲ダメージ |
| T-11 積載量チェック | 重量超過ペナルティを `cells_per_step` に反映 |

### 上位目標

- [ ] スコア計算（占拠・撃破・回復ポイント）の実装
- [ ] スコアパラメータを変えた複数回シミュレーションの比較・分析
- [x] `parts_normalized.json` の追加（496 パーツ）
