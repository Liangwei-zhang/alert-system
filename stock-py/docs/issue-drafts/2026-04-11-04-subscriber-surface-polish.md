# Issue 04: 完善稳定版 `/app` 订阅端体验

## 背景

当前 `/app` 已有 auth、watchlist、notifications、离线草稿等基础入口，但交互深度与信息展示仍偏轻，离“正式产品面”还有距离。

## 目标

在不改变稳定版纯 HTML/JS 路线的前提下，把 `/app` 从可演示壳层推进到可持续使用的订阅端界面。

## 范围

- 完善验证码登录、会话恢复、错误提示与状态反馈
- 补强资产总览、watchlist、持仓与通知中心的展示深度
- 补齐 WebPush 注册/解绑的用户可理解流程
- 优化表单保存、本地草稿与同步动作的一致性

## 建议实现边界

- 直接复用现有 `/v1/auth/*`、`/v1/account/*`、`/v1/notifications/*`、`/v1/watchlist/*`
- 不引入新的 subscriber 端技术栈
- 优先把“已有能力可见、可理解、可恢复”做好，而不是先追求复杂动画或重设计

## 涉及区域

- `frontend/app/*`
- `apps/public_api/routers/ui.py`
- 现有 public auth / account / watchlist / notifications 路由

## 验收标准

- 用户能完成登录、恢复会话、查看资产概览、维护 watchlist、管理通知的完整闭环
- WebPush 开关、注册状态、失败提示对非技术用户可理解
- `/app` 首屏、通知中心与关键表单有基本 smoke / route 测试

## 非目标

- 不在这条 issue 内做新的移动端框架迁移
- 不在这条 issue 内把订阅端扩成策略工作台
