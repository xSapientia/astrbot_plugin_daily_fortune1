import json
import random
import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
from astrbot.api.provider import ProviderRequest


@register(
    "astrbot_plugin_daily_fortune1",
    "xSapientia",
    "每日人品值查询插件，提供运势测算、排行榜、历史记录等功能",
    "0.0.1",
    "https://github.com/xSapientia/astrbot_plugin_daily_fortune1"
)
class DailyFortunePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = f"data/plugin_data/{self.metadata.name}"
        self.ensure_data_dir()

        # 加载数据
        self.fortune_data = self.load_data("fortune_data.json") or {}
        self.history_data = self.load_data("history_data.json") or {}

        # 运势等级定义
        self.fortune_levels = [
            ("大凶", 0, 10),
            ("凶", 11, 30),
            ("小凶", 31, 50),
            ("平", 51, 70),
            ("小吉", 71, 85),
            ("吉", 86, 95),
            ("大吉", 96, 100)
        ]

        # 表情映射
        self.fortune_emojis = {
            "大凶": "😱",
            "凶": "😰",
            "小凶": "😟",
            "平": "😐",
            "小吉": "😊",
            "吉": "😄",
            "大吉": "🎉"
        }

        logger.info("DailyFortunePlugin 初始化完成")

    def ensure_data_dir(self):
        """确保数据目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)

    def load_data(self, filename: str) -> Optional[Dict]:
        """加载数据文件"""
        filepath = os.path.join(self.data_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载数据文件 {filename} 失败: {e}")
        return None

    def save_data(self, data: Dict, filename: str):
        """保存数据文件"""
        filepath = os.path.join(self.data_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据文件 {filename} 失败: {e}")

    def get_today_key(self) -> str:
        """获取今天的日期键"""
        return datetime.now().strftime("%Y-%m-%d")

    def get_fortune_level(self, jrrp: int) -> Tuple[str, str]:
        """根据人品值获取运势等级和表情"""
        for level, min_val, max_val in self.fortune_levels:
            if min_val <= jrrp <= max_val:
                return level, self.fortune_emojis[level]
        return "平", "😐"

    async def get_user_info(self, event: AstrMessageEvent) -> Dict[str, str]:
        """从rawmessage_viewer1插件获取用户增强信息"""
        user_info = {
            "nickname": event.get_sender_name() or "未知",
            "card": "",
            "title": ""
        }

        try:
            # 尝试从event中获取增强信息
            message_id = event.message_obj.message_id

            # 查找rawmessage_viewer1插件
            raw_viewer = None
            for star_meta in self.context.get_all_stars():
                if star_meta.name == "astrbot_plugin_rawmessage_viewer1":
                    raw_viewer = star_meta.instance
                    break

            if raw_viewer and hasattr(raw_viewer, 'enhanced_messages'):
                if message_id in raw_viewer.enhanced_messages:
                    enhanced_msg = raw_viewer.enhanced_messages[message_id]
                    sender = enhanced_msg.get("sender", {})
                    user_info["card"] = sender.get("card", "") or sender.get("nickname", "")
                    user_info["title"] = sender.get("title", "")
        except Exception as e:
            logger.debug(f"获取增强用户信息失败: {e}")

        return user_info

    def calculate_jrrp(self, user_id: str, date: str) -> int:
        """计算人品值"""
        algorithm = self.config.get("jrrp_algorithm", "hash")

        if algorithm == "hash":
            # 基于哈希的算法
            seed = f"{user_id}_{date}"
            hash_value = hash(seed)
            return abs(hash_value) % 101
        elif algorithm == "random":
            # 真随机算法
            return random.randint(0, 100)
        else:
            # 默认算法
            seed = f"{user_id}_{date}"
            random.seed(seed)
            return random.randint(0, 100)

    async def generate_process_and_advice(self, event: AstrMessageEvent, user_info: Dict, jrrp: int, fortune: str) -> Tuple[str, str]:
        """通过LLM生成过程模拟和评语"""
        try:
            # 获取配置的provider或使用默认
            provider_id = self.config.get("llm", {}).get("provider_id")
            if provider_id:
                provider = self.context.get_provider_by_id(provider_id)
            else:
                provider = self.context.get_using_provider()

            if not provider:
                return "水晶球闪烁着神秘的光芒...", "愿好运常伴你左右"

            # 获取人格
            persona_name = self.config.get("llm", {}).get("persona_name")
            persona_prompt = ""
            if persona_name:
                all_personas = self.context.provider_manager.personas
                persona = next((p for p in all_personas if p.get('name') == persona_name), None)
                if persona:
                    persona_prompt = persona.get('prompt', '')
            else:
                # 使用默认人格
                default_persona_name = self.context.provider_manager.selected_default_persona.get("name")
                if default_persona_name:
                    all_personas = self.context.provider_manager.personas
                    persona = next((p for p in all_personas if p.get('name') == default_persona_name), None)
                    if persona:
                        persona_prompt = persona.get('prompt', '')

            # 准备变量
            vars_dict = {
                "nickname": user_info["nickname"],
                "card": user_info["card"],
                "title": user_info["title"],
                "jrrp": str(jrrp),
                "fortune": fortune
            }

            # 过程模拟
            process_prompt = self.config.get("process_prompt", "使用user_id的简称称呼，模拟你使用水晶球缓慢复现今日结果的过程，50字以内")
            process_prompt = self.format_template(process_prompt, vars_dict)

            process_system = persona_prompt + "\n" + process_prompt
            process_resp = await provider.text_chat(
                prompt=f"为{user_info['nickname']}生成今日人品值{jrrp}的占卜过程描述",
                system_prompt=process_system,
                contexts=[]
            )
            process = process_resp.completion_text.strip()

            # 评语建议
            advice_prompt = self.config.get("advice_prompt", "使用user_id的简称称呼，对user_id的今日人品值{jrrp}给出你的评语和建议，50字以内")
            advice_prompt = self.format_template(advice_prompt, vars_dict)

            advice_system = persona_prompt + "\n" + advice_prompt
            advice_resp = await provider.text_chat(
                prompt=f"为{user_info['nickname']}的今日人品值{jrrp}({fortune})给出评语和建议",
                system_prompt=advice_system,
                contexts=[]
            )
            advice = advice_resp.completion_text.strip()

            return process, advice

        except Exception as e:
            logger.error(f"生成过程和建议失败: {e}")
            return "水晶球闪烁着神秘的光芒...", "愿好运常伴你左右"

    def format_template(self, template: str, vars_dict: Dict[str, str]) -> str:
        """格式化模板"""
        for key, value in vars_dict.items():
            template = template.replace(f"{{{key}}}", str(value))
        return template

    @filter.command("jrrp")
    async def jrrp_command(self, event: AstrMessageEvent):
        """今日人品查询"""
        user_id = event.get_sender_id()
        today = self.get_today_key()
        user_info = await self.get_user_info(event)

        # 检查是否已经查询过
        if today not in self.fortune_data:
            self.fortune_data[today] = {}

        if user_id in self.fortune_data[today]:
            # 已查询过，返回缓存结果
            cached = self.fortune_data[today][user_id]
            jrrp = cached["jrrp"]
            fortune = cached["fortune"]
            femoji = cached["femoji"]

            query_template = self.config.get("query_template",
                "📌 今日人品\n{nickname}，今天已经查询过了哦~\n今日人品值: {jrrp}\n运势: {fortune} {femoji}")

            vars_dict = {
                "nickname": user_info["nickname"],
                "card": user_info["card"],
                "title": user_info["title"],
                "jrrp": str(jrrp),
                "fortune": fortune,
                "femoji": femoji
            }

            result = self.format_template(query_template, vars_dict)

            # 如果配置了显示缓存结果
            if self.config.get("show_cached_result", False) and "result" in cached:
                result += f"\n\n-----以下为今日运势测算场景还原-----\n{cached['result']}"

            yield event.plain_result(result)
            return

        # 首次查询
        # 发送检测中消息
        detecting_msg = self.config.get("detecting_message",
            "神秘的能量汇聚，{nickname}，你的命运即将显现，正在祈祷中...")
        detecting_msg = self.format_template(detecting_msg, {"nickname": user_info["nickname"]})
        yield event.plain_result(detecting_msg)

        # 计算人品值
        jrrp = self.calculate_jrrp(user_id, today)
        fortune, femoji = self.get_fortune_level(jrrp)

        # 生成过程和建议
        process, advice = await self.generate_process_and_advice(event, user_info, jrrp, fortune)

        # 格式化结果
        result_template = self.config.get("result_template",
            "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}")

        vars_dict = {
            "nickname": user_info["nickname"],
            "card": user_info["card"],
            "title": user_info["title"],
            "jrrp": str(jrrp),
            "fortune": fortune,
            "femoji": femoji,
            "process": process,
            "advice": advice
        }

        result = self.format_template(result_template, vars_dict)

        # 缓存结果
        cache_days = self.config.get("cache_days", 1)
        self.fortune_data[today][user_id] = {
            "jrrp": jrrp,
            "fortune": fortune,
            "femoji": femoji,
            "process": process,
            "advice": advice,
            "result": result,
            "expire": (datetime.now() + timedelta(days=cache_days)).isoformat()
        }

        # 保存到历史记录
        if user_id not in self.history_data:
            self.history_data[user_id] = {}
        self.history_data[user_id][today] = {
            "jrrp": jrrp,
            "fortune": fortune
        }

        # 清理过期数据
        self.clean_expired_data()

        # 保存数据
        self.save_data(self.fortune_data, "fortune_data.json")
        self.save_data(self.history_data, "history_data.json")

        yield event.plain_result(result)

    @filter.command("jrrprank")
    async def jrrp_rank_command(self, event: AstrMessageEvent):
        """群内人品排行榜"""
        if event.is_private_chat():
            yield event.plain_result("排行榜功能仅在群聊中可用哦~")
            return

        today = self.get_today_key()
        if today not in self.fortune_data:
            yield event.plain_result("今天还没有人查询过人品值呢~")
            return

        # 获取群内所有查询过的用户
        group_users = []
        for user_id, data in self.fortune_data[today].items():
            group_users.append({
                "user_id": user_id,
                "nickname": data.get("nickname", user_id),
                "jrrp": data["jrrp"],
                "fortune": data["fortune"]
            })

        if not group_users:
            yield event.plain_result("今天还没有人查询过人品值呢~")
            return

        # 排序
        group_users.sort(key=lambda x: x["jrrp"], reverse=True)

        # 生成排名内容
        ranks_lines = []
        medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]

        rank_item_template = self.config.get("rank_item_template",
            "{medal} {nickname}: {jrrp} ({fortune})")

        for i, user in enumerate(group_users[:10]):  # 只显示前10名
            medal = medals[i] if i < len(medals) else "🏅"
            line = self.format_template(rank_item_template, {
                "medal": medal,
                "nickname": user["nickname"],
                "jrrp": str(user["jrrp"]),
                "fortune": user["fortune"]
            })
            ranks_lines.append(line)

        ranks = "\n".join(ranks_lines)

        # 格式化排行榜
        rank_template = self.config.get("rank_template",
            "📊【今日人品排行榜】{date}\n━━━━━━━━━━━━━━━\n{ranks}")

        result = self.format_template(rank_template, {
            "date": today,
            "ranks": ranks
        })

        yield event.plain_result(result)

    @filter.command("jrrphistory", alias={"jrrphi"})
    async def jrrp_history_command(self, event: AstrMessageEvent):
        """查看人品历史记录"""
        target_id = event.get_sender_id()
        target_name = event.get_sender_name()

        # 检查是否有@其他人
        for msg in event.message_obj.message:
            if isinstance(msg, Comp.At):
                target_id = str(msg.qq)
                target_name = f"用户{target_id}"
                break

        if target_id not in self.history_data:
            yield event.plain_result(f"{target_name} 还没有人品记录哦~")
            return

        history_days = self.config.get("history_days", 30)
        cutoff_date = datetime.now() - timedelta(days=history_days)

        # 收集历史数据
        history_items = []
        jrrp_values = []

        for date_str, data in self.history_data[target_id].items():
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                if date >= cutoff_date:
                    history_items.append((date_str, data))
                    jrrp_values.append(data["jrrp"])
            except:
                continue

        if not history_items:
            yield event.plain_result(f"{target_name} 最近{history_days}天没有人品记录~")
            return

        # 排序
        history_items.sort(key=lambda x: x[0], reverse=True)

        # 计算统计数据
        avg_jrrp = sum(jrrp_values) / len(jrrp_values)
        max_jrrp = max(jrrp_values)
        min_jrrp = min(jrrp_values)

        # 生成历史记录内容
        history_lines = []
        for date_str, data in history_items[:10]:  # 只显示最近10条
            history_lines.append(f"{date_str}: {data['jrrp']} ({data['fortune']})")

        # 格式化历史记录
        history_template = self.config.get("history_template",
            "📚 {nickname} 的人品历史记录\n{history}\n\n📊 统计信息:\n平均人品值: {avgjrrp:.1f}\n最高人品值: {maxjrrp}\n最低人品值: {minjrrp}")

        result = self.format_template(history_template, {
            "nickname": target_name,
            "history": "\n".join(history_lines),
            "avgjrrp": f"{avg_jrrp:.1f}",
            "maxjrrp": str(max_jrrp),
            "minjrrp": str(min_jrrp)
        })

        yield event.plain_result(result)

    @filter.command("jrrpdelete", alias={"jrrpdel"})
    async def jrrp_delete_command(self, event: AstrMessageEvent, *args):
        """删除个人人品记录"""
        user_id = event.get_sender_id()

        if args and args[0] == "--confirm":
            # 确认删除
            if user_id in self.history_data:
                del self.history_data[user_id]

            # 删除今日记录
            today = self.get_today_key()
            if today in self.fortune_data and user_id in self.fortune_data[today]:
                del self.fortune_data[today][user_id]

            self.save_data(self.fortune_data, "fortune_data.json")
            self.save_data(self.history_data, "history_data.json")

            yield event.plain_result("✅ 您的人品记录已全部删除！")
        else:
            yield event.plain_result("⚠️ 确定要删除您的所有人品记录吗？\n请使用 /jrrpdelete --confirm 确认删除")

    @filter.command("jrrpreset", alias={"jrrpre"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def jrrp_reset_command(self, event: AstrMessageEvent, *args):
        """重置所有人品数据（仅管理员）"""
        if args and args[0] == "--confirm":
            # 确认重置
            self.fortune_data = {}
            self.history_data = {}

            self.save_data(self.fortune_data, "fortune_data.json")
            self.save_data(self.history_data, "history_data.json")

            yield event.plain_result("✅ 所有人品数据已重置！")
        else:
            yield event.plain_result("⚠️ 确定要重置所有人品数据吗？\n请使用 /jrrpreset --confirm 确认重置")

    def clean_expired_data(self):
        """清理过期数据"""
        now = datetime.now()

        # 清理过期的fortune_data
        for date_key in list(self.fortune_data.keys()):
            # 删除超过7天的数据
            try:
                date = datetime.strptime(date_key, "%Y-%m-%d")
                if (now - date).days > 7:
                    del self.fortune_data[date_key]
                    continue
            except:
                pass

            # 检查每个用户的过期时间
            for user_id in list(self.fortune_data[date_key].keys()):
                user_data = self.fortune_data[date_key][user_id]
                if "expire" in user_data:
                    try:
                        expire_time = datetime.fromisoformat(user_data["expire"])
                        if now > expire_time:
                            del self.fortune_data[date_key][user_id]
                    except:
                        pass

    async def terminate(self):
        """插件卸载时的清理工作"""
        logger.info("DailyFortunePlugin 正在卸载...")
