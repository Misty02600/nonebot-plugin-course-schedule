from __future__ import annotations

from pathlib import Path

from arclet.alconna import Alconna, Args
from nonebot import logger
from nonebot_plugin_alconna import (
    AlconnaMatcher,
    File,
    Match,
    MsgTarget,
    UniMessage,
    UniMsg,
    on_alconna,
)
from nonebot_plugin_uninfo import Uninfo

from ..utils.data_manager import data_manager
from ..utils.ics_parser import ics_parser
from ..utils.session_utils import get_user_key

PROMPT_TIMEOUT_SECONDS = 60


bind_schedule = on_alconna(
    Alconna("绑定课表", Args["schedule_text?", str]),
    aliases={"绑定课程"},
    use_cmd_start=True,
    priority=5,
    block=True,
)
unbind_schedule = on_alconna(
    "解绑课表",
    aliases={"解绑课程"},
    use_cmd_start=True,
    priority=5,
    block=True,
)


def _decode_ics_bytes(raw: bytes) -> str | None:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


async def _extract_ics_content(message: UniMessage) -> tuple[str | None, str | None]:
    file_segments = list(message.select(File))
    if not file_segments:
        return None, None

    downloaded = await message.download()
    for file_segment in downloaded.select(File):
        try:
            if file_segment.raw:
                raw = file_segment.raw_bytes
            elif file_segment.path:
                raw = Path(file_segment.path).read_bytes()
            else:
                continue
        except Exception as exc:
            logger.warning(f"读取上传文件失败: {exc}")
            continue

        decoded = _decode_ics_bytes(raw)
        if decoded is not None:
            return decoded, None
        return None, "上传的文件无法按文本读取，请确认它是有效的 ICS 文件。"

    return None, "当前平台暂不支持直接读取该文件，请改为发送 WakeUp 口令或可下载的 ICS 文件。"


def _save_ics_content(session: Uninfo, ics_content: str):
    user_key = get_user_key(session)
    ics_path = data_manager.ensure_user_ics_path(session)
    with open(ics_path, "w", encoding="utf-8") as f:
        f.write(ics_content)

    ics_parser.clear_cache(str(ics_path))
    parsed_courses = ics_parser.parse_ics_file(str(ics_path))
    if parsed_courses:
        return

    data_manager.delete_user_ics(user_key)
    ics_parser.clear_cache(str(ics_path))
    raise ValueError("课表文件解析结果为空，请确认上传的是有效的 ICS 文件。")


async def _bind_from_wakeup_token(
    session: Uninfo,
    target: MsgTarget,
    token_text: str,
) -> str | None:
    token = ics_parser.parse_wakeup_token(token_text)
    if not token:
        return None

    try:
        json_data = await ics_parser.fetch_wakeup_schedule(token)
    except Exception as exc:
        logger.exception("处理 WakeUp 口令失败")
        return f"处理 WakeUp 口令失败: {exc}"

    if not json_data:
        return "无法获取 WakeUp 课程表数据，请检查口令是否正确或已过期。"

    ics_content = ics_parser.convert_wakeup_to_ics(json_data)
    if not ics_content:
        return "课程表数据解析失败，无法生成 ICS 文件。"

    try:
        _save_ics_content(session, ics_content)
    except ValueError as exc:
        return str(exc)
    if not session.scene.is_private:
        data_manager.add_user_to_scene(session, target)
    return "通过 WakeUp 口令绑定课表成功！"


@bind_schedule.handle()
async def handle_bind_schedule(
    matcher: AlconnaMatcher,
    session: Uninfo,
    target: MsgTarget,
    message: UniMsg,
    schedule_text: Match[str],
):
    data_manager.update_user_profile(session)

    has_inline_text = schedule_text.available and schedule_text.result.strip() != ""
    has_inline_file = any(True for _ in message.select(File))

    schedule_input = message
    if not has_inline_text and not has_inline_file:
        schedule_input = await matcher.prompt(
            f"请在{PROMPT_TIMEOUT_SECONDS}秒内发送你的 .ics 文件或 WakeUp 分享口令。",
            timeout=PROMPT_TIMEOUT_SECONDS,
        )
        if schedule_input is None:
            await UniMessage("已超时，请重新发送「绑定课表」。").finish()

    token_source = schedule_text.result.strip() if has_inline_text else schedule_input.extract_plain_text().strip()
    token_result = await _bind_from_wakeup_token(session, target, token_source)
    if token_result is not None:
        await UniMessage(token_result).finish()

    ics_content, file_error = await _extract_ics_content(schedule_input)
    if file_error is not None:
        await UniMessage(file_error).finish()
    if ics_content is not None:
        try:
            _save_ics_content(session, ics_content)
        except ValueError as exc:
            await UniMessage(str(exc)).finish()
        if not session.scene.is_private:
            data_manager.add_user_to_scene(session, target)
        await UniMessage("课表文件绑定成功！").finish()

    await UniMessage(
        "未识别的口令或文件格式，请确认是否为 WakeUp 分享口令或 .ics 文件。"
    ).finish()


@unbind_schedule.handle()
async def handle_unbind_schedule(session: Uninfo):
    user_key = get_user_key(session)
    ics_path = data_manager.ensure_user_ics_path(session)
    data_manager.delete_user_ics(user_key)
    ics_parser.clear_cache(str(ics_path))
    data_manager.remove_user_from_all_scenes(user_key)
    await UniMessage("解绑成功啦！").finish()
