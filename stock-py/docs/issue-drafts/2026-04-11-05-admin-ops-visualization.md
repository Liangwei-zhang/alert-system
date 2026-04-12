# Issue 05: 强化稳定版 `/admin` 的运营与治理可视化

## 背景

当前 `/admin` 已经具备 operators、distribution、tasks、runtime、analytics、acceptance、calibrations 等能力，但部分场景仍更像 API console 而不是成熟的治理工作台。

## 目标

让 `/admin` 更清晰地承担“用户/推送/治理/监控”职责，并降低日常运维对手动 API 调用的依赖。

## 范围

- 增强 operators / users / task center / distribution 的可视化与操作反馈
- 补强 runtime / alerts / audit / acceptance 的信息组织
- 明确 admin 与 platform 的职责边界，避免把策略核心继续堆回 admin
- 优化 admin API console 的筛选、预填与调试可用性，但不让它变成主交互形态

## 建议实现边界

- 已有 calibration / signal results / signal quality 等面板保持在 admin 的治理定位，不重新定义为策略主入口
- admin 端应继续服务运营、审计、观察、应急操作，而不是完整承接策略实验
- 优先复用现有稳定版 `frontend/admin` 结构

## 涉及区域

- `frontend/admin/js/admin-app.js`
- `frontend/admin/js/api-maps.js`
- `frontend/admin/js/admin-data.js`
- `frontend/admin/*.html`
- 现有 `apps/admin_api/routers/*`

## 验收标准

- 常用 operators / tasks / runtime / acceptance 工作流不需要依赖手动拼 API 请求完成
- admin 中各能力域边界更清晰，页面说明与入口组织更接近当前真实产品职责
- 新增治理 UI 有对应静态 route / script / integration 验证

## 非目标

- 不把 `/admin` 重新扩成桌面策略工作台
- 不在这条 issue 内重做整套管理端视觉系统
