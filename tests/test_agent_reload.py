"""
tests/test_agent_reload.py
Agent のリロードパラメータ状態変数テスト

テスト対象:
  - clip / reload_steps / ammo_in_clip / reload_timer の初期値が正しい
  - clip=0（デフォルト）時は後方互換（無限弾）
"""
import pytest
from simulation import Agent


# ─────────────────────────────────────────
# デフォルト値テスト
# ─────────────────────────────────────────
class TestAgentReloadDefaults:

    def test_clip_default_zero(self):
        """clip のデフォルトは 0（リロードなし・無限弾）"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.clip == 0

    def test_reload_steps_default_zero(self):
        """reload_steps のデフォルトは 0"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.reload_steps == 0

    def test_ammo_in_clip_initialized_to_clip(self):
        """clip=30 → ammo_in_clip=30 で初期化される"""
        a = Agent(agent_id=1, x=0, y=0, team=0, clip=30)
        assert a.ammo_in_clip == 30

    def test_ammo_in_clip_zero_when_clip_zero(self):
        """clip=0 → ammo_in_clip=0 で初期化される"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.ammo_in_clip == 0

    def test_reload_timer_default_zero(self):
        """reload_timer のデフォルトは 0（射撃可能状態）"""
        a = Agent(agent_id=1, x=0, y=0, team=0)
        assert a.reload_timer == 0


# ─────────────────────────────────────────
# kwarg 設定時の初期値
# ─────────────────────────────────────────
class TestAgentReloadCustom:

    def test_clip_set_to_custom_value(self):
        """clip=10 を kwarg で設定できる"""
        a = Agent(agent_id=1, x=0, y=0, team=0, clip=10)
        assert a.clip == 10

    def test_reload_steps_set_to_custom_value(self):
        """reload_steps=5 を kwarg で設定できる"""
        a = Agent(agent_id=1, x=0, y=0, team=0, reload_steps=5)
        assert a.reload_steps == 5

    def test_ammo_in_clip_equals_clip_on_init(self):
        """初期化後 ammo_in_clip == clip（満タン）"""
        a = Agent(agent_id=1, x=0, y=0, team=0, clip=20, reload_steps=3)
        assert a.ammo_in_clip == a.clip
