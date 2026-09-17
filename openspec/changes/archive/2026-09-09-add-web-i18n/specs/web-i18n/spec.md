# web-i18n 能力规格

## Purpose

Web 界面支持中文与英文切换:文案集中于语言包管理,用户选择持久化,为多语言使用者提供一致的界面体验。

## ADDED Requirements

### Requirement: Language Switching
Web 界面 SHALL 支持中文(`zh`,默认)与英文(`en`)切换;侧栏底部 SHALL 提供语言切换入口;用户选择 SHALL 持久化并在下次访问时恢复;未做过选择时默认中文。

#### Scenario: 切换语言即时生效
- **WHEN** 用户在侧栏点击 "EN"
- **THEN** 全部已渲染界面文案立即切换为英文,无需刷新

#### Scenario: 选择持久化
- **WHEN** 用户选择英文后刷新页面或重新打开浏览器访问
- **THEN** 界面仍为英文

#### Scenario: 首次访问默认中文
- **WHEN** 全新浏览器(无存储)访问 Web 界面
- **THEN** 界面为中文

### Requirement: Translation Coverage
用户可见文案 SHALL 全部经由翻译函数(`t("命名空间.key")`)输出,禁止组件内硬编码;语言包按命名空间组织(`nav` / `auth` / `dashboard` / `knowledge` / `nodes` / `settings` / `common`);英文包缺失的 key SHALL 回退显示中文,且不得显示裸 key。

#### Scenario: 硬编码扫描通过
- **WHEN** 对组件源码检查用户可见的中文字符串字面量
- **THEN** 除语言包文件外无硬编码文案

#### Scenario: 工具函数文案经调用侧注入
- **WHEN** 非组件的工具/格式化函数(如 `utils/format.ts` 的相对时间)需要输出用户可见文案
- **THEN** 该函数 SHALL 由调用侧注入 `t`(而非自行硬编码中文),其 key 同样纳入语言包与守卫测试

#### Scenario: 缺失 key 回退
- **WHEN** 英文包缺少某 key(如新增文案漏翻)
- **THEN** 界面显示该 key 的中文文案,而非 "ns.key" 裸键名

### Requirement: Language Packs Parity
`zh` 与 `en` 语言包 SHALL 保持 key 集合一致;两包的 key 差异 SHALL 可通过脚本或测试检出,防止长期漂移。

#### Scenario: 语言包一致性校验
- **WHEN** 运行前端校验(构建或专用测试)
- **THEN** 两语言包 key 集合不一致时报告差异明细
