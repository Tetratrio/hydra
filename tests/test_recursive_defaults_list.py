import pytest
from typing import List, Any

from hydra._internal.config_repository import ConfigRepository
from hydra._internal.config_search_path_impl import ConfigSearchPathImpl
from hydra.core import DefaultElement
from hydra.core.plugins import Plugins
from hydra.errors import ConfigCompositionException
from hydra.test_utils.test_utils import chdir_hydra_root

chdir_hydra_root()


def compute_defaults_list(
    config_path: str,
    repo: ConfigRepository,
) -> List[DefaultElement]:
    # TODO: if we have two passes, be sure to cache the loaded configs
    has_self = False

    loaded = repo.load_config(config_path=config_path, is_primary_config=False)
    defaults = loaded.defaults_list

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
        package = loaded.header["package"] if loaded.header["package"] != "" else None
        defaults.append(DefaultElement(config_name=config_path, package=package))

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
    "config_path,expected",
    [
        pytest.param(
            "no_defaults",
            [
                DefaultElement(config_name="no_defaults"),
            ],
            id="no_defaults",
        ),
        pytest.param(
            "duplicate_self",
            pytest.raises(
                ConfigCompositionException,
                match="Duplicate _self_ defined in duplicate_self",
            ),
            id="duplicate_self",
        ),
        pytest.param(
            "explicit_trailing_self",
            [
                DefaultElement(config_name="no_defaults"),
                DefaultElement(config_name="explicit_trailing_self"),
            ],
            id="explicit_trailing_self",
        ),
        pytest.param(
            "implicit_trailing_self",
            [
                DefaultElement(config_name="no_defaults"),
                DefaultElement(config_name="implicit_trailing_self"),
            ],
            id="implicit_trailing_self",
        ),
        pytest.param(
            "leading_self",
            [
                DefaultElement(config_name="leading_self"),
                DefaultElement(config_name="no_defaults"),
            ],
            id="leading_self",
        ),
        pytest.param(
            "a/a1",
            [
                DefaultElement(config_name="a/a1", package="a"),
            ],
            id="primary_in_config_group_no_defaults",
        ),
        pytest.param(
            "a/global",
            [
                DefaultElement(config_name="a/global"),
            ],
            id="primary_in_config_group_global__no_defaults",
        ),
    ],
)
def test_recursive_defaults(
    hydra_restore_singletons: Any, config_path: str, expected: List[Any]
) -> None:
    csp = ConfigSearchPathImpl()
    csp.append(provider="test", path="file://tests/test_data/recursive_defaults_lists")
    repo = ConfigRepository(config_search_path=csp)

    # defaults = OmegaConf.create(defaults)
    # defaults = ConfigSource._create_defaults_list(defaults)

    if isinstance(expected, list):
        ret = compute_defaults_list(config_path=config_path, repo=repo)
        assert ret == expected
    else:
        with expected:
            compute_defaults_list(config_path=config_path, repo=repo)
