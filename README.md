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
- **プラグイン可能な Brain** — `Brain.decide()` を実装するだけで新しい戦略を追加可能
- **同時解決戦闘** — 全エージェントの射撃を一括計算してから適用（相打ちあり）
- **CSV ログ出力** — ステップ・イベントの2種類のログを自動保存、分析に利用可能
- **227 件のユニットテスト** — TDD で開発、全件グリーン

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
| グリッド単位 | 1 マス = 10m × 10m |
| マップサイズ | 縦 500m × 横 100m（50 × 10 セル） |
| ベース奥行き | 30m（3 セル） |
| プラント数 | 3 個（y = 140m / 250m / 350m、横中央） |
| プラント占拠範囲 | 半径 30m（3 セル） |

---

## 戦闘パラメータ

| パラメータ | 値 |
|---|---|
| BR HP | 10,000 |
| DPS（ダメージ/ステップ） | 3,000 |
| 命中率 | 80% |
| 索敵範囲 | 80m（8 セル） |
| ロックオン範囲 | 60m（6 セル） |
| 移動速度 | 21.9 m/s ≈ 2 セル/ステップ |
| リスポーン待機 | 10 ステップ |
| コア HP | 266,666（160 機撃破でゼロ） |
| 撃破ペナルティ | 約 1,666.67（自チームコアへ） |

---

## インストール

Python 3.12 以上を推奨します。

```bash
pip install numpy matplotlib
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

### テスト実行

```bash
python -m pytest tests/ -v
```

---

## ファイル構成

```
BorderBreakシミュレーター/
├── simulation.py                     # メイン実装（全ロジック）
├── conftest.py                       # pytest パス設定
├── README.md                         # このファイル
├── CLAUDE.md                         # 設計仕様書（Claude Code 用）
├── .gitignore
├── tests/
│   ├── test_core.py                  # Core クラスのテスト（25件）
│   ├── test_plant.py                 # Plant クラスのテスト（42件）
│   ├── test_agent.py                 # Agent クラスのテスト（48件）
│   ├── test_brain.py                 # GreedyBaseAttackBrain のテスト（28件）
│   ├── test_plant_capture_brain.py   # PlantCaptureBrain のテスト（25件）
│   └── test_simulation.py            # Simulation 戦闘ロジックのテスト（59件）
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

## 今後の予定

- [ ] 行動戦略の追加（役割分担・陣形など）
- [ ] スコア計算（占拠・撃破・回復ポイント）
- [ ] スコアパラメータを変えた複数回シミュレーションの比較・分析
