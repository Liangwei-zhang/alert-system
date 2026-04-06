# Main - 協調者
**Role**: 總調度，負責子Agent(SubRex/Enya/Rex)的管理與任務分配

**User**: Yvonne (6390423676, Telegram)

**Team**:
- SubRex: 技術執行 + OurBackyard項目運維 → OurBackyard群組(-5178309184)，部署port 6060
- Enya: 創意寫作 + GutterDoctor項目運維 → 群組(-5217202303)，部署port 7070
- Rex: 架構師 + SmartClean項目運維 → 群組(-5160556598)，部署port 8080

**Projects**: 
- OurBackyard-PoC (SubRex, port 6060)
- GutterDoctor (Enya, port 7070)
- SmartClean (Rex, port 8080)
- Stock-Fix (已停止)
- OurBackyard-SDK (Enya, port 8080)
- mem9 (Main, port 8081)

**今日端口記錄 (2026-04-02 → 2026-04-03)**:
| Port | 項目 | Agent | 狀態 |
|------|------|-------|------|
| 3000 | stock-fix-demo | Main | ✅ 運行中 |
| 6060 | p2p-sdk (OurBackyard) | SubRex | ✅ 運行中 |
| 7070 | GutterDoctor | Enya | ⏸️ 明早啟動 |
| 8080 | p2p-fixed (SmartClean) | Rex | ⏸️ 明早啟動 |
| 8082 | mem9 (mnemo-server) | Main | ✅ 運行中 |

**Docker 服務器（明日啟動）**:
```bash
# TURN 服務器
cd ~/OurBackyard-PoC/coturn && docker compose up -d

# mem9 數據庫
docker run -d --name mem9-pgvector -p 5432:5432 ankane/pgvector
docker run -d --name mem9-mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=xxx mysql:8.0

# SmartClean 數據庫
docker run -d --name smartclean_postgres -p 5433:5432 -e POSTGRES_PASSWORD=xxx postgis/postgis:15-3.4
docker run -d --name smartclean_redis -p 6379:6379 redis:7-alpine
docker run -d --name smartclean_pgbouncer -p 6432:5432 -e DATABASE_URL=postgres://xxx edoburu/pgbouncer:latest
```

**端口狀態總結 (2026-03-24)**:
- 3000: stock-fix 前端 ✅
- 3001: stock-fix API ✅
- 6060: p2p-sdk ✅
- 8080: p2p-fixed (Rex) ✅
- 18789: OpenClaw Gateway ✅

**單項監控 (alert-listener.js)**: ✅ 運行中

**已停止的服務**:
- 6061: node 服務
- 7070: GutterDoctor
- 8080: SmartClean
- 8081: mem9 (mnemo-server)
- 8082: mem9-web
- 8084: godot-export
- 8085: 備用服務

**Docker 已停止**:
- ourbackyard-turn
- mem9-pgvector, mem9-mysql
- smartclean 系列

**Skills**: 29個已安裝

---

## Cron 任務格式（租房列表）

搜尋結果統一格式：
```
【房源1】
標題：xxx
租金：xxx/月
房型：x臥x衛
位置：xxx
連結：https://xxx

【房源2】
...
```

每個房源獨立區塊，資訊完整，連結用完整網址。

---

## Cron 任務（黃金價格預警）

- 早間：8:00
- 晚間：20:00

格式：
```
🟢 黃金期貨 GC
📅 日期 | 交易中

當前價格：xxx
漲跌：xxx
昨收：xxx
最高：xxx
最低：xxx
```

---

## 預警系統 (alert-system)

**狀態**: ✅ 全部完成

**監控標的**: 11個 (黃金、白銀、銅 + NVDA, TSLA, IVN.TO, AAPL, MSFT, BTC, ETH, WTI原油)

**API**: http://localhost:3000

**功能**:
- ✅ PostgreSQL 資料庫
- ✅ Redis 緩存
- ✅ Web Dashboard (http://localhost:3000)
- ✅ 自訂預警規則
- ✅ Telegram/Email/Line 通知
- ✅ JWT 認證
- ✅ Docker 部署

---

**stock-fix 項目**:
- GitHub: https://github.com/Liangwei-zhang/stock-fix
- Gen 3.1 算法：三層驗證 (SFP+CHOCH+FVG)，Sigmoid 概率，ATR 動態閾值
- 數據源：Binance (Crypto) > Polygon.io > Yahoo Finance
- 模擬交易：LocalStorage 持久化

---

**Fix**: Token爆→群組發/start重置
