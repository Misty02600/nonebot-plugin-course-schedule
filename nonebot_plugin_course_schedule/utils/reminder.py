from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone

from nonebot import logger
from nonebot_plugin_alconna import Target, UniMessage

from ..config import config
from .data_manager import data_manager
from .ics_parser import ics_parser


async def check_and_send_reminders():
    """定期检查并发送课程提醒。"""
    if not config.course_reminder_enabled:
        return

    shanghai_tz = timezone(timedelta(hours=8))
    now = datetime.now(shanghai_tz)
    reminder_time = now + timedelta(minutes=config.course_reminder_offset)
    reminder_time_end = reminder_time + timedelta(minutes=config.course_reminder_interval)
    logger.debug(
        f"正在检查 {reminder_time.strftime('%Y-%m-%d %H:%M')} 到 "
        f"{reminder_time_end.strftime('%Y-%m-%d %H:%M')} 的课程提醒。"
    )

    for scene_record in data_manager.list_scene_records():
        target_data = scene_record.get("target")
        if not target_data:
            continue

        try:
            target = Target.load(target_data)
        except Exception as exc:
            logger.warning(f"恢复提醒目标失败，跳过当前会话: {exc}")
            continue

        for user_key in scene_record["users"]:
            user_record = data_manager.get_user_record(user_key)
            if user_record is None:
                continue

            ics_path = data_manager.get_ics_file_path(user_key)
            if not os.path.exists(ics_path):
                continue

            try:
                courses = ics_parser.parse_ics_file(str(ics_path))
            except Exception as exc:
                logger.error(f"解析用户 {user_record['user_id']} 的课表失败: {exc}")
                continue

            reminded_courses = set()
            for course in courses:
                start_time = course["start_time"]
                course_key = (course["summary"], course["start_time"], course["end_time"])
                if course_key in reminded_courses:
                    continue
                if not (reminder_time <= start_time < reminder_time_end):
                    continue

                reminded_courses.add(course_key)
                summary = course["summary"]
                location = course.get("location") or "未知地点"
                minutes_left = math.ceil((start_time - now).total_seconds() / 60)
                message = UniMessage.at(user_record["user_id"])
                message += (
                    f" 课程提醒：\n"
                    f"课程：{summary}\n"
                    f"时间：{start_time.strftime('%H:%M')}\n"
                    f"地点：{location}\n"
                    f"还有 {minutes_left} 分钟就要上课啦，记得做好准备哦！"
                )

                try:
                    await target.send(message)
                    logger.debug(
                        f"已发送提醒给用户 {user_record['user_id']} "
                        f"（场景 {scene_record.get('scene_path')}）：{summary}"
                    )
                except Exception as exc:
                    logger.error(
                        f"发送提醒到场景 {scene_record.get('scene_path')} 失败: {exc}"
                    )
