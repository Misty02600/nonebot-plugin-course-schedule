from __future__ import annotations

from typing import Any

from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_uninfo.model import Member, Scene, User


def normalize_scalar(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw) if raw is not None else ""


def normalize_platforms(platform: str | set[str] | None) -> list[str]:
    if platform is None:
        return []
    if isinstance(platform, set):
        return sorted(str(item) for item in platform)
    return [str(platform)]


def platform_key(platform: str | set[str] | None) -> str:
    values = normalize_platforms(platform)
    return ",".join(values) if values else "-"


def build_user_key_from_parts(
    *,
    scope: str,
    adapter: str,
    platform: str | set[str] | None,
    user_id: str,
) -> str:
    return f"{scope}|{adapter}|{platform_key(platform)}|user|{user_id}"


def build_scene_key_from_parts(
    *,
    scope: str,
    adapter: str,
    platform: str | set[str] | None,
    scene_path: str,
) -> str:
    return f"{scope}|{adapter}|{platform_key(platform)}|scene|{scene_path}"


def get_user_key(session: Uninfo) -> str:
    return build_user_key_from_parts(
        scope=normalize_scalar(session.scope),
        adapter=normalize_scalar(session.adapter),
        platform=session.platform,
        user_id=session.user.id,
    )


def get_scene_key(session: Uninfo) -> str:
    return build_scene_key_from_parts(
        scope=normalize_scalar(session.scope),
        adapter=normalize_scalar(session.adapter),
        platform=session.platform,
        scene_path=session.scene_path,
    )


def get_display_name(
    *,
    user: User | None = None,
    member: Member | None = None,
    fallback: str | None = None,
) -> str:
    candidates = [
        member.nick if member else None,
        user.nick if user else None,
        user.name if user else None,
        fallback,
        user.id if user else None,
    ]
    for candidate in candidates:
        if candidate:
            return candidate
    return "未知用户"


def get_session_display_name(session: Uninfo) -> str:
    return get_display_name(user=session.user, member=session.member, fallback=session.user.id)


def get_member_lookup_id(scene: Scene) -> str:
    return scene.parent.id if scene.parent else scene.id
