import gzip
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from apps.workers.cold_storage.worker import ColdStorageWorker
from domains.analytics.archive.export_service import ArchiveExportService
from infra.analytics.clickhouse_client import ClickHouseClient


class FakeStorageClient:
    def __init__(self) -> None:
        self.json_payloads = {}
        self.byte_payloads = {}

    async def put_json(self, key, payload):
        self.json_payloads[key] = payload
        return key

    async def put_bytes(self, key, payload):
        self.byte_payloads[key] = payload
        return key


class FakeExportService:
    def __init__(self) -> None:
        self.calls = []

    async def export_partition(self, table, partition_key):
        self.calls.append((table, partition_key))
        return {"table": table, "partition_key": partition_key}


class ArchiveExportServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.client = ClickHouseClient(root_path=self.tempdir.name)

    async def test_export_partition_writes_manifest_and_compressed_rows(self) -> None:
        now = datetime.now(timezone.utc)
        partition_key = now.strftime("%Y-%m")
        storage = FakeStorageClient()
        service = ArchiveExportService(self.client, storage_client=storage)
        await self.client.insert_rows(
            "signal_events",
            [{"occurred_at": now, "signal_id": 1, "symbol": "AAPL"}],
        )

        manifest = await service.export_partition("signal_events", partition_key)

        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["row_count"], 1)
        self.assertIn(manifest["object_key"], storage.byte_payloads)
        self.assertIn(
            f"analytics-archive/signal_events/{partition_key}/manifest.json", storage.json_payloads
        )
        decompressed = gzip.decompress(storage.byte_payloads[manifest["object_key"]]).decode(
            "utf-8"
        )
        rows = [json.loads(line) for line in decompressed.splitlines() if line.strip()]
        self.assertEqual(rows[0]["symbol"], "AAPL")

    async def test_cold_storage_worker_exports_old_partitions_only(self) -> None:
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=90)
        recent_timestamp = datetime.now(timezone.utc) - timedelta(days=2)
        export_service = FakeExportService()
        worker = ColdStorageWorker(
            client=self.client,
            export_service=export_service,
            tables=("signal_events",),
            retention_days=30,
        )
        await self.client.insert_rows(
            "signal_events",
            [
                {"occurred_at": old_timestamp, "signal_id": 1, "symbol": "AAPL"},
                {"occurred_at": recent_timestamp, "signal_id": 2, "symbol": "MSFT"},
            ],
        )

        result = await worker.archive_old_partitions()

        self.assertEqual(result["archived"], 1)
        self.assertEqual(export_service.calls, [("signal_events", old_timestamp.strftime("%Y-%m"))])


if __name__ == "__main__":
    unittest.main()
