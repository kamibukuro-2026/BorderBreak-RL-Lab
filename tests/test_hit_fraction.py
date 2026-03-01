"""
tests/test_hit_fraction.py
Simulation._calc_hit_fraction() のテスト

テスト対象:
  - ロックオン範囲内: hit_fraction = min(1.0, hit_rate * LOCKON_BONUS)
  - ロックオン境界 (t=0): ペナルティなし → hit_fraction = hit_rate
  - 索敵境界 (t=1): 最大ペナルティ → hit_fraction = hit_rate * (1 - DIST_PENALTY_MAX)
  - 中間点 (t=0.5): 線形補間
  - rate_floor: shots_per_step から計算される最低命中率
  - hit_fraction = max(rate_floor, capped_hit_frac) の保証
  - カスタム hit_rate / shots_per_step がインスタンス変数として使われる
"""
import pytest
from simulation import (
    Simulation, Map, Agent,
    LOCKON_BONUS, DIST_PENALTY_MAX, MISS_FLOOR_PER_SHOT,
    HIT_RATE,
    MAP_W, MAP_H,
)


# ─────────────────────────────────────────
# テスト用ファクトリ
# ─────────────────────────────────────────
def make_sim() -> Simulation:
    return Simulation(Map(MAP_W, MAP_H), plants=[])


def make_agent(agent_id: int, x: int, y: int, team: int, **kwargs) -> Agent:
    return Agent(agent_id=agent_id, x=x, y=y, team=team, **kwargs)


# ─────────────────────────────────────────
# ロックオン範囲内のテスト
# ─────────────────────────────────────────
class TestCalcHitFractionInLockonRange:

    def test_default_hit_rate_in_lockon_gets_bonus(self):
        """デフォルト hit_rate=0.64, ロックオン範囲内 → min(1.0, 0.64*1.25) = 0.80"""
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0)          # hit_rate=HIT_RATE=0.64, lockon_range_c=6
        target  = make_agent(2, 0, 5, team=1)           # dist=5 ≤ 6
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(min(1.0, HIT_RATE * LOCKON_BONUS))

    def test_lower_hit_rate_in_lockon_gets_bonus(self):
        """hit_rate=0.70, ロックオン範囲内 → min(1.0, 0.70*1.25) = 0.875"""
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.70)
        target  = make_agent(2, 0, 5, team=1)
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(0.70 * LOCKON_BONUS)

    def test_hit_rate_with_bonus_capped_at_1(self):
        """hit_rate=0.90 → 0.90*1.25=1.125 → 1.0 にクランプ"""
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.90)
        target  = make_agent(2, 0, 3, team=1)           # dist=3 ≤ 6
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(1.0)

    def test_at_lockon_boundary_with_bonus(self):
        """dist == lockon_range_c の境界では ロックオンボーナス適用"""
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.80, lockon_range_c=6.0)
        target  = make_agent(2, 0, 6, team=1)           # dist=6 = lockon_range_c
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(min(1.0, 0.80 * LOCKON_BONUS))


