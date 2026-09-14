# UI 规范 · Web 前端

> 适用范围:`src/web/`。新增页面/组件前先读本文;规约地图见根目录 `AGENTS.md`。

## 0. 文档版本与变更记录

| 版本 | 变更 | 备注 |
| --- | --- | --- |
| v0.4 | 初版技术基线(React 18 / Vite / TS / react-markdown / i18n) | 保留 |
| v0.5 | **引入设计系统**:语义化色板 + 4/8 间距栅格 + 圆角/阴影/状态色 token;新增组件库基线(Sidebar / Topbar / Panel / Toolbar / Button / Badge / EmptyState / Toast / IconButton) | 本次 |

---

## 1. 技术基线

| 项 | 约定 |
| --- | --- |
| 框架 | React 18 + Vite + TypeScript(严格模式) |
| 渲染 | react-markdown + remark-gfm(GitHub 风格) |
| 状态 | 组件局部 state + Context(ThemeContext / i18n);不引入全局状态库,除非页面复杂度明确需要 |
| 请求 | 统一走 `src/api/client.ts`,组件内禁止直接 `fetch` 业务 API |
| 图标 | `src/components/Icon.tsx`(内联 SVG,**业务区禁止直接用 emoji,装饰性 emoji 仅出现在用户可见文案里且经 i18n**) |

## 2. 布局

### 2.1 全局栅格(Global Shell)
应用外壳固定为 **Sidebar + Main** 两区,Main 内再切两栏/三栏:

```
┌──────────────────────────────────────────────────────────────────────┐
│ Sidebar (固定宽,可拖拽 200–320,默认 240)        │ Main (flex)        │
│ ┌────────────────────────────────────────┐       │ ┌────────────────┐ │
│ │ Brand 标题 + Theme Toggle              │       │ │ Topbar         │ │
│ ├────────────────────────────────────────┤       │ ├────────────────┤ │
│ │ Nav (一级导航)                         │       │ │ Content        │ │
│ ├────────────────────────────────────────┤       │ │  - 知识库页    │ │
│ │ Context Panel (按页面变化)             │       │ │    三栏        │ │
│ │   - 仪表盘:无                          │       │ │  - 其他页      │ │
│ │   - 知识库:节点列表 / Filter           │       │ │    单栏        │ │
│ │   - 节点管理:无                        │       │ │                │ │
│ │   - 设置:无                            │       │ └────────────────┘ │
│ ├────────────────────────────────────────┤       │                    │
│ │ Footer (用户信息 + 退出 + 语言切换)    │       │                    │
│ └────────────────────────────────────────┘       │                    │
└──────────────────────────────────────────────────────────────────────┘
```

- 知识库页在 Main 内切 **三栏:Toolbar(顶部) / Tree Pane(中,可关) / Document Pane(右)**
- 节点管理、仪表盘、设置: **单栏** Content,Sidebar 仅导航
- 移动/窄屏(<1024px):Sidebar 折叠为抽屉;Tree Pane 默认收起,Document 占满

### 2.2 主要尺寸(token 见 §3)
- Sidebar 默认 `240px`,最小 `200px`,最大 `320px`
- Tree Pane 默认 `280px`,可拖拽 `200–480`
- 文档阅读区最大阅读宽度 `760px`(长正文居中、左对齐,避免超宽行)
- 顶部 Topbar 高 `48px`

## 3. 设计系统(Design Tokens)

> 所有颜色 / 间距 / 半径 / 阴影 / 字号必须来自 token。**禁止写死十六进制或裸 px**。

### 3.1 色板(Color Tokens)
| Token | 暗色 | 亮色 | 用途 |
| --- | --- | --- | --- |
| `--color-bg` | `#0d1117` | `#ffffff` | 页面底色 |
| `--color-surface-1` | `#161b22` | `#f6f8fa` | 卡片/面板/侧栏底 |
| `--color-surface-2` | `#21262d` | `#eaeef2` | 工具栏/二级背景 |
| `--color-surface-3` | `#2d333b` | `#d8dee4` | 悬停/Hover |
| `--color-border` | `#30363d` | `#d0d7de` | 常规描边 |
| `--color-border-strong` | `#444c56` | `#afb8c1` | 强调描边(选中态) |
| `--color-text` | `#e6edf3` | `#1f2328` | 主文字 |
| `--color-text-muted` | `#8b949e` | `#656d76` | 次要文字/标签 |
| `--color-text-subtle` | `#6e7681` | `#8c959f` | 三级文字/禁用提示 |
| `--color-accent` | `#58a6ff` | `#0969da` | 主色/链接/聚焦 |
| `--color-accent-hover` | `#79c0ff` | `#0550ae` | 主色悬停 |
| `--color-accent-soft` | `rgba(88,166,255,.12)` | `rgba(9,105,218,.10)` | 主色淡背景(选中/徽章) |
| `--color-success` | `#3fb950` | `#1a7f37` | 成功 |
| `--color-warning` | `#d29922` | `#9a6700` | 警告 |
| `--color-danger` | `#f85149` | `#d1242f` | 错误/危险 |
| `--color-danger-soft` | `rgba(248,81,73,.12)` | `rgba(209,36,47,.10)` | 错误淡背景 |
| `--color-shadow` | `rgba(0,0,0,.4)` | `rgba(0,0,0,.08)` | 阴影 |

