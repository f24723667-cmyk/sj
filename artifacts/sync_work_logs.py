#!/usr/bin/env python3
"""
工作日志同步脚本
自动检查并同步缺失的工作日志文件从钉钉文档到本地
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def run_command(cmd: list[str]) -> dict:
    """执行 dws 命令并返回解析后的 JSON 结果"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            print(f"❌ 命令执行失败: {' '.join(cmd)}")
            print(f"错误信息: {result.stderr}")
            return {}
        
        output = result.stdout.strip()
        if not output:
            return {}
        
        return json.loads(output)
    except Exception as e:
        print(f"❌ 执行命令时出错: {e}")
        return {}


def get_date_range(days: int = 7) -> list[str]:
    """获取最近 N 天的日期列表（YYYY-MM-DD 格式）"""
    today = datetime.now()
    dates = []
    for i in range(days):
        date = today - timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))
    return sorted(dates)


def get_existing_logs(log_dir: str) -> set[str]:
    """获取本地已存在的日志文件日期集合"""
    existing = set()
    log_path = Path(log_dir)
    
    if not log_path.exists():
        print(f"📁 创建日志目录: {log_dir}")
        log_path.mkdir(parents=True, exist_ok=True)
        return existing
    
    for file in log_path.glob("*.md"):
        # 提取文件名中的日期部分（YYYY-MM-DD.md）
        date_str = file.stem
        if len(date_str) == 10 and date_str.count("-") == 2:
            existing.add(date_str)
    
    return existing


def search_dingtalk_doc(date_str: str) -> str | None:
    """在钉钉文档中搜索指定日期的工作日志，返回 nodeId"""
    # 尝试多种搜索格式
    search_queries = [
        f"{date_str} 工作日志",
        f"工作日志/{date_str}",
        f"{date_str}",
    ]
    
    for query in search_queries:
        cmd = ["dws", "doc", "search", "--query", query, "--format", "json"]
        result = run_command(cmd)
        
        if result.get("success") and result.get("documents"):
            # 查找最匹配的文档
            for doc in result["documents"]:
                name = doc.get("name", "")
                if date_str in name and "工作日志" in name:
                    return doc.get("nodeId")
            
            # 如果没有精确匹配，返回第一个结果
            if result["documents"]:
                return result["documents"][0].get("nodeId")
    
    return None


def read_dingtalk_doc(node_id: str) -> str | None:
    """读取钉钉文档内容，返回 markdown 文本"""
    cmd = ["dws", "doc", "read", "--node", node_id, "--format", "json"]
    result = run_command(cmd)
    
    if result.get("success"):
        return result.get("markdown")
    
    return None


def save_log_file(log_dir: str, date_str: str, content: str) -> bool:
    """保存日志内容到本地文件"""
    file_path = Path(log_dir) / f"{date_str}.md"
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"❌ 保存文件失败 {file_path}: {e}")
        return False


def send_notification(user_id: str, count: int):
    """发送钉钉消息通知"""
    message = f"✅ 已同步 {count} 个缺失的工作日志文件到本地文件夹"
    cmd = [
        "dws", "chat", "message", "send",
        "--user", user_id,
        "--text", message,
        "--format", "json"
    ]
    
    result = run_command(cmd)
    if result.get("success"):
        print(f"📱 已发送钉钉通知")
    else:
        print(f"⚠️ 发送钉钉通知失败")


def get_user_id(name: str) -> str | None:
    """根据姓名获取用户 userId"""
    cmd = ["dws", "contact", "user", "search", "--query", name, "--format", "json"]
    result = run_command(cmd)
    
    if result.get("success") and result.get("result"):
        return result["result"][0].get("userId")
    
    return None


def sync_work_logs(
    days: int = 7,
    log_dir: str = "work_logs",
    notify: bool = False,
    user_name: str | None = None
):
    """
    主同步函数
    
    Args:
        days: 检查的天数范围
        log_dir: 日志目录路径
        notify: 是否发送通知
        user_name: 用户姓名（用于发送通知）
    """
    print(f"🔍 开始检查工作日志同步（最近 {days} 天）...")
    print()
    
    # 步骤 1：获取日期范围
    date_list = get_date_range(days)
    print(f"📅 检查日期范围: {date_list[0]} 至 {date_list[-1]}")
    
    # 步骤 2：检查本地文件
    existing_logs = get_existing_logs(log_dir)
    missing_dates = [d for d in date_list if d not in existing_logs]
    
    print(f"📁 本地已有: {len(existing_logs)} 个文件")
    print(f"📋 缺失日期: {len(missing_dates)} 个")
    
    if not missing_dates:
        print("✅ 所有日期的工作日志都已存在，无需同步")
        return
    
    print()
    
    # 步骤 3 & 4：搜索并同步缺失的日志
    synced_count = 0
    synced_dates = []
    failed_dates = []
    
    for date_str in missing_dates:
        print(f"🔎 检查 {date_str}...")
        
        # 搜索钉钉文档
        node_id = search_dingtalk_doc(date_str)
        
        if not node_id:
            print(f"   ⚪ 未找到钉钉文档")
            failed_dates.append(date_str)
            continue
        
        print(f"   📄 找到文档 (nodeId: {node_id[:20]}...)")
        
        # 读取文档内容
        content = read_dingtalk_doc(node_id)
        
        if not content:
            print(f"   ❌ 读取文档内容失败")
            failed_dates.append(date_str)
            continue
        
        # 保存到本地
        if save_log_file(log_dir, date_str, content):
            print(f"   ✅ 已保存到 {log_dir}/{date_str}.md")
            synced_count += 1
            synced_dates.append(date_str)
        else:
            print(f"   ❌ 保存文件失败")
            failed_dates.append(date_str)
    
    # 步骤 5：报告结果
    print()
    print("=" * 60)
    print("📊 同步结果汇总")
    print("=" * 60)
    print(f"✅ 成功同步: {synced_count} 个文件")
    if synced_dates:
        for date in synced_dates:
            print(f"   - {date}")
    
    if failed_dates:
        print(f"⚪ 未能同步: {len(failed_dates)} 个文件")
        for date in failed_dates:
            print(f"   - {date}")
    
    print("=" * 60)
    
    # 步骤 6：发送通知
    if notify and synced_count > 0:
        print()
        if user_name:
            user_id = get_user_id(user_name)
            if user_id:
                send_notification(user_id, synced_count)
            else:
                print(f"⚠️ 未找到用户 '{user_name}' 的 userId")
        else:
            print("⚠️ 未提供用户姓名，跳过发送通知")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="工作日志同步工具")
    parser.add_argument("--days", type=int, default=7, help="检查的天数范围（默认 7 天）")
    parser.add_argument("--dir", type=str, default="work_logs", help="日志目录路径（默认 work_logs）")
    parser.add_argument("--notify", action="store_true", help="同步完成后发送钉钉通知")
    parser.add_argument("--user", type=str, help="接收通知的用户姓名")
    
    args = parser.parse_args()
    
    sync_work_logs(
        days=args.days,
        log_dir=args.dir,
        notify=args.notify,
        user_name=args.user
    )
