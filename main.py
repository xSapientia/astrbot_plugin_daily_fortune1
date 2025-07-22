import json
import os
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register(
    "astrbot_plugin_daily_fortune1",
    "xSapientia",
    "每日运势和人品值插件",
    "0.0.1",
    "https://github.com/xSapientia/astrbot_plugin_daily_fortune1"
)
class DailyFortunePlugin(Star):
    def __init__(self, context: Context):
        """初始化插件"""
        super().__init__(context)

        self.data_dir = "data/plugin_data/astrbot_plugin_daily_fortune1"
        self.config_file = "data/config/astrbot_plugin_daily_fortune1_config.json"
        self.ensure_data_dir()

        # 加载配置
        self.config = self.load_config()

        # 加载数据
        self.fortune_data = self.load_data("fortune_data.json")
        self.history_data = self.load_data("history_data.json")

        # 运势等级映射
        self.fortune_levels = {
            (0, 20): "大凶",
            (21, 40): "凶",
            (41, 60): "平",
            (61, 80): "吉",
            (81, 100): "大吉"
        }

        # 表情映射
        self.fortune_emojis = {
            "大凶": "😱",
            "凶": "😔",
            "平": "😐",
            "吉": "😊",
            "大吉": "🎉"
        }

        logger.info("DailyFortunePlugin 插件已加载")

    def load_config(self) -> Dict:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}")
        return {}

    def ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        config_dir = os.path.dirname(self.config_file)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

    def load_data(self, filename: str) -> Dict:
        """加载数据文件"""
        filepath = os.path.join(self.data_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_data(self, data: Dict, filename: str):
        """保存数据到文件"""
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def get_user_info(self, event: AstrMessageEvent) -> Dict[str, str]:
        """获取用户信息"""
        user_info = {
            "nickname": event.get_sender_name() or "用户",
            "card": "",
            "title": ""
        }

        try:
            # 尝试从消息中提取增强信息
            if hasattr(event, 'message_obj') and hasattr(event.message_obj, 'message_str'):
                message_str = event.message_obj.message_str
                if "<tip>" in message_str and "</tip>" in message_str:
                    tip_start = message_str.find("<tip>") + 5
                    tip_end = message_str.find("</tip>")
                    tip_content = message_str[tip_start:tip_end]

                    if "RawMessage" in tip_content:
                        try:
                            json_start = tip_content.find("{")
                            json_end = tip_content.rfind("}") + 1
                            if json_start != -1 and json_end > json_start:
                                json_str = tip_content[json_start:json_end]
                                raw_data = json.loads(json_str)

                                sender = raw_data.get("sender", {})
                                user_info["nickname"] = sender.get("nickname", user_info["nickname"])
                                user_info["card"] = sender.get("card", "")
                                user_info["title"] = sender.get("title", "")
                        except Exception as e:
                            logger.debug(f"解析增强信息失败: {e}")
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")

        return user_info

    def get_fortune_level(self, jrrp: int) -> str:
        """根据人品值获取运势等级"""
        for (min_val, max_val), level in self.fortune_levels.items():
            if min_val <= jrrp <= max_val:
                return level
        return "平"

    def get_today_key(self) -> str:
        """获取今日日期键值"""
        return datetime.now().strftime("%Y-%m-%d")

    def generate_jrrp(self, user_id: str) -> int:
        """生成人品值"""
        algorithm = self.config.get("jrrp_algorithm", "random")

        if algorithm == "random":
            return random.randint(0, 100)
        elif algorithm == "pseudo_random":
            seed = f"{user_id}{self.get_today_key()}"
            random.seed(hash(seed))
            result = random.randint(0, 100)
            random.seed()
            return result
        else:
            return random.randint(0, 100)

    def clean_old_cache(self):
        """清理过期的缓存数据"""
        cache_days = self.config.get("result_cache_days", 7)
        cutoff_date = datetime.now() - timedelta(days=cache_days)

        for user_id in list(self.fortune_data.keys()):
            user_data = self.fortune_data[user_id]
            for date_key in list(user_data.keys()):
                try:
                    date_obj = datetime.strptime(date_key, "%Y-%m-%d")
                    if date_obj < cutoff_date:
                        del user_data[date_key]
                except:
                    pass
            if not user_data:
                del self.fortune_data[user_id]

    async def call_llm(self, prompt: str, context_list: list = None) -> str:
        """调用LLM"""
        try:
            provider_id = self.config.get("llm_provider_id")
            if provider_id:
                provider = self.context.get_provider_by_id(provider_id)
            else:
                provider = self.context.get_using_provider()

            if not provider:
                logger.warning("未找到可用的LLM提供商")
                return ""

            persona_name = self.config.get("persona_name")
            system_prompt = ""
            if persona_name:
                all_personas = self.context.provider_manager.personas
                persona = next((p for p in all_personas if p.get('name') == persona_name), None)
                if persona:
                    system_prompt = persona.get('prompt', '')

            response = await provider.text_chat(
                prompt=prompt,
                contexts=context_list or [],
                system_prompt=system_prompt
            )

            return response.completion_text
        except Exception as e:
            logger.error(f"调用LLM失败: {e}")
            return ""

    def replace_variables(self, template: str, variables: Dict[str, Any]) -> str:
        """替换模板中的变量"""
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    @filter.command("jrrp")
    async def jrrp_command(self, event: AstrMessageEvent):
        """今日人品值指令"""
        user_id = event.get_sender_id()
        today = self.get_today_key()
        user_info = await self.get_user_info(event)

        self.clean_old_cache()

        if user_id in self.fortune_data and today in self.fortune_data[user_id]:
            # 已查询过
            cached_data = self.fortune_data[user_id][today]

            variables = {
                "nickname": user_info["nickname"],
                "card": user_info["card"],
                "title": user_info["title"],
                "jrrp": cached_data["jrrp"],
                "fortune": cached_data["fortune"],
                "femoji": self.fortune_emojis.get(cached_data["fortune"], "😐")
            }

            query_template = self.config.get("query_template",
                "📌 今日人品\n{nickname}，今天已经查询过了哦~\n今日人品值: {jrrp}\n运势: {fortune} {femoji}")

            result = self.replace_variables(query_template, variables)

            if self.config.get("show_cached_result", True) and "full_result" in cached_data:
                result += f"\n\n-----以下为今日运势测算场景还原-----\n{cached_data['full_result']}"

            yield event.plain_result(result)
        else:
            # 首次查询
            jrrp = self.generate_jrrp(user_id)
            fortune = self.get_fortune_level(jrrp)

            detecting_text = self.config.get("detecting_text",
                "神秘的能量汇聚，{nickname}，你的命运即将显现，正在祈祷中...")
            detecting_msg = self.replace_variables(detecting_text, {"nickname": user_info["nickname"]})
            yield event.plain_result(detecting_msg)

            variables = {
                "nickname": user_info["nickname"],
                "card": user_info["card"],
                "title": user_info["title"],
                "jrrp": jrrp,
                "fortune": fortune,
                "femoji": self.fortune_emojis.get(fortune, "😐")
            }

            # 生成过程和建议
            process_prompt_template = self.config.get("process_prompt_template",
                "使用{nickname}称呼，模拟你使用水晶球缓慢复现今日结果的过程，50字以内")
            process_prompt = self.replace_variables(process_prompt_template, variables)
            process_text = await self.call_llm(process_prompt)
            if not process_text:
                process_text = f"水晶球中浮现出{user_info['nickname']}的身影..."

            advice_prompt_template = self.config.get("advice_prompt_template",
                "使用{nickname}称呼，对{nickname}的今日人品值{jrrp}给出你的评语和建议，50字以内")
            advice_prompt = self.replace_variables(advice_prompt_template, variables)
            advice_text = await self.call_llm(advice_prompt)
            if not advice_text:
                advice_text = "保持积极心态，好运自然来！"

            variables["process"] = process_text
            variables["advice"] = advice_text

            result_template = self.config.get("result_template",
                "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}")
            full_result = self.replace_variables(result_template, variables)

            # 保存数据
            if user_id not in self.fortune_data:
                self.fortune_data[user_id] = {}

            self.fortune_data[user_id][today] = {
                "jrrp": jrrp,
                "fortune": fortune,
                "process": process_text,
                "advice": advice_text,
                "full_result": full_result,
                "timestamp": datetime.now().isoformat()
            }

            if user_id not in self.history_data:
                self.history_data[user_id] = []

            self.history_data[user_id].append({
                "date": today,
                "jrrp": jrrp,
                "fortune": fortune
            })

            self.save_data(self.fortune_data, "fortune_data.json")
            self.save_data(self.history_data, "history_data.json")

            yield event.plain_result(full_result)

    @filter.command("jrrprank")
    async def jrrp_rank_command(self, event: AstrMessageEvent):
        """今日人品排行榜"""
        if not event.get_group_id():
            yield event.plain_result("此功能仅在群聊中可用")
            return

        today = self.get_today_key()
        group_rankings = []

        for user_id, user_data in self.fortune_data.items():
            if today in user_data:
                fortune_info = user_data[today]
                group_rankings.append({
                    "user_id": user_id,
                    "jrrp": fortune_info["jrrp"],
                    "fortune": fortune_info["fortune"],
                    "nickname": user_id
                })

        if not group_rankings:
            yield event.plain_result("今天还没有人查询过人品值哦~")
            return

        group_rankings.sort(key=lambda x: x["jrrp"], reverse=True)

        ranks_lines = []
        medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]

        rank_item_template = self.config.get("rank_item_template",
            "{medal} {nickname}: {jrrp} ({fortune})")

        for idx, ranking in enumerate(group_rankings[:5]):
            medal = medals[idx] if idx < len(medals) else "🏅"
            line = self.replace_variables(rank_item_template, {
                "medal": medal,
                "nickname": ranking["nickname"],
                "jrrp": ranking["jrrp"],
                "fortune": ranking["fortune"]
            })
            ranks_lines.append(line)

        rank_template = self.config.get("rank_template",
            "📊【今日人品排行榜】{date}\n━━━━━━━━━━━━━━━\n{ranks}")

        result = self.replace_variables(rank_template, {
            "date": today,
            "ranks": "\n".join(ranks_lines)
        })

        yield event.plain_result(result)

    @filter.command("jrrphistory", alias={"jrrphi"})
    async def jrrp_history_command(self, event: AstrMessageEvent):
        """查看人品历史记录"""
        user_id = event.get_sender_id()

        if user_id not in self.history_data:
            yield event.plain_result("没有找到历史记录")
            return

        user_info = await self.get_user_info(event)
        history_days = self.config.get("history_days", 30)

        all_history = self.history_data[user_id]
        recent_history = all_history[-history_days:] if len(all_history) > history_days else all_history

        if not recent_history:
            yield event.plain_result("没有历史记录")
            return

        jrrp_values = [h["jrrp"] for h in recent_history]
        avg_jrrp = sum(jrrp_values) / len(jrrp_values)
        max_jrrp = max(jrrp_values)
        min_jrrp = min(jrrp_values)

        history_lines = []
        for record in recent_history[-10:]:
            history_lines.append(f"{record['date']}: {record['jrrp']} ({record['fortune']})")

        history_template = self.config.get("history_template",
            "📚 {nickname} 的人品历史记录\n{history}\n\n📊 统计信息:\n平均人品值: {avgjrrp}\n最高人品值: {maxjrrp}\n最低人品值: {minjrrp}")

        result = self.replace_variables(history_template, {
            "nickname": user_info["nickname"],
            "history": "\n".join(history_lines),
            "avgjrrp": f"{avg_jrrp:.1f}",
            "maxjrrp": max_jrrp,
            "minjrrp": min_jrrp
        })

        yield event.plain_result(result)

    @filter.command("jrrpdelete", alias={"jrrpdel"})
    async def jrrp_delete_command(self, event: AstrMessageEvent, confirm: str = None):
        """删除个人记录"""
        user_id = event.get_sender_id()

        if confirm != "--confirm":
            yield event.plain_result("⚠️ 警告：此操作将删除您的所有人品值记录！\n如果确定要删除，请使用: /jrrpdelete --confirm")
            return

        deleted = False
        if user_id in self.fortune_data:
            del self.fortune_data[user_id]
            deleted = True

        if user_id in self.history_data:
            del self.history_data[user_id]
            deleted = True

        if deleted:
            self.save_data(self.fortune_data, "fortune_data.json")
            self.save_data(self.history_data, "history_data.json")
            yield event.plain_result("✅ 您的人品值记录已成功删除")
        else:
            yield event.plain_result("您没有任何人品值记录")

    @filter.command("jrrpreset", alias={"jrrpre"})
    async def jrrp_reset_command(self, event: AstrMessageEvent, confirm: str = None):
        """重置所有数据（仅管理员）"""
        try:
            # 获取AstrBot主配置
            astrbot_config = self.context.get_config()
            admins = astrbot_config.get("admins", [])

            if not admins:
                yield event.plain_result("未配置管理员列表")
                return

            if event.get_sender_id() not in admins:
                yield event.plain_result("⛔ 只有管理员才能执行此操作")
                return

            if confirm != "--confirm":
                yield event.plain_result("⚠️ 警告：此操作将删除所有用户的人品值记录！\n如果确定要重置，请使用: /jrrpreset --confirm")
                return

            self.fortune_data.clear()
            self.history_data.clear()

            self.save_data(self.fortune_data, "fortune_data.json")
            self.save_data(self.history_data, "history_data.json")

            yield event.plain_result("✅ 所有人品值数据已重置")
        except Exception as e:
            logger.error(f"重置数据失败: {e}")
            yield event.plain_result("重置失败，请检查日志")

    async def terminate(self):
        """插件卸载时的清理工作"""
        logger.info("DailyFortunePlugin 插件已卸载")
