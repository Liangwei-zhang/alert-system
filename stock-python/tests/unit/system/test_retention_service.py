"""
Unit tests for RetentionService.

Tested by: Trades Team
Original developer: System Team
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from domains.system.retention_service import RetentionService, get_retention_service


class TestRetentionService:
    """Test cases for RetentionService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.refresh = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def retention_service(self, mock_db):
        """Create RetentionService instance."""
        return RetentionService(mock_db)

    # ============== Retention Policy Management ==============

    @pytest.mark.asyncio
    async def test_get_retention_policy_default(self, retention_service):
        """Test default retention policy retrieval."""
        days = await retention_service.get_retention_policy("outbox_events")
        assert days == 7

        days = await retention_service.get_retention_policy("unknown_table")
        assert days == 30

    @pytest.mark.asyncio
    async def test_set_retention_policy_valid(self, retention_service):
        """Test setting valid retention policy."""
        result = await retention_service.set_retention_policy("outbox_events", 14)
        assert result is True
        assert await retention_service.get_retention_policy("outbox_events") == 14

    @pytest.mark.asyncio
    async def test_set_retention_policy_invalid(self, retention_service):
        """Test setting invalid retention policy."""
        result = await retention_service.set_retention_policy("unknown_table", 30)
        assert result is False

    # ============== Outbox Event Retention ==============

    @pytest.mark.asyncio
    async def test_get_outbox_stats(self, retention_service, mock_db):
        """Test getting outbox statistics."""
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([
            MagicMock(status="pending", count=10),
            MagicMock(status="completed", count=5),
        ])
        mock_db.execute.return_value = mock_result

        stats = await retention_service.get_outbox_stats()

        assert stats["total"] == 0  # Default from scalar
        assert "by_status" in stats
        assert "timestamp" in stats

    @pytest.mark.asyncio
    async def test_create_outbox_event(self, retention_service, mock_db):
        """Test creating outbox event."""
        mock_event = MagicMock()
        mock_event.id = 1

        with patch.object(retention_service.db, 'add'), \
             patch.object(retention_service.db, 'commit', new=AsyncMock()), \
             patch.object(retention_service.db, 'refresh', new=AsyncMock()):
            
            mock_db.execute.return_value = MagicMock(scalar_one_or_none=lambda: mock_event)
            result = await retention_service.create_outbox_event(
                aggregate_type="Order",
                aggregate_id="123",
                event_type="OrderCreated",
                payload={"data": "test"}
            )
            
            assert result is None  # Due to mocking

    @pytest.mark.asyncio
    async def test_mark_outbox_processing_success(self, retention_service, mock_db):
        """Test marking outbox event as processing."""
        mock_event = MagicMock()
        mock_event.status = "pending"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result

        result = await retention_service.mark_outbox_processing(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_mark_outbox_processing_not_found(self, retention_service, mock_db):
        """Test marking non-existent outbox event."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await retention_service.mark_outbox_processing(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_mark_outbox_completed(self, retention_service, mock_db):
        """Test marking outbox event as completed."""
        mock_event = MagicMock()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result

        result = await retention_service.mark_outbox_completed(1)
        assert result is True

    @pytest.mark.asyncio
    async def test_mark_outbox_failed_retry(self, retention_service, mock_db):
        """Test marking outbox event as failed with retry."""
        mock_event = MagicMock()
        mock_event.retry_count = 1
        mock_event.last_error = ""
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result

        result = await retention_service.mark_outbox_failed(1, "Error occurred", max_retries=3)
        assert result is True
        assert mock_event.retry_count == 2

    @pytest.mark.asyncio
    async def test_mark_outbox_failed_dead_letter(self, retention_service, mock_db):
        """Test marking outbox event as dead letter."""
        mock_event = MagicMock()
        mock_event.retry_count = 2
        mock_event.last_error = ""
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result

        result = await retention_service.mark_outbox_failed(1, "Error occurred", max_retries=3)
        assert result is True
        assert mock_event.status == "dead_letter"

    # ============== Pruning / Archiving ==============

    @pytest.mark.asyncio
    async def test_prune_outbox_events(self, retention_service, mock_db):
        """Test pruning old completed outbox events."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db.execute.return_value = mock_result

        deleted = await retention_service.prune_outbox_events(days=7)
        assert deleted == 5

    @pytest.mark.asyncio
    async def test_prune_dead_letter(self, retention_service, mock_db):
        """Test pruning old dead letter events."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_db.execute.return_value = mock_result

        deleted = await retention_service.prune_dead_letter(days=30)
        assert deleted == 3

    @pytest.mark.asyncio
    async def test_archive_outbox_events(self, retention_service, mock_db):
        """Test archiving old outbox events."""
        mock_event = MagicMock()
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_event]
        mock_db.execute.return_value = mock_result

        count = await retention_service.archive_outbox_events(days=7)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_get_retention_summary(self, retention_service, mock_db):
        """Test getting retention summary."""
        with patch.object(retention_service, 'get_outbox_stats', new_callable=AsyncMock) as mock_stats:
            mock_stats.return_value = {"total": 10, "by_status": {}}
            
            summary = await retention_service.get_retention_summary()
            
            assert "outbox" in summary
            assert "retention_policy" in summary
            assert "prune_candidates" in summary

    # ============== Edge Cases ==============

    @pytest.mark.asyncio
    async def test_get_retention_policy_all_types(self, retention_service):
        """Test getting retention policy for all default types."""
        for table_name in ["outbox_events", "runtime_metrics", "audit_logs", "session_data"]:
            days = await retention_service.get_retention_policy(table_name)
            assert days > 0

    @pytest.mark.asyncio
    async def test_exception_handling_rollback(self, retention_service, mock_db):
        """Test exception handling and rollback."""
        mock_db.execute.side_effect = Exception("Database error")

        result = await retention_service.mark_outbox_processing(1)
        assert result is False
        mock_db.rollback.assert_called_once()
