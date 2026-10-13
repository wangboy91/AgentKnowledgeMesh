# 本轮交付与验证状态

日期：2026-10-12。同一变更 2026-10-12-add-owner-remote-writeback，未重开、未归档。

## 需求、授权与完成范围

用户已确认“正文只在归属电脑，Hub 协调访问，另一台电脑不落盘”，随后明确批准“确定这样 开始迭代修改吧 然后早点闭环”。来源为委托提供的原任务 01a12e2b-e602-7495-a7dc-533559b1403b 用户 turns 01a12f5e-29fc-72c1-9ee8-2ee5daad0bdd、01a12f5e-e2b7-767b-9943-1eb72e30d5fe。此后明确要求先交付不依赖 Windows 写锁取舍的读取/权限/删除切片。

已实现默认关闭的 owner-readonly-v1：稳定 file_id/owner/代次/版本/hash 元数据、在线 owner 内存读取和单文件正文搜索、owner 单文件 read grant 与核验主体白名单、离线/不可达/超时明确失败、返回前身份/权限/版本/墓碑检查、源删除停供、防延迟消息复活、同路径重建新身份/授权、目录不可达不当删除。新元数据表没有 content/chunk/embedding/历史正文列，Node 元数据状态不存正文。

严格模式隔离旧全文 REST/WS/MCP；Node 严格分支不执行旧全文同步。没有新增 Web 页面或第三方正文 MCP，主体白名单默认空。写回保持未启用，API 对有写资格请求返回 501（viewer/只读 token 403），Node write action 不支持，不写磁盘或报告成功。完整写回闭环仍未完成；没有默认选取“所有本地编辑必须走 AKM”。

## 产品文件

新增：

- src/shared/akm_shared/owner_reader.py：Windows 锁定安全读取/POSIX nofollow 分支、稳定本地元数据、保守扫描/墓碑。
- src/server/app/models/owner_file.py：owner 文件、读取授权、版本 hash 元数据表。
- src/server/app/services/owner_gateway.py：单进程内存 RPC、会话绑定、断线/超时清理。
- src/server/app/api/owner_files.py：严格只读 API、owner WS 注册/manifest/回包、当前权限及返回屏障。
- src/server/app/middleware_owner.py：严格模式隔离旧全文路径。
- src/node/app/owner_readonly.py：元数据扫描与实时内存回复，不保存远端正文。
- server/node tests/test_owner_readonly.py：隔离闭环与运行编排。

接入修改：server config/db/main/API/model 聚合/MCP guards，Node config/runner/CLI；同步 README、AGENTS、docs/api-reference.md 与两个 .env.example。没有修改真实 .env 或凭据，未安装新包。现有共享包在虚拟环境为非 editable 安装，验证使用 PYTHONPATH 指向 src/shared；正式使用新模块需按正常发布/本地包构建流程交付，此轮不安装或部署。

## 验证与证据

- 定向：23 项新读取/删除/权限测试 + 原 HTTP MCP 14 项，37 passed，退出 0。
- Node 严格编排：3 passed，退出 0，纳入完整 Node 回归。
- 后端源码冻结前全测：239 passed；断线错误修正后：240 passed，退出 0。以下隔离复核必须另列，不能把这两次称完全隔离。
- Node 全测：157 passed，退出 0。
- 前端：npm run build -- --outDir ../../.workbuddy-ai/verification/owner-readonly-web-build-2026-10-12，退出 0；前端源码未修改。存在既有大包警告及验证目录不在项目根的提示，没有覆盖原 dist。
- openspec validate 2026-10-12-add-owner-remote-writeback --strict：退出 0。
- git diff --check：退出 0；尾空格检查与最终磁盘回读另行核验。

定向闭环是 Windows 上两个逻辑 owner（真实 OwnerReader 临时磁盘 + 真实 owner_websocket 消息处理 + 进程内队列传输）及 HTTPX ASGI。Node 编排使用模拟连接但实际运行分支。没有监听服务，不代表真实 Mac/Windows、多机网络、多 worker 或 PostgreSQL 验收。

日志在 .workbuddy-ai/verification/owner-readonly-server-final-2026-10-12.log、owner-readonly-node-final-2026-10-12.log。最终完全隔离回归使用新临时 AKM_DB_PATH/AKM_KNOWLEDGE_ROOTS/测试密钥，Node 使用临时 AKM_NODE_STATE_DIR/AKM_NODE_ENV_FILE；结果与日志在后续最终核验段追加。

## 隔离复核与实际副作用

复核发现既有 tests/test_auth_matrix.py 的 WS 用例虽隔离节点/账号，却通过 TestClient 生命周期调用默认库 init_db。此前全回归因此初始化了默认库的 owner_files、owner_read_grants、owner_versions 空表；只读核验各 0 行。未运行产品 owner 接入、写入真实 owner 正文或清理旧全文，未通过删除表掩盖初始化。不能把此前全测称完全隔离，也不能宣称默认库没有发生 schema 初始化。最终已明确隔离数据库/知识根/测试密钥重新执行。

## 剩余范围与写回阻塞

