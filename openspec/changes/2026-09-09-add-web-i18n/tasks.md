# Tasks: add-web-i18n

## 1. 基础设施

- [ ] 1.1 `package.json` 增加 `i18next` / `react-i18next` 并 `npm install`;新增 `src/i18n/index.ts`(初始化:fallbackLng zh、localStorage `akm.lang` 解析)与 `zh.ts` / `en.ts` 骨架;`main.tsx` 挂载后应用正常启动(`npm run dev` 冒烟)
- [ ] 1.2 parity 测试:新增用例断言 zh/en 两包 key 集合一致,不一致时输出差异明细;`npx vitest run`(或现有测试入口)通过

## 2. 文案迁移(按页面,中文输出与迁移前逐字一致)

- [ ] 2.1 `Layout.tsx` / `SearchBar.tsx`(nav 命名空间)+ 侧栏底部语言切换组件(中文 / EN,持久化验证)
- [ ] 2.2 `Dashboard.tsx`(dashboard)+ `Nodes.tsx`(nodes)
- [ ] 2.3 `Knowledge.tsx` / `FileTree.tsx` / `MarkdownViewer.tsx`(knowledge)
- [ ] 2.4 其余组件与错误提示(common;`client.ts` 401/403 文案经 t() 映射)
- [ ] 2.5 硬编码扫描:对 src(除 i18n/)grep 中文字符串字面量,结果为零(或仅剩注释)

## 3. 英文包补齐与验证

- [ ] 3.1 `en.ts` 全量翻译(对照 zh 包逐 key);`npm run build` 通过
- [ ] 3.2 双语言全页面走查:每个页面在 zh / EN 下无裸 key、无漏翻、布局无溢出;localStorage 持久化与首次默认中文验证
