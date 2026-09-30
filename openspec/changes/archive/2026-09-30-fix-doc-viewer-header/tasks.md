# doc-viewer-header · 任务清单

## 1. 标题去重(渲染层)

- [x] 1.1 新增 `src/web/src/utils/markdown.ts`,导出 `stripLeadingTitle(content, title)`:跳过前导空行后,若首个非空行是 `# xxx` 且 `xxx.trim() === title.trim()` 则返回去掉该行(含其后空行)的正文,否则原样返回;验证:新增 `src/web/tests/markdown.test.ts` 12 用例(相等即剥离 / 不等不剥离 / 无 H1 / `#` 无空格 / 前导空行 / 中间 H1 保留 / 标题为空 / 空内容 / CRLF / 整篇仅标题)→ `npx vitest run tests/markdown.test.ts` 12 passed
- [x] 1.2 `MarkdownViewer` 渲染正文前套用该函数(`useMemo` 依赖 content 与 cleanedTitle);验证:`npm run build` 通过;组件级渲染断言「标题只出现一次」见 4.1

## 2. meta 行改为文档来源

- [x] 2.1 `MarkdownViewer` 的 meta 行去掉 `document.path` 项,新增来源项(本机用 `HomeIcon`,节点用 `GlobeIcon`);验证:`src/web/tests/doc-header.test.tsx` 断言「完整路径不出现在 meta 行」「本机文档显示本机」「节点文档显示节点名」「节点名缺失回退 node_id」→ 7 passed
- [x] 2.2 `Knowledge.tsx` 在文档归属节点(`node_id !== 'local'`)时拉取 `api.getNodes()` 解析节点名并传入(取不到回退 `node_id`);本机文档直接跳过不发请求;验证:实机打开本机文档,Network 无 `GET /api/nodes`;节点文档场景由 2.1 的组件测试覆盖
- [x] 2.3 `src/web/src/i18n/{zh,en}.ts` 增加 `knowledge.source` / `knowledge.sourceLocal`;验证:`npm test` 中 i18n-parity 与 i18n-usage(无裸 key、无硬编码中文)均通过

## 3. 过滤下拉文案

- [x] 3.1 `filetree.allStatus` 缩短(zh「全部状态」/ en `All statuses`);验证:实机截图确认树工具栏下拉完整显示「全部状态」(改前为被裁断的「全部 RAG 状」)

## 4. 回归与验收

- [x] 4.1 前端验证基线:`cd src/web && npm test`(5 文件 35 用例全通过)+ `npm run build`(tsc + vite 成功);服务端 `187 passed, 1 deselected`、节点 `118 passed` 无回归
- [x] 4.2 `openspec validate 2026-09-30-fix-doc-viewer-header --strict` 通过
- [x] 4.3 端到端视觉验收:隔离 Hub(SQLite,:8899)+ 真实浏览器(playwright 无头 Chromium,1440×900)登录并打开 `AgentKnowledgeMesh/openspec/specs/document-conversion/spec.md` → 头部 innerText 为「面包屑逐段 → 标题 → 本机 / 2.4 KB / 时间 / 未向量化」,正文直接从 `## Purpose` 开始;截图存 `.workbuddy-ai/screenshots/doc-header-after.png`