# ─────────────────────────────────────────
# 索敵〜ロックオン範囲間の距離ペナルティのテスト
# ─────────────────────────────────────────
class TestCalcHitFractionDistancePenalty:

    def test_just_outside_lockon_t_near_zero(self):
        """ロックオン直外 (t≈0) → ペナルティほぼなし"""
        sim = make_sim()
        # lockon=6, search=8 → t=(6.5-6)/(8-6)=0.25
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.80,
                              lockon_range_c=6.0, search_range_c=8.0)
        target  = make_agent(2, 0, 0, team=1)
        target.x, target.y = 0, 0   # dist=0; need to place at exact dist
        # Manually override to set up dist=6.5 is tricky with int coords.
        # Use x=6, y=2 for agent, shooter at (0,0) → dist = sqrt(36+4) = sqrt(40) ≈ 6.32
        target.x, target.y = 6, 2
        dist = shooter.dist_cells(target)    # √40 ≈ 6.32
        t = (dist - 6.0) / (8.0 - 6.0)
        expected = 0.80 * (1.0 - t * DIST_PENALTY_MAX)
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(expected, abs=1e-9)

    def test_at_search_boundary_t_equals_1(self):
        """dist == search_range_c → t=1 → 最大ペナルティ"""
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.80,
                              lockon_range_c=6.0, search_range_c=8.0)
        target  = make_agent(2, 8, 0, team=1)           # dist=8 = search_range_c
        expected = 0.80 * (1.0 - 1.0 * DIST_PENALTY_MAX)   # = 0.80 * 0.60 = 0.48
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(expected)

    def test_midpoint_t_equals_half(self):
        """dist = (lockon + search) / 2 → t=0.5 → 半分のペナルティ"""
        sim = make_sim()
        # lockon=6, search=8 → midpoint dist=7; t=0.5
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.80,
                              lockon_range_c=6.0, search_range_c=8.0)
        target  = make_agent(2, 7, 0, team=1)           # dist=7
        expected = 0.80 * (1.0 - 0.5 * DIST_PENALTY_MAX)  # = 0.80 * 0.80 = 0.64
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(expected)

    def test_beyond_search_range_t_clamped_at_1(self):
        """dist > search_range_c → t は 1.0 にクランプ → 最大ペナルティ"""
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.80,
                              lockon_range_c=6.0, search_range_c=8.0)
        target  = make_agent(2, 0, 10, team=1)          # dist=10 > search_range_c=8
        expected = 0.80 * (1.0 - 1.0 * DIST_PENALTY_MAX)  # same as t=1
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(expected)

    def test_custom_hit_rate_applies_distance_penalty(self):
        """カスタム hit_rate=0.95, 距離ペナルティ適用"""
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.95,
                              lockon_range_c=6.0, search_range_c=8.0)
        target  = make_agent(2, 8, 0, team=1)           # dist=8 = search_range_c → t=1
        expected = 0.95 * (1.0 - DIST_PENALTY_MAX)
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(expected)


# ─────────────────────────────────────────
# rate_floor（発射レート由来の下限）のテスト
# ─────────────────────────────────────────
class TestCalcHitFractionRateFloor:

    def test_rate_floor_shots_1(self):
        """shots_per_step=1 → rate_floor = 1 - 0.99^1 = 0.01"""
        sim = make_sim()
        # hit_rate=0 → hit_frac=0, rate_floor=0.01 が下限として使われる
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.0, shots_per_step=1,
                              lockon_range_c=6.0, search_range_c=8.0)
        target  = make_agent(2, 8, 0, team=1)           # dist=8 → hit_frac=0
        expected_floor = 1.0 - (1.0 - MISS_FLOOR_PER_SHOT) ** 1
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(expected_floor)

    def test_rate_floor_shots_5(self):
        """shots_per_step=5 → rate_floor = 1 - 0.99^5 ≈ 0.0490"""
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.0, shots_per_step=5,
                              lockon_range_c=6.0, search_range_c=8.0)
        target  = make_agent(2, 8, 0, team=1)
        expected_floor = 1.0 - (1.0 - MISS_FLOOR_PER_SHOT) ** 5
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(expected_floor)

    def test_rate_floor_shots_10(self):
        """shots_per_step=10 → rate_floor = 1 - 0.99^10 ≈ 0.0956"""
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.0, shots_per_step=10,
                              lockon_range_c=6.0, search_range_c=8.0)
        target  = make_agent(2, 8, 0, team=1)
        expected_floor = 1.0 - (1.0 - MISS_FLOOR_PER_SHOT) ** 10
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(expected_floor)

    def test_normal_hit_rate_higher_than_floor_wins(self):
        """通常の hit_fraction が rate_floor より大きければ hit_fraction が使われる"""
        sim = make_sim()
        # lockon 範囲内: hit_fraction = min(1.0, 0.80*1.25) = 1.0 >> rate_floor
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.80, shots_per_step=1)
        target  = make_agent(2, 0, 5, team=1)           # dist=5 ≤ lockon_range_c=6
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(1.0)   # floor=0.01 << 1.0

    def test_floor_supersedes_very_low_hit_fraction(self):
        """超低 hit_rate で距離ペナルティがあっても rate_floor が保証される"""
        sim = make_sim()
        # hit_rate=0.001 で t=1 → hit_frac = 0.001 * 0.6 = 0.0006 < floor=0.01
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.001, shots_per_step=1,
                              lockon_range_c=6.0, search_range_c=8.0)
        target  = make_agent(2, 8, 0, team=1)
        floor = 1.0 - (1.0 - MISS_FLOOR_PER_SHOT) ** 1   # 0.01
        hf = sim._calc_hit_fraction(shooter, target)
        assert hf == pytest.approx(floor)


