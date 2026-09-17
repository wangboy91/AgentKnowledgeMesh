# Delta Spec: release-distribution

## ADDED Requirements

### Requirement: 源码构建部署

系统 SHALL 提供从源码构建并部署 Hub 容器的方式,以叠加文件 `deploy/docker-compose.build.yml` 实现:与任一部署 compose(SQLite / PostgreSQL / 外接已有 PostgreSQL)组合使用时,SHALL 将 `akm-hub` 服务的镜像来源改为本地构建(构建上下文 `src/`,构建规则 `src/Dockerfile`),其余业务配置(管理员账号、知识目录挂载、数据卷、数据库连接、向量嵌入配置透传)SHALL 与被叠加的部署 compose 保持一致;镜像构建 SHALL 提供可选依赖构建参数(默认留空),留空时镜像的依赖集合 SHALL 与发布镜像一致。发布流水线 SHALL NOT 受该构建参数影响。

#### Scenario: 源码构建并启动(SQLite 模式)
- **WHEN** 部署方在仓库根目录执行 `docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.build.yml up -d --build`
- **THEN** 以本地源码构建出的镜像启动单容器,8000 端口同时提供 Web 界面与 API,管理员账号、知识目录挂载与数据持久化行为与镜像部署版一致

#### Scenario: 源码构建并启动(PostgreSQL 模式,含 RAG)
- **WHEN** 以 `deploy/docker-compose.pg.yml` 叠加同一 build 文件启动
- **THEN** 同时启动 pgvector 容器,Hub 由源码构建,嵌入配置透传(`AKM_EMBEDDING_PROVIDER`/`AKM_EMBEDDING_MODEL`/`AKM_ARK_API_KEY`/`AKM_ARK_BASE_URL`)与镜像部署版一致

#### Scenario: 按需安装可选依赖
- **WHEN** 部署方设置构建参数(如 `AKM_UV_EXTRAS=local-embedding`)后重新构建
- **THEN** 镜像内包含对应可选依赖(本地嵌入模型),`AKM_EMBEDDING_PROVIDER=local` 可离线使用;未设置该参数时镜像与发布镜像的依赖集合一致(不含 sentence-transformers/torch)

#### Scenario: 发布镜像与流水线不受影响
- **WHEN** 推送版本 tag 触发发布流水线
- **THEN** 发布镜像仍由流水线构建并推送至 GHCR,构建参数不传入(取默认空值),发布镜像的依赖集合与体积特征与本次变更前一致

#### Scenario: 镜像部署路径零改动
- **WHEN** 部署方仅使用基础部署 compose(不叠加 build 文件)执行 `docker compose up -d`
- **THEN** 行为与本次变更前完全一致(仍从 GHCR 拉取镜像)
