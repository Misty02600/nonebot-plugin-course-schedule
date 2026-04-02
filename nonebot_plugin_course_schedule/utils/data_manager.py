# -*- coding: utf-8 -*-
"""
本模块负责插件的数据管理，包括课表文件、用户档案和共享会话绑定关系。

当前绑定数据结构：
{
    "version": 2,
    "users": {
        "<user_key>": {
            "user_id": "...",
            "scope": "...",
            "adapter": "...",
            "platforms": [...],
            "display_name": "...",
            "avatar": "..."
        }
    },
    "scenes": {
        "<scene_key>": {
            "scene_path": "...",
            "scene_id": "...",
            "scene_type": 1,
            "parent_scene_id": "...",
            "scope": "...",
            "adapter": "...",
            "platforms": [...],
            "name": "...",
            "target": {...},
            "users": ["<user_key>", ...]
        }
    }
}
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import nonebot_plugin_localstore as store
from nonebot_plugin_alconna import Target
from nonebot_plugin_uninfo import Uninfo
from nonebot_plugin_uninfo import SupportAdapter, SupportScope

from .session_utils import (
    build_scene_key_from_parts,
    build_user_key_from_parts,
    get_scene_key,
    get_session_display_name,
    get_user_key,
    normalize_platforms,
    normalize_scalar,
)


class DataManager:
    """数据管理类"""

    CURRENT_VERSION = 2

    def __init__(self):
        self.data_path: Path = Path(store.get_plugin_config_dir())
        self.ics_path: Path = self.data_path / "ics"
        self.binding_data_file: Path = self.data_path / "userdata.json"
        self._init_data()

    def _init_data(self):
        """初始化插件数据文件和目录"""
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.ics_path.mkdir(exist_ok=True)
        if not self.binding_data_file.exists():
            self.save_binding_data(self._default_binding_data())

    def _default_binding_data(self) -> dict[str, Any]:
        return {"version": self.CURRENT_VERSION, "users": {}, "scenes": {}}

    def _is_legacy_binding_data(self, raw_data: Any) -> bool:
        if not isinstance(raw_data, dict):
            return False
        return "users" not in raw_data and "scenes" not in raw_data

    def _ics_filename_for_user_key(self, user_key: str) -> str:
        digest = hashlib.sha1(user_key.encode("utf-8")).hexdigest()
        return f"{digest}.ics"

    def _is_legacy_onebot_identity(self, *, scope: str, adapter: str, user_id: str) -> bool:
        return (
            scope == str(SupportScope.qq_client)
            and adapter == str(SupportAdapter.onebot11)
            and user_id.isdigit()
        )

    def _legacy_ics_path(self, user_id: str) -> Path:
        return self.ics_path / f"{user_id}.ics"

    def _migrate_legacy_ics_file(self, user_id: str, user_key: str):
        new_path = self.get_ics_file_path(user_key)
        if new_path.exists():
            return

        legacy_path = self._legacy_ics_path(user_id)
        if legacy_path.exists():
            legacy_path.replace(new_path)

    def _migrate_legacy_binding_data(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        migrated = self._default_binding_data()
        scope = str(SupportScope.qq_client)
        adapter = str(SupportAdapter.onebot11)

        for legacy_scene_id, legacy_user_ids in raw_data.items():
            if not isinstance(legacy_user_ids, list):
                continue

            scene_id = str(legacy_scene_id)
            scene_key = build_scene_key_from_parts(
                scope=scope,
                adapter=adapter,
                platform=None,
                scene_path=scene_id,
            )
            scene_record = {
                "scene_path": scene_id,
                "scene_id": scene_id,
                "scene_type": 1,
                "parent_scene_id": None,
                "scope": scope,
                "adapter": adapter,
                "platforms": [],
                "name": None,
                "target": Target.group(
                    scene_id,
                    scope=scope,
                    adapter=adapter,
                ).dump(save_self_id=False),
                "users": [],
            }

            for legacy_user_id in legacy_user_ids:
                user_id = str(legacy_user_id)
                user_key = build_user_key_from_parts(
                    scope=scope,
                    adapter=adapter,
                    platform=None,
                    user_id=user_id,
                )
                if user_key not in migrated["users"]:
                    migrated["users"][user_key] = {
                        "user_id": user_id,
                        "scope": scope,
                        "adapter": adapter,
                        "platforms": [],
                        "display_name": None,
                        "avatar": None,
                    }
                if user_key not in scene_record["users"]:
                    scene_record["users"].append(user_key)
                self._migrate_legacy_ics_file(user_id, user_key)

            migrated["scenes"][scene_key] = scene_record

        return migrated

    def _normalize_binding_data(self, raw_data: Any) -> dict[str, Any]:
        if not isinstance(raw_data, dict):
            return self._default_binding_data()

        if self._is_legacy_binding_data(raw_data):
            return self._migrate_legacy_binding_data(raw_data)

        data = self._default_binding_data()
        data["users"] = raw_data.get("users", {}) if isinstance(raw_data.get("users"), dict) else {}
        data["scenes"] = raw_data.get("scenes", {}) if isinstance(raw_data.get("scenes"), dict) else {}
        data["version"] = raw_data.get("version", self.CURRENT_VERSION)
        return data

    def load_binding_data(self) -> dict[str, Any]:
        """加载绑定数据，并在需要时自动迁移旧结构。"""
        try:
            with open(self.binding_data_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            normalized = self._default_binding_data()
            self.save_binding_data(normalized)
            return normalized

        normalized = self._normalize_binding_data(raw_data)
        if normalized != raw_data:
            self.save_binding_data(normalized)
        return normalized

    def save_binding_data(self, binding_data: dict[str, Any]):
        """保存绑定数据"""
        binding_data["version"] = self.CURRENT_VERSION
        with open(self.binding_data_file, "w", encoding="utf-8") as f:
            json.dump(binding_data, f, ensure_ascii=False, indent=4)

    def get_ics_file_path(self, user_key: str) -> Path:
        """获取用户 ICS 文件路径。"""
        return self.ics_path / self._ics_filename_for_user_key(user_key)

    def ensure_user_ics_path(self, session: Uninfo) -> Path:
        """获取当前用户的 ICS 文件路径，并按需迁移旧版 OneBot 文件名。"""
        user_key = get_user_key(session)
        path = self.get_ics_file_path(user_key)
        if path.exists():
            return path

        scope = normalize_scalar(session.scope)
        adapter = normalize_scalar(session.adapter)
        if self._is_legacy_onebot_identity(
            scope=scope,
            adapter=adapter,
            user_id=session.user.id,
        ):
            self._migrate_legacy_ics_file(session.user.id, user_key)
        return path

    def delete_user_ics(self, user_key: str):
        path = self.get_ics_file_path(user_key)
        if path.exists():
            path.unlink()

    def get_user_record(self, user_key: str) -> dict[str, Any] | None:
        return self.load_binding_data()["users"].get(user_key)

    def get_scene_record(self, scene_key: str) -> dict[str, Any] | None:
        return self.load_binding_data()["scenes"].get(scene_key)

    def list_scene_records(self) -> list[dict[str, Any]]:
        return list(self.load_binding_data()["scenes"].values())

    def touch_scene(self, session: Uninfo, target: Target):
        """刷新共享会话元数据，不改变绑定成员。"""
        if session.scene.is_private:
            return

        data = self.load_binding_data()
        scene_key = get_scene_key(session)
        record = data["scenes"].setdefault(
            scene_key,
            {
                "scene_path": session.scene_path,
                "scene_id": session.scene.id,
                "scene_type": int(session.scene.type),
                "parent_scene_id": session.scene.parent.id if session.scene.parent else None,
                "scope": normalize_scalar(session.scope),
                "adapter": normalize_scalar(session.adapter),
                "platforms": normalize_platforms(session.platform),
                "name": session.scene.name,
                "target": target.dump(),
                "users": [],
            },
        )
        record["scene_path"] = session.scene_path
        record["scene_id"] = session.scene.id
        record["scene_type"] = int(session.scene.type)
        record["parent_scene_id"] = session.scene.parent.id if session.scene.parent else None
        record["scope"] = normalize_scalar(session.scope)
        record["adapter"] = normalize_scalar(session.adapter)
        record["platforms"] = normalize_platforms(session.platform)
        record["name"] = session.scene.name
        record["target"] = target.dump()
        self.save_binding_data(data)

    def update_user_profile(self, session: Uninfo) -> str:
        """更新当前用户的档案快照。"""
        data = self.load_binding_data()
        user_key = get_user_key(session)
        avatar = session.member.user.avatar if session.member and session.member.user.avatar else session.user.avatar
        record = data["users"].setdefault(
            user_key,
            {
                "user_id": session.user.id,
                "scope": normalize_scalar(session.scope),
                "adapter": normalize_scalar(session.adapter),
                "platforms": normalize_platforms(session.platform),
                "display_name": None,
                "avatar": None,
            },
        )
        record["user_id"] = session.user.id
        record["scope"] = normalize_scalar(session.scope)
        record["adapter"] = normalize_scalar(session.adapter)
        record["platforms"] = normalize_platforms(session.platform)
        record["display_name"] = get_session_display_name(session)
        record["avatar"] = avatar
        self.save_binding_data(data)
        return user_key

    def update_user_snapshot(
        self,
        user_key: str,
        *,
        display_name: str | None = None,
        avatar: str | None = None,
    ):
        """用更新鲜的查询结果覆盖缓存资料。"""
        if display_name is None and avatar is None:
            return

        data = self.load_binding_data()
        record = data["users"].get(user_key)
        if record is None:
            return
        if display_name:
            record["display_name"] = display_name
        if avatar:
            record["avatar"] = avatar
        self.save_binding_data(data)

    def add_user_to_scene(self, session: Uninfo, target: Target):
        """将当前用户加入当前共享会话。"""
        if session.scene.is_private:
            return

        data = self.load_binding_data()
        user_key = get_user_key(session)
        avatar = session.member.user.avatar if session.member and session.member.user.avatar else session.user.avatar
        data["users"].setdefault(
            user_key,
            {
                "user_id": session.user.id,
                "scope": normalize_scalar(session.scope),
                "adapter": normalize_scalar(session.adapter),
                "platforms": normalize_platforms(session.platform),
                "display_name": get_session_display_name(session),
                "avatar": avatar,
            },
        )
        data["users"][user_key]["display_name"] = get_session_display_name(session)
        data["users"][user_key]["avatar"] = avatar

        scene_key = get_scene_key(session)
        scene_record = data["scenes"].setdefault(
            scene_key,
            {
                "scene_path": session.scene_path,
                "scene_id": session.scene.id,
                "scene_type": int(session.scene.type),
                "parent_scene_id": session.scene.parent.id if session.scene.parent else None,
                "scope": normalize_scalar(session.scope),
                "adapter": normalize_scalar(session.adapter),
                "platforms": normalize_platforms(session.platform),
                "name": session.scene.name,
                "target": target.dump(),
                "users": [],
            },
        )
        scene_record["scene_path"] = session.scene_path
        scene_record["scene_id"] = session.scene.id
        scene_record["scene_type"] = int(session.scene.type)
        scene_record["parent_scene_id"] = session.scene.parent.id if session.scene.parent else None
        scene_record["scope"] = normalize_scalar(session.scope)
        scene_record["adapter"] = normalize_scalar(session.adapter)
        scene_record["platforms"] = normalize_platforms(session.platform)
        scene_record["name"] = session.scene.name
        scene_record["target"] = target.dump()
        if user_key not in scene_record["users"]:
            scene_record["users"].append(user_key)
        self.save_binding_data(data)

    def remove_user_from_scene(self, session: Uninfo):
        """将当前用户从当前共享会话移除。"""
        if session.scene.is_private:
            return

        data = self.load_binding_data()
        scene_key = get_scene_key(session)
        user_key = get_user_key(session)
        scene_record = data["scenes"].get(scene_key)
        if scene_record is None:
            return
        if user_key in scene_record["users"]:
            scene_record["users"].remove(user_key)
        if not scene_record["users"]:
            del data["scenes"][scene_key]
        self.save_binding_data(data)

    def remove_user_from_all_scenes(self, user_key: str):
        """将用户从所有共享会话移除。"""
        data = self.load_binding_data()
        empty_scene_keys = []
        for scene_key, scene_record in data["scenes"].items():
            if user_key in scene_record["users"]:
                scene_record["users"].remove(user_key)
            if not scene_record["users"]:
                empty_scene_keys.append(scene_key)
        for scene_key in empty_scene_keys:
            del data["scenes"][scene_key]
        self.save_binding_data(data)


data_manager = DataManager()
