from __future__ import annotations

import os
from datetime import datetime, time, timezone, timedelta

from arclet.alconna import Alconna, Args
from nonebot import logger
from nonebot.adapters import Bot
from nonebot_plugin_alconna import Image, Match, MsgTarget, UniMessage, on_alconna
from nonebot_plugin_uninfo import Uninfo

from ..utils.data_manager import data_manager
from ..utils.date_parser import DateParseError, parse_schedule_date_arg
from ..utils.ics_parser import ics_parser
from ..utils.image_generator import image_generator
from ..utils.profile_utils import resolve_user_profile
from ..utils.session_utils import get_scene_key


group_schedule = on_alconna(
    Alconna("群课表", Args["day?", str]),
    aliases={"群友上什么", "群友在上什么", "群友在上什么课"},
    use_cmd_start=True,
    priority=5,
    block=True,
)


@group_schedule.handle()
async def handle_group_schedule(
    bot: Bot,
    session: Uninfo,
    target: MsgTarget,
    day: Match[str],
):
    if session.scene.is_private:
        await UniMessage("该命令需要在群聊中使用").finish()

    data_manager.touch_scene(session, target)
    scene_record = data_manager.get_scene_record(get_scene_key(session))
    if scene_record is None or not scene_record["users"]:
        await UniMessage("当前群聊还没有人绑定课表哦~").finish()

    raw_day = day.result if day.available else ""
    logger.info(f"{session.scene_path} 查询群课表: {raw_day}")

    shanghai_tz = timezone(timedelta(hours=8))
    now = datetime.now(shanghai_tz)

    try:
        target_date, mode = parse_schedule_date_arg(raw_day, now)
        if mode == "today":
            target_time = now
        else:
            target_time = datetime.combine(target_date, time.min, tzinfo=shanghai_tz)
    except DateParseError:
        await UniMessage(
            "时间格式错误，请输入天数偏移或单日日期，例如：1、明天、下周三、4月2号"
        ).finish()

    next_courses = []
    no_course_summary = "今日无课" if mode == "today" else "当日无课"

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
            logger.warning(f"解析用户 {user_record['user_id']} 的课表失败: {exc}")
            continue

        target_courses = [
            course for course in courses if course["start_time"].date() == target_date
        ]
        current_course = None
        next_course = None
        for course in target_courses:
            if course["start_time"] <= target_time < course["end_time"]:
                current_course = course
                break
            if course["start_time"] > target_time and (
                next_course is None or course["start_time"] < next_course["start_time"]
            ):
                next_course = course

        profile = await resolve_user_profile(bot, session.scene, user_record)
        data_manager.update_user_snapshot(
            user_key,
            display_name=profile["display_name"],
            avatar=profile["avatar"],
        )
        display_course = current_course or next_course

        if display_course is not None:
            next_courses.append(
                {
                    "summary": display_course["summary"],
                    "description": display_course.get("description"),
                    "location": display_course.get("location"),
                    "start_time": display_course["start_time"],
                    "end_time": display_course["end_time"],
                    "user_id": user_record["user_id"],
                    "nickname": profile["display_name"],
                    "avatar": profile["avatar"],
                }
            )
        else:
            next_courses.append(
                {
                    "summary": no_course_summary,
                    "description": "",
                    "location": "",
                    "start_time": None,
                    "end_time": None,
                    "user_id": user_record["user_id"],
                    "nickname": profile["display_name"],
                    "avatar": profile["avatar"],
                }
            )

    if not next_courses:
        await UniMessage("米娜桑接下来都没有课啦！").finish()

    next_courses.sort(key=lambda course: (course["start_time"] is None, course["start_time"]))
    image_bytes = await image_generator.generate_schedule_image(next_courses)
    await UniMessage(Image(raw=image_bytes, name="group-course-schedule.png")).finish()
