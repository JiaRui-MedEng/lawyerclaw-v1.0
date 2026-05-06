# 🔑 Tavily API Key 设置指南

## ❌ 当前问题

你提供的 API Key `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` 验证失败。

**可能原因：**
1. Key 复制时多了空格或字符
2. Key 还未在 Tavily 官网激活
3. Key 格式不正确

---

## ✅ 正确获取 API Key 的步骤

### Step 1: 访问 Tavily 官网

打开浏览器访问：**https://app.tavily.com**

### Step 2: 注册/登录

支持以下登录方式：
- 🔑 Google 账号
- 🔑 GitHub 账号
- 🔑 邮箱注册

### Step 3: 创建 API Key

1. 登录后进入 **Dashboard**
2. 点击左侧菜单 **API Keys**
3. 点击 **"Create API Key"** 按钮
4. 给 Key 起个名字（如 "百佑 LawyerClaw"）
5. 复制生成的 API Key

**正确的 API Key 格式：**
```
tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
（通常是 `tvly-` 开头，后面跟 30-40 个字符）

### Step 4: 添加到 .env 文件

编辑文件：`D:\Projects\Pycharm\lawyerclaw\backend\.env`

添加以下内容：
```bash
# Tavily AI 搜索
TAVILY_API_KEY=tvly-你的真实 API-Key
```

### Step 5: 验证 API Key

运行验证脚本：
```bash
cd D:\Projects\Pycharm\lawyerclaw\backend
python verify_tavily_key.py
```

**成功输出：**
```
API Key: tvly-xxxxx...
长度：50
前缀：tvly-

HTTP 状态码：200
响应：{"query":"test","results":[...]}
```

---

## 🆓 免费额度说明

- **1000 次/月** = 每天约 33 次
- 无需信用卡
- 注册即送

---

## 🔍 测试 API Key 是否有效

### 方法 1: 使用验证脚本

```bash
python verify_tavily_key.py
```

### 方法 2: 使用搜索测试

```bash
python quick_test_tavily.py
```

### 方法 3: 在线测试

访问 Tavily Dashboard 的 **Playground** 页面，直接测试搜索。

---

## 📝 常见问题

### Q1: API Key 无效怎么办？

**解决：**
1. 检查是否有空格：`tvly-xxx `（错误）vs `tvly-xxx`（正确）
2. 重新复制：从 Dashboard 重新复制
3. 检查前缀：必须是 `tvly-` 开头

### Q2: 额度用完了怎么办？

**解决：**
1. 等待下个月自动重置
2. 升级到 Starter 计划（$25/月，10000 次）
3. 使用缓存减少调用

### Q3: 中国用户能使用吗？

**可以！** Tavily 支持全球访问，无需特殊网络。

---

## 🎯 下一步

获取正确的 API Key 后：

1. **添加到 .env 文件**
   ```bash
   TAVILY_API_KEY=tvly-你的 Key
   ```

2. **运行测试**
   ```bash
   python quick_test_tavily.py
   ```

3. **开始使用**
   - 在对话中 AI 会自动使用 Tavily 搜索
   - 或手动调用 `tavily_search` 工具

---

## 📞 需要帮助？

- **Tavily 文档：** https://docs.tavily.com
- **Dashboard:** https://app.tavily.com
- **项目文档：** `docs/TAVILY_SEARCH.md`

---

**提示：** 如果你已经注册了 Tavily，请从 Dashboard 重新复制 API Key，然后更新到 `.env` 文件中。
