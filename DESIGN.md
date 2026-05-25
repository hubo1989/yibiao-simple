---
name: "易标 AI"
description: "清晰、可靠、智能克制的投标标书智能体工作台"
colors:
  clear-tech-blue: "#09A4FA"
  clear-tech-blue-light: "#0ea5e9"
  clear-tech-blue-dark: "#0284c7"
  evidence-green: "#10b981"
  gate-amber: "#f59e0b"
  risk-red: "#ef4444"
  deep-ink-workbench: "#0f0d1a"
  deep-ink-surface: "#1a1825"
  deep-ink-elevated: "#231f35"
  cold-paper: "#ffffff"
  cold-paper-surface: "#f8fafc"
  cold-paper-elevated: "#eef2f7"
  dark-text-primary: "#f8fafc"
  dark-text-secondary: "#cbd5e1"
  light-text-primary: "#1f2937"
  light-text-secondary: "#4b5563"
  dark-border: "#2a2640"
  light-border: "#d6dbe4"
typography:
  display:
    fontFamily: "Inter, -apple-system, PingFang SC, Noto Sans SC, sans-serif"
    fontSize: "40px"
    fontWeight: 700
    lineHeight: 1.16
    letterSpacing: "normal"
  headline:
    fontFamily: "Inter, -apple-system, PingFang SC, Noto Sans SC, sans-serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "normal"
  title:
    fontFamily: "Inter, -apple-system, PingFang SC, Noto Sans SC, sans-serif"
    fontSize: "20px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, -apple-system, PingFang SC, Noto Sans SC, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, -apple-system, PingFang SC, Noto Sans SC, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.02em"
rounded:
  xs: "6px"
  sm: "10px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.clear-tech-blue}"
    textColor: "{colors.cold-paper}"
    rounded: "{rounded.md}"
    padding: "0 20px"
    height: "40px"
  button-secondary:
    backgroundColor: "{colors.deep-ink-surface}"
    textColor: "{colors.dark-text-primary}"
    rounded: "{rounded.md}"
    padding: "0 20px"
    height: "40px"
  button-ghost:
    backgroundColor: "{colors.cold-paper}"
    textColor: "{colors.light-text-secondary}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "40px"
  input-command:
    backgroundColor: "{colors.cold-paper}"
    textColor: "{colors.light-text-primary}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "44px"
  status-chip:
    backgroundColor: "{colors.cold-paper-surface}"
    textColor: "{colors.light-text-secondary}"
    rounded: "{rounded.full}"
    padding: "4px 12px"
---

# Design System: 易标 AI

## 1. Overview

**Creative North Star: "清澈控制台"**

易标的界面是一张清澈的项目控制台。它应该让投标负责人一眼看见项目当前步骤、风险位置、AI 建议和下一步动作，而不是让用户在菜单树里寻找功能。科技感来自信息组织、状态反馈和证据链，不来自炫光、装饰和复杂动效。

系统语气是清晰、可靠、智能克制。页面可以有清新的冷白空间、轻薄蓝色状态、细腻边框和适度阴影，但所有质感都要服务于可读性、可确认性和交付可信度。深色界面适合专注工作台，浅色界面适合长时间阅读、审查和编辑。

这个系统明确拒绝厚重菜单感、传统后台管理系统式的复杂导航堆叠、花哨营销页、大面积宣传 hero、空泛 AI 能力展示、暗黑霓虹 AI 工具感、过度玻璃拟态、炫光和渐变文字。

**Key Characteristics:**
- 单入口优先，用户从指令入口上传、搜索、继续和管理项目。
- 串行流程清晰，步骤、门禁、风险和可跳转状态必须同时可见。
- 证据默认可见，AI 结论必须带来源、置信度、待确认状态或下一动作。
- 组件克制一致，按钮、输入、徽章和容器遵循同一套状态语言。
- 清新但不轻浮，科技感体现在秩序、速度和可信反馈上。

## 2. Colors

这是一套冷白纸面与深墨工作台共存的 restrained palette，清澈科技蓝只用于主操作、当前选择、AI 状态和关键焦点。

### Primary

- **清澈科技蓝**: 主操作、当前步骤、AI 指令焦点、进度高亮和链接。它的出现必须稀少，越少越有指向性。
- **清澈科技蓝 Light**: hover、轻量 AI 标签、浅色背景上的可点击强调。
- **清澈科技蓝 Dark**: pressed、深色界面中的稳定焦点和高对比边框。

### Secondary

- **证据绿**: 已完成、证据已确认、审查通过。不要把它用于普通装饰。
- **门禁琥珀**: 风险待处理、缺材料、需要确认的前置条件。它表达需要动作，不表达失败。
- **风险红**: 废标风险、阻断错误、不可导出的硬性问题。只用于真实风险。

### Neutral

- **深墨工作台**: 深色主题的页面背景，用于专注处理复杂项目。
- **深墨 Surface / Elevated**: 深色主题的导航、面板、浮层和输入区域。
- **冷白纸面**: 浅色主题的正文、审查、编辑和长时间阅读背景。
- **冷白 Surface / Elevated**: 浅色主题的工具条、步骤容器、结果区域和浮层。
- **边框色**: 分隔层级，不承担强调职责。强调只能来自状态和动作。

### Named Rules

**The Blue Rarity Rule.** 清澈科技蓝不能铺满界面。它只用于主动作、当前选择、AI 焦点和可执行状态。

**The Status Means Work Rule.** 绿、琥珀、红必须对应真实工作状态。禁止用语义色做装饰色。

## 3. Typography

**Display Font:** Inter, -apple-system, PingFang SC, Noto Sans SC, sans-serif
**Body Font:** Inter, -apple-system, PingFang SC, Noto Sans SC, sans-serif
**Label/Mono Font:** JetBrains Mono, Fira Code, Consolas, monospace

