# 2026-10-12 HTTP MCP 小切片验证

## 结果

基线 main / HEAD / 缓存 origin/main 均为 e6151a3b62041b625954150cee20a6e65da7e411。开始时工作区干净。未联网刷新远端，不把缓存引用称作实时远端状态。

旧源码上的进程内 HTTP SSE/POST 实测：1 个查询测试通过、8 个权限测试失败，退出 1。viewer 用户与 viewer API Token 的 create/update 都返回写入成功；跨用户、跨 API Token、同用户新 JWT 回发返回 202。全部资料和凭据仅存在于测试内存库，没有生产测试。

最小修复后：定向测试 11 passed，后端全测 214 passed。统一 authorize_principal 由 REST 与 HTTP MCP 共用；工具使用每次 POST 的当前 Principal。SSE 使用 SDK 的凭证归属检查，以凭证摘要绑定会话。SDK 下限从 >=1.0.0 收紧为已安装、已锁定的 >=2.0.0，未安装新包。

## 三个查询

1. 跨电脑资料如何同步？关键词“跨电脑同步”，1 命中，详情包含 Hub 汇聚 Node Markdown。
2. 工作交接应记录什么？关键词“工作交接”，1 命中，详情包含目标、已完成工作、证据和唯一下一步。
3. RAG 是什么流程？关键词“检索增强生成”，1 命中，详情包含先检索片段再支持回答。

实际链路：ASGI GET /api/search → require_auth(viewer) → 内存 SQLite title/path/content LIKE → Document 序列化 → GET /api/documents/{id} 读取正文；同时核对 MCP 关键词格式。完整自然语言“工作交接应记录什么？”直接查询为 0 命中，说明当前关键词路径需要提取关键词。

查询原始结果：.workbuddy-ai/verification/query-trace-2026-10-12.json。三个问题没有调用生成模型，不属于完整语义 RAG 或回答质量评测。

## 命令与退出码

- .venv/Scripts/python.exe -m pytest tests/test_http_mcp_auth.py -q --tb=short：旧基线退出 1（8 failed, 1 passed）；修复后退出 0（11 passed）。
- uv run --no-sync pytest -q --tb=short：退出 0，214 passed in 42.40s。日志 .workbuddy-ai/verification/pytest-2026-10-12.log。
- npm run build -- --outDir ../../.workbuddy-ai/verification/web-build-2026-10-12：退出 0。日志 .workbuddy-ai/verification/web-build-2026-10-12.log。存在包体积警告，未改变前端代码或原有 dist。
- openspec validate 2026-10-12-fix-http-mcp-auth --strict：退出 0。
- uv lock --offline --project src/server：退出 1，缓存缺少 aiosqlite 的跨 Python 版本解析数据。没有联网补包。仅同步现有锁文件的 mcp 需求下限后，uv lock --check --offline --project src/server：退出 0，117 packages，解析版本未改变。
- git diff --check：退出 0。

## Library 文件阻塞

目标：D:\NewWorkAgent\AgentKnowledgeMesh\docs\AgentKnowledgeMesh-功能架构与技术方案-2026-10-12.md。
身份 libfile_5f9cae3329ec819196ddfa0e43667678，file_00000000fc2881f5afb817ccf14a26a9，版本 0，预期 54245 字节。
预期 SHA256：05ae1001ee121fd9fe8bad71cacd1591b685f84ccf05f185b9f209cbdef98fb4。

首次指定本机工作区返回 download_url；原样官方 helper 在 Windows Python 因无 os.setxattr 退出 1。现有 Ubuntu WSL Python 支持该 API，在授权临时目录的扩展属性读写测试退出 0。省略目标的 materialization 返回 workspace_path=/workspace/...，这是云端路径，不是本机；该对象不能用于签名下载。重新明确本机目标返回 download_url，原样官方 helper 在 WSL 下载失败，退出 1，已停止重试，没有改代理、网络、WSL 配置或 helper。

最终目标文件不存在，可读性、真实大小、实际哈希与 Library 身份均未验证。没有正文重建、绕过元数据或重复上传。

## 验证范围和一致性

OpenSpec 两个新增 requirement 均有实现及场景覆盖；授权小切片任务 7/7 完成。旧 Hub stdio 写工具由已有 test_document_write 回归覆盖。代码保留 Hub/Node/MCP/React/检索。

测试用进程内 ASGI（HTTPX raise_app_exceptions=False）、内存 SQLite 和临时验证数据库，未启动监听服务。未跑生产部署、真实外部 MCP 客户端、PostgreSQL 双路集成、Hub+Node 实机同步或语义模型评测。未 commit/push、全库索引、创建持久凭据或碰生产数据。未发现本轮需要额外用户审批的仓库约束，OpenSpec apply 返回 ready。

