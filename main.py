import json
import os
import hashlib
from datetime import datetime, date
import random
from typing import Dict, Any, Optional
import asyncio
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
from astrbot.api.provider import ProviderRequest, LLMResponse


@register("daily_fortune", "阿凌", "今日人品检测插件", "1.0.0", "https://github.com/example/astrbot_plugin_daily_fortune1")
class DailyFortunePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 数据存储路径 - 修改为指定路径
        self.data_dir = Path("data/plugin_data/astrbot_plugin_daily_fortune")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.fortune_file = self.data_dir / "fortune_data.json"
        self.history_file = self.data_dir / "fortune_history.json"

        # 加载数据
        self.fortune_data = self._load_data(self.fortune_file, {})
        self.history_data = self._load_data(self.history_file, {})

        logger.info("今日人品插件已加载")

    def _load_data(self, file_path: Path, default_data: Any) -> Any:
        """加载数据文件"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载数据文件失败: {e}")
        return default_data

    def _save_data(self, file_path: Path, data: Any):
        """保存数据文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据文件失败: {e}")

    def _get_fortune_level_desc(self, fortune_value: int) -> str:
        """根据人品值获取运势描述"""
        if fortune_value == 0:
            return "极其倒霉"
        elif 1 <= fortune_value <= 2:
            return "倒大霉"
        elif 3 <= fortune_value <= 10:
            return "十分不顺"
        elif 11 <= fortune_value <= 20:
            return "略微不顺"
        elif 21 <= fortune_value <= 30:
            return "正常运气"
        elif 31 <= fortune_value <= 98:
            return "好运"
        elif fortune_value == 99:
            return "极其好运"
        elif fortune_value == 100:
            return "万事皆允"
        else:
            return "未知运势"

    def _generate_fortune_value(self, user_id: str, today: str) -> int:
        """基于用户ID和日期生成固定的人品值"""
        min_val = self.config.get("min_fortune", 0)
        max_val = self.config.get("max_fortune", 100)

        # 使用用户ID和日期作为种子生成固定随机数
        seed_string = f"{user_id}_{today}"
        hash_obj = hashlib.md5(seed_string.encode())
        hash_int = int(hash_obj.hexdigest(), 16)

        # 生成范围内的值
        fortune_value = min_val + (hash_int % (max_val - min_val + 1))

        logger.info(f"Generated fortune for {user_id}: {fortune_value}")
        return fortune_value

    async def _get_llm_provider(self):
        """获取LLM供应商"""
        provider_id = self.config.get("provider_id", "").strip()

        if provider_id:
            # 使用指定的供应商ID
            provider = self.context.get_provider_by_id(provider_id)
            if provider:
                return provider
            logger.warning(f"指定的供应商ID {provider_id} 未找到，使用默认供应商")

        # 检查是否配置了自定义API
        api_key = self.config.get("api_key", "").strip()
        api_url = self.config.get("api_url", "").strip()
        model_name = self.config.get("model_name", "").strip()

        if api_key and api_url and model_name:
            # TODO: 这里需要根据实际情况创建自定义供应商
            # 暂时回退到默认供应商
            logger.info("检测到自定义API配置，但暂不支持动态创建供应商，使用默认供应商")

        # 使用默认供应商
        return self.context.get_using_provider()

    async def _get_persona_prompt(self) -> str:
        """获取人格提示词"""
        persona_name = self.config.get("persona_name", "").strip()

        if persona_name:
            # 查找指定人格
            personas = self.context.provider_manager.personas
            for persona in personas:
                # personas 可能是 Personality 对象列表
                try:
                    # 检查是否是 Personality 对象
                    if hasattr(persona, '__dict__'):
                        # 使用属性访问
                        p_name = getattr(persona, 'name', None)
                        if p_name == persona_name:
                            return getattr(persona, 'prompt', '')
                    elif isinstance(persona, dict):
                        # 字典访问
                        if persona.get('name') == persona_name:
                            return persona.get('prompt', '')
                except Exception as e:
                    logger.debug(f"检查人格时出错: {e}")
                    continue
            logger.warning(f"指定的人格 {persona_name} 未找到，使用默认人格")

        # 使用默认人格
        try:
            default_persona = self.context.provider_manager.selected_default_persona
            if default_persona:
                # default_persona 通常是一个字典 {"name": "xxx"}
                default_name = default_persona.get("name") if isinstance(default_persona, dict) else None

                if default_name:
                    personas = self.context.provider_manager.personas
                    for persona in personas:
                        try:
                            if hasattr(persona, '__dict__'):
                                p_name = getattr(persona, 'name', None)
                                if p_name == default_name:
                                    return getattr(persona, 'prompt', '')
                            elif isinstance(persona, dict):
                                if persona.get('name') == default_name:
                                    return persona.get('prompt', '')
                        except:
                            continue
        except Exception as e:
            logger.debug(f"获取默认人格失败: {e}")

        return ""

    async def _call_llm_for_fortune(self, event: AstrMessageEvent, fortune_value: int) -> str:
        """调用LLM生成人品检测结果"""
        try:
            provider = await self._get_llm_provider()
            if not provider:
                return f"🔮 水晶球显现出数字...\n\n💎 人品值：{fortune_value}\n✨ 运势：{self._get_fortune_level_desc(fortune_value)}\n💬 建议：保持平常心，一切顺其自然。"

            user_name = event.get_sender_name()
            fortune_desc = self._get_fortune_level_desc(fortune_value)

            # 构建提示词
            detection_prompt = self.config.get("detection_prompt",
                "测试今日人品的时候，显示user_id的 title&card/nickname，模拟一下水晶球上显现今日人品值的过程、结果，字数不超过50字")
            suggestion_prompt = self.config.get("suggestion_prompt",
                "你对使用人今日人品值下的建议，字数不超过50字")

            full_prompt = f"""用户【{user_name}】今日人品值为{fortune_value}，运势为{fortune_desc}。

第一部分：{detection_prompt}
第二部分：{suggestion_prompt}

请分两部分回复，使用以下格式：
🔮 [第一部分内容]

💎 人品值：{fortune_value}
✨ 运势：{fortune_desc}
💬 建议：[第二部分内容]"""

            # 获取人格提示
            system_prompt = await self._get_persona_prompt()

            # 调用LLM
            response = await provider.text_chat(
                prompt=full_prompt,
                session_id=None,
                contexts=[],
                image_urls=[],
                func_tool=None,
                system_prompt=system_prompt
            )

            if response and response.completion_text:
                return response.completion_text
            else:
                return f"🔮 水晶球显现出数字...\n\n💎 人品值：{fortune_value}\n✨ 运势：{fortune_desc}\n💬 建议：保持平常心，一切顺其自然。"

        except Exception as e:
            logger.error(f"调用LLM失败: {e}")
            return f"🔮 水晶球显现出数字...\n\n💎 人品值：{fortune_value}\n✨ 运势：{fortune_desc}\n💬 建议：保持平常心，一切顺其自然。"

    @filter.command("jrrp")
    async def jrrp_command(self, event: AstrMessageEvent):
        """今日人品检测命令"""
        if not self.config.get("enabled", True):
            yield event.plain_result("今日人品插件已关闭")
            return

        user_id = event.get_sender_id()
        today = date.today().strftime("%Y-%m-%d")
        user_key = f"{user_id}_{today}"

        # 检查今日是否已检测
        if user_key in self.fortune_data:
            # 已检测，显示查询结果
            fortune_info = self.fortune_data[user_key]
            fortune_value = fortune_info["fortune_value"]
            fortune_desc = self._get_fortune_level_desc(fortune_value)
            user_name = event.get_sender_name()

            result = f"📌 【{user_name}】今日人品\n"
            result += f"{user_name}哥哥，今天已经查询过了哦~\n"
            result += f"今日人品值: {fortune_value}\n"
            result += f"运势: {fortune_desc} 😊\n\n"
            result += "-----以下为今日运势测算场景还原-----\n"
            result += fortune_info["llm_response"]

            yield event.plain_result(result)
            return

        # 首次检测，先发送检测中提示
        detecting_msg = self.config.get("detecting_message",
            "神秘的能量汇聚，窥见你的命运，正在祈祷中...")
        yield event.plain_result(detecting_msg)

        # 生成人品值
        fortune_value = self._generate_fortune_value(user_id, today)

        # 调用LLM生成响应
        llm_response = await self._call_llm_for_fortune(event, fortune_value)

        # 保存数据
        fortune_info = {
            "user_id": user_id,
            "user_name": event.get_sender_name(),
            "fortune_value": fortune_value,
            "fortune_desc": self._get_fortune_level_desc(fortune_value),
            "date": today,
            "llm_response": llm_response,
            "group_id": event.get_group_id() if event.get_group_id() else "private"
        }
        self.fortune_data[user_key] = fortune_info
        self._save_data(self.fortune_file, self.fortune_data)

        # 保存历史记录
        if user_id not in self.history_data:
            self.history_data[user_id] = []

        self.history_data[user_id].append({
            "date": today,
            "fortune_value": fortune_value,
            "fortune_desc": self._get_fortune_level_desc(fortune_value)
        })
        self._save_data(self.history_file, self.history_data)

        # 发送最终结果
        user_name = event.get_sender_name()
        final_result = f"【{user_name}】开始测试今日人品...\n\n{llm_response}"
        yield event.plain_result(final_result)

    @filter.command("jrrprank")
    async def jrrp_rank_command(self, event: AstrMessageEvent):
        """人品排行榜命令"""
        if not self.config.get("enabled", True):
            yield event.plain_result("今日人品插件已关闭")
            return

        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("此命令仅在群聊中可用")
            return

        today = date.today().strftime("%Y-%m-%d")

        # 筛选今日该群的人品记录
        group_fortunes = []
        for key, info in self.fortune_data.items():
            if key.endswith(f"_{today}") and (info.get("group_id") == group_id or
                                             (info.get("group_id") == "private" and
                                              info.get("user_id") in await self._get_group_member_list(event, group_id))):
                group_fortunes.append(info)

        if not group_fortunes:
            yield event.plain_result("今日群内还没有人测试人品哦~")
            return

        # 按人品值排序
        group_fortunes.sort(key=lambda x: x["fortune_value"], reverse=True)

        # 获取显示数量限制
        display_limit = self.config.get("rank_display_limit", 10)
        if display_limit == -1:
            display_limit = len(group_fortunes)
        else:
            display_limit = min(display_limit, len(group_fortunes))

        # 构建美化的排行榜
        result = f"📊【今日人品排行榜】{today}\n"
        result += "━━━━━━━━━━━━━━━\n"

        for i, info in enumerate(group_fortunes[:display_limit]):
            rank_emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}."
            # 格式化名字，确保对齐
            name = info['user_name']
            # 限制名字长度
            if len(name) > 8:
                name = name[:7] + "..."
            result += f"{rank_emoji} {name}: {info['fortune_value']} ({info['fortune_desc']})\n"

        if len(group_fortunes) > display_limit:
            result += f"\n... 还有{len(group_fortunes) - display_limit}人"

        yield event.plain_result(result)

    async def _get_group_member_list(self, event: AstrMessageEvent, group_id: str) -> list:
        """获取群成员列表"""
        try:
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                if isinstance(event, AiocqhttpMessageEvent):
                    client = event.bot
                    members = await client.api.get_group_member_list(group_id=group_id)
                    return [str(m.get('user_id')) for m in members if m.get('user_id')]
        except:
            pass
        return []

    @filter.command("jrrphistory")
    async def jrrp_history_command(self, event: AstrMessageEvent):
        """查看个人人品历史"""
        async for result in self._show_history(event):
            yield result

    @filter.command("jrrphi")
    async def jrrp_hi_command(self, event: AstrMessageEvent):
        """查看个人人品历史（简化命令）"""
        async for result in self._show_history(event):
            yield result

    async def _show_history(self, event: AstrMessageEvent):
        """显示个人人品历史"""
        if not self.config.get("enabled", True):
            yield event.plain_result("今日人品插件已关闭")
            return

        user_id = event.get_sender_id()

        if user_id not in self.history_data or not self.history_data[user_id]:
            yield event.plain_result("您还没有人品历史记录")
            return

        user_name = event.get_sender_name()
        history = self.history_data[user_id]

        # 按日期倒序显示最近的记录
        history_sorted = sorted(history, key=lambda x: x["date"], reverse=True)

        result = f"📚 {user_name} 的人品历史记录\n\n"

        # 显示最近10条记录
        for i, record in enumerate(history_sorted[:10]):
            date_str = record["date"]
            fortune_value = record["fortune_value"]
            fortune_desc = record["fortune_desc"]
            result += f"{date_str}: {fortune_value} ({fortune_desc})\n"

        if len(history_sorted) > 10:
            result += f"\n... 共{len(history_sorted)}条记录，仅显示最近10条"

        # 计算统计信息
        values = [r["fortune_value"] for r in history]
        avg_value = sum(values) / len(values)
        max_value = max(values)
        min_value = min(values)

        result += f"\n\n📊 统计信息:\n"
        result += f"平均人品值: {avg_value:.1f}\n"
        result += f"最高人品值: {max_value}\n"
        result += f"最低人品值: {min_value}"

        yield event.plain_result(result)

    @filter.command("jrrpdelete")
    async def jrrp_delete_command(self, event: AstrMessageEvent, confirm: str = ""):
        """删除个人数据"""
        async for result in self._delete_user_data(event, confirm):
            yield result

    @filter.command("jrrpdel")
    async def jrrp_del_command(self, event: AstrMessageEvent, confirm: str = ""):
        """删除个人数据（简化命令）"""
        async for result in self._delete_user_data(event, confirm):
            yield result

    async def _delete_user_data(self, event: AstrMessageEvent, confirm: str):
        """删除用户数据"""
        if not self.config.get("enabled", True):
            yield event.plain_result("今日人品插件已关闭")
            return

        if confirm != "--confirm":
            yield event.plain_result("⚠️ 此操作将清除您的所有人品数据，包括历史记录\n如需确认，请使用: /jrrpdelete --confirm")
            return

        user_id = event.get_sender_id()
        user_name = event.get_sender_name()

        # 删除今日人品数据
        keys_to_delete = []
        for key in self.fortune_data.keys():
            if key.startswith(f"{user_id}_"):
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.fortune_data[key]

        # 删除历史数据
        if user_id in self.history_data:
            del self.history_data[user_id]

        # 保存数据
        self._save_data(self.fortune_file, self.fortune_data)
        self._save_data(self.history_file, self.history_data)

        yield event.plain_result(f"✅ {user_name} 的所有人品数据已清除")

    @filter.command("jrrpreset")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def jrrp_reset_command(self, event: AstrMessageEvent, confirm: str = ""):
        """重置所有数据（仅管理员可用）"""
        if not self.config.get("enabled", True):
            yield event.plain_result("今日人品插件已关闭")
            return

        if confirm != "--confirm":
            yield event.plain_result("⚠️ 此操作将清除所有用户的人品数据！\n如需确认，请使用: /jrrpreset --confirm")
            return

        # 清空所有数据
        self.fortune_data.clear()
        self.history_data.clear()

        # 保存空数据
        self._save_data(self.fortune_file, self.fortune_data)
        self._save_data(self.history_file, self.history_data)

        yield event.plain_result("✅ 所有人品数据已重置")

    async def terminate(self):
        """插件卸载时调用"""
        import shutil

        # 根据配置决定是否删除数据
        if self.config.get("delete_data_on_uninstall", False):
            # 删除数据目录
            if self.data_dir.exists():
                shutil.rmtree(self.data_dir)
                logger.info(f"已删除插件数据目录: {self.data_dir}")

        # 根据配置决定是否删除配置文件
        if self.config.get("delete_config_on_uninstall", False):
            # 删除配置文件
            config_file = Path(f"data/config/astrbot_plugin_daily_fortune1_config.json")
            if config_file.exists():
                config_file.unlink()
                logger.info(f"已删除配置文件: {config_file}")

        logger.info("今日人品插件已卸载")
