import pytest
from typing import List, Any

from hydra._internal.config_repository import ConfigRepository
from hydra._internal.config_search_path_impl import ConfigSearchPathImpl
from hydra.core import DefaultElement
from hydra.core.config_store import ConfigStore
from hydra.core.plugins import Plugins
from hydra.plugins.config_source import ConfigSource
from hydra.test_utils.test_utils import chdir_hydra_root
from omegaconf import OmegaConf

chdir_hydra_root()


def resolve_defaults_list(
    defaults: List[DefaultElement],
    repo: ConfigRepository,
) -> List[DefaultElement]:
    ret = []
    for d in defaults:
        c = repo.load_config(
            f"{d.config_group}/{d.config_name}", is_primary_config=True
        )
        if c is not None:
            ret.append(c.defaults_list)
    return defaults


# registers config source plugins
Plugins.instance()


@pytest.mark.parametrize(  # type: ignore
    "defaults,expected",
    [
        pytest.param([{"a": "a1"}], [{"a": "a1"}], id="simple"),
    ],
)
def test_recursive_defaults(
    hydra_restore_singletons: Any, defaults: List[Any], expected: List[Any]
) -> None:
    defaults = OmegaConf.create(defaults)
    expected = OmegaConf.create(expected)

    cs = ConfigStore.instance()
    cs.store(group="a", name="a1", node={})

    csp = ConfigSearchPathImpl()
    repo = ConfigRepository(config_search_path=csp)
    defaults = ConfigSource._create_defaults_list(defaults)
    expected = ConfigSource._create_defaults_list(expected)

    assert resolve_defaults_list(defaults, repo) == expected
