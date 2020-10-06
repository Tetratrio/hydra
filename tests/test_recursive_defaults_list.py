import copy

import pytest
from typing import List, Any

from hydra._internal.config_repository import ConfigRepository
from hydra._internal.config_search_path_impl import ConfigSearchPathImpl
from hydra.core import DefaultElement
from hydra.core.plugins import Plugins
from hydra.errors import ConfigCompositionException
from hydra.test_utils.test_utils import chdir_hydra_root

chdir_hydra_root()


def compute_element_defaults_list(
    element: DefaultElement,
    repo: ConfigRepository,
) -> List[DefaultElement]:
    # TODO: Should loaded configs be to cached in the repo to avoid loading more than once?
    has_self = False

    loaded = repo.load_config(
        config_path=element.config_path(), is_primary_config=False
    )
    if loaded is None:
        # TODO : add testing for this error (there should already be a similar error)
        raise ConfigCompositionException(f"Could not load {element.config_path()}")

    defaults = loaded.defaults_list

    if element.package is None:
        loaded_pacakge = loaded.header["package"]
        element_package = loaded_pacakge if loaded_pacakge != "" else None
    else:
        element_package = element.package

    for d in defaults:
        if d.config_name == "_self_":
            if has_self is True:
                raise ConfigCompositionException(
                    f"Duplicate _self_ defined in {element.config_path()}"
                )
            has_self = True
            assert d.config_group is None
            d.config_group = element.config_group
            d.package = element_package

    if not has_self:
        me = DefaultElement(
            config_group=element.config_group,
            config_name="_self_",
            package=element_package,
        )
        defaults.insert(0, me)

    ret = []
    for d in defaults:
        if d.config_name == "_self_":
            d = copy.deepcopy(d)
            d.config_name = element.config_name
            ret.append(d)
        else:
            item_defaults = compute_element_defaults_list(element=d, repo=repo)
            ret.extend(item_defaults)

    # list order is determined by first instance from that config group
    # selected config group is determined by the last override
    group_to_choice = {}
    for idx, d in enumerate(reversed(ret)):
        if d.config_group is not None:
            if d.config_group not in group_to_choice:
                group_to_choice[d.config_group] = d.config_name

    for d in ret:
        if d.config_group is not None:
            d.config_name = group_to_choice[d.config_group]

    deduped = []
    seen_groups = set()
    for d in ret:
        if d.config_group is not None:
            fqgn = d.fully_qualified_group_name()
            if fqgn not in seen_groups:
                seen_groups.add(fqgn)
                deduped.append(d)
        else:
            deduped.append(d)

    return deduped


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
                DefaultElement(config_name="a/a1", package="a"),
            ],
            id="primary_in_config_group_no_defaults",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a1"),
            [
                DefaultElement(config_group="a", config_name="a1", package="a"),
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
                DefaultElement(config_name="b/b1", package="b"),
            ],
            id="b/b1",
        ),
        pytest.param(
            DefaultElement(config_group="b", config_name="b1"),
            [
                DefaultElement(config_group="b", config_name="b1", package="b"),
            ],
            id="b/b1",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a2"),
            [
                DefaultElement(config_group="a", config_name="a2", package="a"),
                DefaultElement(config_group="b", config_name="b1", package="b"),
            ],
            id="a/a2",
        ),
        pytest.param(
            DefaultElement(config_name="recursive_item_explicit_self"),
            [
                DefaultElement(config_name="recursive_item_explicit_self"),
                DefaultElement(config_group="a", config_name="a2", package="a"),
                DefaultElement(config_group="b", config_name="b1", package="b"),
            ],
            id="recursive_item_explicit_self",
        ),
        pytest.param(
            DefaultElement(config_name="recursive_item_implicit_self"),
            [
                DefaultElement(config_name="recursive_item_implicit_self"),
                DefaultElement(config_group="a", config_name="a2", package="a"),
                DefaultElement(config_group="b", config_name="b1", package="b"),
            ],
            id="recursive_item_implicit_self",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a3"),
            [
                DefaultElement(config_group="a", config_name="a3", package="a"),
                DefaultElement(config_group="c", config_name="c2", package="c"),
                DefaultElement(config_group="b", config_name="b2", package="b"),
            ],
            id="multiple_item_definitions",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a4"),
            [
                DefaultElement(config_group="a", config_name="a4", package="a"),
                DefaultElement(config_group="b", config_name="b1", package="pkg"),
            ],
            id="a/a4_pkg_override_in_config",
        ),
        pytest.param(
            DefaultElement(config_group="b", config_name="b3"),
            [
                DefaultElement(config_group="b", config_name="b3", package="foo"),
            ],
            id="b/b3",
        ),
        pytest.param(
            DefaultElement(config_group="a", config_name="a5"),
            [
                DefaultElement(config_group="a", config_name="a5", package="a"),
                DefaultElement(config_group="b", config_name="b3", package="foo"),
                DefaultElement(config_group="b", config_name="b3", package="xyz"),
            ],
            id="a/a5",
        ),
    ],
)
def test_recursive_defaults(
    hydra_restore_singletons: Any, element: DefaultElement, expected: List[Any]
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
