# 字体授权汇总（IntelNexus 项目）

本目录（`static/fonts/`）及 `intelnexus/assets/fonts/` 下的字体资源授权信息如下。
所有字体均可免费用于本项目（含嵌入分发），但须遵守各自许可条款。

## 1. Inter

- **用途**：Web 端西文正文 / 标题
- **文件**：`static/fonts/inter/Inter-{Regular,Medium,SemiBold,Bold}.woff2`
- **许可**：SIL Open Font License 1.1（OFL）
- **版权**：Copyright 2020 The Inter Project Authors (https://github.com/rsms/inter)
- **来源**：google/fonts 仓库 variable 字体（Inter[opsz,wght].ttf）提取静态字重
- **许可原文**：https://github.com/google/fonts/blob/main/ofl/inter/OFL.txt（本地全文：`static/fonts/OFL.txt`）
- **许可摘要**：可自由使用、修改、分发与嵌入；须保留版权声明与许可文本；不得单独售卖字体本身。

## 2. JetBrains Mono

- **用途**：Web 端代码 / 数据 / 哈希展示
- **文件**：`static/fonts/jetbrains-mono/JetBrainsMono-{Regular,Bold}.woff2`
- **许可**：SIL Open Font License 1.1（OFL）
- **版权**：Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono)
- **来源**：google/fonts 仓库 variable 字体（JetBrainsMono[wght].ttf）提取静态字重
- **许可原文**：https://github.com/google/fonts/blob/main/ofl/jetbrainsmono/OFL.txt（本地全文：`static/fonts/OFL.txt`，与 Inter 共用同一全文文件）
- **许可摘要**：同 OFL 标准条款（见上）。

## 3. HarmonyOS Sans SC

- **用途**：Web 端简体中文显示
- **文件**：`static/fonts/harmonyos/HarmonyOSSansSC-{Regular,Medium,Bold}.woff2`
- **许可**：HarmonyOS Sans Fonts License Agreement（华为定制许可）
- **版权**：Copyright 2021 Huawei Device Co., Ltd.
- **来源**：GitHub 镜像仓库 ajacocks/harmonyos-sans-font（HarmonyOS_Sans_SC 子集，与华为官方发布版本一致）
- **许可原文**：本目录 `harmonyos/LICENSE.txt`（官方仓库 `HarmonyOS_Sans_SC/LICENSE.txt` 副本）；
  华为官方下载页：https://developer.huawei.com/consumer/cn/design/harmonyos-font/
- **主要条款**（以 LICENSE.txt 全文为准）：
  1. 须保留字体中的版权声明与许可文本；
  2. 不得对字体文件本身进行修改后重新分发（排版渲染、转换格式供本项目使用除外的情形请自行评估）；
  3. 不得单独售卖字体；字体可随应用 / 文档免费分发。

## 4. Noto Sans SC（思源黑体 · 简中）

- **用途**：PDF / Word / matplotlib 等导出链路中文渲染
- **文件**：`intelnexus/assets/fonts/NotoSansSC-{Regular,Bold}.ttf`（静态字重，非 variable，兼容 reportlab）
- **许可**：SIL Open Font License 1.1（OFL）
- **版权**：Copyright 2012 Google Inc. All Rights Reserved.（Noto Sans SC，源自思源黑体 / Source Han Sans SC）
- **来源**：google/fonts 仓库 variable 字体（NotoSansSC[wght].ttf）以 fontTools instancer 提取 wght=400 / 700 静态实例
- **许可原文**：https://github.com/google/fonts/blob/main/ofl/notosanssc/OFL.txt（本地全文：`intelnexus/assets/fonts/OFL.txt`）
- **许可摘要**：同 OFL 标准条款（见上）。

## OFL 许可全文位置（再分发合规）

按 OFL 1.1 第 2 条，再分发须随附许可全文，本项目全文文件位置：

- `static/fonts/OFL.txt`：Inter / JetBrains Mono（版权行含两个项目的声明）
- `intelnexus/assets/fonts/OFL.txt`：Noto Sans SC（版权行为 Copyright 2012 Google Inc.）

## OFL 通用条款提示

- 字体可自由使用、研究、修改与再分发（含嵌入应用、文档、网页）；
- 分发时须随附本许可文本与版权声明；
- 不得使用保留字体名称（Reserved Font Name）发布修改版（如适用）；
- 字体本身不得单独出售（可随软件捆绑销售）。
