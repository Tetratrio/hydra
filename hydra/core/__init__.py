# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
from dataclasses import dataclass
from typing import Optional


@dataclass
class DefaultElement:
    config_name: str
    config_group: Optional[str] = None
    optional: bool = False
    package: Optional[str] = None

    def __repr__(self) -> str:
        ret = ""
        if self.config_group is not None:
            ret += self.config_group
        if self.package is not None:
            ret += f"@{self.package}"

        ret += f"={self.config_name}"
        if self.optional:
            ret += " (optional)"
        return ret
