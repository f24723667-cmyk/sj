# 钉钉文档搜索最佳实践

## 文档标题格式

工作日志文档的常见标题格式：
- `YYYY-MM-DD 工作日志`（最常见）
- `工作日志/YYYY-MM-DD`
- `YYYY-MM-DD`
- `{姓名} {YYYY-MM-DD} 工作日志`

## 搜索策略

### 1. 精确搜索优先

首先尝试最精确的搜索条件：

```bash
dws doc search --query "2026-07-03 工作日志" --format json
```

### 2. 模糊搜索备选

如果精确搜索无结果，尝试更宽泛的条件：

```bash
dws doc search --query "2026-07-03" --format json
```

### 3. 分页处理

如果搜索结果包含 `hasMore: true`，需要使用 `nextPageToken` 继续获取：

```bash
dws doc search --query "工作日志" --page-token "<token>" --format json
```

## 结果解析

### 关键字段

从搜索结果中提取以下字段：

- `nodeId`: 文档唯一标识，用于后续读取
- `name`: 文档名称，用于匹配日期
- `contentType`: 文档类型（ALIDOC 表示在线文档）
- `docUrl`: 文档访问链接

### 匹配逻辑

1. 检查 `name` 是否包含目标日期（YYYY-MM-DD）
2. 检查 `name` 是否包含"工作日志"关键词
3. 优先选择 `contentType` 为 `ALIDOC` 的文档
4. 如果有多个匹配，选择 `createTime` 最近的

## 读取文档

使用 nodeId 读取文档内容：

```bash
dws doc read --node "<nodeId>" --format json
```

返回的 JSON 中包含：
- `markdown`: Markdown 格式的文档内容
- `title`: 文档标题
- `docUrl`: 文档链接

## 常见错误

### 1. 文档不存在

```json
{"documents": [], "hasMore": false, "success": true}
```

**处理**: 记录该日期无文档，跳过

### 2. 权限不足

```json
{"error": {"code": 403, "message": "Permission denied"}}
```

**处理**: 提示用户检查权限或联系文档所有者

### 3. 网络超时

**处理**: 重试一次，如仍失败则跳过并记录

## 性能优化

### 批量搜索

对于多个日期的搜索，可以并行执行：

```python
# Python 示例
import concurrent.futures

dates = ["2026-07-01", "2026-07-02", "2026-07-03"]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(search_dingtalk_doc, d): d for d in dates}
    for future in concurrent.futures.as_completed(futures):
        date = futures[future]
        result = future.result()
        # 处理结果
```

### 缓存机制

将已搜索过的日期和对应的 nodeId 缓存到本地文件，避免重复搜索。

## 安全注意事项

- 不要硬编码 userId 或敏感信息
- 使用环境变量或配置文件存储用户偏好
- 记录操作日志便于审计和调试
