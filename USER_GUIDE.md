# IntelNexus 用户使用指南

> 本指南面向非技术用户，无需任何编程知识。
> 按照步骤操作，5 分钟内即可开始使用。

---

## 快速开始（3 步上手）

### 第一步：下载与解压

从 [GitHub Releases](https://github.com/yuanyyyyyyyyy/IntelNexus/releases) 下载最新版本，解压到任意文件夹（建议桌面或 D 盘根目录）。

你会看到两种版本：

| 文件名 | 适合谁 | 是否需要安装 Python |
|--------|--------|-------------------|
| `IntelNexus-Windows-*.zip` | **大多数人**（推荐） | 不需要 |
| `IntelNexus-Source-*.zip` | 有 Python 环境的用户 | 需要 |

---

### 第二步：启动程序

**EXE 版本（推荐）：**
1. 打开解压后的文件夹
2. 双击 **`launcher.bat`**
3. 等待几秒，浏览器会自动打开

**源码版本：**
1. 打开解压后的文件夹
2. 双击 **`start.bat`**（首次运行会自动安装依赖，约 2-5 分钟）
3. 等待浏览器自动打开

> 看到 IntelNexus 界面就成功了！

---

### 第三步：配置 AI 模型（必须）

IntelNexus 需要 AI 模型才能工作。推荐以下两种方式（任选其一）：

#### 方式 A：在线模型（推荐新手）

无需安装任何软件，只需一个 API Key。

1. 打开界面后，顶部会出现「三步接入 AI 模型」引导卡片
2. 选择提供商（推荐 **DeepSeek**，国内可用）
3. 获取 API Key：
   - DeepSeek：访问 https://platform.deepseek.com 注册，充值 ¥1 即可用很久
   - Moonshot：访问 https://platform.moonshot.cn 注册
   - 通义千问：访问 https://dashscope.console.aliyun.com 注册
4. 粘贴 API Key → 点击「测试连接」→ 点击「保存并启用」

#### 方式 B：本地模型（完全免费，需安装）

1. 下载安装 Ollama：https://ollama.com
2. 安装完成后，打开命令提示符（Win+R 输入 `cmd`），输入：
   ```
   ollama pull qwen2.5:7b
   ```
3. 等待下载完成（约 4GB），回到 IntelNexus 界面刷新即可

---

## 日常使用

### 搜索情报

1. 点击顶部「情报搜索」
2. 输入关键词（如「AI 安全」「数据泄露」）
3. 选择搜索模式（推荐「智能模式」）
4. 点击「情报搜索」按钮
5. 等待 30 秒 - 2 分钟，AI 自动生成报告

### 生成简报

1. 点击顶部「简报中心」
2. 勾选感兴趣的关注点（可多选）
3. 点击「生成简报」
4. 等待 1-3 分钟，AI 生成结构化情报简报

### 定时推送（可选）

1. 简报中心 → 订阅管理 → 添加订阅者
2. 配置推送渠道（邮件 / 企业微信 / 钉钉）
3. 设置推送时间和频率
4. 系统自动按时推送

---

## 常见问题

### 双击 launcher.bat 后浏览器没打开？

手动打开浏览器，访问 http://localhost:8501

### 提示「Python not found」？

你下载的是源码版本，需要先安装 Python：
1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.10 或更高版本
3. 安装时**务必勾选「Add python.exe to PATH」**
4. 安装完成后重新双击 start.bat

> 如果不想安装 Python，请改用 EXE 版本（IntelNexus-Windows-*.zip）

### 模型连接失败？

- **在线模型**：检查 API Key 是否正确、是否过期、余额是否充足
- **本地模型**：确认 Ollama 已启动（任务栏有羊驼图标）

### 搜索结果很少或为空？

- 检查网络连接是否正常
- 如果需要访问境外数据源，确保代理软件已开启
- 尝试更换搜索关键词

### 邮件发送失败？

- 检查 SMTP 密码是否为**授权码**（不是邮箱登录密码）
- 163 邮箱：端口填 `465`，密码填授权码
- 获取授权码：登录 163 邮箱 → 设置 → POP3/SMTP → 开启 → 生成授权码

### 如何更新版本？

1. 下载新版本 ZIP
2. 解压覆盖旧文件夹
3. 重新运行 launcher.bat（EXE 版）或 start.bat（源码版）
4. 你的数据（data 文件夹）不会丢失

---

## 文件说明

| 文件/文件夹 | 说明 | 能否删除 |
|------------|------|---------|
| `launcher.bat` | EXE 版启动器 | 不能 |
| `start.bat` | 源码版启动器 | 不能 |
| `IntelNexus.exe` | 主程序（仅 EXE 版） | 不能 |
| `data/` | 你的配置和数据 | 不能（会丢失配置） |
| `.env` | 环境变量配置 | 不能（含 API Key） |
| `USER_GUIDE.md` | 本指南 | 可以 |

---

## 获取帮助

- 项目地址：https://github.com/yuanyyyyyyyyy/IntelNexus
- 问题反馈：在 GitHub 提交 Issue
- 界面内帮助：点击侧边栏「使用帮助」按钮
