# 任务清单:源码构建部署容器

> 对应 spec delta:`specs/release-distribution/spec.md`;设计决策见 `design.md`。
> 未勾选项均为"需要 Docker daemon 才能跑"的运行时验证(本机 Docker Desktop 引擎未启动)。

## 1. 源码构建叠加文件(spec:源码构建部署)

- [x] 1.1 新增 [deploy/docker-compose.build.yml](../../../deploy/docker-compose.build.yml):只覆盖 `akm-hub` 的 `image`(默认 `akm-hub:local`)+ `build`(context `../src`,dockerfile `Dockerfile`,arg `AKM_UV_EXTRAS`),其余继承基础 compose;验证:三种基础文件叠加后 `docker compose config` 均通过 → SQLite / PG / 外接 PG 三例全部通过,`build.context` 解析为仓库 `src/`,基础配置(管理员账号、卷、DB、Ark 透传)完整保留
- [x] 1.2 校验叠加语义与继承项:确认基础文件未被修改、镜像部署路径零改动(不叠加时仍为 GHCR 镜像) → `git status` 显示三个基础 compose 未改动;不叠加的 `docker compose config` 仍输出 `ghcr.io/wangboy91/akm-hub:${AKM_HUB_VERSION:-latest}` 对应镜像

## 2. 可选依赖构建入口(spec:按需安装可选依赖)

- [x] 2.1 [src/Dockerfile](../../../src/Dockerfile) 增加 `ARG AKM_UV_EXTRAS=""` 与分支(空值走原命令,非空 `--extra "$AKM_UV_EXTRAS"`);验证:分支逻辑在本地 shell 复核(空值/传值两路命令正确)、`local-embedding` extra 存在于 `src/server/pyproject.toml`
- [x] 2.2 确认发布流水线不传该构建参数(`.github/workflows/release.yml` 的 `build-push-action` 无 `build-args`),发布镜像依赖集合不变
- [ ] 2.3 实机构建与冒烟(需 Docker daemon 运行):`docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.build.yml up -d --build` → 容器起于 8000 → `/api/health` 200 → Web 首页可打开 → 管理员登录成功;并确认镜像内无 `.env`/`.venv`/`tests`

## 3. 文档

- [x] 3.1 [docs/deployment.md](../../../docs/deployment.md) 新增「源码构建部署」章节:三种模式命令、可选依赖(`AKM_UV_EXTRAS=local-embedding`)、与镜像部署的差异、升级/回滚方式、耗时提示
- [x] 3.2 [README.md](../../../README.md) Docker 段落补源码构建入口,并指向部署文档
- [x] 3.3 同步修正文档中"需要 local 请自建镜像"的表述,改为指向本变更提供的构建参数(不再让用户自己改 Dockerfile) → `docs/deployment.md` §1.5、`deploy/docker-compose.pg.yml` 与 `.external-pg.yml` 的注释均已改指向 §1.8
- [x] 3.4 文档一致性收尾:§1.3 增加指向 §1.8 的入口(镜像部署用户知道还有源码构建这条路);`src/docker-compose.yml` / `.pg.yml` 文件头加"仓内 dev 遗留配置 + 正确路径"指路注释(不改行为);`src/Makefile` 的旧构建目标记入 design Open Questions

## 4. 验收

- [x] 4.1 `openspec validate 2026-09-17-add-source-build-deploy` 通过
- [ ] 4.2 端到端:源码构建镜像起的 Hub + 安装版 `akm-node login` 接入 → 文档同步 → Web 可见节点与文档(需 Docker daemon 运行)
- [x] 4.3 红线自查:未绑定具体业务领域;未改本仓之外仓库;对外契约无变更(无需同步 api-reference);部署密钥仍只在部署方 `.env`、不进镜像与文档
