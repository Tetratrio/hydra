# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
from dataclasses import dataclass
from typing import Optional

from omegaconf import AnyNode, DictConfig, OmegaConf


@dataclass
class DefaultElement:
    config_name: Optional[str]
    config_group: Optional[str] = None
    optional: bool = False
    package: Optional[str] = None

    # used in package rename
    package2: Optional[str] = None

    # True for default elements that are from overrides.
    # Those have somewhat different semantics
    from_override: bool = False

    # set to True for external overrides with +
    is_add_only: bool = False

    # is a delete indicator, used as input
    is_delete: bool = False
    # is this default deleted? used as output
    is_deleted: bool = False

    def config_path(self) -> str:
        assert self.config_name is not None
        if self.config_group is not None:
            return f"{self.config_group}/{self.config_name}"
        else:
            return self.config_name

    def fully_qualified_group_name(self) -> str:
        if self.package is not None:
            return f"{self.config_group}@{self.package}"
        else:
            return f"{self.config_group}"

    def __repr__(self) -> str:
        package = self.package
        if self.is_package_rename():
            if self.package is not None:
                package = f"{self.package}:{self.package2}"
            else:
                package = f":{self.package2}"

        if self.config_group is None:
            if package is not None:
                ret = f"@{package}={self.config_name}"
            else:
                ret = f"{self.config_name}"
        else:
            if package is not None:
                ret = f"{self.config_group}@{package}={self.config_name}"
            else:
                ret = f"{self.config_group}={self.config_name}"

        if self.is_add_only:
            ret = f"+{ret}"
        if self.is_delete:
            ret = f"~{ret}"
        if self.is_deleted:
            ret = f"{ret} (DELETED)"

        if self.optional:
            ret = f"{ret} (optional)"
        return ret

    def is_package_rename(self) -> bool:
        return self.package2 is not None

    def get_subject_package(self) -> Optional[str]:
        return self.package if self.package2 is None else self.package2

    def is_interpolation(self) -> bool:
        """
        True if config_name is an interpolation
        """
        if isinstance(self.config_name, str):
            node = AnyNode(self.config_name)
            return node._is_interpolation()
        else:
            return False

    def resolve_interpolation(self, group_to_choice: DictConfig) -> None:
        assert self.config_group is not None
        node = OmegaConf.create({self.config_group: self.config_name})
        node._set_parent(group_to_choice)
        self.config_name = node[self.config_group]
