# Tasks: add-web-i18n

## 1. 基础设施

- [x] 1.1 `package.json` 增加 `i18next` / `react-i18next` 并 `npm install`;新增 `src/i18n/index.ts`(初始化:fallbackLng zh、localStorage `akm.lang` 解析)与 `zh.ts` / `en.ts` 骨架;`main.tsx` 挂载后应用正常启动(`npm run dev` 冒烟)
- [x] 1.2 parity 测试:新增用例断言 zh/en 两包 key 集合一致,不一致时输出差异明细;`npx vitest run`(或现有测试入口)通过

## 2. 文案迁移(按页面,中文输出与迁移前逐字一致)

- [x] 2.1 `Layout.tsx` / `SearchBar.tsx`(nav 命名空间)+ 侧栏底部语言切换组件(中文 / EN,持久化验证)
- [x] 2.2 `Dashboard.tsx`(dashboard)+ `Nodes.tsx`(nodes)
- [x] 2.3 `Knowledge.tsx` / `FileTree.tsx` / `MarkdownViewer.tsx`(knowledge)
- [x] 2.4 其余组件与错误提示(common;`client.ts` 401/403 文案经 t() 映射)
- [x] 2.5 硬编码扫描:对 src(除 i18n/)grep 中文字符串字面量,结果为零(或仅剩注释)
  - 复核修正:`src/utils/format.ts` 的 `formatRelative()` 曾硬编码「刚刚 / N 分钟前 / N 小时前 / N 天前」(经 `Nodes.tsx` 的"最后心跳"列渲染),属漏网。已改为接收注入的 `t`,文案移入 `common.justNow` / `minutesAgo` / `hoursAgo` / `daysAgo`;`Nodes.tsx` 调用侧传 `t`
  - 已加永久守卫 `tests/i18n-usage.test.ts`(逐字符剥离注释后扫描 `src/` 字符串字面量),当前命中 0 处

## 3. 英文包补齐与验证

- [x] 3.1 `en.ts` 全量翻译(对照 zh 包逐 key);`npm run build` 通过
- [ ] 3.2 双语言全页面走查:每个页面在 zh / EN 下无裸 key、无漏翻、布局无溢出;localStorage 持久化与首次默认中文验证（**用户接入项**:build 通过;走查待确认）
  - 可静态核验部分已完成(无需浏览器):`tests/i18n-usage.test.ts` 全量核验 —— 源码 23 个文件、214 个 `t()` 字面量 key 全部可在 zh 包解析(无裸 key),en 侧同集合由 parity 测试保证;硬编码中文扫描 0 处;`formatRelative` 在中/英包下输出分别正确
  - 遗留(需人工浏览器):布局溢出、视觉走查、localStorage 持久化与首次默认中文
