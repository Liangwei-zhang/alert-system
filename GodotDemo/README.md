# 🎮 Godot Coin Collector Demo

## 安裝與運行

1. **下載 Godot Engine**
   - 官網：https://godotengine.org/
   - 推薦 Godot 4.x 版本

2. **打開項目**
   - 啟動 Godot
   - 點擊 "Import"
   - 選擇此資料夾路徑

3. **運行遊戲**
   - 按 F5 或點擊播放按鈕
   - 使用方向鍵移動
   - 按 Space 跳躍
   - 收集金幣得分

## 📁 項目結構

```
GodotDemo/
├── project.godot    # 項目配置
├── Player.tscn      # 玩家場景
├── Player.gd        # 玩家腳本
├── Coin.tscn        # 金幣場景
├── Coin.gd          # 金幣腳本
├── Main.tscn        # 主場景（地圖）
└── README.md        # 說明文件
```

## 🎯 操作說明

| 按鍵 | 功能 |
|------|------|
| ↑↓←→ | 移動 |
| Space | 跳躍 |

## 🔧 後續擴展建議

1. **計分 UI** - 添加 Label 顯示分數
2. **敵人 AI** - 簡單的追逐邏輯
3. **音效** - 收集金幣音效
4. **HTTP 集成** - 用 HTTPRequest 節點連接後端保存分數
5. **P2P 聯機** - 結合 WebRTC 實現多人遊戲
