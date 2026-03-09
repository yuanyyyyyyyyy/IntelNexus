# 🚀 IntelNexus 市场版本 - 快速开始

## 新增功能快览

### 1️⃣ 多语言支持
- **位置**: 左侧边栏 → 设置 → 语言
- **支持**: 中文 / English
- 切换后整个应用界面实时更新

### 2️⃣ 多格式报告下载
- **位置**: 生成报告后，报告下方
- **格式**: 
  - **Markdown** - 轻便，易于编辑
  - **PDF** - 专业，便于打印分享
  - **Word (.docx)** - 可编辑，便于二次编辑
- **操作**: 选择格式 → 点击"📥 下载报告" → 自动下载

### 3️⃣ 报告内容优化
✨ 所有导出格式现在都包括：
- 详细的报告信息表（查询、生成时间、平台版本）
- 专业的格式和排版
- 完整的分析结果
- 版权声明

### 4️⃣ 自定义AI模型
- **位置**: 左侧边栏 → 设置 → "➕ 添加自定义模型"
- **支持类型**:
  - OpenAI (GPT-4等)
  - Anthropic (Claude等)
  - Ollama (本地模型)

#### 如何添加自定义模型：
1. 展开"➕ 添加自定义模型"
2. 输入模型名称（自定义，如 "my-gpt-4"）
3. 选择模型类型
4. 填写相应配置：
   - **OpenAI**: API Key、Base URL(可选)、模型ID
   - **Anthropic**: API Key、模型ID
   - **Ollama**: Base URL、模型名称
5. 点击"✅ 添加模型"

#### 使用自定义模型：
- 模型会自动出现在"AI模型"下拉框中
- 直接选择即可使用

#### 管理模型：
- 展开"📋 已添加的模型"查看所有自定义模型
- 点击"🗑️"删除不需要的模型

---

## 工作流演示

### 典型搜索流程

```
1. 输入搜索查询
   ↓
2. 选择搜索模式（网页/学术/新闻/社交）和AI模型
   ↓
3. 点击"搜索"
   ↓
4. 系统自动：
   - 优化查询
   - 多源搜索
   - 筛选结果
   - 抓取内容
   - 生成分析报告
   ↓
5. 生成报告后：
   - 选择下载格式
   - 点击下载
   ↓
6. 获得格式化的分析报告
```

---

## 配置说明

### 环境变量 (.env)
确保设置了必要的API密钥：

```env
# OpenAI
OPENAI_API_KEY=sk-xxx

# Anthropic
ANTHROPIC_API_KEY=xxx

# Google
GOOGLE_API_KEY=xxx

# 本地Ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434

# OpenRouter
OPENROUTER_API_KEY=xxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

### 自定义模型存储
自定义模型保存在: `data/custom_models.json`

结构示例:
```json
{
  "models": [
    {
      "name": "my-gpt4",
      "type": "openai",
      "config": {
        "model_name": "gpt-4",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-xxx"
      }
    }
  ]
}
```

---

## 常见问题

### Q: 如何使用Ollama本地模型？
A: 
1. 确保Ollama服务运行: `ollama serve`
2. 在"➕ 添加自定义模型"中选择"Ollama"
3. 输入模型名称（如 "llama2"）
4. 点击添加

### Q: PDF导出失败怎么办？
A: 
1. 确保已安装 `fpdf2`: `pip install fpdf2`
2. 检查内容中是否有特殊字符

### Q: 可以导出中文报告吗？
A: 
- Markdown: ✅ 完全支持
- Word: ✅ 完全支持
- PDF: ⚠️ 需要中文字体支持，推荐使用Word格式

### Q: 自定义模型不显示怎么办？
A: 
1. 检查 `data/custom_models.json` 是否存在且有效
2. 刷新页面
3. 检查控制台是否有错误信息

---

## 技术要求

### 最低配置
- Python 3.8+
- 4GB RAM
- 网络连接

### 推荐配置
- Python 3.10+
- 8GB+ RAM
- 有线网络

### 依赖包
```
streamlit>=1.0
langchain
langchain-openai
langchain-anthropic
langchain-google-genai
langchain-ollama
fpdf2
python-docx
```

---

## 文件结构

```
robin/
├── ui.py                 # 主应用界面
├── report_export.py      # 报告导出模块
├── custom_models.py      # 自定义模型管理
├── llm_utils.py          # LLM工具和模型配置
├── config.py             # 配置管理
├── data/
│   └── custom_models.json  # 用户保存的自定义模型
├── requirements.txt      # 依赖包
└── IMPROVEMENTS.md       # 详细改进说明
```

---

## 反馈和改进

有任何建议或问题？
- 查看 `IMPROVEMENTS.md` 了解详细的技术实现
- 检查项目 Issues
- 查看 AGENTS.md 了解开发指南

---

## 版本信息
- **版本**: 1.0 (Market Edition)
- **更新时间**: 2026年3月8日
- **状态**: ✅ 生产就绪

---

**祝您使用愉快！🎉**
