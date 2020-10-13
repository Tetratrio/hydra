import pytest
import re
from typing import List, Any

from hydra._internal.config_repository import ConfigRepository
from hydra._internal.config_search_path_impl import ConfigSearchPathImpl
from hydra._internal.defaults_list import (
    expand_defaults_list,
    compute_element_defaults_list,
    convert_overrides_to_defaults,
)
from hydra.core import DefaultElement
from hydra.core.override_parser.overrides_parser import OverridesParser
from hydra.core.plugins import Plugins
from hydra.errors import ConfigCompositionException, OverrideParseException
from hydra.test_utils.test_utils import chdir_hydra_root

chdir_hydra_root()

# TODO: should error indicate the default is coming from? (overrides, specific file's defaults?)


# registers config source plugins
Plugins.instance()


@pytest.mark.parametrize(  # type: ignore
    "element,expected",
    [
        pytest.param(
            DefaultElement(config_name="no_defaults"),
            [
                DefaultElement(config_name="no_defaults"),
            ],
            id="no_defaults",
        ),
        pytest.param(
            DefaultElement(config_name="duplicate_self"),
            pytest.raises(
                ConfigCompositionException,
                match="Duplicate _self_ defined in duplicate_self",
            ),
            id="duplicate_self",
        ),
        pytest.param(
            DefaultElement(config_name="trailing_self"),
            [
                DefaultElement(config_name="no_defaults"),
                DefaultElement(config_name="trailing_self"),
            ],
            id="trailing_self",
        ),
        pytest.param(
            DefaultElement(config_name="implicit_leading_self"),
            [
                DefaultElement(config_name="implicit_leading_self"),
                DefaultElement(config_name="no_defaults"),
            ],
            id="implicit_leading_self",
        ),
        pytest.param(
            DefaultElement(config_name="explicit_leading_self"),
            [
                DefaultElement(config_name="explicit_leading_self"),
                DefaultElement(config_name="no_defaults"),
            ],
            id="explicit_leading_self",
        ),
        pytest.param(
            DefaultElement(config_name="a/a1"),
            [
                DefaultElement(config_name="a/a1"),
            ],
            id="primary_in_config_group_no_defaults",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a1"),
            [
                DefaultElement(config_group="a", config_name="a1"),
            ],
            id="primary_in_config_group_no_defaults",
        ),
        pytest.param(
            DefaultElement(config_name="a/global"),
            [
                DefaultElement(config_name="a/global"),
            ],
            id="a/global",
        ),
        pytest.param(
            DefaultElement(config_name="b/b1"),
            [
                DefaultElement(config_name="b/b1"),
            ],
            id="b/b1",
        ),
        pytest.param(
            DefaultElement(config_group="b", config_name="b1"),
            [
                DefaultElement(config_group="b", config_name="b1"),
            ],
            id="b/b1",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a2"),
            [
                DefaultElement(config_group="a", config_name="a2"),
                DefaultElement(config_group="b", config_name="b1"),
            ],
            id="a/a2",
        ),
        pytest.param(
            DefaultElement(config_name="recursive_item_explicit_self"),
            [
                DefaultElement(config_name="recursive_item_explicit_self"),
                DefaultElement(config_group="a", config_name="a2"),
                DefaultElement(config_group="b", config_name="b1"),
            ],
            id="recursive_item_explicit_self",
        ),
        pytest.param(
            DefaultElement(config_name="recursive_item_implicit_self"),
            [
                DefaultElement(config_name="recursive_item_implicit_self"),
                DefaultElement(config_group="a", config_name="a2"),
                DefaultElement(config_group="b", config_name="b1"),
            ],
            id="recursive_item_implicit_self",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a3"),
            [
                DefaultElement(config_group="a", config_name="a3"),
                DefaultElement(config_group="c", config_name="c2"),
                DefaultElement(config_group="b", config_name="b2"),
            ],
            id="multiple_item_definitions",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a4"),
            [
                DefaultElement(config_group="a", config_name="a4"),
                DefaultElement(config_group="b", config_name="b1", package="file_pkg"),
            ],
            id="a/a4_pkg_override_in_config",
        ),
        pytest.param(
            DefaultElement(config_group="b", config_name="b3"),
            [
                DefaultElement(config_group="b", config_name="b3"),
            ],
            id="b/b3",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a5"),
            [
                DefaultElement(config_group="a", config_name="a5"),
                DefaultElement(config_group="b", config_name="b3"),
                DefaultElement(config_group="b", config_name="b3", package="file_pkg"),
            ],
            id="a/a5",
        ),
        pytest.param(
            DefaultElement(config_group="b", config_name="base_from_a"),
            [
                DefaultElement(config_name="a/a1"),
                DefaultElement(config_group="b", config_name="base_from_a"),
            ],
            id="b/base_from_a",
        ),
        pytest.param(
            DefaultElement(config_group="b", config_name="base_from_b"),
            [
                DefaultElement(config_name="b/b1"),
                DefaultElement(config_group="b", config_name="base_from_b"),
            ],
            id="b/base_from_b",
        ),
        # rename
        pytest.param(
            DefaultElement(config_group="rename", config_name="r1"),
            [
                DefaultElement(config_group="rename", config_name="r1"),
                DefaultElement(config_group="b", package="pkg", config_name="b1"),
            ],
            id="rename_package_from_none",
        ),
        pytest.param(
            DefaultElement(config_group="rename", config_name="r2"),
            [
                DefaultElement(config_group="rename", config_name="r2"),
                DefaultElement(config_group="b", package="pkg2", config_name="b1"),
            ],
            id="rename_package_from_something",
        ),
        pytest.param(
            DefaultElement(config_group="rename", config_name="r3"),
            [
                DefaultElement(config_group="rename", config_name="r3"),
                DefaultElement(config_group="b", package="pkg", config_name="b4"),
            ],
            id="rename_package_from_none_and_change_option",
        ),
        pytest.param(
            DefaultElement(config_group="rename", config_name="r4"),
            [
                DefaultElement(config_group="rename", config_name="r4"),
                DefaultElement(config_group="b", package="pkg2", config_name="b4"),
            ],
            id="rename_package_and_change_option",
        ),
        pytest.param(
            DefaultElement(config_group="rename", config_name="r5"),
            [
                DefaultElement(config_group="rename", config_name="r5"),
                DefaultElement(config_name="rename/r4"),
                DefaultElement(config_group="b", package="pkg2", config_name="b4"),
                DefaultElement(config_group="a", config_name="a1"),
            ],
            id="rename_package_and_change_option",
        ),
        # delete
        pytest.param(
            DefaultElement(config_group="delete", config_name="d1"),
            [
                DefaultElement(config_group="delete", config_name="d1"),
                DefaultElement(config_group="b", config_name="b1", is_deleted=True),
            ],
            id="delete_with_null",
        ),
        pytest.param(
            DefaultElement(config_group="delete", config_name="d2"),
            [
                DefaultElement(config_group="delete", config_name="d2"),
                DefaultElement(config_group="b", config_name="b1", is_deleted=True),
            ],
            id="delete_with_tilda",
        ),
        pytest.param(
            DefaultElement(config_group="delete", config_name="d3"),
            [
                DefaultElement(config_group="delete", config_name="d3"),
                DefaultElement(config_group="b", config_name="b1", is_deleted=True),
            ],
            id="delete_with_tilda_k=v",
        ),
        pytest.param(
            DefaultElement(config_group="delete", config_name="d4"),
            [
                DefaultElement(config_group="delete", config_name="d4"),
                DefaultElement(config_group="b", config_name="b1"),
            ],
            id="file_delete_not_mandatory",
        ),
        pytest.param(
            DefaultElement(config_group="delete", config_name="d5"),
            [
                DefaultElement(config_group="delete", config_name="d5"),
                DefaultElement(config_group="b", config_name="b1"),
            ],
            id="file_delete_not_mandatory",
        ),
        pytest.param(
            DefaultElement(config_group="delete", config_name="d7"),
            [
                DefaultElement(config_group="delete", config_name="d7"),
                DefaultElement(config_group="b", config_name="b1"),
            ],
            id="file_delete_not_mandatory",
        ),
        pytest.param(
            DefaultElement(config_group="delete", config_name="d6"),
            [
                DefaultElement(config_group="delete", config_name="d6"),
                DefaultElement(config_group="b", config_name="b1", is_deleted=True),
                DefaultElement(config_group="b", config_name="b3"),
            ],
            id="specific_delete",
        ),
        pytest.param(
            DefaultElement(config_group="delete", config_name="d8"),
            [
                DefaultElement(config_group="delete", config_name="d8"),
                DefaultElement(config_group="b", config_name="b2"),
                DefaultElement(config_group="c", config_name="c2", is_deleted=True),
            ],
            id="delete_from_included",
        ),
        pytest.param(
            DefaultElement(config_group="delete", config_name="d9"),
            [
                DefaultElement(config_group="delete", config_name="d9"),
            ],
            id="file_delete_not_mandatory",
        ),
        # interpolation
        pytest.param(
            DefaultElement(config_group="interpolation", config_name="i1"),
            [
                DefaultElement(config_group="interpolation", config_name="i1"),
                DefaultElement(config_group="a", config_name="a1"),
                DefaultElement(config_group="b", config_name="b1"),
                DefaultElement(config_group="a_b", config_name="a1_b1"),
            ],
            id="interpolation",
        ),
        pytest.param(
            DefaultElement(
                config_group="interpolation", config_name="i2_legacy_with_self"
            ),
            [
                DefaultElement(
                    config_group="interpolation", config_name="i2_legacy_with_self"
                ),
                DefaultElement(config_group="a", config_name="a1"),
                DefaultElement(config_group="b", config_name="b1"),
                DefaultElement(config_group="a_b", config_name="a1_b1"),
            ],
            id="interpolation",
        ),
        pytest.param(
            DefaultElement(
                config_group="interpolation", config_name="i3_legacy_without_self"
            ),
            [
                DefaultElement(
                    config_group="interpolation", config_name="i3_legacy_without_self"
                ),
                DefaultElement(config_group="a", config_name="a1"),
                DefaultElement(config_group="b", config_name="b1"),
                DefaultElement(config_group="a_b", config_name="a1_b1"),
            ],
            id="interpolation",
        ),
    ],
)
def test_compute_element_defaults_list(
    hydra_restore_singletons: Any,
    element: DefaultElement,
    expected: Any,
) -> None:
    csp = ConfigSearchPathImpl()
    csp.append(provider="test", path="file://tests/test_data/new_defaults_lists")
    repo = ConfigRepository(config_search_path=csp)

    if isinstance(expected, list):
        ret = compute_element_defaults_list(element=element, repo=repo)
        assert ret == expected
    else:
        with expected:
            compute_element_defaults_list(element=element, repo=repo)


