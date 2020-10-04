from dataclasses import dataclass

import pytest
from typing import List, Any, Optional

from hydra._internal.config_loader_impl import DefaultElement
from hydra._internal.config_repository import ConfigRepository
from hydra._internal.config_search_path_impl import ConfigSearchPathImpl
from hydra.core.config_store import ConfigStore
from hydra.core.plugins import Plugins
from hydra.test_utils.test_utils import chdir_hydra_root

chdir_hydra_root()


def resolve_defaults_list(
    defaults: List[DefaultElement],
    repo: ConfigRepository,
) -> List[DefaultElement]:
    ret = []
    for d in defaults:
        repo.load_config(f"{d.config_group}/{d.config_name}")
    return defaults


def create_defaults(defaults: List) -> List[DefaultElement]:
    assert isinstance(defaults, list)
    d = []
    for default in defaults:
        if isinstance(defaults, str):
            element = DefaultElement(config_name=default)
        elif isinstance(default, dict):
            assert len(default) == 1
            group, value = default.popitem()
            assert isinstance(group, str)
            assert isinstance(value, str)
            element = DefaultElement(config_group=group, config_name=value)
        else:
            assert False
        d.append(element)
    return d


# registers config source plugins
Plugins.instance()


@pytest.mark.parametrize(
    "defaults,expected",
    [
        pytest.param([{"a": "a1"}], [{"a": "a1"}], id="simple"),
    ],
)
def test_recursive_defaults(
    hydra_restore_singletons: Any, defaults: List[Any], expected: List[Any]
) -> None:
    cs = ConfigStore.instance()
    cs.store(group="a", name="a1", node={})

    csp = ConfigSearchPathImpl()
    repo = ConfigRepository(config_search_path=csp)
    defaults = create_defaults(defaults)
    expected = create_defaults(expected)

    assert resolve_defaults_list(defaults, repo) == expected
