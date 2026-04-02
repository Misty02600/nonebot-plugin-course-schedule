from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from nonebot.adapters import Bot
from nonebot_plugin_alconna import Image, MsgTarget, UniMessage, on_alconna
from nonebot_plugin_uninfo import Uninfo

from ..utils.data_manager import data_manager
from ..utils.ics_parser import ics_parser
from ..utils.image_generator import image_generator
from ..utils.profile_utils import resolve_user_profile
from ..utils.session_utils import get_scene_key


weekly_ranking = on_alconna(
    "上课排行",
    aliases={"本周上课排行"},
    use_cmd_start=True,
    priority=5,
    block=True,
)


@weekly_ranking.handle()
async def handle_weekly_ranking(bot: Bot, session: Uninfo, target: MsgTarget):
    if session.scene.is_private:
        await UniMessage("该命令需要在群聊中使用").finish()

    data_manager.touch_scene(session, target)
    scene_record = data_manager.get_scene_record(get_scene_key(session))
    if scene_record is None or not scene_record["users"]:
        await UniMessage("当前群聊还没有人绑定课表哦~").finish()

    now = datetime.now(timezone(timedelta(hours=8)))
    today = now.date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    ranking_data = []
    for user_key in scene_record["users"]:
        user_record = data_manager.get_user_record(user_key)
        if user_record is None:
            continue

        ics_path = data_manager.get_ics_file_path(user_key)
        if not os.path.exists(ics_path):
            continue

        try:
            courses = ics_parser.parse_ics_file(str(ics_path))
        except Exception:
            continue

        total_duration = timedelta()
        course_count = 0
        seen = set()

        for course in courses:
            key = (course["summary"], course["start_time"], course["end_time"])
            if key in seen:
                continue
            seen.add(key)

            course_date = course["start_time"].date()
            if start_of_week <= course_date <= end_of_week:
                total_duration += course["end_time"] - course["start_time"]
                course_count += 1

        if course_count == 0:
            continue

        profile = await resolve_user_profile(bot, session.scene, user_record)
        data_manager.update_user_snapshot(
            user_key,
            display_name=profile["display_name"],
            avatar=profile["avatar"],
        )
        ranking_data.append(
            {
                "user_id": user_record["user_id"],
                "nickname": profile["display_name"],
                "avatar": profile["avatar"],
                "total_duration": total_duration,
                "course_count": course_count,
            }
        )

    if not ranking_data:
        await UniMessage("本周大家都没有课呢！").finish()

    ranking_data.sort(key=lambda item: item["total_duration"], reverse=True)
    image_bytes = await image_generator.generate_ranking_image(
        ranking_data,
        start_of_week,
        end_of_week,
    )
    await UniMessage(Image(raw=image_bytes, name="weekly-ranking.png")).finish()
