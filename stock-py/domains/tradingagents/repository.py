"""
Repository for TradingAgents domain.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.tradingagents import (
    FinalAction,
    TradingAgentsAnalysisRecord,
    TradingAgentsStatus,
    TradingAgentsSubmitFailure,
    TriggerType,
)


class TradingAgentsRepository:
    """Repository for TradingAgents analysis records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _accepted_record_values(
        request_id: str,
        ticker: str,
        analysis_date: datetime,
        trigger_type: str,
        selected_analysts: Optional[List[str]] = None,
        trigger_context: Optional[dict] = None,
    ) -> dict:
        import json

        return {
            "request_id": request_id,
            "ticker": ticker.upper(),
            "analysis_date": analysis_date,
            "trigger_type": trigger_type,
            "selected_analysts": json.dumps(selected_analysts) if selected_analysts else None,
            "trigger_context": json.dumps(trigger_context) if trigger_context else None,
            "tradingagents_status": TradingAgentsStatus.PENDING,
        }

    async def insert_accepted(
        self,
        request_id: str,
        ticker: str,
        analysis_date: datetime,
        trigger_type: str,
        selected_analysts: Optional[List[str]] = None,
        trigger_context: Optional[dict] = None,
    ) -> TradingAgentsAnalysisRecord:
        """Insert a new accepted analysis request."""
        record = TradingAgentsAnalysisRecord(
            **self._accepted_record_values(
                request_id=request_id,
                ticker=ticker,
                analysis_date=analysis_date,
                trigger_type=trigger_type,
                selected_analysts=selected_analysts,
                trigger_context=trigger_context,
            )
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def insert_accepted_if_absent(
        self,
        request_id: str,
        ticker: str,
        analysis_date: datetime,
        trigger_type: str,
        selected_analysts: Optional[List[str]] = None,
        trigger_context: Optional[dict] = None,
    ) -> tuple[TradingAgentsAnalysisRecord | None, bool]:
        """Insert a new accepted analysis request, or return the existing record on conflict."""
        result = await self.session.execute(
            insert(TradingAgentsAnalysisRecord)
            .values(
                **self._accepted_record_values(
                    request_id=request_id,
                    ticker=ticker,
                    analysis_date=analysis_date,
                    trigger_type=trigger_type,
                    selected_analysts=selected_analysts,
                    trigger_context=trigger_context,
                )
            )
            .on_conflict_do_nothing(index_elements=[TradingAgentsAnalysisRecord.request_id])
            .returning(TradingAgentsAnalysisRecord.request_id)
        )
        inserted_request_id = result.scalar_one_or_none()
        if inserted_request_id is not None:
            return None, True
        return await self.get_by_request_id(request_id), False

    async def update_projection(
        self,
        request_id: str,
        job_id: Optional[str] = None,
        tradingagents_status: Optional[str] = None,
        final_action: Optional[str] = None,
        decision_summary: Optional[str] = None,
        result_payload: Optional[dict] = None,
    ) -> Optional[TradingAgentsAnalysisRecord]:
        """Update the projection fields of a record."""
        import json

        update_values = {}
        if job_id is not None:
            update_values["job_id"] = job_id
        if tradingagents_status is not None:
            update_values["tradingagents_status"] = tradingagents_status
        if final_action is not None:
            update_values["final_action"] = final_action
        if decision_summary is not None:
            update_values["decision_summary"] = decision_summary
        if result_payload is not None:
            update_values["result_payload"] = json.dumps(result_payload)

        if not update_values:
            return await self.get_by_request_id(request_id)

        update_values["updated_at"] = datetime.utcnow()

        await self.session.execute(
            update(TradingAgentsAnalysisRecord)
            .where(TradingAgentsAnalysisRecord.request_id == request_id)
            .values(**update_values)
        )
        await self.session.flush()

        return await self.get_by_request_id(request_id)

    async def get_by_request_id(self, request_id: str) -> Optional[TradingAgentsAnalysisRecord]:
        """Get a record by request ID."""
        result = await self.session.execute(
            select(TradingAgentsAnalysisRecord).where(
                TradingAgentsAnalysisRecord.request_id == request_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_job_id(self, job_id: str) -> Optional[TradingAgentsAnalysisRecord]:
        """Get a record by job ID."""
        result = await self.session.execute(
            select(TradingAgentsAnalysisRecord).where(TradingAgentsAnalysisRecord.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_pending(
        self,
        limit: int = 100,
        older_than_minutes: int = 5,
    ) -> List[TradingAgentsAnalysisRecord]:
        """List pending records older than specified minutes."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=older_than_minutes)
        result = await self.session.execute(
            select(TradingAgentsAnalysisRecord)
            .where(
                and_(
                    TradingAgentsAnalysisRecord.tradingagents_status.in_(
                        [
                            TradingAgentsStatus.PENDING,
                            TradingAgentsStatus.SUBMITTED,
                            TradingAgentsStatus.RUNNING,
                        ]
                    ),
                    TradingAgentsAnalysisRecord.created_at < cutoff_time,
                )
            )
            .order_by(TradingAgentsAnalysisRecord.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_delayed(
        self,
        delayed_threshold_minutes: int = 30,
    ) -> List[TradingAgentsAnalysisRecord]:
        """List records that are delayed (stuck in submitted/running for too long)."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=delayed_threshold_minutes)
        result = await self.session.execute(
            select(TradingAgentsAnalysisRecord)
            .where(
                and_(
                    TradingAgentsAnalysisRecord.tradingagents_status.in_(
                        [
                            TradingAgentsStatus.SUBMITTED,
                            TradingAgentsStatus.RUNNING,
                        ]
                    ),
                    TradingAgentsAnalysisRecord.submitted_at < cutoff_time,
                )
            )
            .order_by(TradingAgentsAnalysisRecord.submitted_at.asc())
        )
        return list(result.scalars().all())

    async def mark_delayed(
        self,
        request_id: str,
    ) -> Optional[TradingAgentsAnalysisRecord]:
        """Mark a record as delayed."""
        await self.session.execute(
            update(TradingAgentsAnalysisRecord)
            .where(TradingAgentsAnalysisRecord.request_id == request_id)
            .values(
                delayed_at=datetime.utcnow(),
                tradingagents_status=TradingAgentsStatus.RUNNING,  # Keep as running, add delayed flag
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.flush()
        return await self.get_by_request_id(request_id)

    async def mark_submitted(
        self,
        request_id: str,
        job_id: str,
    ) -> None:
        """Mark a record as submitted."""
        await self.session.execute(
            update(TradingAgentsAnalysisRecord)
            .where(TradingAgentsAnalysisRecord.request_id == request_id)
            .values(
                job_id=job_id,
                tradingagents_status=TradingAgentsStatus.SUBMITTED,
                submitted_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.flush()

    async def mark_completed(
        self,
        request_id: str,
        final_action: str,
        decision_summary: Optional[str] = None,
        result_payload: Optional[dict] = None,
    ) -> Optional[TradingAgentsAnalysisRecord]:
        """Mark a record as completed."""
        import json

        await self.session.execute(
            update(TradingAgentsAnalysisRecord)
            .where(TradingAgentsAnalysisRecord.request_id == request_id)
            .values(
                tradingagents_status=TradingAgentsStatus.COMPLETED,
                final_action=final_action,
                decision_summary=decision_summary,
                result_payload=json.dumps(result_payload) if result_payload else None,
                completed_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.flush()
        return await self.get_by_request_id(request_id)

    async def mark_failed(
        self,
        request_id: str,
        error_message: Optional[str] = None,
    ) -> Optional[TradingAgentsAnalysisRecord]:
        """Mark a record as failed."""
        await self.session.execute(
            update(TradingAgentsAnalysisRecord)
            .where(TradingAgentsAnalysisRecord.request_id == request_id)
            .values(
                tradingagents_status=TradingAgentsStatus.FAILED,
                decision_summary=error_message,
                completed_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.flush()
        return await self.get_by_request_id(request_id)

    async def increment_poll_count(self, request_id: str) -> None:
        """Increment poll count and update last poll time."""
        await self.session.execute(
            update(TradingAgentsAnalysisRecord)
            .where(TradingAgentsAnalysisRecord.request_id == request_id)
            .values(
                poll_count=TradingAgentsAnalysisRecord.poll_count + 1,
                last_poll_at=datetime.utcnow(),
            )
        )
        await self.session.flush()

    async def mark_webhook_received(self, request_id: str) -> None:
        """Mark that webhook was received."""
        await self.session.execute(
            update(TradingAgentsAnalysisRecord)
            .where(TradingAgentsAnalysisRecord.request_id == request_id)
            .values(
                webhook_received=True,
                completed_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.flush()

    async def list_analyses(
        self,
        status: Optional[str] = None,
        ticker: Optional[str] = None,
        trigger_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[TradingAgentsAnalysisRecord]:
        """List analyses with filters."""
        conditions = []

        if status:
            conditions.append(TradingAgentsAnalysisRecord.tradingagents_status == status)
        if ticker:
            conditions.append(TradingAgentsAnalysisRecord.ticker == ticker.upper())
        if trigger_type:
            conditions.append(TradingAgentsAnalysisRecord.trigger_type == trigger_type)
        if from_date:
            conditions.append(TradingAgentsAnalysisRecord.created_at >= from_date)
        if to_date:
            conditions.append(TradingAgentsAnalysisRecord.created_at <= to_date)

        query = select(TradingAgentsAnalysisRecord)
        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(TradingAgentsAnalysisRecord.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_analyses(
        self,
        status: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> int:
        """Count analyses matching filters."""
        from sqlalchemy import func, select

        query = select(func.count(TradingAgentsAnalysisRecord.id))

        conditions = []
        if status:
            conditions.append(TradingAgentsAnalysisRecord.tradingagents_status == status)
        if ticker:
            conditions.append(TradingAgentsAnalysisRecord.ticker == ticker.upper())

        if conditions:
            query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return result.scalar_one()


class TradingAgentsFailureRepository:
    """Repository for TradingAgents submit failures."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_submit_failure(
        self,
        request_id: str,
        ticker: str,
        error_message: str,
        error_code: Optional[str] = None,
    ) -> TradingAgentsSubmitFailure:
        """Record a submit failure."""
        failure = TradingAgentsSubmitFailure(
            request_id=request_id,
            ticker=ticker.upper(),
            error_message=error_message,
            error_code=error_code,
            attempt_count=1,
        )
        self.session.add(failure)
        await self.session.flush()
        return failure

    async def get_unresolved_failures(
        self,
        limit: int = 100,
    ) -> List[TradingAgentsSubmitFailure]:
        """Get unresolved failures that are due for retry."""
        now = datetime.utcnow()
        result = await self.session.execute(
            select(TradingAgentsSubmitFailure)
            .where(
                and_(
                    TradingAgentsSubmitFailure.resolved == False,
                    or_(
                        TradingAgentsSubmitFailure.next_retry_at == None,
                        TradingAgentsSubmitFailure.next_retry_at <= now,
                    ),
                )
            )
            .order_by(TradingAgentsSubmitFailure.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_resolved(self, failure_id: int) -> None:
        """Mark a failure as resolved."""
        await self.session.execute(
            update(TradingAgentsSubmitFailure)
            .where(TradingAgentsSubmitFailure.id == failure_id)
            .values(
                resolved=True,
                resolved_at=datetime.utcnow(),
            )
        )
        await self.session.flush()

    async def increment_attempt(
        self,
        failure_id: int,
        next_retry_at: Optional[datetime] = None,
    ) -> None:
        """Increment attempt count and set next retry time."""
        await self.session.execute(
            update(TradingAgentsSubmitFailure)
            .where(TradingAgentsSubmitFailure.id == failure_id)
            .values(
                attempt_count=TradingAgentsSubmitFailure.attempt_count + 1,
                last_retry_at=datetime.utcnow(),
                next_retry_at=next_retry_at,
            )
        )
        await self.session.flush()
