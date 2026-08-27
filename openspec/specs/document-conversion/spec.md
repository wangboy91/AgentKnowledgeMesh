# document-conversion 能力规格

## Purpose

将 PDF、Word、HTML 文件与网页转换为 Markdown 并保存到知识库，降低知识录入门槛。

## Requirements

### Requirement: File Upload Conversion
系统 SHALL 提供 `POST /api/convert/upload` 端点，接收上传文件并转换为 Markdown 保存到知识库。支持格式：`.pdf`、`.docx`、`.doc`、`.html`、`.htm`。

#### Scenario: 上传支持的格式
- **WHEN** 客户端上传允许格式的文件
- **THEN** 系统调用对应转换器（PDF/Word/HTML）生成 Markdown，保存到知识库并返回 `{"title", "path", "size", "message"}`

#### Scenario: 上传不支持的格式
- **WHEN** 客户端上传允许列表之外的文件类型
- **THEN** 系统返回 400，`detail` 说明不支持的类型与支持的格式列表

#### Scenario: 未配置知识库目录
- **WHEN** 转换成功但没有可用的知识库根目录
- **THEN** 系统返回 500，`detail` 为 "No knowledge root configured"

### Requirement: URL Conversion
系统 SHALL 提供 `POST /api/convert/url` 端点，抓取网页并转换为 Markdown 保存到知识库。

#### Scenario: 抓取并转换网页
- **WHEN** 客户端提交 `{"url": <网页地址>}`
- **THEN** 系统抓取网页、提取标题与正文并转换为 Markdown，保存到知识库并返回 `{"title", "path", "size", "message"}`

#### Scenario: 抓取或转换失败
- **WHEN** URL 无法访问或转换过程出错
- **THEN** 系统返回 500 并携带错误信息

### Requirement: Converted Document Storage
转换结果 SHALL 保存到第一个知识库根目录下的 `converted/` 子目录，文件名由安全化标题与时间戳组成，保证唯一。

#### Scenario: 生成唯一文件名
- **WHEN** 转换完成需要落盘
- **THEN** 系统将标题中仅保留字母数字、空格、下划线、连字符并截断至 50 字符，拼接 `_YYYYMMDD_HHMMSS` 时间戳作为文件名（如 `我的文档_20260827_103000.md`）

#### Scenario: 返回相对路径
- **WHEN** 转换保存成功
- **THEN** 响应中的 `path` 为相对于知识库根目录的路径（如 `converted/我的文档_20260827_103000.md`），`size` 为 UTF-8 编码字节数

### Requirement: Upload Temp File Cleanup
上传转换过程 SHALL 清理临时文件。

#### Scenario: 转换结束后删除临时文件
- **WHEN** 上传转换完成（无论成功或失败）
- **THEN** 系统删除保存上传内容的临时文件
