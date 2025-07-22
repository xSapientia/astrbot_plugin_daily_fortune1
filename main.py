from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import json
import random
import os
from datetime import datetime, date
from typing import Dict, Optional, Tuple, Any
import aiofiles
import asyncio

@register(
    "astrbot_plugin_daily_fortune1",
    "xSapientia",
    "今日人品测试插件增强版",
    "0.0.1",
    "https://github.com/xSapientia/astrbot_plugin_daily_fortune1",
)
class DailyFortunePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.context = context
        self.config = config or {}

        # 数据文件路径
        self.data_dir = os.path.join("data", "plugin_data", "astrbot_plugin_daily_fortune1")
        self.fortune_file = os.path.join(self.data_dir, "fortunes.json")
        self.history_file = os.path.join(self.data_dir, "history.json")
        os.makedirs(self.data_dir, exist_ok=True)

        # 运势等级
        self.fortune_levels = [
            (0, 0, "极其倒霉", "😫"),
            (1, 2, "倒大霉", "😣"),
            (3, 10, "十分不顺", "😟"),
            (11, 20, "略微不顺", "😕"),
            (21, 30, "正常运气", "😐"),
            (31, 98, "好运", "😊"),
            (99, 99, "极其好运", "😄"),
            (100, 100, "万事皆允", "🤩")
        ]

        logger.info("今日人品插件1代 v0.0.1 加载成功！")

    def _get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self.config.get(key, default)

    async def _load_json(self, file_path: str) -> dict:
        """加载JSON文件"""
        if not os.path.exists(file_path):
            return {}
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content) if content else {}
        except Exception as e:
            logger.error(f"加载文件失败 {file_path}: {e}")
            return {}

    async def _save_json(self, file_path: str, data: dict):
        """保存JSON文件"""
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"保存文件失败 {file_path}: {e}")

    def _get_fortune_level(self, fortune: int) -> Tuple[str, str]:
        """获取运势等级和emoji"""
        for min_val, max_val, level, emoji in self.fortune_levels:
            if min_val <= fortune <= max_val:
                return level, emoji
        return "正常运气", "😐"

    async def _get_enhanced_user_info(self, event: AstrMessageEvent) -> Dict[str, str]:
        """获取增强的用户信息"""
        user_id = event.get_sender_id()
        info = {
            "user_id": user_id,
            "nickname": event.get_sender_name() or f"用户{user_id[-4:]}",
            "card": "",
            "title": ""
        }

        # 尝试从rawmessage插件获取增强信息
        if event.get_platform_name() == "aiocqhttp":
            try:
                if hasattr(event.message_obj, 'raw_message'):
                    raw = event.message_obj.raw_message
                    if isinstance(raw, dict) and 'sender' in raw:
                        sender = raw['sender']
                        info['nickname'] = sender.get('nickname', info['nickname'])
                        info['card'] = sender.get('card', '')
                        info['title'] = sender.get('title', '')
            except:
                pass

        return info

    def _format_user_name(self, info: Dict[str, str]) -> str:
        """格式化用户显示名称"""
        name = info['card'] if info['card'] else info['nickname']
        if info['title'] and info['title'] not in ['', 'unknown', None]:
            name = f"[{info['title']}]{name}"
        return name

    def _generate_fortune(self) -> int:
        """生成人品值"""
        algorithm = self._get_config("fortune_algorithm", "random")
        min_val = self._get_config("min_fortune", 0)
        max_val = self._get_config("max_fortune", 100)

        if algorithm == "weighted":
            # 加权算法，使中间值概率更高
            values = list(range(min_val, max_val + 1))
            center = (min_val + max_val) / 2
            weights = [100 * (1 / (10 * 2.5)) * (2.71828 ** (-0.5 * ((i - center) / 10) ** 2)) for i in values]
            return random.choices(values, weights=weights)[0]
        else:
            return random.randint(min_val, max_val)

    async def _get_llm_provider(self):
        """获取LLM提供商"""
        provider_id = self._get_config("llm_provider_id", "")

        if provider_id:
            provider = self.context.get_provider_by_id(provider_id)
            if provider:
                return provider

        return self.context.get_using_provider()

    async def _generate_with_llm(self, prompt_template: str, user_info: Dict[str, str], fortune: int, level: str) -> str:
        """使用LLM生成文本"""
        provider = await self._get_llm_provider()
        if not provider:
            return ""

        # 替换变量
        prompt = prompt_template.format(
            nickname=user_info.get('nickname', ''),
            card=user_info.get('card', ''),
            title=user_info.get('title', ''),
            jrrp=fortune,
            fortune=level
        )

        try:
            # 获取人格
            persona_name = self._get_config("persona_name", "")

            # 构建请求参数
            kwargs = {
                "prompt": prompt,
                "session_id": None,
                "contexts": []
            }

            # 尝试通过不同方式设置人格
            if persona_name:
                # 某些provider可能支持personality参数
                kwargs["personality"] = persona_name

            response = await provider.text_chat(**kwargs)
            if response and response.completion_text:
                return response.completion_text.strip()
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")

        return ""

    def _apply_template(self, template: str, **kwargs) -> str:
        """应用模板并替换变量"""
        try:
            # 处理可能的None值
            for key, value in kwargs.items():
                if value is None:
                    kwargs[key] = ""
            return template.format(**kwargs)
        except Exception as e:
            logger.error(f"模板应用失败: {e}, template: {template}, kwargs: {kwargs}")
            return template

    async def _clean_old_cache(self):
        """清理过期缓存"""
        cache_days = self._get_config("cache_days", 7)
        today = date.today()

        fortunes = await self._load_json(self.fortune_file)
        keys_to_delete = []

        for date_key in fortunes.keys():
            try:
                fortune_date = datetime.strptime(date_key, "%Y-%m-%d").date()
                if (today - fortune_date).days > cache_days:
                    keys_to_delete.append(date_key)
            except:
                pass

        for key in keys_to_delete:
            del fortunes[key]

        if keys_to_delete:
            await self._save_json(self.fortune_file, fortunes)

    @filter.command("jrrp")
    async def daily_fortune(self, event: AstrMessageEvent):
        """查看今日人品"""
        try:
            if not self._get_config("enable_plugin", True):
                yield event.plain_result("今日人品插件已关闭")
                return

            user_info = await self._get_enhanced_user_info(event)
            user_id = user_info['user_id']
            nickname = self._format_user_name(user_info)
            today = date.today().strftime("%Y-%m-%d")

            # 清理过期缓存
            await self._clean_old_cache()

            # 加载数据
            fortunes = await self._load_json(self.fortune_file)
            if today not in fortunes:
                fortunes[today] = {}

            # 检查是否已测试
            if user_id in fortunes[today]:
                # 已测试，返回查询结果
                data = fortunes[today][user_id]
                fortune = data["value"]
                level, emoji = self._get_fortune_level(fortune)

                # 应用查询模板
                query_template = self._get_config("query_template",
                    "📌 今日人品\n{nickname}，今天已经查询过了哦~\n今日人品值: {jrrp}\n运势: {fortune} {femoji}")

                result = self._apply_template(
                    query_template,
                    nickname=nickname,
                    jrrp=fortune,
                    fortune=level,
                    femoji=emoji
                )

                # 如果开启了显示缓存结果
                if self._get_config("show_cached_result", True) and "process" in data:
                    result += "\n\n-----以下为今日运势测算场景还原-----\n"
                    result_template = self._get_config("result_template",
                        "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}")
                    result += self._apply_template(
                        result_template,
                        process=data.get("process", ""),
                        jrrp=fortune,
                        fortune=level,
                        advice=data.get("advice", "")
                    )

                yield event.plain_result(result)
                return

            # 首次测试，发送检测提示
            detecting_template = self._get_config("detecting_message",
                "神秘的能量汇聚，{nickname}，你的命运即将显现，正在祈祷中...")
            detecting_msg = self._apply_template(detecting_template, nickname=nickname)
            yield event.plain_result(detecting_msg)

            # 生成人品值
            fortune = self._generate_fortune()
            level, emoji = self._get_fortune_level(fortune)

            # 使用LLM生成内容
            process_prompt = self._get_config("process_prompt",
                "使用{nickname}的简称称呼，模拟你使用水晶球缓慢复现今日结果的过程，50字以内")
            process = await self._generate_with_llm(process_prompt, user_info, fortune, level)
            if not process:
                process = f"{nickname}的水晶球中浮现出神秘的光芒..."

            advice_prompt = self._get_config("advice_prompt",
                "使用{nickname}的简称称呼，对{nickname}的今日人品值{jrrp}给出你的评语和建议，50字以内")
            advice = await self._generate_with_llm(advice_prompt, user_info, fortune, level)
            if not advice:
                advice = "保持平常心，做好自己。"

            # 保存数据
            fortunes[today][user_id] = {
                "value": fortune,
                "user_info": user_info,
                "process": process,
                "advice": advice,
                "time": datetime.now().strftime("%H:%M:%S")
            }
            await self._save_json(self.fortune_file, fortunes)

            # 保存到历史
            history = await self._load_json(self.history_file)
            if user_id not in history:
                history[user_id] = []
            history[user_id].append({
                "date": today,
                "value": fortune
            })
            # 只保留指定天数的历史
            history_days = self._get_config("history_days", 30)
            history[user_id] = history[user_id][-history_days:]
            await self._save_json(self.history_file, history)

            # 应用结果模板
            result_template = self._get_config("result_template",
                "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}")
            result = self._apply_template(
                result_template,
                process=process,
                jrrp=fortune,
                fortune=level,
                advice=advice
            )

            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"处理今日人品指令时出错: {e}", exc_info=True)
            yield event.plain_result("抱歉，处理您的请求时出现了错误。")

    @filter.command("jrrprank")
    async def fortune_rank(self, event: AstrMessageEvent):
        """查看今日人品排行"""
        try:
            if not self._get_config("enable_plugin", True):
                yield event.plain_result("今日人品插件已关闭")
                return

            if event.is_private_chat():
                yield event.plain_result("人品排行榜仅在群聊中可用")
                return

            today = date.today().strftime("%Y-%m-%d")
            fortunes = await self._load_json(self.fortune_file)

            if today not in fortunes or not fortunes[today]:
                yield event.plain_result("📊 今天还没有人查询人品哦~")
                return

            # 获取群内成员的人品数据
            group_fortunes = []
            for user_id, data in fortunes[today].items():
                user_info = data.get("user_info", {})
                if user_info:
                    nickname = self._format_user_name(user_info)
                else:
                    nickname = data.get("name", "未知用户")
                group_fortunes.append((nickname, data["value"]))

            # 排序
            group_fortunes.sort(key=lambda x: x[1], reverse=True)

            # 生成排行内容
            medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
            ranks = []

            rank_item_template = self._get_config("rank_item_template",
                "{medal} {nickname}: {jrrp} ({fortune})")

            for idx, (name, value) in enumerate(group_fortunes):
                medal = medals[idx] if idx < len(medals) else f"{idx+1}."
                level, _ = self._get_fortune_level(value)
                rank_item = self._apply_template(
                    rank_item_template,
                    medal=medal,
                    nickname=name,
                    jrrp=value,
                    fortune=level
                )
                ranks.append(rank_item)

            # 应用排行榜模板
            rank_template = self._get_config("rank_template",
                "📊【今日人品排行榜】{date}\n━━━━━━━━━━━━━━━\n{ranks}")
            result = self._apply_template(
                rank_template,
                date=today,
                ranks="\n".join(ranks)
            )

            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"处理人品排行指令时出错: {e}", exc_info=True)
            yield event.plain_result("抱歉，获取排行榜时出现了错误。")

    @filter.command("jrrphistory", alias={"jrrphi"})
    async def fortune_history(self, event: AstrMessageEvent):
        """查看人品历史"""
        try:
            if not self._get_config("enable_plugin", True):
                yield event.plain_result("今日人品插件已关闭")
                return

            # 获取目标用户
            target_id = event.get_sender_id()
            # TODO: 后续支持@查询他人记录

            history = await self._load_json(self.history_file)

            if target_id not in history or not history[target_id]:
                yield event.plain_result("还没有人品测试记录")
                return

            user_history = history[target_id]

            # 生成记录内容
            records = []
            for record in user_history[-10:]:  # 最近10条
                date_str = record["date"]
                value = record["value"]
                level, _ = self._get_fortune_level(value)
                records.append(f"{date_str}: {value} ({level})")

            # 计算统计
            all_values = [r["value"] for r in user_history]
            avg_jrrp = sum(all_values) / len(all_values)
            max_jrrp = max(all_values)
            min_jrrp = min(all_values)

            # 获取用户名
            user_info = await self._get_enhanced_user_info(event)
            nickname = self._format_user_name(user_info)

            # 应用历史模板
            history_template = self._get_config("history_template",
                "📚 {nickname} 的人品历史记录\n{records}\n\n📊 统计信息:\n平均人品值: {avgjrrp}\n最高人品值: {maxjrrp}\n最低人品值: {minjrrp}")
            result = self._apply_template(
                history_template,
                nickname=nickname,
                records="\n".join(records),
                avgjrrp=f"{avg_jrrp:.1f}",
                maxjrrp=max_jrrp,
                minjrrp=min_jrrp
            )

            yield event.plain_result(result)

        except Exception as e:
            logger.error(f"处理人品历史指令时出错: {e}")
            yield event.plain_result("抱歉，获取历史记录时出现了错误。")

    @filter.command("jrrpdelete", alias={"jrrpdel"})
    async def delete_fortune(self, event: AstrMessageEvent, confirm: str = ""):
        """删除个人数据"""
        try:
            if confirm != "--confirm":
                yield event.plain_result("⚠️ 警告：此操作将清除您的所有人品数据！\n如果确定要继续，请使用：/jrrpdelete --confirm")
                return

            user_id = event.get_sender_id()
            deleted = False

            # 删除今日人品数据
            fortunes = await self._load_json(self.fortune_file)
            for date_key in list(fortunes.keys()):
                if user_id in fortunes[date_key]:
                    del fortunes[date_key][user_id]
                    deleted = True
                    if not fortunes[date_key]:
                        del fortunes[date_key]

            if deleted:
                await self._save_json(self.fortune_file, fortunes)

            # 删除历史记录
            history = await self._load_json(self.history_file)
            if user_id in history:
                del history[user_id]
                await self._save_json(self.history_file, history)
                deleted = True

            if deleted:
                yield event.plain_result("✅ 已清除您的所有人品数据")
            else:
                yield event.plain_result("ℹ️ 您没有人品数据记录")

        except Exception as e:
            logger.error(f"清除用户数据时出错: {e}")
            yield event.plain_result("抱歉，清除数据时出现了错误。")

    @filter.command("jrrpreset", alias={"jrrpre"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def reset_all_fortune(self, event: AstrMessageEvent, confirm: str = ""):
        """清除所有数据（仅管理员）"""
        try:
            if confirm != "--confirm":
                yield event.plain_result("⚠️ 警告：此操作将清除所有人品数据！\n如果确定要继续，请使用：/jrrpreset --confirm")
                return

            # 删除所有数据文件
            for file_path in [self.fortune_file, self.history_file]:
                if os.path.exists(file_path):
                    os.remove(file_path)

            yield event.plain_result("✅ 所有人品数据已清除")
            logger.info(f"Admin {event.get_sender_id()} reset all fortune data")

        except Exception as e:
            yield event.plain_result(f"❌ 清除数据时出错: {str(e)}")

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("今日人品插件1代已卸载")
