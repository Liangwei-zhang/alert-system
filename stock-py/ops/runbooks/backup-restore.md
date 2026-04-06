# Backup And Restore Baseline

這份 runbook 描述目前單機 production baseline 的備份 / 恢復策略。目標不是把所有容器資料卷都當成權威資料，而是先明確哪些資料需要保留、哪些可以重建。

## 權威資料與可重建資料

權威資料：

- PostgreSQL：交易、帳戶、通知、事件 outbox、read-model 原始資料
- MinIO：archive bucket 與報告產物

可重建資料：

- Kafka topic：由 PostgreSQL outbox / 重放流程重建
- ClickHouse analytics table：由 replay / sink 重建
- Redis：cache、runtime registry、broker 協調資料，不做權威備份

## 備份入口

```bash
make ops-backup-baseline
```

輸出會落在 `.local/backups/<UTC timestamp>/`，其中包含：

- `postgres/stock_py.dump`
- `minio/`
- `compose-ps.txt`

如果要手動指定路徑：

```bash
BACKUP_DIR=.local/backups/manual-$(date -u +%Y%m%dT%H%M%SZ) \
  ops/bin/backup-baseline.sh
```

## 備份前檢查

- 確認 compose stack 處於健康狀態
- 確認 PostgreSQL 沒有長時間卡住的 migration 或 DDL
- 確認 MinIO bucket bootstrap 已完成
- 如為 cutover 前備份，先記錄 release SHA 與當前 compose image tag

## 恢復入口

```bash
make ops-restore-baseline BACKUP_DIR=.local/backups/<UTC timestamp>
```

恢復流程只會恢復 PostgreSQL 與 MinIO。Kafka、ClickHouse、Redis 在恢復後重新啟動並由資料平面回補。

`ops/bin/restore-baseline.sh` 會優先讀取 `postgres/stock_py.dump`，同時兼容歷史備份中的 `postgres/stock.dump`。

完成 restore 與 smoke checks 後，建議立刻補一份 rollback 證據：

```bash
make cutover-rollback-verify CUTOVER_REPORT_DIR=ops/reports/cutover/<UTC timestamp> BACKUP_DIR=.local/backups/<UTC timestamp>
```

這會把 backup 可讀性、smoke 檢查結果與 runtime endpoint evidence 寫進 `rollback-verification.md` 與 `evidence/rollback-verification.json`。

## 恢復步驟

1. 停止對外流量與 batch job 觸發。
2. 保留當前故障現場的 compose logs、admin runtime metrics、cutover report。
3. 執行 restore 腳本恢復 PostgreSQL 與 MinIO。
4. 重啟 compose stack。
5. 執行 smoke checks：auth、dashboard、notifications、scanner ingest、TradingAgents webhook。
6. 檢查 admin runtime alerts 是否回到可接受範圍。
7. 視需要重放 outbox / analytics sink，把 Kafka / ClickHouse 補齊。

## 驗證點

- PostgreSQL 可成功查詢核心表
- MinIO bucket 可列出 archive 與報告目錄
- `/health/ready` 返回 ready
- `/v1/admin/runtime/metrics` 可看見 broker lag、PgBouncer、Redis、ClickHouse、object storage 指標
- `/v1/admin/runtime/alerts` 沒有持續性高嚴重度告警

## 風險說明

- ClickHouse 與 Kafka 當前不做權威快照，因此 restore 後短時間內 analytics / event lag 可能高於平時
- 如果 cutover 期間有未歸檔的物件寫入失敗，需另外比對 MinIO mirror 與應用報告目錄
- 如果 production 將來切到 HA 拓撲，這份 runbook 需要升級為分角色節點、快照與 WAL / object versioning 策略