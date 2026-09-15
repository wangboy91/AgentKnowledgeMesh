# Delta Spec: release-distribution

## Purpose

定义 AKM 的版本分发能力:Hub(server+web)以容器镜像经 GHCR 分发部署,akm-node 以 GitHub Release wheel 加一键安装脚本分发到任意机器,安装后提供全局 `akm-node` 命令且凭证升级不丢失。

## ADDED Requirements

### Requirement: Hub 容器镜像分发

系统 SHALL 在版本 tag(`v*`)推送时自动构建 Hub 单容器镜像(前端静态资源与 server 同镜像、单端口对外)并发布到 GHCR(`ghcr.io/wangboy91/akm-hub`,tag 含版本号与 `latest`);镜像构建 SHALL 排除虚拟环境、测试代码、本地数据与含密钥的 `.env` 文件;镜像 SHALL 支持通过环境变量配置管理员账号(`AKM_ADMIN_USERNAME`/`AKM_ADMIN_PASSWORD`)与知识库根目录挂载,数据 SHALL 持久化于卷。

#### Scenario: 拉取镜像一键起服务
- **WHEN** 部署方在装有 Docker 的机器上,使用随 Release 提供的 compose 文件(镜像指向 GHCR 版本 tag)执行 `docker compose up -d`
- **THEN** 单容器在 8000 端口同时提供 Web 界面与 REST/WS API,浏览器可打开并登录

#### Scenario: 首次启动管理员初始化
- **WHEN** 容器以空数据卷首次启动且配置了 `AKM_ADMIN_USERNAME`/`AKM_ADMIN_PASSWORD`
- **THEN** 系统创建对应管理员账号,部署方可直接登录

#### Scenario: 镜像不含密钥与开发产物
- **WHEN** 检查发布镜像的文件层
- **THEN** 其中不存在 `server/.env`、`.venv`、`node_modules`、`tests` 目录内容

### Requirement: akm-node 一键安装

系统 SHALL 为 macOS/Linux 提供 bash 安装脚本、为 Windows 提供 PowerShell 安装脚本,均以一条命令从 GitHub Release 完成 `akm-node` 安装:脚本 SHALL 检测并(缺失时)安装 uv,下载该版本的 `akm-shared` 与 `akm-node` wheel,并以 `uv tool install` 安装出全局 `akm-node` 命令;重复执行脚本 SHALL 幂等(等价于升级到目标版本)。

#### Scenario: 全新 Linux/macOS 机器安装
- **WHEN** 在未装过 AKM 的机器上执行 `curl -fsSL <release>/install-akm-node.sh | bash`
- **THEN** 安装完成后终端提示执行 `akm-node login`,且任意新 shell 中 `akm-node` 命令可用

#### Scenario: 全新 Windows 机器安装
- **WHEN** 在 PowerShell 中执行安装脚本(远程下载或本地运行)
- **THEN** 安装完成后 `akm-node` 命令在新终端可用

#### Scenario: 重复安装升级
- **WHEN** 已安装旧版本 akm-node 的机器再次执行安装脚本(目标为新版本)
- **THEN** `akm-node` 升级到新版本,已保存的节点凭证不受影响

### Requirement: akm-node 凭证与配置持久化

akm-node 的凭证与配置 SHALL 持久化于用户目录(`~/.akm-node/.env`),SHALL 支持通过环境变量 `AKM_NODE_ENV_FILE` 覆盖该路径;`akm-node login` SHALL 将凭证写入该路径;配置读取 SHALL 兼容源码仓内开发场景(仓库 `src/node/.env`)。包升级(重装/升级 wheel)SHALL NOT 导致凭证丢失。

#### Scenario: 安装版登录后凭证可持久
- **WHEN** `uv tool install` 安装的 `akm-node login` 成功后,执行 `uv tool install --upgrade`(或重装)再运行 `akm-node`
- **THEN** 节点无需重新登录,以原凭证接入 Hub

#### Scenario: 自定义凭证路径
- **WHEN** 以 `AKM_NODE_ENV_FILE=/path/to/my.env` 启动 `akm-node`
- **THEN** 凭证与配置从该文件读取,`akm-node login` 亦写入该文件

#### Scenario: 源码仓开发场景兼容
- **WHEN** 在仓库 `src/node/` 下存在开发用 `.env` 并运行 `uv run akm-node`
- **THEN** 该文件中的配置仍然生效(与用户目录文件并存时,用户目录文件优先生效)

#### Scenario: 同步快照升级不丢
- **WHEN** 安装版 `akm-node` 完成过同步(存在快照)后升级重装再运行
- **THEN** 同步快照仍可用,节点按增量继续同步而非全量重扫;开发仓内已存在的快照继续在原位置使用
