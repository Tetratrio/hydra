import pytest
from typing import List, Any

from hydra._internal.config_repository import ConfigRepository
from hydra._internal.config_search_path_impl import ConfigSearchPathImpl
from hydra._internal.defaults_list import (
    expand_defaults_list,
    compute_element_defaults_list,
)
from hydra.core import DefaultElement
from hydra.core.plugins import Plugins
from hydra.errors import ConfigCompositionException
from hydra.test_utils.test_utils import chdir_hydra_root

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
