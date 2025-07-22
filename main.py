import json
import asyncio
import random
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, List
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp
from astrbot.api.provider import BaseProvider


@register(
    "astrbot_plugin_daily_fortune1",
    "xSapientia",
    "每日人品值和运势查询插件，支持排行榜和历史记录",
    "0.0.1",
    "https://github.com/xSapientia/astrbot_plugin_daily_fortune1"
)
class DailyFortunePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = Path("data/plugin_data/astrbot_plugin_daily_fortune1")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 数据文件路径
        self.fortune_file = self.data_dir / "daily_fortune.json"
        self.history_file = self.data_dir / "fortune_history.json"

        # 加载数据
        self.daily_data = self._load_data(self.fortune_file)
        self.history_data = self._load_data(self.history_file)

        # 运势等级映射
        self.fortune_levels = {
            (0, 1): ("极凶", "💀"),
            (2, 10): ("大凶", "😨"),
            (11, 20): ("凶", "😰"),
            (21, 30): ("小凶", "🫨"),
            (31, 40): ("平", "😐"),
            (41, 60): ("小吉", "🙂"),
            (61, 80): ("吉", "😊"),
            (81, 98): ("大吉", "😉"),
            (99, 100): ("天和", "😇")
        }

        # 初始化LLM提供商
        self._init_provider()

        logger.info("astrbot_plugin_daily_fortune1 插件已加载")

    def _init_provider(self):
        """初始化LLM提供商"""
        provider_id = self.config.get("llm_provider_id", "")

        if provider_id:
            # 使用指定的provider_id
            try:
                self.provider = self.context.get_provider_by_id(provider_id)
                if self.provider:
                    logger.info(f"使用provider_id: {provider_id} 连接成功")
                else:
                    logger.warning(f"未找到provider_id: {provider_id}，将使用默认提供商")
                    self.provider = None
            except Exception as e:
                logger.error(f"获取provider失败: {e}")
                self.provider = None
        else:
            # 使用第三方接口配置
            api_config = self.config.get("llm_api", {})
            if api_config.get("api_key") and api_config.get("url"):
                logger.info(f"使用第三方接口: {api_config['url']}")
                # 这里需要根据实际情况创建provider
                self.provider = None
            else:
                self.provider = None

        # 获取人格配置
        self.persona_name = self.config.get("persona_name", "")
        if self.persona_name:
            personas = self.context.provider_manager.personas
            found = False
            for p in personas:
                if p.get('name') == self.persona_name:
                    prompt = p.get('prompt', '')
                    logger.info(f"使用人格: {self.persona_name}, prompt前20字符: {prompt[:20]}...")
                    found = True
                    break
            if not found:
                logger.warning(f"未找到人格: {self.persona_name}")

    def _load_data(self, file_path: Path) -> Dict:
        """加载JSON数据"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载数据文件失败: {e}")
        return {}

    def _save_data(self, data: Dict, file_path: Path):
        """保存JSON数据"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存数据文件失败: {e}")

    def _get_today_key(self) -> str:
        """获取今日日期作为key"""
        return date.today().strftime("%Y-%m-%d")

    def _calculate_jrrp(self, user_id: str) -> int:
        """计算今日人品值"""
        algorithm = self.config.get("jrrp_algorithm", "hash")
        today = self._get_today_key()

        if algorithm == "hash":
            # 基于用户ID和日期的哈希算法
            seed = f"{user_id}_{today}"
            hash_value = int(hashlib.md5(seed.encode()).hexdigest(), 16)
            return hash_value % 101
        elif algorithm == "random":
            # 纯随机算法
            random.seed(f"{user_id}_{today}")
            return random.randint(0, 100)
        else:
            # 默认算法
            return random.randint(0, 100)

    def _get_fortune_info(self, jrrp: int) -> tuple:
        """根据人品值获取运势信息"""
        for (min_val, max_val), (fortune, emoji) in self.fortune_levels.items():
            if min_val <= jrrp <= max_val:
                return fortune, emoji
        return "未知", "❓"

    async def _get_user_info(self, event: AstrMessageEvent) -> Dict[str, str]:
        """获取用户信息（从rawmessage_viewer1插件）"""
        user_id = event.get_sender_id()
        nickname = event.get_sender_name()
        card = nickname  # 默认值
        title = "无"  # 默认值

        # 尝试从rawmessage_viewer1插件获取增强信息
        try:
            if event.get_platform_name() == "aiocqhttp":
                message_id = event.message_obj.message_id

                # 查找rawmessage_viewer1插件
                plugins = self.context.get_all_stars()
                for plugin_meta in plugins:
                    if plugin_meta.metadata.name == "astrbot_plugin_rawmessage_viewer1":
                        plugin_instance = plugin_meta.instance
                        if hasattr(plugin_instance, 'enhanced_messages'):
                            enhanced_msg = plugin_instance.enhanced_messages.get(message_id, {})
                            sender = enhanced_msg.get("sender", {})
                            nickname = sender.get("nickname", nickname)
                            card = sender.get("card", nickname)
                            title = sender.get("title", "无")
                            break
        except Exception as e:
            logger.debug(f"获取增强用户信息失败: {e}")

        return {
            "user_id": user_id,
            "nickname": nickname,
            "card": card,
            "title": title
        }

    async def _generate_with_llm(self, prompt: str, system_prompt: str = "") -> str:
        """使用LLM生成内容"""
        try:
            provider = self.provider or self.context.get_using_provider()
            if not provider:
                return "LLM服务暂时不可用"

            # 获取当前会话的人格信息
            contexts = []
            if self.persona_name:
                # 使用指定的人格
                personas = self.context.provider_manager.personas
                for p in personas:
                    if p.get('name') == self.persona_name:
                        system_prompt = p.get('prompt', '') + "\n" + system_prompt
                        break

            response = await provider.text_chat(
                prompt=prompt,
                contexts=contexts,
                system_prompt=system_prompt
            )

            return response.completion_text
        except Exception as e:
            logger.error(f"LLM生成失败: {e}")
            return "生成失败"

    @filter.command("jrrp")
    async def jrrp(self, event: AstrMessageEvent):
        """今日人品查询"""
        user_info = await self._get_user_info(event)
        user_id = user_info["user_id"]
        nickname = user_info["nickname"]
        today = self._get_today_key()

        # 初始化今日数据
        if today not in self.daily_data:
            self.daily_data[today] = {}

        # 检查是否已经查询过
        if user_id in self.daily_data[today]:
            # 已查询，返回缓存结果
            cached = self.daily_data[today][user_id]
            jrrp = cached["jrrp"]
            fortune, femoji = self._get_fortune_info(jrrp)

            # 构建查询模板
            query_template = self.config.get("templates", {}).get("query",
                "📌 今日人品\n{nickname}，今天已经查询过了哦~\n今日人品值: {jrrp}\n运势: {fortune} {femoji}")

            result = query_template.format(
                nickname=nickname,
                jrrp=jrrp,
                fortune=fortune,
                femoji=femoji
            )

            # 如果配置启用了显示缓存结果
            if self.config.get("show_cached_result", True) and "result" in cached:
                result += f"\n\n-----以下为今日运势测算场景还原-----\n{cached['result']}"

            yield event.plain_result(result)
            return

        # 首次查询，显示检测中消息
        detecting_msg = self.config.get("detecting_message",
            "神秘的能量汇聚，{nickname}，你的命运即将显现，正在祈祷中...")
        yield event.plain_result(detecting_msg.format(nickname=nickname))

        # 计算人品值
        jrrp = self._calculate_jrrp(user_id)
        fortune, femoji = self._get_fortune_info(jrrp)

        # 准备LLM生成的变量
        vars_dict = {
            "nickname": nickname,
            "card": user_info["card"],
            "title": user_info["title"],
            "jrrp": jrrp,
            "fortune": fortune,
            "femoji": femoji
        }

        # 生成过程模拟
        process_prompt = self.config.get("prompts", {}).get("process",
            "使用user_id的简称称呼，模拟你使用水晶球缓慢复现今日结果的过程，50字以内")
        process_prompt = process_prompt.format(**vars_dict)
        process = await self._generate_with_llm(process_prompt)

        # 生成建议
        advice_prompt = self.config.get("prompts", {}).get("advice",
            "使用user_id的简称称呼，对user_id的今日人品值{jrrp}给出你的评语和建议，50字以内")
        advice_prompt = advice_prompt.format(**vars_dict)
        advice = await self._generate_with_llm(advice_prompt)

        # 构建结果
        result_template = self.config.get("templates", {}).get("random",
            "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}。")

        result = result_template.format(
            process=process,
            jrrp=jrrp,
            fortune=fortune,
            advice=advice
        )

        # 缓存结果
        self.daily_data[today][user_id] = {
            "jrrp": jrrp,
            "fortune": fortune,
            "process": process,
            "advice": advice,
            "result": result,
            "nickname": nickname,
            "timestamp": datetime.now().isoformat()
        }
        self._save_data(self.daily_data, self.fortune_file)

        # 更新历史记录
        if user_id not in self.history_data:
            self.history_data[user_id] = {}
        self.history_data[user_id][today] = {
            "jrrp": jrrp,
            "fortune": fortune
        }
        self._save_data(self.history_data, self.history_file)

        yield event.plain_result(result)

    @filter.command("jrrprank")
    async def jrrprank(self, event: AstrMessageEvent):
        """群内今日人品排行榜"""
        if event.is_private_chat():
            yield event.plain_result("排行榜功能仅在群聊中可用")
            return

        today = self._get_today_key()

        if today not in self.daily_data:
            yield event.plain_result("今天还没有人查询过人品值呢~")
            return

        # 获取群成员的人品值
        group_data = []
        for user_id, data in self.daily_data[today].items():
            group_data.append({
                "user_id": user_id,
                "nickname": data.get("nickname", "未知"),
                "jrrp": data["jrrp"],
                "fortune": data.get("fortune", "未知")
            })

        # 排序
        group_data.sort(key=lambda x: x["jrrp"], reverse=True)

        # 构建排行榜
        rank_template = self.config.get("templates", {}).get("rank",
            "{medal} {nickname}: {jrrp} ({fortune})")

        ranks = []
        medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]

        for i, user in enumerate(group_data[:10]):  # 只显示前10名
            medal = medals[i] if i < len(medals) else "🏅"
            rank_line = rank_template.format(
                medal=medal,
                nickname=user["nickname"],
                jrrp=user["jrrp"],
                fortune=user["fortune"]
            )
            ranks.append(rank_line)

        # 构建完整排行榜
        board_template = self.config.get("templates", {}).get("board",
            "📊【今日人品排行榜】{date}\n━━━━━━━━━━━━━━━\n{ranks}")

        result = board_template.format(
            date=today,
            ranks="\n".join(ranks)
        )

        yield event.plain_result(result)

    @filter.command("jrrphistory", alias={"jrrphi"})
    async def jrrphistory(self, event: AstrMessageEvent):
        """查看人品历史记录"""
        # 检查是否有@某人
        target_user_id = event.get_sender_id()
        target_nickname = event.get_sender_name()

        # 检查消息中是否有At
        for comp in event.message_obj.message:
            if isinstance(comp, Comp.At):
                target_user_id = str(comp.qq)
                # 尝试获取被@用户的昵称
                target_nickname = f"用户{target_user_id}"
                break

        if target_user_id not in self.history_data:
            yield event.plain_result(f"{target_nickname} 还没有任何人品记录呢~")
            return

        # 获取历史天数配置
        history_days = self.config.get("history_days", 30)
        user_history = self.history_data[target_user_id]

        # 按日期排序并限制天数
        sorted_dates = sorted(user_history.keys(), reverse=True)[:history_days]

        if not sorted_dates:
            yield event.plain_result(f"{target_nickname} 还没有任何人品记录呢~")
            return

        # 计算统计数据
        jrrp_values = [user_history[date]["jrrp"] for date in sorted_dates]
        avg_jrrp = round(sum(jrrp_values) / len(jrrp_values), 1)
        max_jrrp = max(jrrp_values)
        min_jrrp = min(jrrp_values)

        # 构建历史记录列表
        history_lines = []
        for date in sorted_dates[:10]:  # 只显示最近10条
            data = user_history[date]
            history_lines.append(f"{date}: {data['jrrp']} ({data['fortune']})")

        # 使用模板
        history_template = self.config.get("templates", {}).get("history",
            "📚 {nickname} 的人品历史记录\n{history}\n\n📊 统计信息:\n平均人品值: {avgjrrp}\n最高人品值: {maxjrrp}\n最低人品值: {minjrrp}")

        result = history_template.format(
            nickname=target_nickname,
            history="\n".join(history_lines),
            avgjrrp=avg_jrrp,
            maxjrrp=max_jrrp,
            minjrrp=min_jrrp
        )

        yield event.plain_result(result)

    @filter.command("jrrpdelete", alias={"jrrpdel"})
    async def jrrpdelete(self, event: AstrMessageEvent, confirm: str = ""):
        """删除个人人品历史记录"""
        user_id = event.get_sender_id()

        if confirm != "--confirm":
            yield event.plain_result("⚠️ 警告：此操作将删除您的所有人品历史记录！\n如确认删除，请使用：/jrrpdelete --confirm")
            return

        # 删除历史记录
        if user_id in self.history_data:
            del self.history_data[user_id]
            self._save_data(self.history_data, self.history_file)

        # 删除今日记录
        today = self._get_today_key()
        if today in self.daily_data and user_id in self.daily_data[today]:
            del self.daily_data[today][user_id]
            self._save_data(self.daily_data, self.fortune_file)

        yield event.plain_result("✅ 您的人品历史记录已成功删除")

    @filter.command("jrrpreset", alias={"jrrpre"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def jrrpreset(self, event: AstrMessageEvent, confirm: str = ""):
        """重置所有人品数据（仅管理员）"""
        if confirm != "--confirm":
            yield event.plain_result("⚠️ 警告：此操作将删除所有用户的人品数据！\n如确认重置，请使用：/jrrpreset --confirm")
            return

        # 清空所有数据
        self.daily_data = {}
        self.history_data = {}
        self._save_data(self.daily_data, self.fortune_file)
        self._save_data(self.history_data, self.history_file)

        yield event.plain_result("✅ 所有人品数据已重置")

    async def terminate(self):
        """插件卸载时的清理工作"""
        logger.info("astrbot_plugin_daily_fortune1 插件正在卸载...")

        # 根据配置决定是否删除数据
        if self.config.get("delete_data_on_uninstall", False):
            import shutil
            if self.data_dir.exists():
                shutil.rmtree(self.data_dir)
                logger.info(f"已删除插件数据目录: {self.data_dir}")

        if self.config.get("delete_config_on_uninstall", False):
            import os
            config_file = f"data/config/{self.metadata.name}_config.json"
            if os.path.exists(config_file):
                os.remove(config_file)
                logger.info(f"已删除配置文件: {config_file}")

        logger.info("astrbot_plugin_daily_fortune1 插件已卸载")
