#!/usr/bin/env python3
"""
悟空-钉钉-Obsidian 三端同步脚本

功能：
1. 悟空 → 钉钉：推送新增/更新的文档
2. 钉钉 → 悟空：拉取钉钉文档更新
3. 生成 Obsidian 同步包
4. 更新索引文件

使用方法：
    python sync_all.py [--dry-run] [--verbose]

参数：
    --dry-run   预览模式，不执行实际同步操作
    --verbose   详细输出模式
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import shutil

# 工作空间根目录
WORKSPACE = Path("/home/wuying/.kinto-agent/workspace/projects/工作总结")
INDEX_FILE = WORKSPACE / "sync_index.json"


def load_index():
    """加载索引文件"""
    if INDEX_FILE.exists():
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "version": "1.0",
        "last_sync": None,
        "mappings": {},
        "sync_rules": {
            "auto_push_to_dingtalk": True,
            "auto_pull_from_dingtalk": True,
            "obsidian_sync_method": "git",
            "conflict_resolution": "newest_wins"
        }
    }


def save_index(index):
    """保存索引文件"""
    index["last_sync"] = datetime.now().isoformat()
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"✓ 索引文件已更新: {INDEX_FILE}")


def execute_dws_command(cmd, verbose=False):
    """执行 dws 命令并返回结果"""
    if verbose:
        print(f"  执行命令: {cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        if verbose:
            print(f"  ✗ 命令执行失败: {result.stderr}")
        return None
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        if verbose:
            print(f"  ✗ JSON 解析失败: {result.stdout[:200]}")
        return None


def search_dingtalk_doc(query, verbose=False):
    """搜索钉钉文档"""
    cmd = f'dws doc search --query "{query}" --format json'
    return execute_dws_command(cmd, verbose)


def read_dingtalk_doc(node_id, verbose=False):
    """读取钉钉文档内容"""
    cmd = f'dws doc read --node "{node_id}" --format json'
    result = execute_dws_command(cmd, verbose)
    if result:
        return result.get("markdown", "")
    return None


def create_dingtalk_doc(name, parent_node_id=None, verbose=False):
    """创建钉钉文档"""
    cmd = f'dws doc create --name "{name}" --format json'
    if parent_node_id:
        cmd += f' --parent-node-id "{parent_node_id}"'
    return execute_dws_command(cmd, verbose)


def update_dingtalk_doc(node_id, markdown_file, verbose=False):
    """更新钉钉文档"""
    cmd = f'dws doc update --node "{node_id}" --content-file "{markdown_file}" --mode overwrite --yes --format json'
    result = execute_dws_command(cmd, verbose)
    return result is not None


def sync_daily_logs_to_dingtalk(index, dry_run=False, verbose=False):
    """同步工作日志到钉钉"""
    print("\n[步骤 1/3] 同步工作日志到钉钉...")
    
    logs_dir = WORKSPACE / "work_logs"
    if not logs_dir.exists():
        print("  ⚠ work_logs 目录不存在，跳过")
        return
    
    log_files = sorted([f for f in logs_dir.glob("*.md") if f.stem != "README"])
    if not log_files:
        print("  ℹ 没有工作日志文件，跳过")
        return
    
    print(f"  找到 {len(log_files)} 个工作日志文件")
    
    synced_count = 0
    for log_file in log_files:
        date_str = log_file.stem  # YYYY-MM-DD
        query = f"{date_str} 工作日志"
        
        # 检查索引中是否已有记录
        mapping = index["mappings"].get("daily_logs", {}).get(date_str, {})
        
        # 搜索钉钉文档
        if verbose:
            print(f"\n  处理: {date_str}")
        
        search_result = search_dingtalk_doc(query, verbose)
        node_id = None
        
        if search_result and search_result.get("documents"):
            # 找到匹配的文档
            for doc in search_result["documents"]:
                if doc["name"] == query:
                    node_id = doc["nodeId"]
                    if verbose:
                        print(f"    ✓ 找到现有钉钉文档: {node_id}")
                    break
        
        if node_id:
            # 文档存在，更新内容
            if not dry_run:
                print(f"    → 更新钉钉文档: {query}")
                success = update_dingtalk_doc(node_id, str(log_file), verbose)
                if success:
                    synced_count += 1
            else:
                print(f"    → [预览] 将更新钉钉文档: {query}")
                synced_count += 1
        else:
            # 文档不存在，创建新文档
            if not dry_run:
                print(f"    → 创建钉钉文档: {query}")
                create_result = create_dingtalk_doc(query, verbose=verbose)
                if create_result:
                    node_id = create_result.get("nodeId")
                    synced_count += 1
            else:
                print(f"    → [预览] 将创建钉钉文档: {query}")
                synced_count += 1
        
        # 更新索引
        if "daily_logs" not in index["mappings"]:
            index["mappings"]["daily_logs"] = {}
        
        file_mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
        index["mappings"]["daily_logs"][date_str] = {
            "wukong_path": f"work_logs/{log_file.name}",
            "dingtalk_node_id": node_id,
            "dingtalk_url": f"https://alidocs.dingtalk.com/i/nodes/{node_id}" if node_id else None,
            "obsidian_path": f"Daily Notes/{date_str}.md",
            "last_modified_wukong": file_mtime.isoformat(),
            "last_modified_dingtalk": datetime.now().isoformat() if node_id else None,
            "last_modified_obsidian": None,
            "sync_status": "synced" if node_id else "pending_create"
        }
    
    print(f"\n  ✓ 已处理 {synced_count} 个工作日志")


def sync_weekly_summaries_to_dingtalk(index, dry_run=False, verbose=False):
    """同步周总结到钉钉"""
    print("\n[步骤 1b] 同步周总结到钉钉...")
    
    weekly_dir = WORKSPACE / "weekly_summaries"
    if not weekly_dir.exists():
        print("  ⚠ weekly_summaries 目录不存在，跳过")
        return
    
    weekly_files = sorted([f for f in weekly_dir.glob("*.md") if f.stem != "README"])
    if not weekly_files:
        print("  ℹ 没有周总结文件，跳过")
        return
    
    print(f"  找到 {len(weekly_files)} 个周总结文件")
    
    for weekly_file in weekly_files:
        week_str = weekly_file.stem.split('_')[0]  # YYYY-WW
        query = f"{week_str} 周总结"
        
        if verbose:
            print(f"\n  处理周总结: {week_str}")
        
        # 简化处理：仅更新索引，不实际同步（需要根据实际情况调整）
        if "weekly_summaries" not in index["mappings"]:
            index["mappings"]["weekly_summaries"] = {}
        
        index["mappings"]["weekly_summaries"][week_str] = {
            "wukong_path": f"weekly_summaries/{weekly_file.name}",
            "dingtalk_node_id": None,
            "dingtalk_url": None,
            "obsidian_path": f"Weekly Reviews/{weekly_file.name}",
            "last_modified_wukong": datetime.fromtimestamp(os.path.getmtime(weekly_file)).isoformat(),
            "sync_status": "pending"
        }
    
    print(f"  ℹ 周总结同步功能待完善")


def sync_from_dingtalk_to_wukong(index, dry_run=False, verbose=False):
    """从钉钉拉取文档到悟空"""
    print("\n[步骤 2/3] 从钉钉拉取最新文档...")
    
    # 拉取最近7天的工作日志
    today = datetime.now()
    pulled_count = 0
    
    for i in range(7):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        query = f"{date_str} 工作日志"
        
        if verbose:
            print(f"\n  检查: {date_str}")
        
        search_result = search_dingtalk_doc(query, verbose)
        
        if search_result and search_result.get("documents"):
            for doc in search_result["documents"]:
                if doc["name"] == query:
                    node_id = doc["nodeId"]
                    
                    # 检查本地是否已存在
                    local_file = WORKSPACE / "work_logs" / f"{date_str}.md"
                    if local_file.exists():
                        if verbose:
                            print(f"    ℹ 本地已存在，跳过")
                        break
                    
                    # 读取钉钉文档内容
                    if not dry_run:
                        markdown = read_dingtalk_doc(node_id, verbose)
                        
                        if markdown:
                            local_file.parent.mkdir(exist_ok=True)
                            with open(local_file, 'w', encoding='utf-8') as f:
                                f.write(markdown)
                            print(f"    ✓ 已拉取: {date_str}")
                            pulled_count += 1
                            
                            # 更新索引
                            if "daily_logs" not in index["mappings"]:
                                index["mappings"]["daily_logs"] = {}
                            
                            index["mappings"]["daily_logs"][date_str] = {
                                "wukong_path": f"work_logs/{date_str}.md",
                                "dingtalk_node_id": node_id,
                                "dingtalk_url": doc.get("docUrl"),
                                "obsidian_path": f"Daily Notes/{date_str}.md",
                                "last_modified_wukong": datetime.now().isoformat(),
                                "last_modified_dingtalk": datetime.now().isoformat(),
                                "last_modified_obsidian": None,
                                "sync_status": "synced"
                            }
                    else:
                        print(f"    → [预览] 将拉取: {date_str}")
                        pulled_count += 1
                    break
    
    print(f"\n  ✓ 已拉取 {pulled_count} 个文档")


def generate_obsidian_sync_package(index, dry_run=False, verbose=False):
    """生成 Obsidian 同步包"""
    print("\n[步骤 3/3] 生成 Obsidian 同步包...")
    
    sync_dir = WORKSPACE / "sync_for_obsidian"
    
    if dry_run:
        print(f"  → [预览] 将生成同步包到: {sync_dir}")
        return
    
    # 清理旧同步包
    if sync_dir.exists():
        shutil.rmtree(sync_dir)
    
    sync_dir.mkdir(exist_ok=True)
    
    # 复制最新的工作日志（最近7天）
    logs_dir = WORKSPACE / "work_logs"
    daily_notes_dir = sync_dir / "Daily Notes"
    daily_notes_dir.mkdir(exist_ok=True)
    
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob("*.md"))[-7:]  # 最近7天
        for log_file in log_files:
            dest = daily_notes_dir / log_file.name
            shutil.copy2(log_file, dest)
            if verbose:
                print(f"    ✓ 复制: {log_file.name}")
    
    # 复制周报和月报
    for subdir, dest_name in [("weekly_summaries", "Weekly Reviews"), 
                               ("monthly_summaries", "Monthly Reviews")]:
        src_dir = WORKSPACE / subdir
        dest_dir = sync_dir / dest_name
        
        if src_dir.exists():
            dest_dir.mkdir(exist_ok=True)
            for file in src_dir.glob("*.md"):
                shutil.copy2(file, dest_dir / file.name)
                if verbose:
                    print(f"    ✓ 复制: {file.name}")
    
    # 复制索引文件
    shutil.copy2(INDEX_FILE, sync_dir / "sync_index.json")
    
    # 生成 README
    readme_content = f"""# Obsidian 同步包

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 使用说明

