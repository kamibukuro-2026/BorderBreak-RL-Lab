"""
tests/test_core.py
Core クラスの単体テスト

テスト対象:
  - Core.hp / max_hp / team（初期値）
  - Core.destroyed プロパティ
  - Core.hp_pct プロパティ
  - Core.apply_damage() メソッド
  - CORE_DMG_PER_KILL 定数（160機撃破でゼロになる数値）
"""
import pytest
from simulation import Core, CORE_HP, CORE_DMG_PER_KILL


# ─────────────────────────────────────────
# 初期状態
# ─────────────────────────────────────────
class TestCoreInitial:
    def test_hp_equals_core_hp(self):
        """初期 HP は CORE_HP と等しい"""
        core = Core(team=0)
        assert core.hp == float(CORE_HP)

    def test_max_hp_equals_core_hp(self):
        """max_hp は CORE_HP と等しい"""
        core = Core(team=0)
        assert core.max_hp == float(CORE_HP)

    def test_not_destroyed_on_init(self):
        """生成直後は destroyed=False"""
        core = Core(team=0)
        assert not core.destroyed

    def test_hp_pct_100_on_init(self):
        """生成直後の hp_pct は 100.0"""
        core = Core(team=0)
        assert core.hp_pct == pytest.approx(100.0)

    def test_team_a(self):
        core = Core(team=0)
        assert core.team == 0

    def test_team_b(self):
        core = Core(team=1)
        assert core.team == 1


# ─────────────────────────────────────────
# apply_damage()
# ─────────────────────────────────────────
class TestApplyDamage:
    def test_normal_damage_reduces_hp(self):
        """通常ダメージで HP が減る"""
        core = Core(team=0)
        core.apply_damage(1_000)
        assert core.hp == pytest.approx(float(CORE_HP) - 1_000)

    def test_zero_damage_no_change(self):
        """0 ダメージでは HP は変化しない"""
        core = Core(team=0)
        core.apply_damage(0)
        assert core.hp == float(CORE_HP)

    def test_damage_accumulates(self):
        """複数回のダメージが累積される"""
        core = Core(team=0)
        core.apply_damage(1_000)
        core.apply_damage(2_000)
        assert core.hp == pytest.approx(float(CORE_HP) - 3_000)

    def test_exact_kill(self):
        """HP と同量のダメージで HP = 0.0"""
        core = Core(team=0)
        core.apply_damage(float(CORE_HP))
        assert core.hp == 0.0

    def test_overkill_clamps_to_zero(self):
        """HP を超えるダメージでも 0.0 で止まる（負にならない）"""
        core = Core(team=0)
        core.apply_damage(float(CORE_HP) * 10)
        assert core.hp == 0.0

    def test_apply_damage_after_destroyed(self):
        """破壊後にさらにダメージを与えても 0.0 を維持"""
        core = Core(team=0)
        core.apply_damage(float(CORE_HP))
        core.apply_damage(99_999)
        assert core.hp == 0.0


# ─────────────────────────────────────────
# destroyed プロパティ
# ─────────────────────────────────────────
class TestDestroyed:
    def test_false_when_full_hp(self):
        assert not Core(team=0).destroyed

    def test_false_when_one_hp(self):
        """HP が 1 でもまだ生存"""
        core = Core(team=0, hp=1.0)
        assert not core.destroyed

    def test_true_when_zero_hp(self):
        """HP = 0.0 で destroyed=True"""
        core = Core(team=0, hp=0.0)
        assert core.destroyed

    def test_true_after_exact_kill(self):
        core = Core(team=0)
        core.apply_damage(float(CORE_HP))
        assert core.destroyed

    def test_true_after_overkill(self):
        core = Core(team=0)
        core.apply_damage(float(CORE_HP) + 1)
        assert core.destroyed


# ─────────────────────────────────────────
# hp_pct プロパティ
# ─────────────────────────────────────────
class TestHpPct:
    def test_100_when_full(self):
        core = Core(team=0)
        assert core.hp_pct == pytest.approx(100.0)

    def test_50_when_half(self):
        core = Core(team=0, hp=float(CORE_HP) / 2)
        assert core.hp_pct == pytest.approx(50.0)

    def test_0_when_zero(self):
        core = Core(team=0, hp=0.0)
        assert core.hp_pct == pytest.approx(0.0)

    def test_proportional(self):
        """任意の HP に対して比率が正しい"""
        hp = float(CORE_HP) * 0.3
        core = Core(team=0, hp=hp)
        assert core.hp_pct == pytest.approx(30.0)


# ─────────────────────────────────────────
# CORE_DMG_PER_KILL 定数 / 160機撃破ルール
# ─────────────────────────────────────────
class TestKillDamageConstant:
    def test_kill_damage_is_core_hp_divided_by_160(self):
        """CORE_DMG_PER_KILL = CORE_HP / 160"""
        assert CORE_DMG_PER_KILL == pytest.approx(CORE_HP / 160)

    def test_kill_damage_approximate_value(self):
        """≈ 1666.67"""
        assert CORE_DMG_PER_KILL == pytest.approx(1_666.67, abs=0.01)

    def test_159_kills_does_not_destroy(self):
        """159機撃破ではコアが残る"""
        core = Core(team=0)
        for _ in range(159):
            core.apply_damage(CORE_DMG_PER_KILL)
        assert core.hp > 0
        assert not core.destroyed

    def test_160_kills_depletes_core(self):
        """160機撃破でコアHPがほぼ0になる（浮動小数点誤差を1HP以内で許容）"""
        core = Core(team=0)
        for _ in range(160):
            core.apply_damage(CORE_DMG_PER_KILL)
        # apply_damage は max(0, ...) でクランプするため 0.0 以下にはならない
        # 浮動小数点の累積誤差により厳密に 0 にならない場合を考慮
        assert core.hp == pytest.approx(0.0, abs=1.0)
