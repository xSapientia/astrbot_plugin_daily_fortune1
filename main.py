import os
import json
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
import random
import logging

from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Star, register
from astrbot.api.platform import Platform
from astrbot.core.message.components import Plain, At
from astrbot.core.provider.manager import ProviderManager
from astrbot.core.config.manager import ConfigManager

logger = logging.getLogger(__name__)

@register(
    "astrbot_plugin_daily_fortune1",
    "每日人品值检测，支持排行榜和历史查询",
    "xSapientia",
    "0.0.1"
)
class DailyFortunePlugin(Star):
    def __init__(self):
        super().__init__()
        self.data_dir = os.path.join("data", "plugin_data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.data_file = os.path.join(self.data_dir, "daily_fortune.json")self.config = self.load_config()
        self.data = self.load_data()
        # 从配置获取设置
        self.enabled = self.config.get("enabled", True)
        self.min_value = self.config.get("min_value", 0)
        self.max_value = self.config.get("max_value", 100)
        self.ranking_limit = self.config.get("ranking_limit", 10)self.detecting_message = self.config.get("detecting_message", "神秘的能量汇聚，窥见你的命运，正在祈祷中...")
        self.detection_prompt = self.config.get("detection_prompt", "测试今日人品的时候，显示user_id的 title&card/nickname，模拟一下水晶球上显现今日人品值的过程、结果，字数不超过50字")
        self.advice_prompt = self.config.get("advice_prompt", "你对使用人今日人品值下的建议，字数不超过50字")

        # LLM配置
        self.provider_id = self.config.get("llm_provider_id", "")
        self.api_key = self.config.get("llm_api_key", "")
        self.api_url = self.config.get("llm_api_url", "")
        self.model_name = self.config.get("llm_model_name", "")
        self.persona_name = self.config.get("persona_name", "")

    def load_config(self) -> Dict:
        """加载插件配置"""
        config_manager = ConfigManager()
        return config_manager.get("astrbot_plugin_daily_fortune1", {})

    def load_data(self) -> Dict:
        """加载数据文件"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"daily_records": {}, "user_history": {}, "group_records": {}}
        return {"daily_records": {}, "user_history": {}, "group_records": {}}

    def save_data(self):
        """保存数据到文件"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据失败: {e}")

    def get_today_key(self) -> str:"""获取今日日期键"""
        tz = timezone(timedelta(hours=8))  # 中国时区
        return datetime.now(tz).strftime("%Y-%m-%d")

    def get_fortune_level(self, value: int) -> str:"""根据人品值获取运势等级"""
        if value == 0:
            return "极其倒霉"
        elif 1 <= value <= 2:
            return "倒大霉"
        elif 3 <= value <= 10:
            return "十分不顺"
        elif 10 <= value <= 20:
            return "略微不顺"
        elif 20 <= value <= 30:
            return "正常运气"
        elif 30 <= value <= 98:
            return "好运"
        elif value == 99:
            return "极其好运"
        elif value == 100:
            return "万事皆允"
        else:
            return "好运"

    def generate_fortune_value(self, user_id: str) -> int:
        """为用户生成今日人品值"""
        today = self.get_today_key()
        seed = f"{user_id}_{today}"
        random.seed(hashlib.md5(seed.encode()).hexdigest())
        return random.randint(self.min_value, self.max_value)

    async def get_llm_response(self, prompt: str, event: AstrMessageEvent) -> str:
        """调用LLM获取回复"""
        try:# 获取核心组件
            provider_manager = ProviderManager.get_instance()
            # 确定使用的provider
            if self.provider_id:
                provider = provider_manager.get_provider(self.provider_id)
            else:
                provider = provider_manager.get_default_provider()

            if not provider:
                return "无法获取LLM服务"

            #构建消息
            user_info = f"用户名: {event.sender.nickname}"
            if hasattr(event.sender, 'card') and event.sender.card:
                user_info += f", 群名片: {event.sender.card}"
            if hasattr(event.sender,'title') and event.sender.title:
                user_info += f", 头衔: {event.sender.title}"

            full_prompt = f"{user_info}\n{prompt}"

            # 调用LLM
            response = await provider.text_chat([{"role": "user", "content": full_prompt}])
            return response.get("content", "神秘的能量无法解读...")

        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return "水晶球暂时失效了..."

    async def handle_fortune_check(self, event: AstrMessageEvent) -> str:
        """处理人品检测"""
        if not self.enabled:
            return "今日人品功能暂时关闭"
        user_id = str(event.sender.user_id)
        today = self.get_today_key()

        # 检查今日是否已测过
        if today in self.data["daily_records"] and user_id in self.data["daily_records"][today]:
            # 已测过，返回查询结果
            record = self.data["daily_records"][today][user_id]
            result = f"📌 【{event.sender.nickname}】今日人品\n"
            result += f"{event.sender.nickname}，今天已经查询过了哦~\n"
            result += f"今日人品值: {record['value']}\n"
            result += f"运势: {record['level']} 😊\n\n"
            result += "-----以下为今日运势测算场景还原-----\n"
            result += record["full_response"]
            return result

        # 首次检测
        await event.reply([Plain(self.detecting_message)])

        # 生成人品值
        fortune_value = self.generate_fortune_value(user_id)
        fortune_level = self.get_fortune_level(fortune_value)

        # 获取LLM回复
        detection_response = await self.get_llm_response(
            f"{self.detection_prompt}，人品值是{fortune_value}",
            event
        )

        advice_response = await self.get_llm_response(
            f"{self.advice_prompt}，人品值是{fortune_value}，运势等级是{fortune_level}",
            event
        )

        # 构建完整回复
        full_response = f"【{event.sender.nickname}】开始测试今日人品...\n\n"
        full_response += f"{detection_response}\n\n"
        full_response += f"💎 人品值：{fortune_value}\n"
        full_response += f"✨ 运势：{fortune_level}\n"
        full_response += f"💬 建议：{advice_response}"

        # 保存记录
        if today not in self.data["daily_records"]:
            self.data["daily_records"][today] = {}

        self.data["daily_records"][today][user_id] = {
            "value": fortune_value,
            "level": fortune_level,
            "nickname": event.sender.nickname,
            "timestamp": datetime.now().isoformat(),
            "full_response": full_response
        }

        # 保存历史记录
        if user_id not in self.data["user_history"]:
            self.data["user_history"][user_id] = {}
        self.data["user_history"][user_id][today] = {
            "value": fortune_value,
            "level": fortune_level
        }

        # 记录群组数据（如果是群聊）
        if hasattr(event, 'group_id') and event.group_id:
            group_id = str(event.group_id)
            if group_id not in self.data["group_records"]:
                self.data["group_records"][group_id] = {}
            if today not in self.data["group_records"][group_id]:
                self.data["group_records"][group_id][today] = []

            self.data["group_records"][group_id][today].append({
                "user_id": user_id,
                "nickname": event.sender.nickname,
                "value": fortune_value,
                "level": fortune_level
            })

        self.save_data()
        return full_response

    async def handle_ranking(self, event: AstrMessageEvent) -> str:
        """处理人品排行榜"""
        if not hasattr(event, 'group_id') or not event.group_id:
            return "排行榜功能仅在群聊中可用"

        group_id = str(event.group_id)
        today = self.get_today_key()

        if group_id not in self.data["group_records"] or today not in self.data["group_records"][group_id]:
            return "今日群内暂无人品记录"

        records = self.data["group_records"][group_id][today]sorted_records = sorted(records, key=lambda x: x["value"], reverse=True)
        # 限制显示数量
        if self.ranking_limit > 0:
            sorted_records = sorted_records[:self.ranking_limit]
        result = f"🏆 今日群人品排行榜({today})\n\n"
        for i, record in enumerate(sorted_records, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            result += f"{emoji} {record['nickname']} - {record['value']} ({record['level']})\n"

        return result

    async def handle_history(self, event: AstrMessageEvent) -> str:
        """处理历史查询"""
        user_id = str(event.sender.user_id)

        if user_id not in self.data["user_history"]:
            return "暂无历史人品记录"history = self.data["user_history"][user_id]if not history:
            return "暂无历史人品记录"

        result = f"📊 【{event.sender.nickname}】的人品历史\n\n"

        # 按日期排序，最近的在前
        sorted_dates = sorted(history.keys(), reverse=True)[:10]  # 显示最近10天
        for date in sorted_dates:
            record = history[date]
            result += f"📅 {date}: {record['value']} ({record['level']})\n"

        return result

    async def handle_delete(self, event: AstrMessageEvent, confirm: bool = False) -> str:
        """处理数据删除"""
        if not confirm:
            return "确定要清除您的所有人品数据吗？请使用 -jrrpdelete --confirm 确认操作"

        user_id = str(event.sender.user_id)

        # 删除历史记录
        if user_id in self.data["user_history"]:
            del self.data["user_history"][user_id]# 删除每日记录
        for date in self.data["daily_records"]:
            if user_id in self.data["daily_records"][date]:
                del self.data["daily_records"][date][user_id]# 删除群组记录
        for group_id in self.data["group_records"]:
            for date in self.data["group_records"][group_id]:
                self.data["group_records"][group_id][date] = [
                    record for record in self.data["group_records"][group_id][date]
                    if record["user_id"] != user_id]

        self.save_data()
        return "✅ 您的所有人品数据已清除"

    async def handle_reset(self, event: AstrMessageEvent, confirm: bool = False) -> str:
        """处理全部数据重置（仅管理员）"""
        # 这里需要检查是否为管理员，具体实现根据AstrBot的权限系统
        if not confirm:
            return "确定要清除所有用户的人品数据吗？请使用 -jrrpreset --confirm 确认操作"

        self.data = {"daily_records": {}, "user_history": {}, "group_records": {}}
        self.save_data()
        return "✅ 所有人品数据已重置"

    async def handler(self, event: AstrMessageEvent) -> None:
        """主处理函数"""
        if not isinstance(event.message_str, str):
            return

        message = event.message_str.strip()

        # 处理各种命令
        if message == "-jrrp":
            response = await self.handle_fortune_check(event)
            await event.reply([Plain(response)])

        elif message == "-jrrprank":
            response = await self.handle_ranking(event)
            await event.reply([Plain(response)])
        elif message in ["-jrrphistory", "-jrrphi"]:
            response = await self.handle_history(event)
            await event.reply([Plain(response)])

        elif message.startswith("-jrrpdelete") or message.startswith("-jrrpdel"):
            confirm = "--confirm" in message
            response = await self.handle_delete(event, confirm)
            await event.reply([Plain(response)])

        elif message.startswith("-jrrpreset"):
            confirm = "--confirm" in message
            response = await self.handle_reset(event, confirm)
            await event.reply([Plain(response)])
