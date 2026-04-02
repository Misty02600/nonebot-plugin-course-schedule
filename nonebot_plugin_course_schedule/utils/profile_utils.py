from __future__ import annotations

from nonebot.adapters import Bot
from nonebot_plugin_uninfo import get_interface
from nonebot_plugin_uninfo.model import Scene

from .session_utils import get_display_name, get_member_lookup_id


async def resolve_user_profile(
    bot: Bot,
    scene: Scene,
    user_record: dict,
) -> dict[str, str | None]:
    display_name = user_record.get("display_name") or user_record["user_id"]
    avatar = user_record.get("avatar")

    interface = get_interface(bot)
    if interface is None:
        return {"display_name": display_name, "avatar": avatar}

    try:
        member = await interface.get_member(
            scene.type,
            get_member_lookup_id(scene),
            user_record["user_id"],
        )
    except Exception:
        member = None
    if member is not None:
        return {
            "display_name": get_display_name(
                user=member.user,
                member=member,
                fallback=display_name,
            ),
            "avatar": member.user.avatar or avatar,
        }

    try:
        user = await interface.get_user(user_record["user_id"])
    except Exception:
        user = None
    if user is not None:
        return {
            "display_name": get_display_name(user=user, fallback=display_name),
            "avatar": user.avatar or avatar,
        }

    return {"display_name": display_name, "avatar": avatar}