# ─────────────────────────────────────────
# インスタンス変数が使われることの確認
# ─────────────────────────────────────────
class TestCalcHitFractionUsesInstanceVars:

    def test_uses_shooter_hit_rate(self):
        """hit_rate インスタンス変数が反映される（異なる値で比較）"""
        sim = make_sim()
        a_low  = make_agent(1, 0, 0, team=0, hit_rate=0.50,
                             lockon_range_c=6.0, search_range_c=8.0)
        a_high = make_agent(3, 0, 0, team=0, hit_rate=0.95,
                             lockon_range_c=6.0, search_range_c=8.0)
        target = make_agent(2, 8, 0, team=1)   # dist=8 = search_range_c, t=1
        hf_low  = sim._calc_hit_fraction(a_low, target)
        hf_high = sim._calc_hit_fraction(a_high, target)
        assert hf_high > hf_low

    def test_uses_shooter_shots_per_step(self):
        """shots_per_step が rate_floor に影響する"""
        sim = make_sim()
        a1 = make_agent(1, 0, 0, team=0, hit_rate=0.0, shots_per_step=1,
                         lockon_range_c=6.0, search_range_c=8.0)
        a5 = make_agent(3, 0, 0, team=0, hit_rate=0.0, shots_per_step=5,
                         lockon_range_c=6.0, search_range_c=8.0)
        target = make_agent(2, 8, 0, team=1)
        hf1 = sim._calc_hit_fraction(a1, target)
        hf5 = sim._calc_hit_fraction(a5, target)
        # shots=5 の方が rate_floor が大きい
        assert hf5 > hf1

    def test_uses_shooter_lockon_range_c(self):
        """lockon_range_c インスタンス変数が使われる"""
        sim = make_sim()
        # lockon_range_c=5 なら dist=5 は境界（ロックオン）→ ボーナスあり
        # lockon_range_c=4 なら dist=5 は範囲外（ペナルティあり）
        target = make_agent(2, 5, 0, team=1)
        a_wide = make_agent(1, 0, 0, team=0, hit_rate=0.80,
                             lockon_range_c=5.0, search_range_c=8.0)
        a_narrow = make_agent(3, 0, 0, team=0, hit_rate=0.80,
                               lockon_range_c=4.0, search_range_c=8.0)
        hf_wide   = sim._calc_hit_fraction(a_wide, target)
        hf_narrow = sim._calc_hit_fraction(a_narrow, target)
        assert hf_wide > hf_narrow   # ボーナスあり vs ペナルティあり


# ─────────────────────────────────────────
# _resolve_combat() が _calc_hit_fraction() を使うテスト
# ─────────────────────────────────────────
class TestResolveCombatDeterministic:

    def test_in_lockon_range_deals_full_dps(self):
        """hit_rate=1.0, ロックオン範囲内(dist=5) → hit_fraction=1.0 → damage=DPS"""
        from simulation import DPS, AGENT_HP
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, hit_rate=1.0)
        target  = make_agent(2, 0, 5, team=1)   # dist=5 ≤ lockon=6
        sim.add_agent(shooter)
        sim.add_agent(target)
        sim._resolve_combat()
        assert target.hp == AGENT_HP - DPS

    def test_low_hit_rate_reduces_damage(self):
        """hit_rate=0.40 でロックオン範囲内(dist=5) → hit_fraction = min(1.0, 0.40*LOCKON_BONUS)=0.50"""
        from simulation import DPS, AGENT_HP
        sim = make_sim()
        # dist=5 ≤ lockon=6 → hit_frac = min(1.0, 0.40*1.25) = 0.50
        shooter = make_agent(1, 0, 0, team=0, hit_rate=0.40)
        target  = make_agent(2, 0, 5, team=1)
        sim.add_agent(shooter)
        sim.add_agent(target)
        sim._resolve_combat()
        expected_hf = min(1.0, 0.40 * LOCKON_BONUS)   # = 0.50
        expected_dmg = int(DPS * expected_hf)
        assert target.hp == AGENT_HP - expected_dmg

    def test_zero_dps_still_no_damage(self):
        """dps=0 はどんな hit_fraction でもダメージなし"""
        from simulation import AGENT_HP
        sim = make_sim()
        shooter = make_agent(1, 0, 0, team=0, dps=0)
        target  = make_agent(2, 0, 5, team=1)
        sim.add_agent(shooter)
        sim.add_agent(target)
        sim._resolve_combat()
        assert target.hp == AGENT_HP
