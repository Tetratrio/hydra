import copy
from dataclasses import dataclass
from itertools import filterfalse
from typing import Dict, List, Optional, Union

from omegaconf import DictConfig, OmegaConf

from hydra._internal.config_repository import ConfigRepository
from hydra.core import DefaultElement
from hydra.core.override_parser.types import Override
from hydra.errors import ConfigCompositionException, MissingConfigException


@dataclass(frozen=True, eq=True)
class DeleteKey:
    fqgn: str
    config_name: Optional[str]
    must_delete: bool

    def __repr__(self) -> str:
        if self.config_name is None:
            return self.fqgn
        else:
            return f"{self.fqgn}={self.config_name}"


@dataclass
class DefaultsList:
    original: List[DefaultElement]
    effective: List[DefaultElement]


def compute_element_defaults_list(
    element: DefaultElement,
    repo: ConfigRepository,
) -> List[DefaultElement]:
    group_to_choice = OmegaConf.create({})
    delete_groups: Dict[DeleteKey, int] = {}
    ret = _compute_element_defaults_list_impl(
        element=element,
        group_to_choice=group_to_choice,
        delete_groups=delete_groups,
        repo=repo,
    )

    _post_process_deletes(ret, delete_groups)
    return ret


def _post_process_deletes(
    ret: List[DefaultElement],
    delete_groups: Dict[DeleteKey, int],
) -> None:
    # verify all deletions deleted something
    for g, c in delete_groups.items():
        if c == 0 and g.must_delete:
            raise ConfigCompositionException(
                f"Could not delete. No match for '{g}' in the defaults list."
            )

    # remove delete overrides
    ret[:] = filterfalse(lambda x: x.is_delete, ret)


def expand_defaults_list(
    defaults: List[DefaultElement],
    repo: ConfigRepository,
) -> List[DefaultElement]:
    return _expand_defaults_list(self_name=None, defaults=defaults, repo=repo)


def _expand_defaults_list(
    self_name: Optional[str],
    defaults: List[DefaultElement],
    repo: ConfigRepository,
) -> List[DefaultElement]:
    group_to_choice = OmegaConf.create({})
    delete_groups = {}
    for d in reversed(defaults):
        if d.is_delete:
            delete_key = DeleteKey(
                d.fully_qualified_group_name(),
                d.config_name if d.config_name != "_delete_" else None,
                must_delete=d.from_override,
            )
            delete_groups[delete_key] = 0
        else:
            if d.config_group is not None:
                if d.fully_qualified_group_name() not in group_to_choice:
                    group_to_choice[d.fully_qualified_group_name()] = d.config_name

    dl = DefaultsList(original=copy.deepcopy(defaults), effective=defaults)
    ret = _expand_defaults_list_impl(
        self_name=self_name,
        defaults_list=dl,
        group_to_choice=group_to_choice,
        delete_groups=delete_groups,
        repo=repo,
    )

    _post_process_deletes(ret, delete_groups)

    return ret


def _validate_self(element: DefaultElement, defaults: DefaultsList) -> None:
    # check that self is present only once
    has_self = False
    for d in defaults.effective:
        if d.config_name == "_self_":
            if has_self is True:
                raise ConfigCompositionException(
                    f"Duplicate _self_ defined in {element.config_path()}"
                )
            has_self = True
            assert d.config_group is None
            d.config_group = element.config_group
            d.package = element.package

    if not has_self:
        me = copy.deepcopy(element)
        me.config_name = "_self_"
        me.from_override = False
        defaults.effective.insert(0, me)


