# 帳戶組執行手冊

> 狀態（2026-04-04）：auth / subscription / watchlist / portfolio / search 代碼主體已落地；目前已有 `tests/e2e/test_subscription_flow.py` 與 `tests/integration/account/test_account_router.py` 作為主鏈路與 account router baseline，更細的 integration 清單仍待逐域補齊。已刪除的 `domains/portfolio/projections.py` 不再屬於當前結構。

## 1. 目標

帳戶組負責最先搬遷的低風險高價值域：

- auth
- account
- subscription
- watchlist
- portfolio
- search

這一組完成後，整個 Python 專案才會有第一條完整的「登入 -> 查看資料 -> 修改資料 -> 開始訂閱」主鏈路。

## 2. 範圍邊界

帳戶組負責：

- 發碼、驗碼、登出、refresh
- profile、dashboard、update profile
- 開始訂閱與快照
- watchlist CRUD
- portfolio CRUD
- search symbols

帳戶組不負責：

- scanner
- notifications fanout
- push/email provider
- trade workflow
- TradingAgents submit / webhook

## 3. 開發順序

請嚴格照以下順序做：

1. `auth`
2. `account/profile`
3. `start-subscription`
4. `watchlist`
5. `portfolio`
6. `search`

不要顛倒順序。因為後面的 domain 會依賴前面的 auth、account、subscription state。

## 4. 必建文件

```text
infra/db/models/auth.py
infra/db/models/account.py
infra/db/models/watchlist.py
infra/db/models/portfolio.py
infra/db/models/symbols.py
domains/auth/schemas.py
domains/auth/repository.py
domains/auth/policies.py
domains/auth/service.py
domains/account/schemas.py
domains/account/repository.py
domains/account/service.py
domains/subscription/schemas.py
domains/subscription/repository.py
domains/subscription/policies.py
domains/subscription/service.py
domains/watchlist/schemas.py
domains/watchlist/repository.py
domains/watchlist/policies.py
domains/watchlist/service.py
domains/portfolio/schemas.py
domains/portfolio/repository.py
domains/portfolio/policies.py
domains/portfolio/service.py
domains/search/schemas.py
domains/search/repository.py
domains/search/service.py
apps/public_api/routers/auth.py
apps/public_api/routers/account.py
apps/public_api/routers/watchlist.py
apps/public_api/routers/portfolio.py
apps/public_api/routers/search.py
tests/unit/auth/
tests/unit/account/
tests/unit/subscription/
tests/unit/watchlist/
tests/unit/portfolio/
tests/unit/search/
tests/integration/auth/
tests/integration/account/
tests/integration/watchlist/
tests/integration/portfolio/
tests/integration/search/
```

## 5. 類與函數清單

