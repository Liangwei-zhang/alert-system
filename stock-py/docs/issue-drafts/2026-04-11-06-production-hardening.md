# Issue 06: 生产硬化与高可用证据沉淀

## 背景

当前仓库已具备 compose-first 交付、load baseline、cutover rehearsal、K8s baseline、PgBouncer / Kafka / ClickHouse / MinIO 等骨架，但距离“有证据地证明可交付、可回滚、可扩容”仍有一段距离。

## 目标

把现有工具链与运行时能力进一步产品化，形成稳定的高可用与交付证据，而不只是分散脚本和文档。

## 范围

- 继续打磨 load baseline / cutover / threshold calibration 流程
- 强化 compose-first 交付下的运行时监控、告警与回滚证据
- 规划并逐步落实读路径缓存、notification fanout、scanner 分桶 / 分片
- 补齐对 production hardening 关键结论的自动化或半自动化沉淀

## 建议实现边界

- 以当前 compose-first 现实为主，而不是跳到 K8s-first 方案
- 优先沉淀证据与阈值治理，再谈更大规模架构升级
- 不在这条 issue 内引入新的基础设施大迁移

## 涉及区域

- `ops/`
- `Makefile`
- `docs/POST_MIGRATION_V2_PLAN.md`
- `apps/admin_api/routers/runtime_monitoring.py`
- `infra/observability/*`
- `domains/analytics/*`

## 验收标准

- baseline、cutover、runtime evidence 有清晰的标准目录、命令与验收产物
- 至少一项读路径缓存或 fanout / scanner 容量能力进入可验证实现，而非仅停留在文档
- 关键高可用结论可以通过已有 runbook / report / QA 命令复现

## 非目标

- 不在这条 issue 内直接宣布“已支持 300 万 DAU”
- 不做脱离当前仓库边界的全新部署体系重构
