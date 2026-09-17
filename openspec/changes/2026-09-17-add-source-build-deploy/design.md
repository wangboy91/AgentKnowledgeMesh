# 源码构建部署 · 设计

## Context

现状两套 compose:

| | 镜像来源 | 配置完整度 |
| --- | --- | --- |
| `deploy/docker-compose*.yml`(随 Release 分发) | `image: ghcr.io/wangboy91/akm-hub:<tag>` | 完整:管理员账号、知识目录、数据卷、Ark 嵌入透传、外接库连接 |
| `src/docker-compose*.yml`(仓内 dev) | `build: .` | 陈旧:无管理员账号变量、PG 版无 Ark 透传、`KNOWLEDGE_DIR` 默认 `~/Knowledge`、node 版无凭证卷 |

约束:
- 部署配置(尤其安全相关:管理员账号、密钥透传)不应有两份会各自演进的副本
- 发布流水线 `.github/workflows/release.yml` 与发布镜像行为不能受影响
- 用户实际执行目录是仓库根(源码构建场景下用户手上就是整个仓)

## Goals / Non-Goals

**Goals:**
- 一条命令从当前源码构建并起 Hub 容器,三种数据库模式(SQLite / PostgreSQL / 外接 PostgreSQL)都支持
- 源码构建与镜像部署的**业务配置完全一致**,差异只有镜像来源
- 让"发布镜像不含的可选依赖"(local 嵌入)有正式的构建入口,而不是文档里一句"请自建镜像"

**Non-Goals:**
- 不改发布流水线、不改发布镜像的依赖集合与体积特征
- 不引入多架构(buildx)构建、镜像缓存服务、CI 构建缓存等基建
- 不做 node 容器化(见 D5)

## Decisions

### D1: 用叠加文件(override),不复制一份 build compose
`deploy/docker-compose.build.yml` 只声明 `akm-hub` 的 `image` + `build`,与任一基础 compose 组合:

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.build.yml up -d --build
```

- 依据:compose 多 `-f` 合并语义,后者覆盖同名字段、其余继承。管理员账号、卷、DB、Ark 透传全部来自基础文件,天然不漂移
- 备选:独立写一份 `docker-compose.build.yml` 完整配置 —— 与基础文件重复 90%,必然漂移(这正是 `src/` 那套的现状)
- 备选:在基础 compose 里用 `${AKM_HUB_IMAGE:-ghcr.io/...}` + 可选 build —— compose 无法条件性 build,`image` 与 `build` 同时存在时仍会尝试构建

### D2: 叠加文件与基础文件同目录,构建上下文写 `../src`
`build.context: ../src` 相对本文件所在目录 `deploy/` 解析,指向仓库 `src/`。
两个文件同目录这一事实让解析结果不受"相对首个文件 vs 相对各自文件"两种规则差异影响(两种规则下都指向同一处),避免路径歧义。用法文档统一写"在仓库根目录执行",不影响解析结果。

### D3: 可选依赖走构建参数,不维护多个 Dockerfile 变体
`src/Dockerfile` 增加 `ARG AKM_UV_EXTRAS=""`,空值走原命令,非空则 `uv sync --no-dev --no-install-project --extra "$AKM_UV_EXTRAS"`。
- 依据:同一份 Dockerfile 既服务发布(不传参)又服务源码构建(可传 `local-embedding`),不引入需要同步维护的分支文件
- 备选:多 Dockerfile(local / 默认两份)—— 两份只有一行不同,维护成本高于收益

### D4: 发布流水线不传参数,发布镜像依赖集合不变
`release.yml` 的 `build-push-action` 不加 `build-args`,因此 `AKM_UV_EXTRAS` 取默认空值,发布镜像与本次变更前完全一致(不含 torch)。
- 风险控制:这是"不能把 torch 塞进发布镜像"的硬约束,写进 spec 的验收场景

### D5: node 容器不在本次范围
容器化 node 需要解决:交互式 `login`(容器内怎么输入凭证)、凭证卷持久化、宿主机知识目录挂载语义,以及"Hub 地址"从容器视角的写法(`host.docker.internal`)。这是独立设计,不该混进本次改动。
`README.md` 里 `docker compose -f docker-compose.node.yml up -d` 的引用与文件位置不符(`docker-compose.node.yml` 只在 `src/`),已在 proposal 记为遗留项。

## Risks / Trade-offs

- [本地构建耗时与磁盘占用] 首次构建需拉 node/python 基础镜像、`npm install`、`uv sync`,数分钟级 → 在 compose 头注释与文档中明确标注,不设自动化绕过
- [传错 extra 名导致构建失败] → uv 会报出未知 extra 的明确错误;文档只给当前唯一可用值(`local-embedding`),并说明留空的含义
- [`AKM_UV_EXTRAS` 被误用于发布镜像] → 发布流水线不传参(默认空),不构成风险
- [叠加文件被单独执行] `docker compose -f deploy/docker-compose.build.yml up` 会因缺少端口/卷等基础配置而行为异常 → 文件头注释首行即标注"不单独使用",文档只给叠加用法

## Migration Plan

纯新增,既有镜像部署路径零改动。回滚 = 删除 `deploy/docker-compose.build.yml` 并还原 `src/Dockerfile` 的 ARG 段。

## Open Questions

- 是否把 node 容器也纳入源码构建部署(需先定容器内 login 与凭证卷的方案)?
- `src/docker-compose*.yml` 这套旧 dev compose 与新叠加方式功能重叠,是否清理(或改为叠加同一 build 文件),避免两套配置继续漂移?
  补充事实:`src/Makefile` 的 `docker-up` / `docker-up-pg` / `docker-up-node` 三个目标就是从 `src/` 用这套旧配置 `up -d --build`,是**第三个**源码构建入口(前两个:新叠加文件、手工 docker build)。本次只在旧文件头加指路注释、不动其行为与 Makefile 目标;清理时需一并决定这些目标的去向。
