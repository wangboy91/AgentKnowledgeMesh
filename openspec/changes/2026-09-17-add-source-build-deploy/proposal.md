# 源码构建部署容器

## Why

当前部署只有一条路径:打 tag → Actions 构建镜像推到 GHCR → 部署机拉镜像跑 `deploy/docker-compose*.yml`。有三个它覆盖不到的诉求:

1. **不想等发版**:想直接用手上这份源码(未发布的改动、临时分支)跑起来;
2. **需要改源码或装可选依赖**:发布镜像刻意不含 `sentence-transformers`(local 嵌入),文档只说"需要 local 请自建镜像",却没给出自建方式;
3. **内网/离线环境**:拉不到 GHCR。

仓库里确实有 `src/docker-compose*.yml` 这套"从源码 build"的 compose,但它们与 `deploy/` 版已经漂移——缺 `AKM_ADMIN_USERNAME`/`AKM_ADMIN_PASSWORD`(首启无法固定管理员)、PG 版缺 Ark 嵌入透传(语义检索必然报 Key 未配置)、`KNOWLEDGE_DIR` 默认值还是 `~/Knowledge`、node 版没有凭证卷(容器一重建就丢登录)。直接让用户用它们,等于让人踩一遍已经修过的坑。

## What Changes

- **新增 `deploy/docker-compose.build.yml`**:源码构建**叠加文件**(override)。只覆盖 `akm-hub` 的镜像来源(改为本地 `build`),其余配置(管理员账号、知识目录挂载、数据卷、数据库连接、Ark 嵌入透传)全部继承被叠加的部署 compose —— 与镜像部署行为一致,只换镜像来源。
- **`src/Dockerfile` 新增可选依赖构建参数 `AKM_UV_EXTRAS`**(默认留空):留空 = 与发布镜像依赖集合一致;传 `local-embedding` = 额外装本地嵌入模型,`AKM_EMBEDDING_PROVIDER=local` 即可离线免 Key 跑语义检索。
- **文档**:`docs/deployment.md` 新增「源码构建部署」章节(三种模式命令、可选依赖、与镜像部署的差异、升级与回滚);`README.md` 的 Docker 段落补源码构建入口。
- **不改动发布流水线与发布镜像**:`release.yml` 不传构建参数,镜像依赖集合与行为保持不变。

## Capabilities

### New Capabilities

(无)

### Modified Capabilities

- `release-distribution`:新增「源码构建部署」要求 —— 以叠加文件方式提供源码构建部署,配置与被叠加的部署 compose 保持一致;镜像构建支持可选依赖构建参数,默认与发布镜像依赖集合一致。

## Impact

- **新增/修改文件**:`deploy/docker-compose.build.yml`(新增)、`src/Dockerfile`(加 `ARG` 与分支)、`docs/deployment.md`、`README.md`
- **不涉及代码**:server / web / node 无改动;REST / WS / MCP / Context API 契约不变,无需同步 `docs/api-reference.md`
- **不受影响**:`.github/workflows/release.yml`、`deploy/docker-compose.yml` / `.pg.yml` / `.external-pg.yml` 三个基础文件、既有镜像部署路径
- **遗留(本变更不处理,记入 design 的 Open Questions)**:
  - `src/docker-compose*.yml` 这套旧 dev compose 与新叠加方式功能重叠且配置陈旧(本次只在其文件头加指路注释,不改行为);
  - `src/Makefile` 的 `docker-up` / `docker-up-pg` / `docker-up-node` 目标正是从 `src/` 用这套旧配置构建 —— 是第三个源码构建入口,清理时需一并决定去向;
  - `README.md` 的 `docker-compose.node.yml` 引用与文件实际位置不符(`docker-compose.node.yml` 只在 `src/` 有),本次已改为指向节点接入章节