### 方法1: Git 同步（推荐）
```bash
cd /path/to/your/obsidian/vault
git pull origin main
```

### 方法2: 手动复制
将此文件夹中的内容复制到您的 Obsidian vault 对应目录：
- Daily Notes/ → 日常笔记
- Weekly Reviews/ → 周总结
- Monthly Reviews/ → 月总结

### 方法3: 网盘同步
配置网盘客户端同步此文件夹到您的本地 Obsidian vault

## 同步状态

详见 `sync_index.json` 文件
"""
    
    with open(sync_dir / "README.md", 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"  ✓ 已生成 Obsidian 同步包: {sync_dir}")
    print(f"    包含 {len(list(daily_notes_dir.glob('*.md')))} 个日常笔记")


def main():
    parser = argparse.ArgumentParser(description='悟空-钉钉-Obsidian 三端同步脚本')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不执行实际同步操作')
    parser.add_argument('--verbose', action='store_true', help='详细输出模式')
    args = parser.parse_args()
    
    print("=" * 70)
    print("悟空-钉钉-Obsidian 三端同步开始")
    print(f"工作空间: {WORKSPACE}")
    if args.dry_run:
        print("模式: 预览模式（不会执行实际操作）")
    print("=" * 70)
    
    # 加载索引
    index = load_index()
    
    try:
        # 步骤1：悟空 → 钉钉
        sync_daily_logs_to_dingtalk(index, args.dry_run, args.verbose)
        sync_weekly_summaries_to_dingtalk(index, args.dry_run, args.verbose)
        
        # 步骤2：钉钉 → 悟空
        sync_from_dingtalk_to_wukong(index, args.dry_run, args.verbose)
        
        # 步骤3：生成 Obsidian 同步包
        generate_obsidian_sync_package(index, args.dry_run, args.verbose)
        
        # 保存索引
        if not args.dry_run:
            save_index(index)
        
        print("\n" + "=" * 70)
        print("✓ 同步完成！")
        if not args.dry_run:
            print(f"索引文件: {INDEX_FILE}")
            print(f"Obsidian 同步包: {WORKSPACE / 'sync_for_obsidian'}")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n✗ 同步失败: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
