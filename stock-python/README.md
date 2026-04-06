# stock-py

股票訂閱與預警系統 - Python 重構版

## 三端架構

### 1. 管理端 (Admin) - 用戶/推送/治理
- 用戶管理 (創建/編輯/刪除/權限)
- 訂閱管理 (計劃/狀態/過期)
- 推送管理 (設備/統計/手動推送)
- 項目治理 (任務/回測/分發/審計)

### 2. 桌面端 (Platform) - 股票/算法/預警
- 股票監控 (實時報價/監控列表/搜索)
- 核心算法 (信號生成/策略引擎/回測/Market Regime)
- 預警系統 (預警觸發/確認/分發)
- 持倉管理 (持倉展示/交易記錄/P&L)

### 3. 訂閱端 (Subscriber) - 客戶/預警/資料
- 認證 (登入/註冊/驗證碼)
- 資料輸入 (關注股票/持有股票/現金)
- 接收預警 (站內/WebPush/郵件)
- 數據展示 (總資產/持倉明細/現金)

## 技術棧

- **後端**: FastAPI (async/await)
- **數據庫**: PostgreSQL (asyncpg) + 連接池
- **緩存**: Redis
- **任務隊列**: Celery
- **實時**: WebSocket
- **UI**: Tabler HTML

## 支持 100萬日活

- ✅ FastAPI (async) - 高性能
- ✅ PostgreSQL 連接池 (20+40)
- ✅ Redis 緩存/限流/發布訂閱
- ✅ Celery 後台任務
- ✅ WebSocket 實時更新
- ✅ WebPush 瀏覽器推送
- ✅ 離線支持 (IndexedDB + Service Worker)

## 安裝

```bash
pip install -r requirements.txt
cp .env.example .env
# 編輯 .env 配置數據庫和 Redis

# 運行
uvicorn app.main:app --reload
```

## API 文檔

啟動後訪問: http://localhost:8000/docs

## 項目結構

```
stock-py/
├── app/
│   ├── api/
│   │   ├── admin/           # 管理端 API
│   │   ├── platform/        # 桌面端 API
│   │   └── subscriber/      # 訂閱端 API
│   ├── core/                # 核心配置
│   ├── models/              # 數據模型
│   ├── services/            # 業務服務
│   ├── tasks/              # 後台任務
│   └── scanner/            # 買賣 Scanner
├── static/
│   ├── pages/               # HTML 頁面
│   │   ├── admin/          # 管理端
│   │   ├── platform/       # 桌面端
│   │   └── subscriber/     # 訂閱端
│   └── js/                 # 客戶端 JS
├── docs/                   # 文檔
└── requirements.txt
```

## License

Apache 2.0