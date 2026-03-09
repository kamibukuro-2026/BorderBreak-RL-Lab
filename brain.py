"""Border Break シミュレーター — Brain（行動戦略）クラス群"""
from __future__ import annotations

from typing import TYPE_CHECKING

from game_types import Action, ACTION_DELTA, Map, Plant

if TYPE_CHECKING:
    from agent import Agent


# ─────────────────────────────────────────
# 行動戦略（Brain）
# ─────────────────────────────────────────
class Brain:
    """行動決定ロジックの基底クラス。サブクラスで decide() をオーバーライドする。"""

    def decide(self, agent: Agent, game_map: Map,
               plants: list[Plant], agents: list[Agent]) -> Action:
        del agent, game_map, plants, agents  # サブクラスでオーバーライド想定。基底実装は何もしない。
        return Action.STAY


class GreedyBaseAttackBrain(Brain):
    """
    敵ベースへ向かいながら、敵を検知したら戦闘を行う貪欲戦略。

    行動状態（優先順）:
      1. ATTACK  : ロックオン距離（LOCKON_RANGE_C）内に敵がいる
                   → STAY（足を止めて射撃。ダメージ適用は Simulation が担当）
      2. APPROACH: 索敵範囲（SEARCH_RANGE_C）内に敵がいる
                   → 最も近い敵へ貪欲移動
      3. PATROL  : 敵が視界外
                   → 目標（敵ベース）へ貪欲移動
    """

    def __init__(self, target: tuple[int, int]):
        """
        Parameters
        ----------
        target : (x, y) セル座標  ← 敵ベース中心など
        """
        self.target = target

    def decide(self, agent: Agent, game_map: Map,
               plants: list[Plant], agents: list[Agent]) -> Action:
        del plants  # 現バージョンでは未使用

        # 生存している敵エージェントを列挙
        enemies = [a for a in agents if a.alive and a.team != agent.team]
        visible = [e for e in enemies if agent.in_search_range(e)]

        if visible:
            nearest = min(visible, key=lambda e: agent.dist_cells(e))

            # 状態1 ATTACK: ロックオン距離内かつ被索敵済み → 足を止めて射撃
            # T-13: detected=False の敵は位置不明扱い → ATTACK しない
            if agent.in_lockon_range(nearest) and nearest.detected:
                return Action.STAY

            # 状態2 APPROACH: 索敵範囲内 → 最も近い敵へ接近
            return self._move_toward(agent, nearest.x, nearest.y, game_map)

        # 状態3 PATROL: 敵なし → 敵ベースへ直進
        return self._move_toward(agent, *self.target, game_map)

    def _move_toward(self, agent: Agent, tx: int, ty: int, game_map: Map) -> Action:
        """指定座標 (tx, ty) に向かう貪欲移動アクションを返す。"""
        dy = ty - agent.y
        dx = tx - agent.x

        if dx == 0 and dy == 0:
            return Action.STAY

        candidates: list[Action] = []
        if abs(dy) >= abs(dx):
            if dy > 0: candidates.append(Action.MOVE_DOWN)
            if dy < 0: candidates.append(Action.MOVE_UP)
            if dx > 0: candidates.append(Action.MOVE_RIGHT)
            if dx < 0: candidates.append(Action.MOVE_LEFT)
        else:
            if dx > 0: candidates.append(Action.MOVE_RIGHT)
            if dx < 0: candidates.append(Action.MOVE_LEFT)
            if dy > 0: candidates.append(Action.MOVE_DOWN)
            if dy < 0: candidates.append(Action.MOVE_UP)

        for action in candidates:
            ddx, ddy = ACTION_DELTA[action]
            if game_map.is_walkable(agent.x + ddx, agent.y + ddy):
                return action

        return Action.STAY  # 全方向ふさがれた場合