### 5.1 Auth

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/auth.py` | `UserModel` | `users` ORM model |
| `infra/db/models/auth.py` | `EmailCodeModel` | `email_codes` ORM model |
| `infra/db/models/auth.py` | `SessionModel` | `sessions` ORM model |
| `domains/auth/schemas.py` | `SendCodeRequest` | `email` |
| `domains/auth/schemas.py` | `VerifyCodeRequest` | `email`, `code`, `locale`, `timezone` |
| `domains/auth/schemas.py` | `RefreshTokenRequest` | `refresh_token` |
| `domains/auth/schemas.py` | `AuthSessionResponse` | `access_token`, `refresh_token`, `user` |
| `domains/auth/repository.py` | `UserRepository` | `get_by_email()`, `get_by_id()`, `upsert_by_email()`, `update_last_login()` |
| `domains/auth/repository.py` | `EmailCodeRepository` | `create_code()`, `find_valid_code()`, `mark_used()`, `delete_expired()` |
| `domains/auth/repository.py` | `SessionRepository` | `create_session()`, `revoke_by_token_hash()`, `rotate_refresh_session()` |
| `domains/auth/policies.py` | `AuthPolicy` | `can_return_dev_code()`, `is_new_user()`, `validate_send_code_limit()` |
| `domains/auth/service.py` | `AuthService` | `send_code()`, `verify_code()`, `logout()`, `refresh()` |

### 5.2 Account / Subscription

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/account.py` | `UserAccountModel` | `user_account` ORM model |
| `infra/db/models/account.py` | `SubscriptionSnapshotModel` | `subscription_snapshots` ORM model |
| `domains/account/schemas.py` | `UpdateAccountRequest` | `name`, `locale`, `timezone`, `total_capital`, `currency` |
| `domains/account/schemas.py` | `AccountDashboardResponse` | `user`, `account`, `portfolio`, `watchlist`, `subscription` |
| `domains/account/repository.py` | `AccountRepository` | `get_profile()`, `get_dashboard()`, `upsert_account()`, `update_user_profile()` |
| `domains/account/service.py` | `AccountService` | `get_profile()`, `get_dashboard()`, `update_profile()` |
| `domains/subscription/schemas.py` | `StartSubscriptionRequest` | `account`, `watchlist`, `portfolio`, `allow_empty_portfolio` |
| `domains/subscription/repository.py` | `SubscriptionRepository` | `save_snapshot()`, `update_user_subscription_extra()`, `load_subscription_summary()` |
| `domains/subscription/policies.py` | `SubscriptionPolicy` | `build_state()`, `validate_start_request()`, `enforce_watchlist_limit()`, `enforce_portfolio_limit()` |
| `domains/subscription/service.py` | `StartSubscriptionService` | `start_subscription()` |

### 5.3 Watchlist

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/watchlist.py` | `WatchlistItemModel` | `user_watchlist` ORM model |
| `domains/watchlist/schemas.py` | `CreateWatchlistRequest` | `symbol`, `notify`, `min_score` |
| `domains/watchlist/schemas.py` | `UpdateWatchlistRequest` | `notify`, `min_score` |
| `domains/watchlist/repository.py` | `WatchlistRepository` | `list_by_user()`, `get_by_id()`, `get_by_user_and_symbol()`, `create()`, `update()`, `delete()` |
| `domains/watchlist/policies.py` | `WatchlistPolicy` | `normalize_symbol()`, `validate_min_score()`, `enforce_plan_limit()` |
| `domains/watchlist/service.py` | `WatchlistService` | `list_items()`, `add_item()`, `update_item()`, `delete_item()` |

### 5.4 Portfolio

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/portfolio.py` | `PortfolioPositionModel` | `user_portfolio` ORM model |
| `domains/portfolio/schemas.py` | `CreatePortfolioRequest` | `symbol`, `shares`, `avg_cost`, `total_capital`, `target_profit`, `stop_loss`, `notify`, `notes` |
| `domains/portfolio/schemas.py` | `UpdatePortfolioRequest` | 更新字段可選 |
| `domains/portfolio/repository.py` | `PortfolioRepository` | `list_by_user()`, `get_by_id()`, `get_by_user_and_symbol()`, `create()`, `update()`, `delete()` |
| `domains/portfolio/policies.py` | `PortfolioPolicy` | `normalize_symbol()`, `validate_numbers()`, `enforce_plan_limit()` |
| `domains/portfolio/service.py` | `PortfolioService` | `list_positions()`, `add_position()`, `update_position()`, `delete_position()` |

