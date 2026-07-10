# 设计需求提交表深度分析指南

## 📋 表格基本信息

- **表格名称**: 设计需求提交表
- **baseId**: `QG53mjyd80RwNKL3TXlGA0yNV6zbX04v`
- **tableId**: `8m5FjY1`
- **访问链接**: https://alidocs.dingtalk.com/i/nodes/QG53mjyd80RwNKL3TXlGA0yNV6zbX04v?iframeQuery=sheetId%3D8m5FjY1

## 🔑 核心字段说明

| 字段名 | 类型 | 用途 | 关键值 |
|--------|------|------|--------|
| 设计需求内容 | primaryDoc | 需求描述（主键） | - |
| 提交人 | creator | 记录创建者 | 姓名+uid |
| 选择部门 | singleSelect | 部门分类 | 总部后勤人员 / 区域人员 |
| 进度选择 | singleSelect | 完成状态 | 完成 / 未完成 / 异常完成 |
| 完成设计时间 | date | 设计完成日期 | YYYY-MM-DD HH:mm:ss |
| 需求完成时长 | formula | 自动计算天数 | DATEDIF公式 |
| 所用公司 | singleSelect | 所属公司 | 驰骋控股/物流/同驰等 |
| 用途 | singleSelect | 业务用途 | 品牌推广/促销宣传/招聘等 |
| 类型 | singleSelect | 物料类型 | 电子版/印刷品/广告物料等 |
| 取货方式 | singleSelect | 交付方式 | 自行取货/送到物料库等 |
| 预算总金额 | number | 预算金额 | 元 |
| 制作途径 | singleSelect | 制作方式 | 自制/委外/采购 |
| 门店店号 | text | 门店标识 | 如"17477东城大厦店" |
| 审批单状态 | text | OA审批状态 | 审批通过/审批中等 |

## 📊 周报汇总分析维度

### 1. 工作量统计

```bash
# 读取本周所有记录
dws aitable record list \
  --base-id "QG53mjyd80RwNKL3TXlGA0yNV6zbX04v" \
  --table-id "8m5FjY1" \
  --format json
```

**分析指标**:
- 本周新增需求总数
- 按设计师分组的工作量分布
- 按部门分组的需求来源（总部 vs 区域）
- 按类型分组的物料需求分布

### 2. 效率分析

**关键指标**:
- **平均完成时长**: 从`需求完成时长`字段计算平均值
- **完成率**: `进度选择="完成"`的记录数 / 总记录数
- **超期率**: 实际完成时间 > 期望完成日期的记录比例

**计算公式**:
```
平均完成时长 = SUM(需求完成时长) / COUNT(完成的设计任务)
完成率 = COUNT(进度选择="完成") / COUNT(全部记录) × 100%
```

### 3. 待处理需求清单

筛选条件:
- `进度选择` = "未完成"
- 或 `进度选择` = "异常完成（已结束）"

**输出格式**:
| 需求内容 | 提交人 | 提交时间 | 期望完成日期 | 当前状态 |
|---------|--------|---------|------------|---------|
| ... | ... | ... | ... | ... |

### 4. 重点项目识别

**识别规则**:
- 同一设计师本周处理≥3个需求 → 高负荷设计师
- 同一门店本周提交≥2个需求 → 重点门店
- 预算总额>500元的需求 → 高价值项目

## 🎯 团队周报集成示例

在团队周报中增加以下章节：

### 七、设计需求数据分析

#### 7.1 本周工作概览
- **新增需求总数**: N项
- **已完成**: M项 (完成率 XX%)
- **进行中**: K项
- **平均完成时长**: X天

#### 7.2 设计师工作量分布
| 设计师 | 完成任务数 | 平均时长 | 完成率 |
|-------|-----------|---------|-------|
| 柴建化 | 5 | 2.3天 | 100% |
| 胡梦颖 | 3 | 1.8天 | 100% |
| ... | ... | ... | ... |

#### 7.3 需求类型分布
| 类型 | 数量 | 占比 |
|-----|------|------|
| 门店广告 | 8 | 40% |
| 效果图 | 6 | 30% |
| 电子版设计 | 4 | 20% |
| 其他 | 2 | 10% |

#### 7.4 待处理需求清单
⚠️ 以下需求尚未完成，需重点关注：

1. **[需求标题]** - 提交人: XXX, 期望完成: YYYY-MM-DD
2. **[需求标题]** - 提交人: YYY, 期望完成: YYYY-MM-DD

#### 7.5 管理建议
基于数据分析提出改进建议：
- 如果某设计师负荷过高 → 建议分配更多资源
- 如果某类需求平均时长过长 → 优化流程或提供模板
- 如果超期率高 → 加强进度跟踪和提醒机制

## 🛠️ 自动化脚本示例

### Python脚本：统计本周设计需求数据

```python
import json
from datetime import datetime, timedelta

def analyze_design_requests(records, week_start, week_end):
    """分析本周的设计需求数据"""
    
    # 过滤本周记录
    week_records = []
    for record in records:
        submit_time = record['cells'].get('Eq70pGV', '')
        if submit_time and week_start <= submit_time[:10] <= week_end:
            week_records.append(record)
    
    # 统计指标
    total = len(week_records)
    completed = sum(1 for r in week_records 
                   if r['cells'].get('sYc2tLyE8U', {}).get('name') == '完成')
    pending = sum(1 for r in week_records 
                 if r['cells'].get('sYc2tLyE8U', {}).get('name') == '未完成')
    
    # 按设计师分组
    designer_stats = {}
    for record in week_records:
        designer = record['cells'].get('dNp4o3F', [{}])[0].get('corpId', '未分配')
        if designer not in designer_stats:
            designer_stats[designer] = {'count': 0, 'completed': 0}
        designer_stats[designer]['count'] += 1
        if record['cells'].get('sYc2tLyE8U', {}).get('name') == '完成':
            designer_stats[designer]['completed'] += 1
    
    return {
        'total': total,
        'completed': completed,
        'pending': pending,
        'completion_rate': f"{completed/total*100:.1f}%" if total > 0 else "0%",
        'designer_stats': designer_stats
    }

# 使用示例
# records = json.loads(open('records.json').read())
# stats = analyze_design_requests(records, '2026-07-01', '2026-07-07')
# print(json.dumps(stats, ensure_ascii=False, indent=2))
```

## 📝 注意事项

1. **权限要求**: 需要有该AI表格的查看权限
2. **数据时效性**: 建议每周汇总时读取最新数据
3. **隐私保护**: 汇总报告中避免展示敏感信息（如具体预算金额）
4. **数据完整性**: 如果某些字段为空，需要在报告中注明"数据缺失"
5. **异常处理**: 如果API调用失败，应有降级方案（如手动填写）

## 🔗 相关资源

- [钉钉AI表格官方文档](https://open.dingtalk.com/document/)
- [dws aitable命令参考](~/.real/users/user-d38061d90b1223e142a160d7665c10b7/.skills/dingtalk-workspace-02a535c879c9/references/products/aitable.md)
- [团队周报汇总系统主文档](./SKILL.md)
