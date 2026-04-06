# UI/UX Pro Max 技能

整合自 https://github.com/nextlevelbuilder/ui-ux-pro-max-skill

## 功能

提供專業 UI/UX 設計能力，基於 67 種 UI 風格、161 種配色方案、57 種字體搭配。

## 使用方式

當用戶請求 UI/UX 設計相關幫助時使用此技能。

### 1. 生成 UI 風格

根據描述選擇最佳風格：

| 風格關鍵詞 | 推薦風格 |
|-----------|----------|
| 簡潔、空白、極簡 | Minimalism & Swiss Style |
| 磨砂玻璃、半透明、模糊 | Glassmorphism |
| 軟 3D、凸起、童趣 | Claymorphism / Neumorphism |
| 粗獷、原始、對比強 | Brutalism |
| 霓虹、Cyberpunk、80s | Retro-Futurism |
| 深色、OLED、省電 | Dark Mode (OLED) |
| 3D、沉浸、遊戲 | 3D & Hyperrealism |
| 流動、液體、玻璃 | Liquid Glass |
| 動畫、交互、Micro-interactions | Motion-Driven / Micro-interactions |
| 落地頁、轉化、CTA | Hero-Centric / Conversion-Optimized |
| 儀表板、數據、BI | Data-Dense Dashboard / Heat Map |

### 2. 配色方案

從 `data/colors.csv` 選擇：

```css
/* 示例：Glassmorphism 配色 */
--glass-bg: rgba(255, 255, 255, 0.15);
--glass-border: rgba(255, 255, 255, 0.2);
--glass-blur: 15px;
```

### 3. 字體搭配

從 `data/typography.csv` 選擇配對。

### 4. 檢查無障礙

驗證 WCAG 對比度：

- WCAG AA: 4.5:1 (普通文字) / 3:1 (大文字)
- WCAG AAA: 7:1 (普通文字) / 4.5:1 (大文字)

### 5. 框架兼容輸出

根據選擇的風格輸出對應框架代碼：

- Tailwind CSS (10/10 最優)
- MUI / Material-UI
- Bootstrap
- Chakra UI
- Framer Motion (動畫)
- GSAP (動畫)

## 數據文件

- `styles.csv` - 67 種 UI 風格完整定義
- `colors.csv` - 161 種配色方案
- `typography.csv` - 57 種字體搭配
- `ux-guidelines.csv` - 99 條 UX 準則
- `charts.csv` - 25 種圖表類型

## 源路徑

原始數據：
```
/home/nico/.openclaw/workspace-main/ui-ux-pro-max-skill/src/ui-ux-pro-max/data/
```