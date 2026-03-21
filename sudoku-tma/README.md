# 🎮 Sudoku TMA - 數獨小遊戲

這是一個 Telegram Mini App (TMA) 數獨遊戲，使用 Vite + React + TypeScript 開發。

## 🚀 快速開始

### 1. 安裝依賴
```bash
cd sudoku-tma
npm install
```

### 2. 啟動開發服務器
```bash
npm run dev
```

### 3. 創建公開訪問鏈接（用於 Telegram）
```bash
# 安裝 localtunnel
npm install -g localtunnel

# 啟動隧道
lt --port 5173
```

### 4. 配置 Telegram Bot
1. 打開 Telegram，搜索 @BotFather
2. 輸入 `/newbot` 創建機器人
3. 輸入 `/newapp` 選擇你的機器人
4. 輸入 Web App URL（localtunnel 提供的網址）
5. 點擊 BotFather 給你的鏈接開始遊戲

## 🎮 功能

- ✅ 4 種難度（簡單、中等、困難、專家）
- ✅ 計時器
- ✅ 候選數字功能
- ✅ 錯誤標記
- ✅ 最佳時間記錄
- ✅ 響應式設計（手機/電腦）
- ✅ Telegram SDK 整合

## 📁 項目結構

```
sudoku-tma/
├── src/
│   ├── App.tsx      # 遊戲邏輯
│   ├── App.css     # 樣式
│   └── main.tsx    # 入口
├── index.html
├── package.json
├── vite.config.ts
└── README.md
```

## 🔧 技術棧

- **前端框架**: React 18 + TypeScript
- **構建工具**: Vite
- **Telegram SDK**: @telegram-apps/sdk-react
- **樣式**: CSS Variables

## 🎯 未來擴展

- [ ] 排行榜功能（使用 Telegram User ID）
- [ ] 每日挑戰
- [ ] 廣告獲利（Adsgram）
- [ ] Steam 版本移植
- [ ] P2P 對戰模式（WebRTC）

## 📱 截圖

遊戲界面包含：
- 9x9 數獨棋盤
- 數字輸入鍵盤
- 計時器
- 難度選擇
- 獲勝畫面

---
*這個項目可以作為未來 Steam 遊戲的基礎*