### 3.2 间距 / 圆角 / 阴影
```css
--space-1: 4px;   --space-2: 8px;   --space-3: 12px;  --space-4: 16px;
--space-5: 20px;  --space-6: 24px;  --space-8: 32px;  --space-10: 40px;
--radius-sm: 4px; --radius-md: 6px; --radius-lg: 8px; --radius-xl: 12px;
--shadow-sm: 0 1px 2px var(--color-shadow);
--shadow-md: 0 4px 12px var(--color-shadow);
--shadow-lg: 0 8px 24px var(--color-shadow);
```

### 3.3 字号 / 行高
| Token | 用途 |
| --- | --- |
| `--text-xs` 12 / 1.4 | 标签/徽章/元信息 |
| `--text-sm` 13 / 1.5 | 表格/树/正文次要 |
| `--text-base` 14 / 1.6 | 正文 |
| `--text-md` 15 / 1.7 | Markdown 正文 |
| `--text-lg` 16 / 1.5 | 卡片标题 |
| `--text-xl` 20 / 1.4 | 区块标题 |
| `--text-2xl` 28 / 1.3 | 文档主标题 |
| `--text-3xl` 36 / 1.2 | Dashboard 数字 |

### 3.4 字体栈
```css
--font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
             "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC",
             "Helvetica Neue", Arial, sans-serif;
--font-mono: "JetBrains Mono", "SF Mono", "Fira Code", Menlo, Consolas, monospace;
```

## 4. 主题

- 暗色/亮色双主题,经 `ThemeContext`;颜色一律用主题变量,**禁止写死色值**(测试要点:每页两种主题都过一遍)
- 用户偏好存 `localStorage`(`akm.theme`)
- 跟随系统:`prefers-color-scheme`(可选)

## 5. 国际化(i18n,V0.4 起)

- 库:`react-i18next`;语言包:`src/i18n/zh.ts` / `en.ts`;默认 `zh`,回退 `zh`
- **组件内禁止硬编码用户可见文案**,一律 `t("命名空间.key")`
- 命名空间按页面/领域:`nav` `auth` `dashboard` `knowledge` `nodes` `settings` `common` `layout`;两包 key 必须同步(提交前 diff 检查)
- 语言偏好存 `localStorage`(键 `akm.lang`)
- **业务区不再使用 emoji 作为图标**(渲染不稳定、跨字体差异大),emoji 仅可作为 i18n 文案的一部分或装饰性点缀

## 6. 组件库基线(Components)

> 必须复用,禁止在页面里重新发明。所有 className 必须落在下文表格内。

| Class | 用途 | 关键 token |
| --- | --- | --- |
| `.app` | 全局 Grid Shell | `display: grid; grid-template-columns: var(--sidebar-w) 1fr` |
| `.app-sidebar` | 左侧栏(可拖拽改 `--sidebar-w`) | `bg: surface-1` |
| `.app-sidebar__section` | 分段(标题 + 内容) | `padding: space-3` |
| `.app-sidebar__footer` | 侧栏底部固定:用户信息 + 退出 + 语言 | `border-top; padding: space-3` |
| `.sidebar-brand` | 顶部品牌区 | `display: flex; gap: space-2` |
| `.nav` / `.nav__item` | 一级导航 | `.nav__item--active` 用 accent-soft + accent |
| `.icon-btn` | 方形图标按钮(主题切换等) | `--size: 32px` |
| `.btn` / `.btn--primary` / `.btn--ghost` / `.btn--danger` | 通用按钮 | `.btn--sm` 紧凑尺寸 |
| `.badge` / `.badge--indexed` / `.badge--pending` / `.badge--excluded` | 状态徽章 | `radius-xl; padding: 0 space-2` |
| `.input` / `.select` | 表单控件 | `height: 32px; radius-md` |
| `.toolbar` | 内容区顶部工具栏 | `padding: space-2 space-4; border-bottom; bg: surface-1` |
| `.toolbar__group` | 工具栏按钮组 | `display: flex; gap: space-1` |
| `.panel` | 三栏中的左/中/右 | `bg: bg; overflow: hidden` |
| `.panel__header` | Panel 顶部(可粘性) | `padding: space-3 space-4; border-bottom` |
| `.panel__body` | Panel 内容区 | `overflow-y: auto` |
| `.tree` | 文件树容器 | `padding: space-1; font-size: text-sm` |
| `.tree__item` / `.tree__item--active` | 树条目 | `radius-md; padding: space-1 space-2` |
| `.tree__toggle` | 折叠箭头 | `width: 16px; transition: transform .15s` |
| `.tree__icon` | 节点图标(emoji 容器,仅限此处) | `width: 16px` |
| `.doc-viewer` | 文档阅读容器 | `max-width: 760px; padding: space-8` |
| `.doc-viewer__header` | 文档头(标题 + meta + 面包屑) | `border-bottom; margin-bottom: space-6` |
| `.doc-toolbar` | 文档顶部工具(Edit/RAG) | `sticky; top: 0; bg: bg` |
| `.doc-empty` | 空/错/加载占位 | `display: grid; place-items: center; height: 100%` |
| `.empty-illustration` | 空态插画槽 | `width: 96px; height: 96px` |
| `.toast-host` | Toast 容器(全局右下) | `position: fixed; right: space-4; bottom: space-4; z: 1000` |
| `.card` | 卡片(Dashboard/节点列表) | `bg: surface-1; border; radius-lg; padding: space-5` |
| `.table` | 数据表 | `th 上方、下方 td 描边` |
| `.kbd` | 快捷键展示 | `font-mono; padding: 1px 4px; border; radius-sm` |