### 5.5 Search

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/symbols.py` | `SymbolModel` | `symbols` ORM model |
| `domains/search/schemas.py` | `SearchSymbolsQuery` | `q`, `limit`, `cursor` |
| `domains/search/repository.py` | `SearchRepository` | `search_symbols()`, `get_symbol_by_code()` |
| `domains/search/service.py` | `SearchService` | `search_symbols()` |

## 6. Router 函數清單

| 文件 | 函數 | 路由 |
|---|---|---|
| `apps/public_api/routers/auth.py` | `send_code()` | `POST /v1/auth/send-code` |
| `apps/public_api/routers/auth.py` | `verify_code()` | `POST /v1/auth/verify` |
| `apps/public_api/routers/auth.py` | `logout()` | `POST /v1/auth/logout` |
| `apps/public_api/routers/auth.py` | `refresh()` | `POST /v1/auth/refresh` |
| `apps/public_api/routers/account.py` | `get_profile()` | `GET /v1/account/profile` |
| `apps/public_api/routers/account.py` | `get_dashboard()` | `GET /v1/account/dashboard` |
| `apps/public_api/routers/account.py` | `update_profile()` | `PUT /v1/account/profile` |
| `apps/public_api/routers/account.py` | `start_subscription()` | `POST /v1/account/start-subscription` |
| `apps/public_api/routers/watchlist.py` | `list_watchlist()` | `GET /v1/watchlist` |
| `apps/public_api/routers/watchlist.py` | `create_watchlist_item()` | `POST /v1/watchlist` |
| `apps/public_api/routers/watchlist.py` | `update_watchlist_item()` | `PUT /v1/watchlist/{id}` |
| `apps/public_api/routers/watchlist.py` | `delete_watchlist_item()` | `DELETE /v1/watchlist/{id}` |
| `apps/public_api/routers/portfolio.py` | `list_portfolio()` | `GET /v1/portfolio` |
| `apps/public_api/routers/portfolio.py` | `create_position()` | `POST /v1/portfolio` |
| `apps/public_api/routers/portfolio.py` | `update_position()` | `PUT /v1/portfolio/{id}` |
| `apps/public_api/routers/portfolio.py` | `delete_position()` | `DELETE /v1/portfolio/{id}` |
| `apps/public_api/routers/search.py` | `search_symbols()` | `GET /v1/search/symbols` |

## 7. 每個功能的實作順序

### 7.1 `auth/send-code`

順序：

1. `SendCodeRequest`
2. `EmailCodeRepository.create_code()`
3. `AuthPolicy.validate_send_code_limit()`
4. `AuthService.send_code()`
5. `router.send_code()`
6. unit test
7. integration test

### 7.2 `auth/verify`

順序：

1. `VerifyCodeRequest`
2. `EmailCodeRepository.find_valid_code()` / `mark_used()`
3. `UserRepository.upsert_by_email()`
4. `SessionRepository.create_session()`
5. `AuthService.verify_code()`
6. `router.verify_code()`
7. unit / integration test

### 7.3 `account/start-subscription`

順序：

1. `StartSubscriptionRequest`
2. `SubscriptionPolicy.validate_start_request()`
3. `AccountRepository.get_dashboard()`
4. `SubscriptionRepository.save_snapshot()`
5. `StartSubscriptionService.start_subscription()`
6. outbox `account.subscription.started`
7. router 測試

### 7.4 `watchlist create/update`

必做：

- symbol `trim + upper`
- plan limit 驗證
- 重複 symbol 檢查
- outbox `watchlist.changed`

### 7.5 `portfolio create/update`

必做：

- symbol `trim + upper`
- 數值正數驗證
- plan limit 驗證
- outbox `portfolio.changed`

## 8. 事件與交接點

帳戶組要輸出的事件：

- `account.subscription.started`
- `watchlist.changed`
- `portfolio.changed`

這三個事件是交給訊號組與數據組的正式接口，payload schema 必須固定。

## 9. 驗收標準

帳戶組完成的判準：

- 登入、登出、refresh 可跑通
- account dashboard 結構與現有產品口徑一致
- start-subscription 保持現有校驗邏輯
- watchlist / portfolio 的 symbol normalization 行為與現有修復後版本一致
- search API 可用且不掃全表

## 10. 不要做的事情

- 不要把通知 fanout 寫進 `start_subscription()`
- 不要在 watchlist / portfolio router 裡直接操作 outbox
- 不要在 search service 內調第三方 provider
- 不要在 account service 裡直接產生 scanner 任務

帳戶組只負責把核心使用者資料域做乾淨，後續聯動由事件和其他組承接。