import pytest
from typing import List, Any

from hydra._internal.config_repository import ConfigRepository
from hydra._internal.config_search_path_impl import ConfigSearchPathImpl
from hydra.core import DefaultElement
from hydra.core.config_store import ConfigStore
from hydra.core.plugins import Plugins
from hydra.errors import ConfigCompositionException
from hydra.plugins.config_source import ConfigSource
from hydra.test_utils.test_utils import chdir_hydra_root
from omegaconf import OmegaConf

chdir_hydra_root()


def resolve_defaults_list(
    config_path: str,
    defaults: List[DefaultElement],
    repo: ConfigRepository,
) -> List[DefaultElement]:
    # TODO: if we have two passes, be sure to cache the loaded configs
    has_self = False
    for d in defaults:
        if d.config_name == "_self_":
            if has_self is True:
                raise ConfigCompositionException(
                    f"Duplicate _self_ defined in {config_path}"
                )
            has_self = True
            assert d.config_group is None
            d.config_name = config_path

    if not has_self:
        # TODO: should inherit package of config
        defaults.append(DefaultElement(config_name=config_path))

    # ret = []
    for d in defaults:
        pass
        # if d.config_group is not None:
        #     path = f"{d.config_group}/{d.config_name}"
        # else:
        #     path = d.config_name
        # c = repo.load_config(path, is_primary_config=True)
        # if c is None:
        #     raise IOError(f"Can't load {path}")
        # if len(c.defaults_list) > 0:
        #     # merge?
        #     ret.append(c.defaults_list)
    return defaults


# registers config source plugins
Plugins.instance()


@pytest.mark.parametrize(  # type: ignore
    "defaults,expected",
    [
        pytest.param(
            ["no_defaults"],
            [
                DefaultElement(config_name="no_defaults"),
                DefaultElement(config_name="test_config"),
            ],
            id="no_defaults",
        ),
        pytest.param(
            ["_self_", "foo", "_self_"],
            pytest.raises(
                ConfigCompositionException,
                match="Duplicate _self_ defined in test_config",
            ),
            id="duplicate_self",
        ),
        pytest.param(
            ["no_defaults", "_self_"],
            [
                DefaultElement(config_name="no_defaults"),
                DefaultElement(config_name="test_config"),
            ],
            id="explicit_trailing_self",
        ),
        pytest.param(
            ["_self_", "no_defaults"],
            [
                DefaultElement(config_name="test_config"),
                DefaultElement(config_name="no_defaults"),
            ],
            id="explicit_leading_self",
        ),
        # pytest.param(
        #     [{"a": "a1"}],
        #     [{"a": "a1"}],
        #     id="simple",
        # ),
    ],
)
def test_recursive_defaults(
    hydra_restore_singletons: Any, defaults: List[Any], expected: List[Any]
) -> None:
    cs = ConfigStore.instance()
    cs.store(group="a", name="a1", node={})

    csp = ConfigSearchPathImpl()
    csp.append(provider="test", path="file://tests/test_data/recursive_defaults_lists")
    repo = ConfigRepository(config_search_path=csp)

    defaults = OmegaConf.create(defaults)
    defaults = ConfigSource._create_defaults_list(defaults)

    if isinstance(expected, list):
        ret = resolve_defaults_list(
            config_path="test_config", defaults=defaults, repo=repo
        )
        assert ret == expected
    else:
        with expected:
            resolve_defaults_list(
                config_path="test_config", defaults=defaults, repo=repo
            )
