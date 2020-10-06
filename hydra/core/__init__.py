# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
from dataclasses import dataclass
from typing import Optional


@dataclass
class DefaultElement:
    config_name: str
    config_group: Optional[str] = None
    optional: bool = False
    package: Optional[str] = None

    def config_path(self) -> str:
        if self.config_group is not None:
            return f"{self.config_group}/{self.config_name}"
        else:
            return self.config_name

    def fully_qualified_group_name(self) -> str:
        if self.package is not None:
            return f"{self.config_group}@{self.package}"
        else:
            return f"@{self.package}"
