# Kubernetes Roadmap Notes

目前這個倉庫沒有把 Kubernetes 當作默認生產交付面。近期目標是先把 compose + VM 單機 baseline 做實，再決定是否升級到 K8s。

## 為什麼現在不直接切 K8s

- 眼前的主要風險是 data plane 可運維性，不是編排抽象不足
- 一部分 worker 是 batch-style entrypoint，尚未收斂成穩定的 Deployment / CronJob / Job 分工
- 如果現在直接補 K8s manifest，多半只是把尚未驗證的服務邊界重新包裝一次

## 什麼情況下值得切換

當下列需求變成真實需求時，再把 K8s 視為主路徑：

- 需要多副本 public/admin API 與 worker 高可用
- 需要滾動發布、節點擴縮容與更細的資源配額
- 需要集中式 secrets / config / observability 整合
- 已有明確的 Job / CronJob / Deployment 分界

## 預期映射

如果未來切 K8s，建議映射如下：

- `public-api` / `admin-api` / `scheduler` / `event-pipeline` / `retention` / `tradingagents-bridge` -> Deployments
- `migrate` / `kafka-setup` / `minio-setup` -> Jobs 或 init-like bootstrap jobs
- `scanner` / `market-data` / `cold-storage` / `backtest` / `receipt-escalation` -> CronJobs 或 on-demand Jobs
- `postgres` / `kafka` / `clickhouse` / `minio` -> 優先使用受管服務或專用 operator，而不是先自己維護單 repo manifest

## 先決條件

在編寫實際 K8s manifests 之前，先完成：

- 至少一次成功的真實 data plane cutover rehearsal
- backup / restore runbook 演練
- alert routing 與指標消費方案定稿
- batch job 調度策略定稿