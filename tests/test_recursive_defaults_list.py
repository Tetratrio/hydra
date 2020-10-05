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


def compute_defaults_list(
    config_path: str,
    repo: ConfigRepository,
) -> List[DefaultElement]:
    # TODO: Should loaded configs be to cached in the repo to avoid loading more than once?
    has_self = False

    loaded = repo.load_config(config_path=config_path, is_primary_config=False)
    if loaded is None:
        # TODO : add testing for this error (there should already be a similar error)
        raise ConfigCompositionException(f"Could not load {config_path}")

    defaults = loaded.defaults_list

    for d in defaults:
        if d.config_name == "_self_":
            if has_self is True:
                raise ConfigCompositionException(
                    f"Duplicate _self_ defined in {config_path}"
                )
            has_self = True
            assert d.config_group is None

    if not has_self:
        defaults.insert(0, DefaultElement(config_name="_self_"))

    ret = []
    for d in defaults:
        if d.config_name != "_self_":
            if d.config_group is not None:
                path = f"{d.config_group}/{d.config_name}"
            else:
                path = d.config_name
            item_defaults = compute_defaults_list(config_path=path, repo=repo)
            ret.extend(item_defaults)
        else:
            d = copy.deepcopy(d)
            lpackage = loaded.header["package"]
            package = lpackage if lpackage != "" else None
            d.config_name = config_path
            d.package = package
            ret.append(d)

    return ret


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
            "trailing_self",
            [
                DefaultElement(config_name="no_defaults"),
                DefaultElement(config_name="trailing_self"),
            ],
            id="trailing_self",
        ),
        pytest.param(
            "implicit_leading_self",
            [
                DefaultElement(config_name="implicit_leading_self"),
                DefaultElement(config_name="no_defaults"),
            ],
            id="implicit_leading_self",
        ),
        pytest.param(
            "explicit_leading_self",
            [
                DefaultElement(config_name="explicit_leading_self"),
                DefaultElement(config_name="no_defaults"),
            ],
            id="explicit_leading_self",
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
            id="a/global",
        ),
        pytest.param(
            "b/b1",
            [
                DefaultElement(config_name="b/b1", package="b"),
            ],
            id="b/b1",
        ),
        pytest.param(
            "a/a2",
            [
                DefaultElement(config_name="a/a2", package="a"),
                DefaultElement(config_name="b/b1", package="b"),
            ],
            id="a/a2",
        ),
        pytest.param(
            "recursive_item_explicit_self",
            [
                DefaultElement(config_name="recursive_item_explicit_self"),
                DefaultElement(config_name="a/a2", package="a"),
                DefaultElement(config_name="b/b1", package="b"),
            ],
            id="recursive_item_explicit_self",
        ),
        pytest.param(
            "recursive_item_implicit_self",
            [
                DefaultElement(config_name="recursive_item_implicit_self"),
                DefaultElement(config_name="a/a2", package="a"),
                DefaultElement(config_name="b/b1", package="b"),
            ],
            id="recursive_item_implicit_self",
        ),
    ],
)
def test_recursive_defaults(
    hydra_restore_singletons: Any, config_path: str, expected: List[Any]
) -> None:
    csp = ConfigSearchPathImpl()
    csp.append(provider="test", path="file://tests/test_data/recursive_defaults_lists")
    repo = ConfigRepository(config_search_path=csp)

    if isinstance(expected, list):
        ret = compute_defaults_list(config_path=config_path, repo=repo)
        assert ret == expected
    else:
        with expected:
            compute_defaults_list(config_path=config_path, repo=repo)
