from __future__ import annotations

import os

from nonebot_plugin_alconna import MsgTarget, UniMessage, on_alconna
from nonebot_plugin_uninfo import Uninfo

from ..utils.data_manager import data_manager


bind_group = on_alconna(
    "绑定群聊",
    use_cmd_start=True,
    priority=5,
    block=True,
)
unbind_group = on_alconna(
    "解绑群聊",
    use_cmd_start=True,
    priority=5,
    block=True,
)


@bind_group.handle()
async def handle_bind_group(session: Uninfo, target: MsgTarget):
    if session.scene.is_private:
        await UniMessage("该命令需要在群聊中使用").finish()

    ics_path = data_manager.ensure_user_ics_path(session)
    if not os.path.exists(ics_path):
        await UniMessage("请先绑定课表！").finish()

    data_manager.add_user_to_scene(session, target)
    await UniMessage("绑定当前群聊成功！").finish()


@unbind_group.handle()
async def handle_unbind_group(session: Uninfo):
    if session.scene.is_private:
        await UniMessage("该命令需要在群聊中使用").finish()

    data_manager.remove_user_from_scene(session)
    await UniMessage("解绑当前群聊成功！").finish()
