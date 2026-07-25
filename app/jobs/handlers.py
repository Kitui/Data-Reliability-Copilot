from __future__ import annotations

from datetime import UTC
from typing import Any

from app.jobs.worker import JobContext, JobHandler


class DatasetAuditHandler(JobHandler):
    def execute(self, context: JobContext) -> dict[str, Any]:
        from app.api.dependencies import get_audit_store
        from app.api.routes.datasets import register_audit_dataset
        from app.api.routes.quality_rules import assigned_rules_for_dataset, persist_rule_executions
        from app.auditor import audit_dataframe
        from app.ingestion import read_csv_bytes
        from app.schemas import AuditRuleConfig, UploadedFileInfo
        from app.services.dataset_files import build_dataset_file_service

        payload = context.payload
        files = build_dataset_file_service()
        content = files.read_bytes(payload["storage_key"])
        filename = payload["filename"]
        upload = UploadedFileInfo.model_validate(payload["upload"])
        frame = read_csv_bytes(content, filename)
        rule_config = AuditRuleConfig.model_validate(payload.get("rule_config") or {})
        quality_rules = assigned_rules_for_dataset(context.workspace_id, filename)
        result = audit_dataframe(frame, filename, rule_config=rule_config, upload=upload, quality_rules=quality_rules)
        result.audit_kind = payload.get("audit_kind", "dataset_import")
        result.dataset_version = int(payload.get("dataset_version", 1))
        get_audit_store().save(result, context.workspace_id)
        persist_rule_executions(result.audit_id, result.rule_executions)
        register_audit_dataset(result, context.workspace_id, payload.get("owner_name") or "Workspace team")
        return {
            "audit_id": result.audit_id,
            "dataset_name": result.dataset_name,
            "score": result.score.overall,
            "risk_level": result.summary.risk_level,
            "issue_count": len(result.issues),
        }


class ScheduledAuditHandler(JobHandler):
    def execute(self, context: JobContext) -> dict[str, Any]:
        from time import perf_counter

        from sqlalchemy import select

        from app.api.dependencies import get_audit_store
        from app.api.routes.audits import save_upload
        from app.api.routes.datasets import register_audit_dataset
        from app.api.routes.quality_rules import assigned_rules_for_dataset, persist_rule_executions
        from app.auditor import audit_dataframe
        from app.db.models import AuditScheduleRecord, DatasetRecord, ScheduledAuditRunRecord, UploadRecord
        from app.db.session import get_session_factory
        from app.ingestion import read_csv_bytes
        from app.services.dataset_files import build_dataset_file_service

        timer = perf_counter()
        payload = context.payload
        schedule_id = int(payload["schedule_id"])
        run_id = int(payload["run_id"])
        actor_name = str(payload.get("actor_name") or "Scheduled automation")
        Session = get_session_factory()

        with Session() as db:
            run = db.get(ScheduledAuditRunRecord, run_id)
            schedule = db.scalar(
                select(AuditScheduleRecord).where(
                    AuditScheduleRecord.id == schedule_id,
                    AuditScheduleRecord.workspace_id == context.workspace_id,
                )
            )
            if run is None or schedule is None:
                raise RuntimeError("Scheduled audit run is unavailable.")
            run.status = "in_progress"
            db.commit()
            dataset = db.scalar(
                select(DatasetRecord).where(
                    DatasetRecord.id == schedule.dataset_id,
                    DatasetRecord.workspace_id == context.workspace_id,
                )
            )
            if dataset is None or not dataset.latest_audit_id:
                raise RuntimeError("The scheduled dataset has no completed source audit.")
            source_audit_id = dataset.latest_audit_id
            upload = db.scalar(select(UploadRecord).where(UploadRecord.audit_id == source_audit_id))
            if upload is None:
                raise RuntimeError("The scheduled dataset has no persisted source file.")
            dataset_name = dataset.name

        try:
            files = build_dataset_file_service()
            content = files.read_bytes(upload.relative_path)
            upload_info = save_upload(
                content,
                upload.original_filename or f"{dataset_name}.csv",
                upload.content_type or "text/csv",
                context.workspace_id,
            )
            frame = read_csv_bytes(content, upload.original_filename or f"{dataset_name}.csv")
            rules = assigned_rules_for_dataset(context.workspace_id, dataset_name)
            result = audit_dataframe(frame, dataset_name, upload=upload_info, quality_rules=rules)
            result.audit_kind = "scheduled"
            try:
                source_payload = get_audit_store().get(source_audit_id, context.workspace_id)
                result.dataset_version = source_payload.dataset_version if source_payload else None
            except Exception:
                result.dataset_version = None
            get_audit_store().save(result, context.workspace_id)
            persist_rule_executions(result.audit_id, result.rule_executions)
            register_audit_dataset(result, context.workspace_id, actor_name)

            from datetime import datetime

            completed = datetime.now(UTC)
            duration = int((perf_counter() - timer) * 1000)
            with Session() as db:
                run = db.get(ScheduledAuditRunRecord, run_id)
                schedule = db.get(AuditScheduleRecord, schedule_id)
                if run is not None:
                    run.audit_id = result.audit_id
                    run.status = "completed"
                    run.completed_at = completed
                    run.duration_ms = duration
                    run.score = result.score.overall
                    run.issue_count = len(result.issues)
                if schedule is not None:
                    schedule.last_run_at = completed
                    schedule.last_status = "completed"
                    schedule.last_audit_id = result.audit_id
                    schedule.last_error = None
                    schedule.claimed_at = None
                    schedule.updated_at = completed
                db.commit()
            return {
                "schedule_id": schedule_id,
                "run_id": run_id,
                "audit_id": result.audit_id,
                "score": result.score.overall,
                "issue_count": len(result.issues),
                "duration_ms": duration,
            }
        except Exception as exc:
            from datetime import datetime

            completed = datetime.now(UTC)
            duration = int((perf_counter() - timer) * 1000)
            with Session() as db:
                run = db.get(ScheduledAuditRunRecord, run_id)
                schedule = db.get(AuditScheduleRecord, schedule_id)
                if run is not None:
                    run.status = "failed"
                    run.completed_at = completed
                    run.duration_ms = duration
                    run.error_message = str(exc)[:4000]
                if schedule is not None:
                    schedule.last_run_at = completed
                    schedule.last_status = "failed"
                    schedule.last_error = str(exc)[:4000]
                    schedule.claimed_at = None
                    schedule.updated_at = completed
                db.commit()
            raise


HANDLERS = {
    "dataset_audit": DatasetAuditHandler(),
    "scheduled_audit": ScheduledAuditHandler(),
}
