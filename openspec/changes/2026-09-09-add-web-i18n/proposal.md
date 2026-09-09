# Proposal: add-web-i18n

## Why

Web 界面文案硬编码中文,无法服务非中文使用者;随着知识库作为内网 wiki 与产品基座被更多角色使用,需要中英文切换能力。

## What Changes

- 引入 `react-i18next`,语言包 `src/web/src/i18n/zh.ts` / `en.ts`,默认 `zh`,缺失 key 回退 `zh`
- 全部界面文案迁移为 `t("命名空间.key")` 调用;命名空间按页面/领域划分(`nav` / `auth` / `dashboard` / `knowledge` / `nodes` / `settings` / `common`)
- 侧栏底部新增"中文 / EN"切换入口,选择持久化到 `localStorage`(`akm.lang`)
- 语言包 key 双向同步约束写入 UI 规范(`docs/conventions/ui.md`),新增文案必须两包同补

## Capabilities

### New Capabilities

- `web-i18n`: Web 界面的多语言能力(语言包、切换、持久化、回退)

### Modified Capabilities

(无 —— 文案迁移是等价替换,不改变任何端点与交互行为)

## Impact

- **web**:全部组件文案迁移;新增 i18n 初始化与切换组件;`package.json` 新增 `react-i18next` / `i18next` 依赖
- **行为不变**:接口、路由、主题逻辑零改动;纯展示层变更
- **验证**:`npm run build` 通过;双语言全页面走查