### 6.1 按钮 size 规则
- 默认:32px 高,水平 padding `space-3`
- `.btn--sm`:24px 高,水平 padding `space-2`,字号 xs

### 6.2 状态色与徽章映射
- `indexed` → `success`-soft 背景 + success 主色
- `pending` → `warning`-soft 背景 + warning 主色
- `excluded` → `text-muted`-soft 背景 + text-muted 主色
- `error` → `danger`-soft + danger
- `node online` → success
- `node offline` → text-subtle

## 7. 交互一致性

| 场景 | 约定 |
| --- | --- |
| 危险操作(删除节点/文档、吊销 token) | 二次确认弹窗(用 `window.confirm` 或自定义 Modal);文案含操作对象名 |
| 加载态 | 列表/树骨架或 spinner,**禁止无反馈白屏** |
| 空态 | 必须给引导文案 + 下一步动作(如"尚未选择文档,请从左侧文件树选择") + 视觉插画(`.empty-illustration`) |
| 错误 | 统一 toast(`.toast-host`);401 跳登录、403 提示无权限;**禁止 alert** 作为业务提示 |
| 长文本/路径 | `.truncate`(单行)或 `.clamp-2`(两行)+ title 悬浮 |
| 复制 Token/Plaintext | 一键复制到剪贴板,成功后 toast 提示 |
| 拖拽分隔条 | 悬停高亮 `--color-accent`,按住时高亮 + `cursor: col-resize` |

## 8. 响应式断点

| 断点 | 行为 |
| --- | --- |
| ≥1280px | 三栏完整 |
| 1024–1279px | Tree Pane 默认收起到 Icon Rail(80px),点开恢复 |
| <1024px | Sidebar 折叠为抽屉,Toggle 在 Topbar 左侧;Tree Pane 与 Document 切换显示 |

实现:统一用 CSS 媒体查询 + CSS 变量,避免 JS 监听 resize。

## 9. localStorage 键约定

统一前缀 `akm.`:

| Key | 类型 | 说明 |
| --- | --- | --- |
| `akm.theme` | `'dark' \| 'light'` | 主题 |
| `akm.lang` | `'zh' \| 'en'` | 语言 |
| `akm.sidebar` | `number`(像素) | 侧栏宽度 |
| `akm.tree.<node_id>` | `string[]` 目录路径 | 文件树展开状态(`<node_id>` 或 `local`) |
| `akm.tree.visible` | `'visible' \| 'collapsed'` | 知识库 Tree Pane 是否折叠 |
| `akm.auth` | `AuthSession` JSON | 登录会话 |

新增键须登记在本文件并写入 PR description。

## 10. 可访问性(A11y)

- 所有可点击元素必须有 `aria-label` 或文本内容
- 自定义按钮(`div role="button"`)必须同时处理 `Enter` 和 `Space`
- 颜色对比:正文/背景 ≥ 4.5:1(用 `--color-text` on `--color-bg` 已满足)
- icon-only 按钮必须有 `aria-label`

## 11. 性能与代码组织

- 单文件组件,**禁止超过 400 行**(被多次反复改的可拆 `<SubComp>`)
- 一个组件一个 `.tsx`,样式统一进 `index.css`(全应用单一样式入口,V0.5 不引 CSS Modules)
- 业务图标集中于 `components/Icon.tsx`,组件不直接 inline `<svg>`
- 严禁写死颜色:搜索 `#[0-9a-f]{3,6}` 仅允许出现在 token 定义段(§3.1)
