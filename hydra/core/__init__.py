# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
from dataclasses import dataclass
from typing import Optional


@dataclass
class DefaultElement:
    config_name: str
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

    def config_path(self) -> str:
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
        return ret

    def is_package_rename(self) -> bool:
        return self.package2 is not None

    def get_subject_package(self) -> Optional[str]:
        return self.package if self.package2 is None else self.package2
