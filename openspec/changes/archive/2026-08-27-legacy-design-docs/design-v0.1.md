# AgentKnowledgeMesh V0.1 产品与技术设计文档

## 项目定位

AgentKnowledgeMesh 是一个面向 AI Agent 时代的分布式个人知识库系统。

核心目标：

让多台电脑上的 Markdown 知识文件、Agent
记忆文件、项目文档形成统一知识网络。

解决问题：

-   Claude Code、Codex、OpenClaw、Hermes、WorkBuddy
    等多个智能体无法共享上下文
-   本地电脑、云服务器、家庭服务器之间知识孤岛
-   大量 md 文件无法形成可检索、可调用的知识库

定位：

> Personal Distributed Knowledge OS

类似：

-   Obsidian（知识管理）
-   Git（版本思想）
-   NAS（数据聚合）
-   RAG（AI知识召回）

但核心服务对象是 AI Agent。

------------------------------------------------------------------------

# 一、总体架构

采用 Hub + Node 分布式架构。

                     AgentKnowledgeMesh Hub
                  (Web + API Server)
                           |
                    WebSocket / HTTP
                           |
     ------------------------------------------------
     |                    |                          |
    Node-Mac          Node-Windows             Node-Linux

    本地Markdown       本地Markdown              服务端Markdown

    Claude Code       Codex                     OpenClaw

------------------------------------------------------------------------

# 二、核心组件

## 1. Hub Server

职责：

-   管理所有节点
-   提供 Web 页面
-   提供统一搜索
-   提供 Agent Context API
-   管理节点状态

技术建议：

Backend:

-   Go

Database:

-   SQLite

Frontend:

-   Next.js

目录：

    server/

    ├── api
    ├── node_manager
    ├── search
    ├── auth
    └── database

------------------------------------------------------------------------

## 2. Knowledge Node

每台电脑运行一个 Node。

支持：

-   Mac
-   Windows
-   Linux

职责：

1.  扫描本地 Markdown

2.  文件监听

3.  提供读取接口

4.  提供写入接口

5.  向 Hub 注册

目录：

    node/

    ├── scanner
    ├── watcher
    ├── api
    └── sync

------------------------------------------------------------------------

# 三、数据模型

## Node表

``` sql
nodes

id

name

platform

ip

status

last_online

token
```

------------------------------------------------------------------------

## 文件索引

``` sql
documents


id

node_id

path

title

hash

size

updated_time

tags
```

------------------------------------------------------------------------

# 四、Markdown知识结构

推荐目录：

    Knowledge/

    ├── projects

    │   ├── ai-crm.md

    │   ├── ai-video.md


    ├── technology

    │   ├── agent.md

    │   ├── mcp.md


    ├── decisions

    │   ├── business.md


    ├── memories

    │   ├── personal.md


    └── skills

        ├── coding.md

------------------------------------------------------------------------

# 五、Web功能

## 1. 知识浏览

支持：

-   文件树
-   Markdown预览
-   Markdown编辑
-   标签

页面：

    Dashboard

    ├── Nodes

    ├── Knowledge

    ├── Search

    └── Agent Context

------------------------------------------------------------------------

## 2. 节点管理

展示：

    MacBook

    🟢 Online


    Home Server

    🟢 Online


    Cloud Server

    🟡 Offline

------------------------------------------------------------------------

# 六、Agent调用能力（核心）

提供统一 API：

## Context API

请求：

    GET

    /api/context?q=AI CRM

返回：

``` json
{
 "query":"AI CRM",

 "documents":[

 {
 "title":"AI CRM设计",
 "content":"..."
 }

 ]

}
```

用途：

Claude Code:

    用户:
    设计CRM系统


    AgentKnowledgeMesh:

    搜索相关知识


    返回历史方案


    注入Prompt


    继续工作

------------------------------------------------------------------------

# 七、搜索设计

V0.1：

关键词搜索即可。

流程：

    用户问题

    ↓

    Hub Search

    ↓

    匹配Markdown

    ↓

    返回Top N

    ↓

    Agent Context

V0.2:

增加：

-   Embedding
-   Vector Database
-   RAG

推荐：

Qdrant

------------------------------------------------------------------------

# 八、通信设计

Node连接Hub：

WebSocket

消息：

注册：

``` json
{
"type":"register",

"node":"mac001"

}
```

心跳：

``` json
{
"type":"heartbeat"
}
```

文件更新：

``` json
{
"type":"update",

"path":"ai-crm.md"

}
```

------------------------------------------------------------------------

# 九、MVP开发计划

## 第一阶段

目标：

单机知识库。

完成：

-   扫描md
-   Web查看
-   Markdown渲染
-   搜索

------------------------------------------------------------------------

## 第二阶段

目标：

多电脑。

完成：

-   Node注册
-   WebSocket通信
-   节点管理
-   远程读取

------------------------------------------------------------------------

## 第三阶段

目标：

Agent接入。

完成：

-   Context API
-   MCP Server
-   Claude Code调用
-   OpenClaw调用

------------------------------------------------------------------------

# 十、Claude Code开发要求

请按照以下原则开发：

## 代码原则

-   模块化
-   清晰目录结构
-   每个模块提供README
-   使用Docker支持部署

## 优先级

不要先做：

-   类Obsidian复杂编辑器
-   双向实时同步
-   图谱

优先做：

1.  Markdown管理

2.  多节点访问

3.  Agent知识调用

------------------------------------------------------------------------

# 十一、未来扩展

## MCP Server

让所有Agent直接调用：

    Agent

    ↓

    MCP

    ↓

    AgentKnowledgeMesh

    ↓

    Knowledge

------------------------------------------------------------------------

## Personal AI Memory

记录：

-   用户习惯
-   项目历史
-   决策过程
-   Agent执行记录

------------------------------------------------------------------------

## Knowledge Graph

未来增加：

实体：

项目

人物

技术

决策

关系：

创建

依赖

影响

------------------------------------------------------------------------

# 项目名称

AgentKnowledgeMesh

一句话：

> Your distributed memory layer for AI Agents.
