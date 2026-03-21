# 🎮 Sudoku TMA - 技術規格文檔

## 🏗️ 系統架構

```
┌─────────────────────────────────────────────────────────────────┐
│                      Sudoku Telegram Mini App                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    React Frontend                         │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │   │
│  │  │   Menu     │  │   Game     │  │    Won     │        │   │
│  │  │  選難度    │  │   遊戲     │  │   獲勝     │        │   │
│  │  └────────────┘  └────────────┘  └────────────┘        │   │
│  │                        │                                 │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │              Sudoku Engine                       │    │   │
│  │  │  - 生成算法  - 求解算法  - 難度控制              │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Telegram SDK (@telegram-apps/sdk-react)      │   │
│  │  - 用戶信息  - 啟動參數  - Theme                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Local Storage (持久化)                        │   │
│  │  - 最佳紀錄  - 遊戲設置                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 技術棧

| 層級 | 技術 | 版本 |
|------|------|------|
| **框架** | React | 18.x |
| **語言** | TypeScript | 5.x |
| **構建工具** | Vite | 8.x |
| **Telegram SDK** | @telegram-apps/sdk-react | 最新 |
| **樣式** | CSS3 (Variables) | - |
| **狀態管理** | React Hooks (useState, useEffect) | - |
| **本地存儲** | localStorage | - |

## 📁 項目結構

```
sudoku-tma/
├── src/
│   ├── App.tsx          # 主應用組件
│   ├── App.css          # 樣式
│   ├── main.tsx         # 入口文件
│   └── vite-env.d.ts    # Vite 類型
├── public/
│   └── favicon.ico
├── index.html            # HTML 模板
├── package.json          # 依賴配置
├── tsconfig.json         # TypeScript 配置
├── vite.config.ts        # Vite 配置
└── README.md             # 項目文檔
```

## 🔧 核心模組

### 1. SudokuGenerator (數獨生成器)
```typescript
class SudokuGenerator {
  generate(difficulty: number): { puzzle: Grid; solution: Grid }
  private fillBox(): void
  private solve(): boolean
  private isValid(): boolean
  private removeCells(): void
  private countSolutions(): number
}
```

### 2. Custom Hooks
| Hook | 功能 |
|------|------|
| `useTimer` | 計時器 (開始/暫停/重置) |
| `useStorage<T>` | localStorage 封裝 |

### 3. 遊戲狀態
```typescript
type GameState = 'menu' | 'playing' | 'won';
type Difficulty = 1 | 2 | 3 | 4;  // 簡單/中等/困難/專家
```

## 🎮 遊戲功能

| 功能 | 實現方式 |
|------|----------|
| 數獨生成 | 回溯算法 + 隨機填充 |
| 難度控制 | 移除格子數量 + 唯一解驗證 |
| 計時 | useEffect + setInterval |
| 筆記模式 | 候選數數組 |
| 錯誤檢查 | 與 solution 比對 |
| 提示 | 填入正確數字 |
| 生命值 | 錯誤次數計數 |
| 高亮 | 行/列/宮格 CSS class |
| 記錄 | localStorage |

## 🎨 UI 架構

```
App
├── Menu (遊戲選單)
│   ├── Logo + Title
│   ├── User Info (Telegram SDK)
│   ├── Difficulty Buttons
│   └── Best Times
│
├── Game (遊戲中)
│   ├── Header (返回/計時器/提示)
│   ├── Board (9x9 棋盤)
│   │   └── Cell (每個格子)
│   │       └── Notes (候選數)
│   └── Controls
│       ├── Numpad (數字鍵盤)
│       └── Actions (筆記/清除)
│
└── Won (結果)
    ├── Trophy Animation
    ├── Time Display
    └── Action Buttons
```

## 🔗 API 整合

### Telegram SDK
```typescript
import { init, useLaunchParams } from '@telegram-apps/sdk-react';

// 初始化
init();

// 獲取用戶信息
const lp = useLaunchParams();
lp.initDataUnsafe?.user?.first_name
```

### localStorage
```typescript
// 存儲
localStorage.setItem('sudoku-best', JSON.stringify(times));

// 讀取
JSON.parse(localStorage.getItem('sudoku-best') || '{}');
```

## 🚀 部署流程

### 開發
```bash
npm install
npm run dev          # 本地開發
lt --port 5173       # 隧道映射
```

### 生產
```bash
npm run build        # 構建輸出到 dist/
# → 部署到 Vercel / Netlify / Cloudflare Pages
```

### Telegram 配置
1. @BotFather → /newbot
2. /newapp → 選擇機器人
3. 輸入 Web App URL

## 📱 響應式設計

| 斷點 | 棋盤格子大小 |
|------|-------------|
| > 400px | 38px |
| ≤ 400px | 34px |

## 🔮 未來擴展

| 功能 | 技術 |
|------|------|
| 排行榜 | Telegram Leaderboard API |
| 每日挑戰 | 後端 API + 日期 seed |
| 廣告變現 | Adsgram SDK |
| P2P 對戰 | WebRTC |
| Steam 移植 | Godot / Cocos2d-x |

---
*最後更新: 2026-03-18*