@pytest.mark.parametrize(  # type: ignore
    "input_defaults,expected",
    [
        pytest.param(
            [
                DefaultElement(config_group="a", config_name="a1"),
                DefaultElement(config_group="a", config_name="a6"),
            ],
            [
                DefaultElement(config_group="a", config_name="a6"),
            ],
            id="simple",
        ),
        pytest.param(
            [
                DefaultElement(config_group="a", config_name="a2"),
                DefaultElement(config_group="a", config_name="a6"),
            ],
            [
                DefaultElement(config_group="a", config_name="a6"),
            ],
            id="simple",
        ),
        pytest.param(
            [
                DefaultElement(config_group="a", config_name="a5"),
                DefaultElement(config_group="b", config_name="b1"),
                DefaultElement(config_group="b", package="file_pkg", config_name="b1"),
            ],
            [
                DefaultElement(config_group="a", config_name="a5"),
                DefaultElement(config_group="b", config_name="b1"),
                DefaultElement(config_group="b", config_name="b1", package="file_pkg"),
            ],
            id="a/a5",
        ),
    ],
)
def test_expand_defaults_list(
    hydra_restore_singletons: Any,
    input_defaults: List[DefaultElement],
    expected: List[DefaultElement],
) -> None:
    csp = ConfigSearchPathImpl()
    csp.append(provider="test", path="file://tests/test_data/new_defaults_lists")
    repo = ConfigRepository(config_search_path=csp)

    ret = expand_defaults_list(self_name=None, defaults=input_defaults, repo=repo)
    assert ret == expected


