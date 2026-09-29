# Tasks: add-node-file-watch

> 状态:**实现、单测与端到端验证均已完成**。端到端经真实 Hub(SQLite,隔离实例)+ 真实 akm-node 进程执行。

## 1. 依赖与配置

- [x] 1.1 `src/node/pyproject.toml` 增加 `watchfiles>=0.21` 依赖
- [x] 1.2 `NodeSettings` 增加 `watch_enabled`(默认 `true`)、`watch_debounce_seconds`(3)、`watch_reconcile_seconds`(300)、`watch_exclude`(空);全部走 `AKM_` 前缀;单测覆盖默认值与环境变量覆盖
- [x] 1.3 `watch_reconcile_seconds=0` 表示关闭对账,单测确认循环立即返回、不退化为忙轮询

## 2. 过滤判定下沉(shared)

- [x] 2.1 在 `akm_shared.scanner` 抽出 `is_watchable_markdown`(扩展名 / 位于 root 下 / 隐藏项 / 排除目录;**不做 stat**,否则删除事件会被误过滤)与 `scan_one`(单文件完整扫描,含大小上限与可读性)
- [x] 2.2 `scanner.py` 的 `scan_single_root` 改用 `scan_one`,行为保持不变
- [x] 2.3 单测:扩展名(含 `.MD` 大小写)、隐藏项、隐藏根目录不误拒、内置排除、`extra_excluded`、root 外路径、删除事件可通过判定

## 3. 监听与对账循环(node)

- [x] 3.1 `runner.py` 新增 `_watch_loop()`:`awatch` 监听存在的知识根,`watch_filter` 走 2.1 判定,`debounce` 取配置;无知识根时空转等待而非退出
- [x] 3.2 `runner.py` 新增 `_reconcile_loop()`:按间隔调用 `sync_documents()`;间隔为 0 时不启动
- [x] 3.3 两循环内部捕获全部异常并退避重试,**不参与 `asyncio.wait(FIRST_COMPLETED)` 竞争退出**;断线/退出时由 cancel 收掉,避免重连后叠加多组循环
- [x] 3.4 `sync.py` 增加 `asyncio.Lock` 并发保护:串行化上传,单测断言并发触发时 `max_active == 1`
- [x] 3.5 启动日志打印监听状态(开启 / 关闭、监听目录、防抖与对账间隔)

## 4. 局部增量路径

- [x] 4.1 `sync.py` 增加 `sync_paths(changed, deleted)`:定位知识根 → `scan_one` → 与快照比对 → 复用 `build_payload` 上传
- [x] 4.2 **局部路径不产生 `deletions`**:仅 `Change.deleted` 事件进 `deletions`;单测覆盖"快照中存在但本轮未扫描到的路径不得进入 deletions"
- [x] 4.3 写入稳定性:`stat` 双检(间隔 300ms,比对 `st_size` 与 `st_mtime_ns`),不稳定则跳过该文件且不阻塞本轮其他文件
- [x] 4.4 单测:空变更集不发请求、变更全部被过滤时不发空请求、单文件变更 payload 只含该文件、多根前缀一致、失败不动快照、rejected 不入快照

## 5. 服务化模板(deploy/,直接改,不属本变更工件)

- [x] 5.1 `deploy/install-akm-node.sh` 安装完成后打印 systemd user unit 与 launchd plist 模板及启用命令
- [x] 5.2 `deploy/install-akm-node.ps1` 打印 Windows 计划任务注册命令(`Register-ScheduledTask`)
- [x] 5.3 `deploy/docker-compose.node.yml` 设 `AKM_WATCH_ENABLED=false` 并注明"bind mount 不传播 inotify";`deploy/.env.example` 新增第 9 节说明四个 `AKM_WATCH_*` 变量

## 6. 端到端验证(真实 Hub + Node,已执行)

- [x] 6.1 Hub+Node 同机:新增 `.md` → Hub 端该文档出现,**实测延迟 0.53s**(远优于 10s 目标)
- [x] 6.2 修改 → hash 更新(0.52s);删除 → Hub 文档消失(0.27s);检索不再命中该文档
- [x] 6.3 关闭监听(`AKM_WATCH_ENABLED=false`)→ 启动日志明确提示"依赖定时对账",文件由全量对账路径收敛(日志无任何 `Local sync` 行,证明监听确实未运行)
- [x] 6.4 断网 30 秒后恢复 → 变更不丢:期间新增 + 修改各一,Hub 恢复后重连同步报 `created=1 updated=1`,两条变更均落库
- [x] 6.5 事件风暴:批量创建 100 个 `.md` → 防抖生效,**仅 1 轮上传**(`Local sync: 100 full-text`),100 个全部到达 Hub
- [x] 6.6 删除一个文件的同时修改另一个 → 两个变更均生效,且 `notes/seed.md` 等其余文件未被误删
- [x] 6.7 附加:重启节点后无变更轮次仅报 `0 full-text, N hash-only`,`created=0 updated=0 deleted=0`(近乎零流量)

## 7. 收尾

- [x] 7.1 `src/node` pytest 102 passed;`src/server` pytest 164 passed(server 无代码改动,回归确认)
- [x] 7.2 更新 `docs/deployment.md`(新增 §2.5 后台常驻与文件监听、FAQ 两条)、`README.md`(功能列表、节点同步行为与单向性说明)
- [x] 7.3 `openspec validate --strict` 通过;红线自查:无对外契约变更(纯客户端行为,Hub 协议与端点不变,故 `api-reference.md` 无需改动)、未触碰本仓外仓库、无私有部署配置混入交付路径