def _compute_element_defaults_list_impl(
    element: DefaultElement,
    group_to_choice: DictConfig,
    delete_groups: Dict[DeleteKey, int],
    repo: ConfigRepository,
) -> List[DefaultElement]:
    # TODO: Should loaded configs be to cached in the repo to avoid loading more than once?
    #  Ensure new approach does not cause the same config to be loaded more than once.

    deleted = delete_if_matching(delete_groups, element)
    if deleted:
        return []

    loaded = repo.load_config(
        config_path=element.config_path(),
        is_primary_config=element.primary,
    )

    if loaded is None:
        if element.optional:
            element.set_skip_load("missing_optional_config")
            return [element]
        else:
            missing_config_error(
                repo=repo,
                config_name=element.config_path(),
                msg=f"Cannot find config : {element.config_path()}, check that it's in your config search path",
                with_search_path=True,
            )
    else:
        original = copy.deepcopy(loaded.defaults_list)
        effective = loaded.defaults_list

    defaults = DefaultsList(original=original, effective=effective)
    _validate_self(element, defaults)

    return _expand_defaults_list_impl(
        self_name=element.config_name,
        defaults_list=defaults,
        group_to_choice=group_to_choice,
        delete_groups=delete_groups,
        repo=repo,
    )


def _find_match_before(
    defaults: List[DefaultElement], like: DefaultElement
) -> Optional[DefaultElement]:
    fqgn = like.fully_qualified_group_name()
    for d2 in defaults:
        if d2 == like:
            break
        if d2.fully_qualified_group_name() == fqgn:
            return d2
    return None


def _verify_no_add_conflicts(defaults: List[DefaultElement]) -> None:
    for d in reversed(defaults):
        if d.from_override and not d.is_delete:
            fqgn = d.fully_qualified_group_name()
            match = _find_match_before(defaults, d)
            if d.is_add_only and match is not None:
                raise ConfigCompositionException(
                    f"Could not add '{fqgn}={d.config_name}'. '{fqgn}' is already in the defaults list."
                )
            if not d.is_add_only and match is None:
                msg = (
                    f"Could not override '{fqgn}'. No match in the defaults list."
                    f"\nTo append to your default list use +{fqgn}={d.config_name}"
                )
                raise ConfigCompositionException(msg)


def _process_renames(defaults: List[DefaultElement]) -> None:
    while True:
        last_rename_index = -1
        for idx, d in reversed(list(enumerate(defaults))):
            if d.is_package_rename():
                last_rename_index = idx
                break
        if last_rename_index != -1:
            rename = defaults.pop(last_rename_index)
            renamed = False
            for d in defaults:
                if is_matching(rename, d):
                    d.package = rename.get_subject_package()
                    renamed = True
            if not renamed:
                raise ConfigCompositionException(
                    f"Could not rename package. "
                    f"No match for '{rename.config_group}@{rename.package}' in the defaults list"
                )
        else:
            break


def delete_if_matching(delete_groups: Dict[DeleteKey, int], d: DefaultElement) -> bool:
    matched = False
    for delete in delete_groups:
        if delete.fqgn == d.fully_qualified_group_name():
            if delete.config_name is None:
                # fqdn only
                matched = True
                delete_groups[delete] += 1
                d.is_deleted = True
                d.set_skip_load("deleted_from_list")
            else:
                if delete.config_name == d.config_name:
                    matched = True
                    delete_groups[delete] += 1
                    d.is_deleted = True
                    d.set_skip_load("deleted_from_list")

    return matched


