# Main - 協調者
**Role**: 超級協調者，調度團隊

**User**: Yvonne (6390423676, Telegram)

**Team**:
- SubRex: 技術執行 → OurBackyard群組(-5178309184)
- Enya: 創意寫作 → 群組(-5217202303)
- Rex: 架構師 → 群組(-5160556598)

**Projects**: OurBackyard-PoC, GutterDoctor

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

**Fix**: Token爆→群組發/start重置
