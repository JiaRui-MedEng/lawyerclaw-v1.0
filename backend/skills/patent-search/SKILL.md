# Registry disclosure: a 9235.net Patent API credential is required (not optional / not "no env vars").
# Provide via environment variable PATENT_API_TOKEN and/or OpenClaw config key skills.entries.patent-search.apiKey - see COMPLIANCE.md.
credentials_required: true
credential_env_vars:
  - PATENT_API_TOKEN
openclaw_skill_api_key: "skills.entries.patent-search.apiKey"

locales:
  en:
    title: "Patent Search Skill"
    description: "Search, view and analyze patents in OpenClaw (global databases). Requires a 9235.net API token: set PATENT_API_TOKEN or OpenClaw skills.entries.patent-search.apiKey."
    long_description: |
      # Patent Search Skill
      
      The Patent Search Skill enables you to search, view, and analyze patent information from global databases directly within OpenClaw. Whether you're conducting technology research, competitor analysis, or investment due diligence, this skill provides comprehensive patent intelligence at your fingertips.
      
      ## Key Features
      
      ### 🔍 Intelligent Patent Search
      - Natural language understanding - search like you're talking to a colleague
      - Advanced Boolean search syntax for precise results
      - Real-time search suggestions and auto-completion
      - Global coverage including CN, US, EP, JP, and WO patents
      
      ### 📊 Comprehensive Analysis
      - Multi-dimensional statistical analysis (applicant, IPC, timeline, legal status)
      - Visual trend charts and heat maps
      - Competitive intelligence and technology landscape mapping
      - Citation network analysis and similarity detection
      
      ### 🏢 Business Intelligence
      - Company patent portfolio analysis
      - Technology strength assessment
      - Innovation trend tracking
      - Risk assessment and opportunity identification
      
      ### 🎯 User Experience
      - Clean, intuitive interface with responsive design
      - Progressive disclosure - show details only when needed
      - Personalized search history and recommendations
      
      ## Use Cases
      
      ### For Researchers & Engineers
      - Technology landscape analysis
      - Prior art search for innovation
      - Technical solution reference
      - Patentability assessment
      
      ### For Business Professionals
      - Competitor technology monitoring
      - Investment due diligence
      - M&A technology assessment
      - Market entry strategy
      
      ### For Legal Professionals
      - Freedom-to-operate analysis
      - Patent infringement risk assessment
      - Portfolio management
      - Litigation support
      
      ## Getting Started
      
      1. **Install the skill**: `openclaw skills install patent-search`
      2. **Configure API Token**: Apply at https://www.9235.net/api/open
      3. **Start searching**: `patent search "your technology"`
      4. **Explore features**: Try analysis, company profiles, and more
      
      ## Examples
      
      ### Basic Search
      ```bash
      # Search by keyword
      patent search "drone"
      patent search "graphene"
      patent search "new energy vehicle"
      
      # Search with options
      patent search "drone" --page 2 --page-size 20
      patent search "drone" --sort applicationDate
      patent search "drone" --sort !documentDate  # descending order
      patent search "drone" --scope all  # global search
      patent search "drone" --details  # show detailed information
      ```
      
      ### Advanced Search
      ```bash
      # Field-specific search
      patent search "agency:Beijing Bosijia Intellectual Property Agency Co., Ltd."
      patent search "documentYear:[2020 TO 2024] AND lithium battery"
      patent search 'applicant:"Tsinghua University" AND artificial intelligence'
      patent search "drone AND type:invention-grant AND legalStatus:valid-patent"
      
      # Complex queries
      patent search "(drone OR autonomous vehicle) AND (radar OR sensor) AND applicationYear:[2020 TO 2024]"
      patent search "battery AND NOT mainIpc:H"
      patent search "battery AND type:invention-grant AND legalStatus:valid-patent AND province:Guangdong"
      ```
      
      ### Patent Details and Analysis
      ```bash
      # View patent details
      patent detail CN110382353B
      patent detail US9876543B2
      
      # View claims
      patent claims CN110382353B
      
      # View legal information
      patent law CN110382353B
      
      # Citation analysis
      patent citing CN110382353B
      
      # Find similar patents
      patent similar CN110382353B
      ```
      
      ### Company Analysis
      ```bash
      # Company patent portfolio
      patent company "DJI Technology Co., Ltd."
      patent company "Huawei Technologies Co., Ltd."
      
      # Statistical analysis by company
      patent analysis "applicant:Huawei Technologies Co., Ltd." --dimension ipc
      patent analysis "applicant:Alibaba Group Holding Limited" --dimension applicationYear
      ```
      
      ### Statistical Analysis
      ```bash
      # IPC classification distribution
      patent analysis "artificial intelligence" --dimension ipc
      
      # Applicant distribution
      patent analysis "lithium battery" --dimension applicant
      
      # Provincial distribution
      patent analysis "5G" --dimension province
      
      # Application trend analysis
      patent analysis "new energy vehicle" --dimension applicationYear
      ```
      
      ### File Operations
      ```bash
      # Download patent PDF
      patent download CN110382353B --type pdf
      
      # Download patent images
      patent download CN110382353B --type image
      
      # Download all files to specified directory
      patent download CN110382353B --type all --output ./patent_files/
      ```
      
      ### Natural Language Queries
      ```bash
      "Show me recent AI patents from Google"
      "Analyze battery technology trends"
      "Compare Apple and Samsung mobile patents"
      "Search for drone patents from DJI"
      "What are the latest 5G patents?"
      "Find similar patents to US9876543B2"
      ```
      
      ## Security & compliance disclosure
      
      - **SKILL.md encoding**: This file is maintained as plain UTF-8 (NFC) without zero-width or bidi-override characters. If a scanner still reports hidden characters, verify against a fresh checkout or hex view of the repository file.
      - **Credentials**: Your patent API token is taken only from (1) the `PATENT_API_TOKEN` environment variable, or (2) the OpenClaw CLI command `openclaw config get skills.entries.patent-search.apiKey` when you run scripts on a machine where the CLI is installed. This skill **does not** open or parse `~/.openclaw/openclaw.json` (or other dotfiles) directly.
      - **Network**: Requests use HTTPS to `https://www.9235.net/api` (third-party patent data service). Search text, patent IDs, and related parameters are sent as needed for the feature you invoke.
      - **Packaging**: Do not ship real tokens in the repository or skill bundle; use `config.example.json` plus env vars or OpenClaw config. Full text: see `COMPLIANCE.md` in this skill package.
      
      ## Support
      
      - **Email**: xxiao98@gmail.com
      
      ## License
      
      MIT License - Free for personal and commercial use.
  zh:
    title: "专利检索技能"
    description: "在 OpenClaw 中搜索、查看与分析全球专利数据。**必须**配置 9235.net 专利 API 凭证：环境变量 PATENT_API_TOKEN，或 OpenClaw 的 skills.entries.patent-search.apiKey。"
    long_description: |
      # 专利检索技能
      
      专利检索技能让您能够在OpenClaw中直接搜索、查看和分析全球专利数据库中的专利信息。无论您在进行技术调研、竞品分析还是投资尽职调查，本技能都能为您提供全面的专利情报。
      
      ## 核心功能
      
      ### 🔍 智能专利搜索
      - 自然语言理解 - 像与同事交谈一样搜索
      - 高级布尔搜索语法，获得精确结果
      - 实时搜索建议和自动补全
      - 全球覆盖，包括中国、美国、欧洲、日本和世界知识产权组织专利
      
      ### 📊 全面分析
      - 多维度统计分析（申请人、IPC、时间线、法律状态）
      - 可视化趋势图和热力图
      - 竞争情报和技术图谱
      - 引用网络分析和相似性检测
      
      ### 🏢 商业智能
      - 公司专利组合分析
      - 技术实力评估
      - 创新趋势跟踪
      - 风险评估和机会识别
      
      ### 🎯 用户体验
      - 简洁直观的响应式界面设计
      - 渐进式披露 - 仅在需要时显示详细信息
      - 个性化搜索历史和推荐
      
      ## 使用场景
      
      ### 研究人员和工程师
      - 技术图谱分析
      - 创新前案搜索
      - 技术方案参考
      - 专利性评估
      
      ### 商业专业人士
      - 竞争对手技术监控
      - 投资尽职调查
      - 并购技术评估
      - 市场进入策略
      
      ### 法律专业人士
      - 自由实施分析
      - 专利侵权风险评估
      - 组合管理
      - 诉讼支持
      
      ## 快速开始
      
      1. **安装技能**：`openclaw skills install patent-search`
      2. **配置API Token**：在 https://www.9235.net/api/open 申请
      3. **开始搜索**：`patent search "您的技术"`
      4. **探索功能**：尝试分析、企业画像等功能
      
      ## 示例
      
      ### 基础搜索
      ```bash
      # 按关键词搜索
      patent search "无人机"
      patent search "石墨烯"
      patent search "新能源汽车"
      
      # 带选项搜索
      patent search "无人机" --page 2 --page-size 20
      patent search "无人机" --sort applicationDate
      patent search "无人机" --sort !documentDate  # 降序排序
      patent search "无人机" --scope all  # 全球搜索
      patent search "无人机" --details  # 显示详细信息
      ```
      
      ### 高级搜索
      ```bash
      # 字段限定搜索
      patent search "agency:北京博思佳知识产权代理有限公司"
      patent search "documentYear:[2020 TO 2024] AND 锂电池"
      patent search 'applicant:"清华大学" AND 人工智能'
      patent search "无人机 AND type:发明授权 AND legalStatus:有效专利"
      
      # 复杂查询
      patent search "(无人机 OR 无人车) AND (雷达 OR 传感器) AND applicationYear:[2020 TO 2024]"
      patent search "电池 AND NOT mainIpc:H"
      patent search "电池 AND type:发明授权 AND legalStatus:有效专利 AND province:广东省"
      ```
      
      ### 专利详情和分析
      ```bash
      # 查看专利详情
      patent detail CN110382353B
      patent detail US9876543B2
      
      # 查看权利要求
      patent claims CN110382353B
      
      # 查看法律信息
      patent law CN110382353B
      
      # 引用分析
      patent citing CN110382353B
      
      # 查找相似专利
      patent similar CN110382353B
      ```
      
      ### 企业分析
      ```bash
      # 企业专利组合
      patent company "深圳市大疆创新科技有限公司"
      patent company "华为技术有限公司"
      
      # 按企业统计分析
      patent analysis "applicant:华为技术有限公司" --dimension ipc
      patent analysis "applicant:阿里巴巴集团控股有限公司" --dimension applicationYear
      ```
      
      ### 统计分析
      ```bash
      # IPC分类分布
      patent analysis "人工智能" --dimension ipc
      
      # 申请人分布
      patent analysis "锂电池" --dimension applicant
      
      # 省份分布
      patent analysis "5G" --dimension province
      
      # 申请趋势分析
      patent analysis "新能源汽车" --dimension applicationYear
      ```
      
      ### 文件操作
      ```bash
      # 下载专利PDF
      patent download CN110382353B --type pdf
      
      # 下载专利图片
      patent download CN110382353B --type image
      
      # 下载所有文件到指定目录
      patent download CN110382353B --type all --output ./patent_files/
      ```
      
      ### 自然语言查询
      ```bash
      "显示谷歌最近的AI专利"
      "分析电池技术趋势"
      "对比苹果和三星的手机专利"
      "搜索大疆公司的无人机专利"
      "最新的5G专利有哪些？"
      "查找与US9876543B2相似的专利"
      ```
      
      ## 安全与合规声明
      
      - **SKILL.md 编码**：本文件以 UTF-8（NFC）维护，不含零宽字符与双向文本覆盖控制符。若扫描器仍报隐藏字符，请对照仓库原始文件或十六进制查看。
      - **凭证**：专利 API Token 仅从 (1) 环境变量 `PATENT_API_TOKEN`，或 (2) 本机已安装 OpenClaw CLI 时通过命令 `openclaw config get skills.entries.patent-search.apiKey` 获取。本技能**不会**直接打开或解析 `~/.openclaw/openclaw.json` 等主目录下的配置文件。
      - **网络**：通过 HTTPS 访问第三方服务 `https://www.9235.net/api`；检索式、专利号及分页等参数会随功能需要发送。
      - **发布与仓库**：请勿在仓库或技能包内包含真实 Token；请使用 `config.example.json`，并通过环境变量或 OpenClaw 配置注入密钥。完整说明见技能包内 `COMPLIANCE.md`。
      
      ## 支持
      
      - **邮箱**：xxiao98@gmail.com
      
      ## 许可证
      
      MIT许可证 - 个人和商业使用免费。