def _expand_defaults_list_impl(
    self_name: Optional[str],
    defaults_list: DefaultsList,
    group_to_choice: DictConfig,
    delete_groups: Dict[DeleteKey, int],
    repo: ConfigRepository,
) -> List[DefaultElement]:

    # list order is determined by first instance from that config group
    # selected config group is determined by the last override

    deferred_overrides = []
    defaults = defaults_list.effective

    ret: List[Union[DefaultElement, List[DefaultElement]]] = []
    for d in reversed(defaults):
        fqgn = d.fully_qualified_group_name()
        if d.config_name == "_self_":
            if self_name is None:
                raise ConfigCompositionException(
                    "self_name is not specified and defaults list contains a _self_ item"
                )
            d = copy.deepcopy(d)
            # override self_name
            if fqgn in group_to_choice:
                d.config_name = group_to_choice[fqgn]
            else:
                d.config_name = self_name
            added_sublist = [d]
        elif d.is_package_rename():
            added_sublist = [d]  # defer rename
        elif d.is_delete:
            delete_key = DeleteKey(
                fqgn,
                d.config_name if d.config_name != "_delete_" else None,
                must_delete=d.from_override,
            )
            if delete_key not in delete_groups:
                delete_groups[delete_key] = 0
            added_sublist = [d]
        elif d.from_override:
            added_sublist = [d]  # defer override processing
            deferred_overrides.append(d)
        elif d.is_interpolation():
            deferred_overrides.append(d)
            added_sublist = [d]  # defer interpolation
        else:
            if delete_if_matching(delete_groups, d):
                added_sublist = [d]
            else:
                if fqgn in group_to_choice:
                    d.config_name = group_to_choice[fqgn]

                added_sublist = _compute_element_defaults_list_impl(
                    element=d,
                    group_to_choice=group_to_choice,
                    delete_groups=delete_groups,
                    repo=repo,
                )

        for dd in reversed(added_sublist):
            if (
                dd.config_group is not None
                and dd.config_name != "_keep_"
                and not dd.is_delete
                and not dd.skip_load
            ):
                fqgn = dd.fully_qualified_group_name()
                if fqgn not in group_to_choice and not d.is_interpolation():
                    group_to_choice[fqgn] = dd.config_name

        ret.append(added_sublist)

    ret.reverse()
    result: List[DefaultElement] = [item for sublist in ret for item in sublist]  # type: ignore

    _process_renames(result)
    _verify_no_add_conflicts(result)

    # prepare a local group_to_choice with the defaults to support
    # legacy interpolations like ${defaults.1.a}
    # TODO: deprecated this interpolation style in the defaults list
    group_to_choice2 = copy.deepcopy(group_to_choice)
    group_to_choice2.defaults = []
    for d in defaults_list.original:
        if d.config_group is not None:
            group_to_choice2.defaults.append({d.config_group: d.config_name})
        else:
            group_to_choice2.defaults.append(d.config_name)

    # expand deferred
    for d in deferred_overrides:
        if d.is_interpolation():
            d.resolve_interpolation(group_to_choice2)

        item_defaults = _compute_element_defaults_list_impl(
            element=d,
            group_to_choice=group_to_choice,
            delete_groups=delete_groups,
            repo=repo,
        )
        index = result.index(d)
        result[index:index] = item_defaults

    deduped = []
    seen_groups = set()
    for d in result:
        if d.config_group is not None:
            fqgn = d.fully_qualified_group_name()
            if fqgn not in seen_groups:
                if not d.is_deleted:
                    seen_groups.add(fqgn)
                deduped.append(d)
        else:
            deduped.append(d)

    return deduped


def missing_config_error(
    repo: ConfigRepository,
    config_name: Optional[str],
    msg: str,
    with_search_path: bool,
) -> None:
    def add_search_path() -> str:
        descs = []
        for src in repo.get_sources():
            if src.provider != "schema":
                descs.append(f"\t{repr(src)}")
        lines = "\n".join(descs)

        if with_search_path:
            return msg + "\nSearch path:" + f"\n{lines}"
        else:
            return msg

    raise MissingConfigException(
        missing_cfg_file=config_name, message=add_search_path()
    )


def is_matching(rename: DefaultElement, other: DefaultElement) -> bool:
    if rename.config_group != other.config_group:
        return False
    if rename.package == other.package:
        return True
    return False


def convert_overrides_to_defaults(
    parsed_overrides: List[Override],
) -> List[DefaultElement]:
    ret = []
    for override in parsed_overrides:
        if override.is_add() and override.is_package_rename():
            raise ConfigCompositionException(
                "Add syntax does not support package rename, remove + prefix"
            )

        value = override.value()
        if override.is_delete() and value is None:
            value = "_delete_"

        if not isinstance(value, str):
            raise ConfigCompositionException(
                "Defaults list supported delete syntax is in the form"
                " ~group and ~group=value, where value is a group name (string)"
            )

        if override.is_package_rename():
            default = DefaultElement(
                config_group=override.key_or_group,
                config_name=value,
                package=override.pkg1,
                package2=override.pkg2,
                from_override=True,
            )
        else:
            default = DefaultElement(
                config_group=override.key_or_group,
                config_name=value,
                package=override.get_subject_package(),
                from_override=True,
            )

        if override.is_delete():
            default.is_delete = True

        if override.is_add():
            default.is_add_only = True
        ret.append(default)
    return ret
