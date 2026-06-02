# BoneMet 应用图标（统一 `bonemet.ico`）

## 已定稿

**采用 `bonemet-icon.svg`（深色底 + 抽象椎体条 + 淡扫描环，Cursor 式简约科技风）。**

| 文件 | 说明 |
|------|------|
| `bonemet-icon.svg` | 矢量源稿（可改色/改形） |
| `bonemet.png` / `bonemet.ico` | 安装包用，由脚本生成 |

重新导出：

```bash
make export-icon
# 或 python scripts/export_bonemet_icon.py
```

打 release 包时会自动尝试运行 `export_bonemet_icon.py`。

---

## 设计说明（归档）

**风格参考：Cursor、Linear、Vercel** —— 简约、高级、科技感。

| 要素 | 建议 |
|------|------|
| 构图 | 圆角方形底 + **单一几何图形** 居中，小尺寸仍可辨认 |
| 图形 | **抽象脊柱/椎体**（3～4 个圆角横条略错位）或 **细扫描圆环 + 中心光点** |
| 配色 | 深色底（`#0d1117`～`#1e293b`）+ 青绿/薄荷渐变高光（医疗科技） |
| 质感 | 轻微渐变、可选极淡外发光；避免立体卡通、避免写实骨骼 |
| 禁止 | 文字、骷髅、肋骨、X 光人像、宠物骨、吉祥物小人 |

仓库内提供草稿矢量图，可作起点或给 AI 作风格参考：

- `installer/windows/bonemet-icon.svg`

导出流程：SVG → 1024×1024 PNG → 多尺寸 ICO。

---

## 文件放置

| 文件 | 用途 |
|------|------|
| `installer/windows/bonemet.ico` | Windows 安装包、快捷方式、控制面板 |
| `installer/windows/bonemet.png` | Linux 桌面菜单（256×256+，透明或深色底） |

打 release 包时会复制到安装目录根部的 `bonemet.ico` / `bonemet.png`。

### 从 SVG / PNG 生成 ICO

```bash
# 若已安装 ImageMagick（Git Bash 或 PowerShell）
magick installer/windows/bonemet-icon.svg -resize 1024x1024 installer/windows/bonemet.png
magick installer/windows/bonemet.png -define icon:auto-resize=256,128,64,48,32,16 installer/windows/bonemet.ico
```

或在线：PNG → ICO，勾选 16/32/48/256。

---

## 给 AI 绘图工具的提示词（简约科技风）

### 中文版（主提示）

```
高端医疗科技 SaaS 应用图标，类似 Cursor / Linear 的极简高级感。产品：BoneMet 骨显像辅助诊断工作站。

风格：极简、扁平偏轻拟物、深色模式友好、专业科技感；不要吉祥物、不要卡通小人、不要写实医学插画。

主体（二选一）：
A）深色圆角方形底（近黑 #0d1117 或深蓝灰 #1a2332），中央 3～4 个圆角胶囊形横条竖向略错位排列，像抽象椎体/脊柱符号；横条用青绿到薄荷渐变（#a5f3fc → #34d399），可选极淡外发光。
B）同色深底 + 细圆扫描环（低透明度）+ 中心一颗柔和光点，环与点均为青绿色系。

可选：极细同心圆或网格暗示「扫描」，透明度 10～20%，不要抢主体。

气质：冷静、精准、可信、现代；像开发者工具/AI 医疗平台，不是儿科 App。

禁止：狗骨头、哑铃形、骷髅、肋骨、X光、人形、文字、字母、水印、彩虹霓虹、复杂纹理。

构图：1:1，图形占 45～55%，大量留白（深色底上的呼吸感），1024×1024 PNG，无文字，边缘锐利。
```

### English

```
Premium medical-tech SaaS app icon, minimalist like Cursor or Linear. Product: BoneMet bone imaging workstation.

Style: minimal, flat with subtle depth, dark-mode friendly, professional tech — NO mascot, NO cartoon human, NO realistic anatomy.

Subject (pick one):
A) Dark squircle background (#0d1117 / #1a2332), center: 3-4 rounded capsule bars stacked with slight offset as abstract spine/vertebrae; cyan-to-mint gradient (#a5f3fc → #34d399), optional soft glow.
B) Same dark base + thin scan rings (low opacity) + soft center dot in teal/cyan.

Optional: very subtle concentric rings at 10-20% opacity.

NO: dog bone, dumbbell bone, skull, ribs, x-ray, human figure, text, letters, neon rainbow, busy texture.

1:1, mark 45-55% of frame, 1024 PNG, no text, crisp edges.
```

### 负向提示

```
卡通, 吉祥物, 小人, 可爱腮红, 狗骨头, 骷髅, 肋骨, X光, 照片, 文字, logo字母, 花哨, 渐变过多, 立体卡通, 儿童, 恐怖
mascot, chibi, dog bone, skull, ribcage, text, cluttered, childish
```

### 用现稿迭代时（若已有深色几何版）

```
将图标改为 Cursor 级极简：只保留深色圆角底 + 中央抽象椎体条或扫描环，去掉一切人物与文字；提高对比、减少装饰；青绿渐变高光；1024 无字 PNG。
```

---

## 与旧方案对比

| 方向 | 适用 |
|------|------|
| 可爱 Q 版小人 + 骨头淡影 | 科室友好、偏 C 端 |
| **简约科技几何（当前）** | **与 Cursor 同级气质、医院信息化/研发交付** ✅ |

---

## 生成后自检

- [ ] 缩至 **32×32** 仍清晰（不是糊成一团）  
- [ ] 像 **科技产品** 而非玩具/宠物/恐怖医学  
- [ ] **无文字**  
- [ ] `bonemet.png` + `bonemet.ico` 放入 `installer/windows/`  
- [ ] `make release-pack-windows` 验证快捷方式图标
