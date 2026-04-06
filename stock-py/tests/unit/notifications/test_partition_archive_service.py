import gzip
import json
import unittest

from domains.notifications.partition_archive_service import (
    NotificationPartitionArchiveService,
    PartitionArchiveSpec,
)


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


class StubNotificationPartitionArchiveService(NotificationPartitionArchiveService):
    def __init__(self, *, storage_client, partitions, rows):
        super().__init__(
            object(),
            storage_client=storage_client,
            max_partitions_per_table=4,
        )
        self._partitions = partitions
        self._rows = rows
        self.deleted = []
        self.specs = (
            PartitionArchiveSpec(
                table_name="notifications",
                model=object,
                timestamp_column=None,
                retention_days=90,
            ),
            PartitionArchiveSpec(
                table_name="message_receipts_archive",
                model=object,
                timestamp_column=None,
                retention_days=180,
            ),
        )

    async def _list_eligible_partitions(self, spec):
        return list(self._partitions.get(spec.table_name, []))

    async def _load_partition_rows(self, spec, *, start_at, end_at):
        del end_at
        return list(self._rows.get((spec.table_name, start_at.strftime("%Y-%m")), []))

    async def _delete_partition_rows(self, spec, *, start_at, end_at):
        del end_at
        key = (spec.table_name, start_at.strftime("%Y-%m"))
        self.deleted.append(key)
        return len(self._rows.get(key, []))


class NotificationPartitionArchiveServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_archive_expired_partitions_exports_manifests_and_compressed_rows(self) -> None:
        storage = FakeStorageClient()
        service = StubNotificationPartitionArchiveService(
            storage_client=storage,
            partitions={
                "notifications": ["2026-01"],
                "message_receipts_archive": ["2025-12"],
            },
            rows={
                ("notifications", "2026-01"): [
                    {"id": "n-1", "created_at": "2026-01-04T00:00:00+00:00"},
                    {"id": "n-2", "created_at": "2026-01-08T00:00:00+00:00"},
                ],
                ("message_receipts_archive", "2025-12"): [
                    {"id": "r-1", "created_at": "2025-12-30T00:00:00+00:00"}
                ],
            },
        )

        outcome = await service.archive_expired_partitions()

        self.assertEqual(outcome.partitions_archived, 2)
        self.assertEqual(outcome.rows_pruned, 3)
        self.assertEqual(
            sorted(service.deleted),
            [
                ("message_receipts_archive", "2025-12"),
                ("notifications", "2026-01"),
            ],
        )
        manifest = storage.json_payloads["retention-archive/notifications/2026-01/manifest.json"]
        self.assertEqual(manifest["row_count"], 2)
        payload = gzip.decompress(
            storage.byte_payloads["retention-archive/notifications/2026-01/rows.jsonl.gz"]
        ).decode("utf-8")
        rows = [json.loads(line) for line in payload.splitlines() if line.strip()]
        self.assertEqual(rows[0]["id"], "n-1")


if __name__ == "__main__":
    unittest.main()
