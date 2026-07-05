from __future__ import annotations

from pathlib import Path

from app.schemas import AuditListItem, AuditResult


class AuditStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, audit: AuditResult) -> None:
        path = self._path(audit.audit_id)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(audit.model_dump_json(indent=2), encoding="utf-8")
        temp_path.replace(path)

    def get(self, audit_id: str) -> AuditResult | None:
        path = self._path(audit_id)
        if not path.exists():
            return None
        return AuditResult.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[AuditListItem]:
        audits: list[AuditListItem] = []
        for path in self.root.glob("*.json"):
            try:
                audit = AuditResult.model_validate_json(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            audits.append(
                AuditListItem(
                    audit_id=audit.audit_id,
                    dataset_name=audit.dataset_name,
                    created_at=audit.created_at,
                    score=audit.score.overall,
                    risk_level=audit.summary.risk_level,
                    issue_count=len(audit.issues),
                    summary_source=audit.summary.source,
                )
            )
        return sorted(audits, key=lambda item: item.created_at, reverse=True)

    def _path(self, audit_id: str) -> Path:
        safe_id = audit_id.replace("/", "").replace("\\", "")
        return self.root / f"{safe_id}.json"
