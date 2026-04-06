# Definition of Done (DoD)

Each domain must meet the following criteria to be considered complete.

## Platform Domain

- [ ] Database migrations are functional and versioned
- [ ] Redis caching is integrated and tested
- [ ] Security middleware is applied to all endpoints
- [ ] Health check endpoints are operational
- [ ] Logging is structured and centralized
- [ ] Configuration is environment-driven

## Account Domain

- [ ] User registration works end-to-end
- [ ] Login with email/password is functional
- [ ] JWT tokens are generated and validated
- [ ] Token refresh mechanism works
- [ ] Email verification is implemented
- [ ] Subscription tiers are enforced
- [ ] Admin user management is operational

## Signal Domain

- [ ] Signal model supports all required fields
- [ ] Signal CRUD operations are functional
- [ ] Signal generation from OHLCV data works
- [ ] Signal triggering updates status correctly
- [ ] Signal expiration is handled
- [ ] Scanner workers generate buy/sell signals
- [ ] Backtesting service calculates metrics
- [ ] Signal statistics are accurate

## Notification Domain

- [ ] In-app notifications are created and delivered
- [ ] Unread count tracking works
- [ ] Mark as read functionality works
- [ ] Device registration for push works
- [ ] Push notifications are dispatched
- [ ] Email dispatch is async and reliable
- [ ] WebSocket connections are stable
- [ ] Real-time broadcasting works

## Portfolio Domain

- [ ] Portfolio CRUD operations work
- [ ] Position tracking is accurate
- [ ] Buy/Sell execution updates portfolio
- [ ] Cash deposit/withdrawal works
- [ ] P&L calculations are correct
- [ ] Transaction history is maintained

## Market Data Domain

- [ ] Stock quote retrieval works
- [ ] Batch quote fetching is supported
- [ ] Stock search returns results
- [ ] Historical data retrieval works
- [ ] Watchlist management is functional
- [ ] Real-time price updates via WebSocket

## Subscription Domain

- [ ] Subscription tiers define correct limits
- [ ] Feature flags are enforced per tier
- [ ] Trial period is handled correctly
- [ ] Subscription status changes work
- [ ] Admin can modify subscriptions

## Admin Domain

- [ ] Admin user CRUD operations work
- [ ] Role-based access is enforced
- [ ] System stats are calculated correctly
- [ ] Subscription management works
- [ ] Celery task monitoring works
- [ ] Audit logging captures all actions

## Quality Assurance

- [ ] Unit tests cover 80%+ of domain logic
- [ ] Integration tests pass for API endpoints
- [ ] E2E tests cover critical user flows
- [ ] Contract tests validate OpenAPI specs
- [ ] Load tests verify performance under load

## Documentation

- [ ] API endpoints are documented in OpenAPI spec
- [ ] Team execution guide is complete
- [ ] README is up-to-date
- [ ] Code comments explain complex logic

## Security

- [ ] Passwords are hashed (bcrypt)
- [ ] JWT tokens have expiration
- [ ] Authentication is required where needed
- [ ] CORS is properly configured
- [ ] Audit logs capture security events