**Character:** 单一 sans 字体保证产品界面的稳定和效率。中文界面依赖字重、字号、行距和留白建立层级，不使用显示字体制造风格感。

### Hierarchy

- **Display** (700, 40px, 1.16): 只用于原型首页或关键项目标题。不要用于卡片内部标题。
- **Headline** (700, 32px, 1.2): 用于页面级标题、项目流程页主标题。
- **Title** (650, 20px, 1.3): 用于面板标题、步骤组标题和重要对象名。
- **Body** (400, 14px, 1.6): 用于正文说明、步骤摘要、审查解释。长文本行宽控制在 65-75ch。
- **Label** (600, 12px, 0.02em): 用于状态标签、字段名、分组提示和短辅助信息。

### Named Rules

**The Work Surface Type Rule.** 产品界面使用固定字号尺度，禁止按视口宽度流式缩放字体。

**The No Slogan Rule.** 标题必须描述任务或对象，不写营销口号。

## 4. Elevation

易标使用“层级分明但不悬浮”的 elevation。默认用背景层、细边框和留白建立结构；阴影只用于浮层、hover、焦点或需要被用户立即注意的 AI 状态。静态页面区块不应像营销卡片一样漂浮。

### Shadow Vocabulary

- **Surface Low** (`0 1px 3px rgba(15, 23, 42, 0.08)`): 浅色主题中的轻量浮层和 toolbar。
- **Surface Medium** (`0 4px 12px rgba(15, 23, 42, 0.10)`): 下拉菜单、popover、小型确认区域。
- **Surface High** (`0 8px 30px rgba(15, 23, 42, 0.12)`): 侧栏、抽屉、重要详情面板。
- **AI Focus Glow** (`0 0 24px rgba(9, 164, 250, 0.16)`): AI 指令输入、生成中状态和当前步骤焦点。

### Named Rules

**The Grounded Surface Rule.** 页面主结构必须落在背景上。只有浮层、当前状态和交互反馈可以获得阴影。

## 5. Components

### Buttons

- **Shape:** 稳定的中圆角按钮，默认 12px，紧凑工具按钮可用 10px。
- **Primary:** 清澈科技蓝背景、冷白文字、高度 40px、水平 padding 20px。一个视图内只保留一个主要动作。
- **Hover / Focus:** hover 允许轻微亮度变化或 1px 边框强化；focus 必须有可见 ring。禁止夸张位移、弹跳和发光。
- **Secondary / Ghost:** Secondary 用于同级但非主动作；Ghost 用于返回、筛选、搜索和低风险命令。

### Chips

- **Style:** 胶囊形，12px 标签字，轻色背景，细边框或状态色弱底。
- **State:** chips 表达 prompt 建议、状态筛选和已确认条件。选中态必须同时使用文本、图标或边框变化，不能只靠颜色。

### Cards / Containers

- **Corner Style:** 面板和容器默认 12-16px，列表项 10-12px。
- **Background:** 深色主题使用深墨 Surface，浅色主题使用冷白 Surface。不要把所有内容都包成同款卡片。
- **Shadow Strategy:** 默认无阴影，hover 或浮层才出现低到中等阴影。
- **Border:** 1px 细边框用于分层。禁止使用粗侧边彩条作为状态表达。
- **Internal Padding:** 工具容器 16px，信息面板 20-24px，复杂详情区 24-32px。

### Inputs / Fields

- **Style:** 指令输入是核心入口，背景必须安静，边框清晰，placeholder 具体。普通输入默认 44px 高度，项目命令输入可更高。
- **Focus:** focus 使用清澈科技蓝边框和轻 ring。AI 指令入口可加极弱 glow，但不能玻璃化。
- **Error / Disabled:** error 使用风险红边框和明确文本；disabled 降低透明度并保留可读标签。

### Navigation

- **Style:** 导航应该轻，少层级，少菜单。项目内优先使用串行步骤、指令入口和上下文操作，避免厚重左侧功能树。
- **Active State:** 当前项使用背景层和清澈科技蓝文字，禁止大面积色块。
- **Mobile:** 先保留主任务、当前步骤和指令入口，次级导航折叠或移动到流程下方。

### Signature Component

**AI Command Entry** 是易标的标志组件。它既是创建项目入口，也是搜索项目、继续任务、修复风险和项目内调度入口。它必须清楚提示可做什么，执行后要展示识别到的项目、步骤、风险和下一动作。

## 6. Do's and Don'ts

### Do:

- **Do** 使用清澈科技蓝作为主动作和 AI 焦点，保持稀少和明确。
- **Do** 让项目流程串行可见，同时标出已完成、当前、可执行、风险和门禁状态。
- **Do** 为 AI 建议展示来源、引用位置、置信度、待确认状态或下一动作。
- **Do** 用浅色冷白纸面承载长时间审查和编辑，用深墨工作台承载专注状态和复杂流程。
- **Do** 为所有可交互组件提供 hover、focus、disabled 和 loading 状态。

### Don't:

- **Don't** 做厚重菜单感，不要传统后台管理系统式的复杂导航堆叠。
- **Don't** 做花哨营销页，不要大面积宣传 hero、装饰性卡片堆叠或空泛 AI 能力展示。
- **Don't** 做暗黑霓虹 AI 工具感，不要过度玻璃拟态、炫光、渐变文字或装饰性动效。
- **Don't** 使用粗侧边彩条表达状态。状态要通过完整边框、背景弱色、图标、文字和步骤结构表达。
- **Don't** 让一个页面出现多个同等强度的主按钮。用户必须知道下一步是什么。