class PlantCaptureBrain(GreedyBaseAttackBrain):
    """
    プラント占拠を優先しながら、敵を検知したら戦闘を行う戦略。

    行動状態（優先順）:
      1. ATTACK  : ロックオン距離（LOCKON_RANGE_C）内に敵がいる
                   → STAY（足を止めて射撃）
      2. APPROACH: 索敵範囲（SEARCH_RANGE_C）内・ロックオン外に敵がいる
                   → 最も近い敵へ貪欲移動
      3. CAPTURE : 敵が視界外・自チーム未占拠プラントがある
                   → 自チームのベースに最も近い未占拠プラントへ貪欲移動
                   （チームA: y が最小のプラント、チームB: y が最大のプラント）
      4. PATROL  : 全プラントが自チーム占拠済み（またはプラントなし）
                   → 目標（敵ベース）へ貪欲移動
    """

    def decide(self, agent: Agent, game_map: Map,
               plants: list[Plant], agents: list[Agent]) -> Action:
        # 生存している敵エージェントを列挙
        enemies = [a for a in agents if a.alive and a.team != agent.team]
        visible = [e for e in enemies if agent.in_search_range(e)]

        if visible:
            nearest = min(visible, key=lambda e: agent.dist_cells(e))

            # 状態1 ATTACK: ロックオン距離内かつ被索敵済み → 足を止めて射撃
            # T-13: detected=False の敵は位置不明扱い → ATTACK しない
            if agent.in_lockon_range(nearest) and nearest.detected:
                return Action.STAY

            # 状態2 APPROACH: 索敵範囲内 → 最も近い敵へ接近
            return self._move_toward(agent, nearest.x, nearest.y, game_map)

        # 状態3 CAPTURE: 自チームが占拠していないプラントを探す
        uncaptured = [p for p in plants if p.owner != agent.team]
        if uncaptured:
            # 自チームのベースに最も近い未占拠プラントを選択
            if agent.team == 0:
                target_plant = min(uncaptured, key=lambda p: p.y)  # 上端ベース → y最小
            else:
                target_plant = max(uncaptured, key=lambda p: p.y)  # 下端ベース → y最大
            return self._move_toward(agent, target_plant.x, target_plant.y, game_map)

        # 状態4 PATROL: 全プラント占拠済み → 敵ベースへ直進
        return self._move_toward(agent, *self.target, game_map)


class AggressiveCombatBrain(GreedyBaseAttackBrain):
    """
    戦闘重視の戦略。マップ上で可視化された敵（detected=True）を積極的に追撃する。

    行動状態（優先順）:
      1. ATTACK  : ロックオン距離（LOCKON_RANGE_C）内に敵がいる
                   → STAY（足を止めて射撃）
      2. APPROACH: 索敵範囲（SEARCH_RANGE_C）内・ロックオン外の敵がいる
                   → 最も近い敵へ貪欲移動
      3. HUNT    : 索敵範囲外だが detected=True の敵がいる
                   → 最近接 detected 敵へ貪欲移動
      4. PATROL  : 追跡対象なし → 目標（敵ベース）へ貪欲移動
    """

    def decide(self, agent: Agent, game_map: Map,
               plants: list[Plant], agents: list[Agent]) -> Action:
        del plants  # 未使用

        enemies = [a for a in agents if a.alive and a.team != agent.team]
        visible = [e for e in enemies if agent.in_search_range(e)]

        if visible:
            nearest = min(visible, key=lambda e: agent.dist_cells(e))

            # 状態1 ATTACK: ロックオン距離内かつ被索敵済み → 足を止めて射撃
            # T-13: detected=False の敵は位置不明扱い → ATTACK しない
            if agent.in_lockon_range(nearest) and nearest.detected:
                return Action.STAY

            # 状態2 APPROACH: 索敵範囲内 → 最も近い敵へ接近
            return self._move_toward(agent, nearest.x, nearest.y, game_map)

        # 状態3 HUNT: detected=True の敵（味方が発見済み）を追撃
        detected_enemies = [e for e in enemies if e.detected]
        if detected_enemies:
            target = min(detected_enemies, key=lambda e: agent.dist_cells(e))
            return self._move_toward(agent, target.x, target.y, game_map)

        # 状態4 PATROL: 追跡対象なし → 敵ベースへ直進
        return self._move_toward(agent, *self.target, game_map)