工程红线：通用产品内容、未改其他仓库、已同步 REST/MCP 契约文档、私有配置未入交付路径。变更工件留在 openspec/changes/2026-10-12-fix-http-mcp-auth，未归档，以便审阅工作区差异。

唯一下一步：通过支持 Windows 本机及身份元数据的 Library 传输路径获取原始方案，验证实际字节和预期 SHA256 后阅读；不扩大 Wiki 实施。

## 最后安全自查与传输诊断补充

官方 helper 的 WSL 输出只有 `library file transfer failed: download failed`（退出 1）。可确认的阶段为字节下载；未进入成功的最终文件安装与元数据验证。底层异常类型、HTTP 状态和证书诊断均未暴露，所以网络失败、证书失败、链接过期、明确权限拒绝四者都不能证实或排除。不能将统一错误包装成已查明的网络故障；没有证据认定是可恢复临时错误，停止刷新 transfer 和下载重试。原始 Windows 失败的精确异常为 AttributeError: module 'os' has no attribute 'setxattr'，发生在元数据应用阶段。

用户最小手动步骤：在 ChatGPT Library 找到现有“AgentKnowledgeMesh-功能架构与技术方案-2026-10-12.md”原生文件，选择下载，保存到本报告的目标 docs 路径；不要重新上传成副本。然后 PowerShell 执行 Get-Item（长度应为 54245）、Get-Content -Raw -Encoding utf8（验证可读）与 Get-FileHash -Algorithm SHA256（比对上述预期值）。继续保留本报告中的 Library ID、file ID 与版本 0。手工字节下载不等于本轮官方辅助程序已验证扩展属性，Library 身份元数据验证仍单列未完成，不宣称完整物化成功。

补测 `uv run --no-sync pytest tests/test_http_mcp_auth.py -q --tb=short`：退出 0，14 passed in 5.76s；日志 .workbuddy-ai/verification/http-mcp-final-2026-10-12.log。新增测试只覆盖现有修复的边界，没有增加产品功能：

- 当前 principal：HTTP Request 每次消息携带当前身份；admin 降级为 viewer 后写入拒绝，缺失 HTTP principal 返回错误。
- 撤销/禁用：API Token 吊销后 POST 返回 401；用户禁用后 POST 与 SSE 建连均返回 401。
- 匿名：POST 写调用与 SSE 建连均返回 401。
- viewer：用户和 API Token 的 create/update 结果 isError=true，内存库正文与行数不变；检索保持可用。
- 会话归属：跨用户、跨 API Token、同用户新 JWT 回发为 404；同凭证初始化及工具调用成功；断开后 404。
- 并发：admin 与 viewer 两条 SSE 同时调用各自工具，admin 创建成功、viewer 更新拒绝，数据库没有 unauthorized 内容；principal 不放在全局变量。
- stdio：无 HTTP Request 的工具上下文明确保持 Hub 本机信任，创建归属 local。此项验证为处理器测试，未运行外部 stdio 客户端。

pyproject.toml 与 uv.lock 的修改只将 mcp 需求下限 >=1.0.0 收紧为 >=2.0.0，以保证使用的 SSE 凭证归属与回调接口。现有虚拟环境与基线锁文件均已经是 2.0.0，无新增依赖、下载、安装或版本升级。

当前 git diff --stat（只计已跟踪文件）：8 files changed, 62 insertions(+), 15 deletions(-)。工作区修改：AGENTS.md、README.md、docs/api-reference.md、src/server/app/api/mcp.py、src/server/app/services/auth.py、src/server/app/services/mcp_server.py、src/server/pyproject.toml、src/server/uv.lock。新增：src/server/tests/test_http_mcp_auth.py；openspec/changes/2026-10-12-fix-http-mcp-auth 下的 .openspec.yaml、proposal.md、design.md、tasks.md、specs/mcp-integration/spec.md、verification.md。忽略目录 .workbuddy-ai 中保留查询、日志和构建证据，未提交。

最终代码冻结后的全回归：uv run --no-sync pytest -q --tb=short，退出 0，217 passed in 46.64s。日志 .workbuddy-ai/verification/pytest-final-2026-10-12.log。该次运行包含最后的 principal 类型注解与三项新增边界测试，替代前述 214 passed 作为最终后端证据。最终定向为 14 passed。随后只补充本验证报告，未再修改程序代码。OpenSpec 最后严格校验与 git diff --check 均退出 0；前端源码本轮始终未修改，之前成功构建仍对应最终前端源码。
