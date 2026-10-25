"""Runtime settings from ``CL_*`` environment variables (see docs/DEVELOPMENT.md)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Profile = Literal["lite", "standard", "full"]
Storage = Literal["local", "s3"]

# Until the project has its own address. Override with CL_CRAWLER_CONTACT.
DEFAULT_CONTACT = "https://github.com/csp4z/compromise-ledger/issues"

_DEFAULT_STORAGE: dict[Profile, Storage] = {"lite": "local", "standard": "s3", "full": "s3"}


@dataclass(frozen=True, slots=True)
class Settings:
    profile: Profile
    data_dir: Path
    storage: Storage
    catalog_uri: str
    warehouse: str
    crawler_contact: str
    seeds_dir: Path
    exports_dir: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        profile = env.get("CL_PROFILE", "lite")
        if profile not in _DEFAULT_STORAGE:
            raise ValueError(f"CL_PROFILE must be lite, standard, or full, not {profile!r}")
        storage = env.get("CL_STORAGE", _DEFAULT_STORAGE[profile])
        if storage not in ("local", "s3"):
            raise ValueError(f"CL_STORAGE must be local or s3, not {storage!r}")
        data_dir = Path(env.get("CL_DATA_DIR", ".lake")).resolve()
        return cls(
            profile=profile,
            data_dir=data_dir,
            storage=storage,
            catalog_uri=env.get("CL_CATALOG_URI", f"sqlite:///{data_dir / 'catalog.db'}"),
            warehouse=env.get("CL_WAREHOUSE", (data_dir / "warehouse").as_uri()),
            crawler_contact=env.get("CL_CRAWLER_CONTACT", DEFAULT_CONTACT),
            seeds_dir=Path(env.get("CL_SEEDS_DIR", "data/seeds")).resolve(),
            exports_dir=Path(env.get("CL_EXPORTS_DIR", str(data_dir / "exports"))).resolve(),
        )
