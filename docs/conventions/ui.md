# UI 规范 · Web 前端

> 适用范围:`src/web/`。新增页面/组件前先读本文;规约地图见根目录 `AGENTS.md`。

## 1. 技术基线

| 项 | 约定 |
| --- | --- |
| 框架 | React 18 + Vite + TypeScript(严格模式) |
| 渲染 | react-markdown + remark-gfm(GitHub 风格) |
| 状态 | 组件局部 state + Context(ThemeContext / i18n);不引入全局状态库,除非页面复杂度明确需要 |
| 请求 | 统一走 `src/api/client.ts`,组件内禁止直接 `fetch` 业务 API |

## 2. 布局

- 全局:`Layout` 侧栏(可拖拽调宽)+ 内容区;侧栏底部固定放:主题切换、语言切换、当前用户/登出
- 知识库页(Knowledge):三栏 —— 节点列表(左,窄)/ 文档树(中,默认收起)/ 文档渲染(右);窄屏(<1024px)两栏退化
- 节点管理、仪表盘:沿用现有单栏 + 表格/卡片模式

## 3. 主题

- 暗色/亮色双主题,经 `ThemeContext`;颜色一律用主题变量/既有 class,**禁止写死色值**(测试要点:每页两种主题都过一遍)
- 用户偏好存 `localStorage`

## 4. 国际化(i18n,V0.4 起)

- 库:`react-i18next`;语言包:`src/i18n/zh.ts` / `en.ts`;默认 `zh`,回退 `zh`
- **组件内禁止硬编码用户可见文案**,一律 `t("命名空间.key")`
- 命名空间按页面/领域:`nav` `auth` `dashboard` `knowledge` `nodes` `settings` `common`;两包 key 必须同步(提交前 diff 检查)
- 语言偏好存 `localStorage`(键约定见 §6)

## 5. 交互一致性

| 场景 | 约定 |
| --- | --- |
| 危险操作(删除节点/文档、吊销 token) | 二次确认弹窗,文案含操作对象名 |
| 加载态 | 列表/树骨架或 spinner,禁止无反馈白屏 |
| 空态 | 给引导文案 + 下一步动作(如"尚未选择节点") |
| 错误 | 统一 toast/提示;401 跳登录、403 提示无权限(服务端裁决为准) |
| 长文本/路径 | 截断 + title 悬浮 |

## 6. localStorage 键约定

统一前缀 `akm.`:`akm.theme` `akm.sidebar` `akm.lang` `akm.auth` `akm.tree.<node_id>`。新增键须登记在本文件。
