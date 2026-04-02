from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

from arclet.alconna import Alconna, Args
from nonebot import logger
from nonebot_plugin_alconna import Image, Match, UniMessage, on_alconna
from nonebot_plugin_uninfo import Uninfo

from ..utils.data_manager import data_manager
from ..utils.date_parser import DateParseError, parse_schedule_date_arg
from ..utils.ics_parser import ics_parser
from ..utils.image_generator import image_generator
from ..utils.session_utils import get_session_display_name


show_today = on_alconna(
    Alconna("课表", Args["day?", str]),
    aliases={"查看课表", "查看今日课表", "查看我的课表", "我的课表"},
    use_cmd_start=True,
    priority=5,
    block=True,
)


@show_today.handle()
async def handle_show_today(session: Uninfo, day: Match[str]):
    data_manager.update_user_profile(session)

    raw_day = day.result if day.available else ""
    shanghai_tz = timezone(timedelta(hours=8))
    now = datetime.now(shanghai_tz)

    try:
        target_date, mode = parse_schedule_date_arg(raw_day, now)
    except DateParseError:
        await UniMessage(
            "时间格式错误，请输入天数偏移或单日日期，例如：1、明天、下周三、4月2号"
        ).finish()

    ics_path = data_manager.ensure_user_ics_path(session)
    if not os.path.exists(ics_path):
        await UniMessage(
            "你还没有绑定课表哦~请发送「绑定课表」以绑定课表"
        ).finish()

    courses = ics_parser.parse_ics_file(str(ics_path))
    if mode == "today":
        filtered_courses = [
            course
            for course in courses
            if course["start_time"].date() == target_date and course["end_time"] > now
        ]
    else:
        filtered_courses = [
            course for course in courses if course["start_time"].date() == target_date
        ]

    if not filtered_courses:
        await UniMessage("当日没有课啦！").finish()

    filtered_courses.sort(key=lambda course: course["start_time"])

    merged_courses = []
    seen = {}
    for course in filtered_courses:
        key = (course["summary"], course["start_time"], course["end_time"])
        if key in seen:
            location = course.get("location")
            if location:
                existing_location = seen[key].get("location") or ""
                seen[key]["location"] = (
                    f"{existing_location}, {location}" if existing_location else location
                )
        else:
            seen[key] = course.copy()
            merged_courses.append(seen[key])

    nickname = get_session_display_name(session)
    for course in merged_courses:
        course["nickname"] = nickname

    logger.info(f"{session.user.id} 查询课表: {raw_day}")
    image_bytes = (
        await image_generator.generate_user_schedule_image(merged_courses, nickname)
        if mode == "today"
        else await image_generator.generate_user_schedule_image(
            merged_courses,
            nickname,
            target_date,
        )
    )
    await UniMessage(Image(raw=image_bytes, name="course-schedule.png")).finish()
