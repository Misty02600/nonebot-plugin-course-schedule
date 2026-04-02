from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

from .config import Config, config

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_localstore")
require("nonebot_plugin_alconna")
require("nonebot_plugin_uninfo")

__plugin_meta__ = PluginMetadata(
    name="电子课程表",
    description="绑定课表、查看课程、查看群友的课程，以及……上课排行",
    usage="""▶ 课表帮助：打印本信息
▶ 绑定课表：发送你的 .ics 文件或 WakeUp 分享口令来绑定课表
  ▷ 重新绑定，并在群聊里自动绑定当前群聊
▶ 解绑课表：删掉课表
  ▷ 解绑会将你解绑所有群聊
▶ 绑定群聊：让自己显示在本群的课表中
  ▷ 绑定课表时会自动绑定群聊
▶ 解绑群聊：让自己从本群的课表中消失
▶ 查看课表 <日期>：显示你今天要上的课程
▶ 群课表 <日期>：显示群友正在上的课和将要上的课
▶ 上课排行：看看苦逼群友本周上了多少课
""",
    type="application",
    homepage="https://github.com/GLDYM/nonebot-plugin-course-schedule",
    config=Config,
    supported_adapters=inherit_supported_adapters(
        "nonebot_plugin_alconna",
        "nonebot_plugin_uninfo",
    ),
    extra={"author": "Polaris_Light", "version": "1.1.1", "priority": 5},
)

from nonebot_plugin_alconna import (
    UniMessage,
    on_alconna,
)
from nonebot_plugin_apscheduler import scheduler

from .commands import bind_group, bind_schedule, group_schedule, show_today, weekly_ranking
from .utils.reminder import check_and_send_reminders


scheduler.add_job(
    check_and_send_reminders,
    trigger="interval",
    minutes=config.course_reminder_interval,
    id="course_schedule_reminder",
    replace_existing=True,
)

help_cmd = on_alconna(
    "课表帮助",
    aliases={"课程帮助"},
    use_cmd_start=True,
    priority=5,
    block=True,
)


@help_cmd.handle()
async def handle_help():
    await UniMessage(__plugin_meta__.usage).finish()
