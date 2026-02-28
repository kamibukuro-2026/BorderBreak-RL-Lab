"""
catalog.py のユニットテスト（16件）

data/ ディレクトリに存在するファイル（weapons_all.json, rank_param.json,
sys_calc_constants.json, bland_data.json, parts_param_config.json）を使用する。
parts_normalized.json は存在しないが、Catalog はそれを graceful に扱う。
"""
import pytest
from pathlib import Path
from catalog import Catalog, LoadoutKeys, WeaponRef

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def catalog():
    return Catalog(data_dir=DATA_DIR)


# ------------------------------------------------------------------ #
#  初期化                                                              #
# ------------------------------------------------------------------ #

class TestCatalogInit:
    def test_loads_without_error(self, catalog):
        # クラッシュなく初期化できていることを確認
        assert catalog is not None

    def test_custom_data_dir(self):
        c = Catalog(data_dir=DATA_DIR)
        assert c is not None

    def test_nonexistent_dir_no_crash(self, tmp_path):
        # 存在しないディレクトリを渡しても例外にならない
        c = Catalog(data_dir=tmp_path / "no_such_dir")
        assert c is not None


# ------------------------------------------------------------------ #
#  parts（parts_normalized.json なし）                                 #
# ------------------------------------------------------------------ #

class TestCatalogPartsWithoutNormalizedFile:
    def test_list_parts_head_empty(self, catalog):
        # parts_normalized.json がないため空リストが返る
        result = catalog.list_parts("head")
        assert result == []

    def test_list_parts_invalid_category_empty(self, catalog):
        result = catalog.list_parts("invalid_cat")
        assert result == []

    def test_get_part_raises_key_error(self, catalog):
        with pytest.raises(KeyError):
            catalog.get_part("head", "a")

    def test_find_part_keys_by_name_empty(self, catalog):
        result = catalog.find_part_keys_by_name("head", "テストヘッド")
        assert result == []


# ------------------------------------------------------------------ #
#  weapons（weapons_all.json あり）                                    #
# ------------------------------------------------------------------ #

class TestCatalogWeapons:
    def test_list_weapon_datasets_sorted(self, catalog):
        datasets = catalog.list_weapon_datasets()
        assert isinstance(datasets, list)
        assert len(datasets) > 0
        assert datasets == sorted(datasets)

    def test_weapon_as_main_in_datasets(self, catalog):
        assert "WEAPON_AS_MAIN" in catalog.list_weapon_datasets()

    def test_list_weapons_returns_tuples(self, catalog):
        items = catalog.list_weapons("WEAPON_AS_MAIN")
        assert len(items) > 0
        for key, name in items:
            assert isinstance(key, str)
            assert isinstance(name, str)

    def test_get_weapon_returns_dict(self, catalog):
        # weapons_all.json に WEAPON_AS_EXTRA の最初のキー "a" が存在する
        w = catalog.get_weapon("WEAPON_AS_EXTRA", "a")
        assert isinstance(w, dict)
        assert "name" in w

    def test_get_weapon_not_found_raises(self, catalog):
        with pytest.raises(KeyError):
            catalog.get_weapon("WEAPON_AS_MAIN", "NONEXISTENT_KEY_XYZ")

    def test_get_weapon_invalid_dataset_raises(self, catalog):
        with pytest.raises(KeyError):
            catalog.get_weapon("NO_SUCH_DATASET", "a")

    def test_find_weapons_by_name_returns_weapon_refs(self, catalog):
        # weapons_all.json の WEAPON_AS_EXTRA "a" は "デュエルソード"
        refs = catalog.find_weapons_by_name("デュエルソード")
        assert isinstance(refs, list)
        if refs:
            for r in refs:
                assert isinstance(r, WeaponRef)
                assert isinstance(r.dataset, str)
                assert isinstance(r.key, str)

    def test_find_weapons_by_name_not_found(self, catalog):
        refs = catalog.find_weapons_by_name("存在しない武器名XYZ")
        assert refs == []


# ------------------------------------------------------------------ #
#  システムテーブルプロパティ                                           #
# ------------------------------------------------------------------ #

class TestCatalogSystemTables:
    def test_rank_param_has_armor(self, catalog):
        rp = catalog.rank_param
        assert isinstance(rp, dict)
        assert "armor" in rp

    def test_sys_consts_has_weight_penalty(self, catalog):
        sc = catalog.sys_consts
        assert isinstance(sc, dict)
        assert "WEIGHT_PENALTY" in sc

    def test_bland_is_dict(self, catalog):
        b = catalog.bland
        assert isinstance(b, dict)
        assert len(b) > 0

    def test_param_limits_has_area_transport(self, catalog):
        pl = catalog.param_limits
        assert isinstance(pl, dict)
        assert "areaTransport" in pl