Windows 原失败实验：目标 CreateFileW GENERIC_READ(0x80000000)、share=FILE_SHARE_READ(1)、OPEN_EXISTING(3)、OPEN_REPARSE_POINT(0x00200000)；源临时文件 DELETE(0x10000)、share=7、OPEN_EXISTING；SetFileInformationByHandle FileRenameInfoEx(22)、flags=3、UTF-16LE 绝对目标路径。返回 False / GetLastError=32，关闭句柄后目标读为 old。实验只用临时文件，未重复失败实验；未接入的 owner_disk 原型已移除。

父会话提供的 Microsoft 原始资料结论与可恢复原位写取舍记录于 design.md；没有把它当已验证方案，也没有把原子保存改为可恢复保存。写回 CAS、operation_id/unknown 对账、真实磁盘保存 ack 和并发/异常恢复仍未实施。

旧正文/chunk/向量/历史/备份清理仍仅迁移方案，不执行永久删除。旧副本存在时不宣称整个部署零副本；切回默认模式会重新开放旧接口，不能当严格迁移后的安全回退。第三方 Agent/扩展/OS swap/用户手动复制不由应用自动保证。未验收恶意 Windows junction 替换、映射 I/O、第三方不落盘、真实跨设备或 PostgreSQL。

## 环境与 Git

当前终端/文件执行实际可用；早期一次续读 transport disconnected，后续成功，不承诺持续连接。首次核验 HEAD=0622a07，外部随后变为 45994ff；本会话未 git add/commit/push 或回退其他工作。原 HTTP MCP auth/会话归属修复保留，本轮 14 项安全回归再次通过。

未部署、付费调用、安装新基础设施、创建真实凭据、改系统安全设置或删除用户数据；旧完整方案附件没有重试/重建，也未声称已保存。独立只读切片已交付，完整功能仍留在同一变更待完成。

## 最终完全隔离核验

- 后端：显式将 AKM_DB_TYPE=sqlite、AKM_DB_PATH、AKM_KNOWLEDGE_ROOTS 指向新系统临时目录，AKM_SECRET_KEY 为合成测试值，PYTHONPATH 指向 src/shared；uv run --no-sync pytest -q --tb=short，退出 0，240 passed in 51.57s。日志 .workbuddy-ai/verification/owner-readonly-server-isolated-final-2026-10-12.log。
- Node：AKM_NODE_STATE_DIR/AKM_NODE_ENV_FILE/知识根指向新临时目录，PYTHONPATH 指向 src/shared；uv run --no-sync pytest -q --tb=short，退出 0，157 passed in 3.25s。日志 .workbuddy-ai/verification/owner-readonly-node-isolated-final-2026-10-12.log。
- 隔离首次失败：旧 test_smoke 将默认路径断言套于显式覆盖配置，1 failed/239 passed；已修正为检查 Settings.model_fields 的默认路径，支持合法临时 DB 覆盖。另一次删除途中测试收到安全的 503 而非预期 410（微小测试超时0.15秒在负载下到期），1 failed/239 passed；正常链路测试改用生产默认5秒，仅专门超时测试使用0.05秒。最终全回归通过，不把失败轮次当成功。
- OpenSpec 严格校验、git diff --check 及全部变更 Markdown 尾空格检查退出0/通过；基线正式 specs 未改，受影响8项能力新增模式例外 delta，加新 owner-remote-writeback 共9份 delta。
- 本会话未启动监听服务，所有验证进程均完成；无本会话遗留的监听服务。源码在最终全回归前冻结，随后只补文档。
- tasks.md：决策/授权2项及独立只读5项完成（7/16）；完整写回目标9项仍未完成，不归档或声称完整闭环。

## 隔离写回小实验后续结果

新增可重跑脚本 src/server/scripts/verify_owner_exclusive_write.py，只使用脚本自建系统临时文件和合成字节，不导入产品 app 或访问数据库。产品写回开关/源模块未修改。

最终命令退出0：外部已有写句柄→busy且不改字节；校验后跨进程写/截断/删除/rename拒绝32，替换拒绝5（无锁对照均成功）；同base请求至多一写，旧base重试conflict；此前外部修改conflict。另确定性子进程异常退出反例留下 NEW!INAL-COMPLETE 混合字节，证明原位写非崩溃原子。精确 API/标志、身份/hash/阶段和未验证项见 design.md，原始 JSON 在 .workbuddy-ai/verification/owner-exclusive-write-experiment-2026-10-12.json。首轮因错误码断言过窄退出1，日志另保留；未重复旧锁+原子替换失败实验。

没有实现恢复日志/持久 receipt，不能承诺崩溃恢复、丢ack幂等或映射/旧缓冲/恶意路径替换安全。实验通过不等于产品保存成功保证成立；保持产品只读和 PUT501，完整写回仍未完成。

原完整方案检查：docs/AgentKnowledgeMesh-功能架构与技术方案-2026-10-12.md 在本次只读核验中不存在，因此无实际大小/hash可核对；未下载或重建。上一报告的54245字节与预期SHA256仅为历史预期，不能冒充落盘结果。

后续实验完成后，任务总计10/19完成（此前7/16为只读切片交付时状态），完整写回目标9项仍保留未完成。最终原始JSON磁盘回读可解析：5组观察、all_observations_matched=true、safe_atomic_writeback_ready=false；实验脚本及新增记录尾空格检查通过。没有产品代码变动，不重复跑无新产品变化的全回归。
