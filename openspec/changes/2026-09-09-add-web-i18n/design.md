# Design: add-web-i18n

## Context

现状:`src/web` 全部文案为 JSX 内硬编码中文;`ThemeContext` 已建立 Context + localStorage 的偏好管理模式(`akm.theme`),语言偏好沿用同一模式(`akm.lang`)。规范见 [docs/conventions/ui.md](../../docs/conventions/ui.md) §4。

## Goals / Non-Goals

**Goals:**
- 迁移后行为与视觉零变化(中文默认即现状)
- 新文案接入成本最低(两包各加一行)
- key 漂移可被自动化检出

**Non-Goals:**
- 第三种语言、服务端(Accept-Language)协商、时区/数字本地化
- 后端错误消息翻译(接口 detail 保持现状,由前端按状态码映射本地化文案)

## Decisions

1. **`react-i18next` + `i18next`**(社区标准,React 18 兼容):初始化 `fallbackLng: "zh"`,`returnNull: false`;备选轻量自研 Context 方案(无依赖,但缺插值/复数/回退生态),弃。
2. **单一命名空间文件对**(`zh.ts` / `en.ts`,内部按命名空间分组导出)而非按命名空间拆多文件:当前文案量级小,双文件 diff 即可审阅一致性;量级增长后再拆。
3. **语言解析顺序**:localStorage `akm.lang` → 默认 `zh`;不读浏览器语言(避免与显式默认冲突,保持可预期)。
4. **parity 校验用测试实现**:vitest/现有测试设施内加一个"两包 key 集合 diff"用例,构建期即可拦截;不引入独立 lint 工具。
5. **后端错误文案前端映射**:`client.ts` 已统一 401/403 处理,提示文案经 `t()` 输出;接口 `detail` 原文作为次要信息展示。

## Risks / Trade-offs

- [迁移遗漏(死文案)] → 迁移按页面逐个进行 + 硬编码扫描任务;中文默认下遗漏不炸,仅 EN 下露中文,验收走查覆盖
- [key 命名失控] → ui.md §4 固定命名空间清单,新增命名空间须先改规范
- [切换瞬间未翻译区块闪烁] → i18next 同步初始化,仅语言包加载后的重渲染,可接受

## Migration Plan

1. 安装依赖 + 初始化(默认 zh,零行为变化)→ 2. 按页面迁移(Layout → Dashboard → Knowledge → Nodes → 其余)→ 3. 切换入口与持久化 → 4. parity 测试
回滚:移除切换入口即可,语言包与 t() 调用无副作用。

## Open Questions

无。