@pytest.mark.parametrize(  # type: ignore
    "config_with_defaults,overrides,expected",
    [
        # change item
        pytest.param(
            "test_overrides",
            ["a=a6"],
            [
                DefaultElement(config_name="test_overrides"),
                DefaultElement(config_group="a", config_name="a6"),
                DefaultElement(config_group="a", package="pkg", config_name="a1"),
                DefaultElement(config_group="c", config_name="c1"),
            ],
            id="change_option",
        ),
        pytest.param(
            "test_overrides",
            ["a@:pkg2=a6"],
            [
                DefaultElement(config_name="test_overrides"),
                DefaultElement(config_group="a", package="pkg2", config_name="a6"),
                DefaultElement(config_group="a", package="pkg", config_name="a1"),
                DefaultElement(config_group="c", config_name="c1"),
            ],
            id="change_both",
        ),
        pytest.param(
            "test_overrides",
            ["a@pkg:pkg2=a6"],
            [
                DefaultElement(config_name="test_overrides"),
                DefaultElement(config_group="a", config_name="a1"),
                DefaultElement(config_group="a", package="pkg2", config_name="a6"),
                DefaultElement(config_group="c", config_name="c1"),
            ],
            id="change_both",
        ),
        pytest.param(
            "test_overrides",
            ["a@XXX:dest=a6"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not rename package. No match for 'a@XXX' in the defaults list"
                ),
            ),
            id="change_both_invalid_package",
        ),
        # adding item
        pytest.param(
            "no_defaults",
            ["+b=b1"],
            [
                DefaultElement(config_name="no_defaults"),
                DefaultElement(config_group="b", config_name="b1"),
            ],
            id="adding_item",
        ),
        pytest.param(
            "no_defaults",
            ["+b=b2"],
            [
                DefaultElement(config_name="no_defaults"),
                DefaultElement(config_group="b", config_name="b2"),
                DefaultElement(config_group="c", config_name="c2"),
            ],
            id="adding_item_recursive",
        ),
        pytest.param(
            "test_overrides",
            ["+b@pkg=b1"],
            [
                DefaultElement(config_name="test_overrides"),
                DefaultElement(config_group="a", config_name="a1"),
                DefaultElement(config_group="a", package="pkg", config_name="a1"),
                DefaultElement(config_group="c", config_name="c1"),
                DefaultElement(
                    config_group="b",
                    package="pkg",
                    config_name="b1",
                ),
            ],
            id="adding_item_at_package",
        ),
        pytest.param(
            "one_missing_item",
            ["+a=a1"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not add 'a=a1'. 'a' is already in the defaults list."
                ),
            ),
            id="adding_duplicate_item",
        ),
        pytest.param(
            "test_overrides",
            ["+a=a2"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not add 'a=a2'. 'a' is already in the defaults list."
                ),
            ),
            id="adding_duplicate_item",
        ),
        pytest.param(
            "test_overrides",
            ["+a=a6", "+c=c2"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not add 'c=c2'. 'c' is already in the defaults list."
                ),
            ),
            id="adding_duplicate_item_recursive",
        ),
        pytest.param(
            "test_overrides",
            ["+a@pkg:pkg2=a1"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Add syntax does not support package rename, remove + prefix"
                ),
            ),
            id="add_rename_error",
        ),
        pytest.param(
            "test_overrides",
            ["+a@pkg=a2"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not add 'a@pkg=a2'. 'a@pkg' is already in the defaults list."
                ),
            ),
            id="adding_duplicate_item@pkg",
        ),
        pytest.param(
            "no_defaults",
            ["c=c1"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not override 'c'. No match in the defaults list."
                    "\nTo append to your default list use +c=c1"
                ),
            ),
            id="adding_without_plus",
        ),
        # deleting item
        pytest.param(
            "no_defaults",
            ["~db=mysql"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not delete. No match for 'db=mysql' in the defaults list."
                ),
            ),
            id="delete_no_match",
        ),
        pytest.param(
            "no_defaults",
            ["~db"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not delete. No match for 'db' in the defaults list."
                ),
            ),
            id="delete_no_match",
        ),
        pytest.param(
            "no_defaults",
            ["~db=foo"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not delete. No match for 'db=foo' in the defaults list."
                ),
            ),
            id="delete_no_match",
        ),
        pytest.param(
            "test_overrides",
            ["~a"],
            [
                DefaultElement(config_name="test_overrides"),
                DefaultElement(config_group="a", config_name="a1", is_deleted=True),
                DefaultElement(config_group="a", package="pkg", config_name="a1"),
                DefaultElement(config_group="c", config_name="c1"),
            ],
            id="delete",
        ),
        pytest.param(
            "test_overrides",
            ["~a=a1"],
            [
                DefaultElement(config_name="test_overrides"),
                DefaultElement(config_group="a", config_name="a1", is_deleted=True),
                DefaultElement(config_group="a", package="pkg", config_name="a1"),
                DefaultElement(config_group="c", config_name="c1"),
            ],
            id="delete",
        ),
        pytest.param(
            "test_overrides",
            ["~a=zzz"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Could not delete. No match for 'a=zzz' in the defaults list."
                ),
            ),
            id="delete",
        ),
        pytest.param(
            "test_overrides",
            ["~a@pkg"],
            [
                DefaultElement(config_name="test_overrides"),
                DefaultElement(config_group="a", config_name="a1"),
                DefaultElement(
                    config_group="a", package="pkg", config_name="a1", is_deleted=True
                ),
                DefaultElement(config_group="c", config_name="c1"),
            ],
            id="delete",
        ),
        pytest.param(
            "test_overrides",
            ["a=foo", "~a"],
            [
                DefaultElement(config_name="test_overrides"),
                DefaultElement(config_group="a", config_name="a1", is_deleted=True),
                DefaultElement(config_group="a", package="pkg", config_name="a1"),
                DefaultElement(config_group="c", config_name="c1"),
                DefaultElement(
                    config_group="a",
                    config_name="foo",
                    is_deleted=True,
                    from_override=True,
                ),
            ],
            id="delete_after_set_from_overrides",
        ),
        # syntax error
        pytest.param(
            "test_overrides",
            ["db"],
            pytest.raises(
                OverrideParseException,
                match=re.escape(
                    "Error parsing override 'db'\nmissing EQUAL at '<EOF>'"
                ),
            ),
            id="syntax_error",
        ),
        pytest.param(
            "test_overrides",
            ["db=[a,b,c]"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Defaults list supported delete syntax is in the form "
                    "~group and ~group=value, where value is a group name (string)"
                ),
            ),
            id="syntax_error",
        ),
        pytest.param(
            "test_overrides",
            ["db={a:1,b:2}"],
            pytest.raises(
                ConfigCompositionException,
                match=re.escape(
                    "Defaults list supported delete syntax is in the form "
                    "~group and ~group=value, where value is a group name (string)"
                ),
            ),
            id="syntax_error",
        ),
    ],
)
def test_apply_overrides_to_defaults(
    config_with_defaults: str,
    overrides: List[str],
    expected: Any,
) -> None:
    assert isinstance(config_with_defaults, str)

    csp = ConfigSearchPathImpl()
    csp.append(provider="test", path="file://tests/test_data/new_defaults_lists")
    repo = ConfigRepository(config_search_path=csp)

    def create_defaults() -> Any:
        parser = OverridesParser.create()
        parsed_overrides = parser.parse_overrides(overrides=overrides)
        overrides_as_defaults = convert_overrides_to_defaults(parsed_overrides)
        ret = [
            DefaultElement(config_name=config_with_defaults),
        ]
        ret.extend(overrides_as_defaults)
        return ret

    if isinstance(expected, list):
        defaults = create_defaults()
        ret = expand_defaults_list(self_name=None, defaults=defaults, repo=repo)
        assert ret == expected
    else:
        with expected:
            defaults = create_defaults()
            expand_defaults_list(self_name=None, defaults=defaults, repo=repo)
