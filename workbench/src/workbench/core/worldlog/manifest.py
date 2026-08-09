import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.events import SCHEMA_VERSION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RunManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    seed_root: int = Field(ge=0, lt=2**64)
    workplace_id: str
    config_hash: str
    schema_version: int = SCHEMA_VERSION
    event_count: int = Field(ge=0)
    world_sha256: str

    @classmethod
    def for_log(
        cls,
        log_path: Path,
        *,
        run_id: str,
        seed_root: int,
        workplace_id: str,
        config_hash: str,
    ) -> RunManifest:
        event_count = sum(
            1 for line in log_path.read_bytes().splitlines() if line.strip()
        )
        return cls(
            run_id=run_id,
            seed_root=seed_root,
            workplace_id=workplace_id,
            config_hash=config_hash,
            event_count=event_count,
            world_sha256=_sha256(log_path),
        )

    def matches_log(self, log_path: Path) -> bool:
        return _sha256(log_path) == self.world_sha256


def write_manifest(manifest: RunManifest, path: Path) -> None:
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> RunManifest:
    return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
