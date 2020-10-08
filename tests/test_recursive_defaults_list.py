import pytest
from typing import List, Any

from hydra._internal.config_repository import ConfigRepository
from hydra._internal.config_search_path_impl import ConfigSearchPathImpl
from hydra._internal.defaults_list import (
    expand_defaults_list,
    compute_element_defaults_list,
)
from hydra.core import DefaultElement
from hydra.core.override_parser.overrides_parser import OverridesParser
from hydra.core.override_parser.types import Override
from hydra.core.plugins import Plugins
from hydra.errors import ConfigCompositionException
from hydra.plugins.config_source import ConfigSource
from hydra.test_utils.test_utils import chdir_hydra_root
from omegaconf import OmegaConf

chdir_hydra_root()


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
    ],
)
def test_compute_element_defaults_list(
    hydra_restore_singletons: Any,
    element: DefaultElement,
    expected: List[DefaultElement],
) -> None:
    csp = ConfigSearchPathImpl()
    csp.append(provider="test", path="file://tests/test_data/recursive_defaults_lists")
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
    csp.append(provider="test", path="file://tests/test_data/recursive_defaults_lists")
    repo = ConfigRepository(config_search_path=csp)

    ret = expand_defaults_list(self_name=None, defaults=input_defaults, repo=repo)
    assert ret == expected


def convert_overrides_to_defaults(
    parsed_overrides: List[Override],
) -> List[DefaultElement]:
    ret = []
    for override in parsed_overrides:
        value = override.value()
        assert isinstance(value, str)
        if override.is_package_rename():
            default = DefaultElement(
                config_group=override.key_or_group,
                config_name=value,
                package=override.pkg1,
                package2=override.pkg2,
            )
        else:
            default = DefaultElement(
                config_group=override.key_or_group,
                config_name=value,
                package=override.get_subject_package(),
            )
        ret.append(default)
    return ret


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
        #         pytest.param(
        #             defaults_list,
        #             ["db@:dest=postgresql"],
        #             [
        #                 {"db@dest": "postgresql"},
        #                 {"db@src": "mysql"},
        #                 {"hydra/launcher": "basic"},
        #             ],
        #             id="change_both",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["db@src:dest=postgresql"],
        #             [{"db": "mysql"}, {"db@dest": "postgresql"}, {"hydra/launcher": "basic"}],
        #             id="change_both",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["db@XXX:dest=postgresql"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape(
        #                     "Could not rename package. No match for 'db@XXX' in the defaults list."
        #                 ),
        #             ),
        #             id="change_both_invalid_package",
        #         ),
        #         # adding item
        #         pytest.param([], ["+db=mysql"], [{"db": "mysql"}], id="adding_item"),
        #         pytest.param(
        #             defaults_list,
        #             ["+db@backup=mysql"],
        #             [
        #                 {"db": "mysql"},
        #                 {"db@src": "mysql"},
        #                 {"hydra/launcher": "basic"},
        #                 {"db@backup": "mysql"},
        #             ],
        #             id="adding_item_at_package",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["+db=mysql"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape(
        #                     "Could not add 'db=mysql'. 'db' is already in the defaults list."
        #                 ),
        #             ),
        #             id="adding_duplicate_item",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["+db@src:foo=mysql"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape(
        #                     "Add syntax does not support package rename, remove + prefix"
        #                 ),
        #             ),
        #             id="add_rename_error",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["+db@src=mysql"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape(
        #                     "Could not add 'db@src=mysql'. 'db@src' is already in the defaults list."
        #                 ),
        #             ),
        #             id="adding_duplicate_item",
        #         ),
        #         pytest.param(
        #             [],
        #             ["db=mysql"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape(
        #                     "Could not override 'db'. No match in the defaults list."
        #                     "\nTo append to your default list use +db=mysql"
        #                 ),
        #             ),
        #             id="adding_without_plus",
        #         ),
        #         # deleting item
        #         pytest.param(
        #             [],
        #             ["~db=mysql"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape(
        #                     "Could not delete. No match for 'db' in the defaults list."
        #                 ),
        #             ),
        #             id="delete_no_match",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["~db"],
        #             [{"db@src": "mysql"}, {"hydra/launcher": "basic"}],
        #             id="delete",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["~db=mysql"],
        #             [{"db@src": "mysql"}, {"hydra/launcher": "basic"}],
        #             id="delete",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["~db=postgresql"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape(
        #                     "Could not delete. No match for 'db=postgresql' in the defaults list."
        #                 ),
        #             ),
        #             id="delete_mismatch_value",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["~db@src"],
        #             [{"db": "mysql"}, {"hydra/launcher": "basic"}],
        #             id="delete",
        #         ),
        #         # syntax error
        #         pytest.param(
        #             defaults_list,
        #             ["db"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape(
        #                     "Error parsing override 'db'\nmissing EQUAL at '<EOF>'"
        #                 ),
        #             ),
        #             id="syntax_error",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["db=[a,b,c]"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape("Config group override value type cannot be a list"),
        #             ),
        #             id="syntax_error",
        #         ),
        #         pytest.param(
        #             defaults_list,
        #             ["db={a:1,b:2}"],
        #             pytest.raises(
        #                 HydraException,
        #                 match=re.escape("Config group override value type cannot be a dict"),
        #             ),
        #             id="syntax_error",
        #         ),
    ],
)
def test_apply_overrides_to_defaults(
    config_with_defaults: str,
    overrides: List[str],
    expected: List[DefaultElement],
) -> None:

    csp = ConfigSearchPathImpl()
    csp.append(provider="test", path="file://tests/test_data/recursive_defaults_lists")
    repo = ConfigRepository(config_search_path=csp)

    parser = OverridesParser.create()
    if isinstance(expected, list):
        parsed_overrides = parser.parse_overrides(overrides=overrides)
        overrides_as_defaults = convert_overrides_to_defaults(parsed_overrides)
        defaults = [
            DefaultElement(config_name=config_with_defaults),
        ]
        defaults.extend(overrides_as_defaults)
        ret = expand_defaults_list(self_name=None, defaults=defaults, repo=repo)
        assert ret == expected
    else:
        with expected:
            parsed_overrides = parser.parse_overrides(overrides=overrides)
            # ConfigLoaderImpl._apply_overrides_to_defaults(
            #     overrides=parsed_overrides, defaults=defaults
            # )
