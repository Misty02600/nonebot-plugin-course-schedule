from pathlib import Path

from nonebot import get_plugin_config
from pydantic import BaseModel, Field


# fmt:off
class Config(BaseModel):
    course_font_path: str = Field(
        default_factory=lambda: str(
            Path(__file__).parent / "resources" / "MapleMono-NF-CN-Medium.ttf"
        )
    )
    course_reminder_enabled: bool = True
    course_reminder_offset: int = 30  # 上课前提醒提前量（分钟）
    course_reminder_interval: int = 5 # 上课提醒检查间隔（分钟），此值不应大于 60 或 course_reminder_offset。
# fmt:on

config = get_plugin_config(Config)
