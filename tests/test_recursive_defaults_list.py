import copy

import pytest
from typing import List, Any, Optional, Dict

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
    group_to_choice = {}
    return _compute_element_defaults_list_impl(
        element=element,
        group_to_choice=group_to_choice,
        repo=repo,
    )


def expand_defaults_list(
    self_name: Optional[str],
    defaults: List[DefaultElement],
    repo: ConfigRepository,
) -> List[DefaultElement]:
    group_to_choice = {}
    for d in reversed(defaults):
        if d.config_group is not None:
            if d.fully_qualified_group_name() not in group_to_choice:
                group_to_choice[d.fully_qualified_group_name()] = d.config_name

    return _expand_defaults_list_impl(
        self_name=self_name,
        defaults=defaults,
        group_to_choice=group_to_choice,
        repo=repo,
    )


def _compute_element_defaults_list_impl(
    element: DefaultElement,
    group_to_choice: Dict[str, str],
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
        # TODO: should we really depend on the loaded package?
        loaded_package = loaded.header["package"]
        element_package = loaded_package if loaded_package != "" else None
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

    return _expand_defaults_list_impl(
        self_name=element.config_name,
        defaults=defaults,
        group_to_choice=group_to_choice,
        repo=repo,
    )


def _expand_defaults_list_impl(
    self_name: Optional[str],
    defaults: List[DefaultElement],
    group_to_choice: Dict[str, str],
    repo: ConfigRepository,
) -> List[DefaultElement]:

    # list order is determined by first instance from that config group
    # selected config group is determined by the last override

    ret = []
    for d in reversed(defaults):
        if d.config_name == "_self_":
            if self_name is None:
                raise ConfigCompositionException(
                    "self_name is not specified adn defaults list contains a _self_ item"
                )
            d = copy.deepcopy(d)
            # override self_name
            if d.fully_qualified_group_name() in group_to_choice:
                d.config_name = group_to_choice[d.fully_qualified_group_name()]
            else:
                d.config_name = self_name
            added_sublist = [d]
        else:
            if d.fully_qualified_group_name() in group_to_choice:
                d.config_name = group_to_choice[d.fully_qualified_group_name()]
            item_defaults = _compute_element_defaults_list_impl(
                element=d,
                group_to_choice=group_to_choice,
                repo=repo,
            )
            added_sublist = item_defaults

        ret.append(added_sublist)

        for dd in reversed(added_sublist):
            if dd.config_group is not None:
                fqgn = dd.fully_qualified_group_name()
                if fqgn not in group_to_choice:
                    group_to_choice[fqgn] = dd.config_name

    ret.reverse()
    ret = [item for sublist in ret for item in sublist]

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
                DefaultElement(config_group="a", config_name="a6", package="a"),
            ],
            id="simple",
        ),
        pytest.param(
            [
                DefaultElement(config_group="a", config_name="a2"),
                DefaultElement(config_group="a", config_name="a6"),
            ],
            [
                DefaultElement(config_group="a", config_name="a6", package="a"),
            ],
            id="simple",
        ),
        # pytest.param(
        #     [
        #         DefaultElement(config_group="a", config_name="a5"),
        #         DefaultElement(config_group="b", config_name="b1"),
        #     ],
        #     [
        #         DefaultElement(config_group="a", config_name="a5", package="a"),
        #         DefaultElement(config_group="b", config_name="b1", package="foo"),
        #         DefaultElement(config_group="b", config_name="b3", package="xyz"),
        #     ],
        #     id="a/a5",
        # ),
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
