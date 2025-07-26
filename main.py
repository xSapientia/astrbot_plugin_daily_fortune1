import json
import asyncio
import random
import hashlib
import numpy as np
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp


@register(
    "astrbot_plugin_daily_fortune1",
    "xSapientia",
    "每日人品值和运势查询插件，支持排行榜和历史记录",
    "0.1.0",
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

        # 初始化运势等级映射
        self._init_fortune_levels()

        # 初始化奖牌配置
        self._init_medals()

        # 初始化LLM提供商
        self._init_provider()

        # 初始化正在处理的用户集合
        self.processing_users = set()

        logger.info("astrbot_plugin_daily_fortune1 插件已加载")

    def _parse_ranges_string(self, ranges_str: str) -> List[List[int]]:
        """解析人品值分段字符串"""
        try:
            ranges = []
            parts = [part.strip() for part in ranges_str.split(',')]
            for part in parts:
                if '-' in part:
                    min_val, max_val = part.split('-', 1)
                    ranges.append([int(min_val.strip()), int(max_val.strip())])
                else:
                    # 如果没有'-'，则认为是单个值
                    val = int(part.strip())
                    ranges.append([val, val])
            return ranges
        except Exception as e:
            logger.error(f"[daily_fortune] 解析人品值分段失败: {e}")
            return []

    def _parse_list_string(self, list_str: str) -> List[str]:
        """解析逗号分隔的字符串列表"""
        try:
            return [item.strip() for item in list_str.split(',') if item.strip()]
        except Exception as e:
            logger.error(f"[daily_fortune] 解析字符串列表失败: {e}")
            return []

    def _init_fortune_levels(self):
        """初始化运势等级映射"""
        # 获取配置的人品值分段字符串
        jrrp_ranges_str = self.config.get("jrrp_ranges", "0-1, 2-10, 11-20, 21-30, 31-40, 41-60, 61-80, 81-98, 99-100")
        jrrp_ranges_config = self._parse_ranges_string(jrrp_ranges_str)

        # 获取配置的运势描述字符串
        fortune_names_str = self.config.get("fortune_names", "极凶, 大凶, 凶, 小凶, 末吉, 小吉, 中吉, 大吉, 极吉")
        fortune_names_config = self._parse_list_string(fortune_names_str)

        # 获取配置的emoji字符串
        fortune_emojis_str = self.config.get("fortune_emojis", "💀, 😨, 😰, 😟, 😐, 🙂, 😊, 😄, 🤩")
        fortune_emojis_config = self._parse_list_string(fortune_emojis_str)

        # 保存配置字符串供模板使用
        self.jrrp_ranges_str = jrrp_ranges_str
        self.fortune_names_str = fortune_names_str
        self.fortune_emojis_str = fortune_emojis_str

        # 构建运势等级映射
        self.fortune_levels = {}

        for i, range_config in enumerate(jrrp_ranges_config):
            if len(range_config) >= 2:
                min_val = int(range_config[0])
                max_val = int(range_config[1])

                # 获取对应的运势描述和emoji，如果超出范围则使用默认值
                fortune_name = fortune_names_config[i] if i < len(fortune_names_config) else "未知"
                fortune_emoji = fortune_emojis_config[i] if i < len(fortune_emojis_config) else "❓"

                self.fortune_levels[(min_val, max_val)] = (fortune_name, fortune_emoji)

        # 如果配置为空或无效，使用默认配置
        if not self.fortune_levels:
            self.fortune_levels = {
                (0, 1): ("极凶", "💀"),
                (2, 10): ("大凶", "😨"),
                (11, 20): ("凶", "😰"),
                (21, 30): ("小凶", "😟"),
                (31, 40): ("末吉", "😐"),
                (41, 60): ("小吉", "🙂"),
                (61, 80): ("中吉", "😊"),
                (81, 98): ("大吉", "😄"),
                (99, 100): ("极吉", "🤩")
            }

        logger.info(f"[daily_fortune] 运势等级映射已初始化，共 {len(self.fortune_levels)} 个等级")

    def _init_medals(self):
        """初始化奖牌配置"""
        medals_str = self.config.get("medals", "🥇, 🥈, 🥉, 🏅, 🏅")
        self.medals = self._parse_list_string(medals_str)

        # 如果配置为空，使用默认值
        if not self.medals:
            self.medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]

        self.medals_str = medals_str
        logger.info(f"[daily_fortune] 奖牌配置已初始化，共 {len(self.medals)} 个奖牌")

    def _get_provider_info(self, provider):
        """获取provider详细信息的辅助方法"""
        try:
            # 尝试多种属性获取名称，优先使用用户自定义的备注名称
            name = None
            
            # 尝试获取用户自定义的备注名称（可能的属性名）
            possible_custom_name_attrs = [
                'alias', 'custom_name', 'user_name', 'remark', 'comment', 
                'label', 'config_name', 'nickname', 'display_name', 'title',
                'friendly_name', 'custom_alias', 'user_alias', 'description'
            ]
            
            for attr in possible_custom_name_attrs:
                if hasattr(provider, attr):
                    value = getattr(provider, attr, None)
                    if value and str(value).strip():
                        name = str(value).strip()
                        break
            
            # 如果还没有找到，尝试从配置对象中获取
            if not name and hasattr(provider, 'config'):
                config = getattr(provider, 'config', {})
                if isinstance(config, dict):
                    for key in ['name', 'alias', 'custom_name', 'nickname', 'display_name', 'title', 'label']:
                        if key in config and config[key]:
                            name = str(config[key]).strip()
                            break
            
            # 尝试其他可能的嵌套属性
            if not name:
                for attr_path in ['settings.name', 'meta.name', 'info.name', 'data.name']:
                    try:
                        obj = provider
                        for part in attr_path.split('.'):
                            obj = getattr(obj, part, None)
                            if obj is None:
                                break
                        if obj and str(obj).strip():
                            name = str(obj).strip()
                            break
                    except:
                        continue
            
            # 如果仍然没有找到，使用标准属性
            if not name:
                if hasattr(provider, 'provider_name') and provider.provider_name:
                    name = provider.provider_name
                elif hasattr(provider, 'name') and provider.name:
                    name = provider.name
            
            # 最后从类名推断
            if not name:
                class_name = provider.__class__.__name__
                if 'OpenAI' in class_name:
                    name = 'OpenAI'
                elif 'Claude' in class_name:
                    name = 'Claude'
                elif 'Gemini' in class_name:
                    name = 'Gemini'
                else:
                    name = class_name.replace('Provider', '').replace('Official', '')
            
            provider_id_attr = getattr(provider, 'provider_id', getattr(provider, 'id', str(provider)))
            provider_type = getattr(provider, 'provider_type', getattr(provider, 'type', 'Unknown'))
            model = getattr(provider, 'model_name', getattr(provider, 'model', 'Unknown'))
            
            return name, provider_id_attr, provider_type, model
        except Exception as e:
            logger.debug(f"Error getting provider info: {e}")
            return 'Unknown', 'Unknown', 'Unknown', 'Unknown'

    def _init_provider(self):
        """初始化LLM提供商"""
        provider_id = self.config.get("llm_provider_id", "")

        if provider_id:
            try:
                # 显示所有可用的provider
                all_providers = self.context.get_all_providers()
                logger.debug(f"[daily_fortune] 所有可用的providers:")
                for p in all_providers:
                    name, pid, ptype, model = self._get_provider_info(p)
                    logger.debug(f"Available provider: {name} (ID: {pid}, Type: {ptype}, Model: {model})")
                
                # 查找指定的provider
                self.provider = self.context.get_provider_by_id(provider_id)
                if self.provider:
                    name, pid, ptype, model = self._get_provider_info(self.provider)
                    logger.debug(f"Found matching provider: {name} (ID: {pid}, Type: {ptype}, Model: {model})")
                    asyncio.create_task(self._test_provider_connection())
                else:
                    logger.warning(f"[daily_fortune] 未找到provider_id: {provider_id}")
                    # 尝试通过名称匹配
                    for p in all_providers:
                        name, _, _, _ = self._get_provider_info(p)
                        if name == provider_id or str(p) == provider_id:
                            self.provider = p
                            logger.debug(f"[daily_fortune] 通过名称匹配找到: {provider_id}")
                            break
                    
                    if not self.provider:
                        logger.warning(f"[daily_fortune] 所有匹配方式都失败，将使用默认提供商")
                        self.provider = None
            except Exception as e:
                logger.error(f"[daily_fortune] 获取provider失败: {e}")
                self.provider = None
        else:
            # 使用第三方接口配置
            api_config = self.config.get("llm_api", {})
            if api_config.get("api_key") and api_config.get("url"):
                logger.info(f"[daily_fortune] 配置了第三方接口: {api_config['url']}")
                # 创建自定义provider
                asyncio.create_task(self._test_third_party_api(api_config))
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
                    logger.info(f"[daily_fortune] 使用人格: {self.persona_name}, prompt前20字符: {prompt[:20]}...")
                    found = True
                    break
            if not found:
                logger.warning(f"[daily_fortune] 未找到人格: {self.persona_name}")
        else:
            # 输出默认人格信息
            default_persona = self.context.provider_manager.selected_default_persona
            if default_persona:
                persona_name = default_persona.get("name", "未知")
                # 查找完整人格信息
                personas = self.context.provider_manager.personas
                for p in personas:
                    if p.get('name') == persona_name:
                        prompt = p.get('prompt', '')
                        logger.info(f"[daily_fortune] 使用默认人格: {persona_name}, prompt前20字符: {prompt[:20]}...")
                        break

    async def _test_provider_connection(self):
        """测试provider连接"""
        try:
            if self.provider:
                # 从AstrBot配置中获取用户自定义的provider名称
                provider_display_name = self._get_provider_display_name()
                
                logger.debug(f"Sending 'Ping' to provider: {provider_display_name}")
                response = await asyncio.wait_for(
                    self.provider.text_chat(prompt="REPLY `PONG` ONLY"), timeout=45.0
                )
                logger.debug(f"Received response from {provider_display_name}: {response}")
                
                if response and response.completion_text:
                    logger.info(f"[daily_fortune] Provider连接测试成功: {provider_display_name}")
                else:
                    logger.warning(f"[daily_fortune] Provider连接测试失败：无响应 - {provider_display_name}")
        except Exception as e:
            provider_display_name = self._get_provider_display_name()
            logger.error(f"[daily_fortune] Provider连接测试失败: {provider_display_name} - {e}")

    def _get_provider_display_name(self):
        """获取用户配置的provider显示名称"""
        # 直接从插件配置中获取用户填写的provider名称
        provider_display_name = self.config.get("llm_provider_id", "")
        return provider_display_name if provider_display_name else "Unknown"

    async def _test_third_party_api(self, api_config):
        """测试第三方API连接"""
        try:
            import aiohttp

            # 智能处理URL
            url = api_config['url'].rstrip('/')
            if not url.endswith('/chat/completions'):
                if url.endswith('/v1'):
                    url += '/chat/completions'
                else:
                    url += '/v1/chat/completions'

            headers = {
                'Authorization': f"Bearer {api_config['api_key']}",
                'Content-Type': 'application/json'
            }

            data = {
                'model': api_config.get('model', 'gpt-3.5-turbo'),
                'messages': [{'role': 'user', 'content': 'REPLY `PONG` ONLY'}],
                'max_tokens': 10
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info(f"[daily_fortune] 第三方API连接测试成功: {api_config['url']}")
                    else:
                        text = await resp.text()
                        logger.warning(f"[daily_fortune] 第三方API连接测试失败: {resp.status} - {text}")
        except Exception as e:
            logger.error(f"[daily_fortune] 第三方API连接测试失败: {e}")

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
        algorithm = self.config.get("jrrp_algorithm", "random")
        today = self._get_today_key()

        if algorithm == "random":
            # 纯随机算法（添加时间变量实现真随机）
            current_time = datetime.now().strftime("%H:%M:%S.%f")  # 包含微秒的时间
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            return random.randint(0, 100)

        elif algorithm == "hash":
            # 基于用户ID和日期的哈希算法（保持固定）
            seed = f"{user_id}_{today}"
            hash_value = int(hashlib.md5(seed.encode()).hexdigest(), 16)
            return hash_value % 101

        elif algorithm == "normal":
            # 正态分布算法（中间值概率高）
            current_time = datetime.now().strftime("%H:%M:%S.%f")
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            # 均值50，标准差20的正态分布
            value = int(np.random.normal(50, 20))
            # 限制在0-100范围内
            return max(0, min(100, value))

        elif algorithm == "lucky":
            # 幸运算法（高分值概率较高）
            current_time = datetime.now().strftime("%H:%M:%S.%f")
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            # 使用beta分布，α=8, β=2，偏向高分
            value = int(np.random.beta(8, 2) * 100)
            return value

        elif algorithm == "challenge":
            # 挑战算法（极端值概率较高）
            current_time = datetime.now().strftime("%H:%M:%S.%f")
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            # 30%概率获得极低或极高值
            if random.random() < 0.3:
                # 极端值
                if random.random() < 0.5:
                    return random.randint(0, 20)  # 极低
                else:
                    return random.randint(80, 100)  # 极高
            else:
                # 普通值
                return random.randint(21, 79)
        else:
            # 默认使用random算法
            current_time = datetime.now().strftime("%H:%M:%S.%f")  # 包含微秒的时间
            seed = f"{user_id}_{today}_{current_time}"
            random.seed(seed)
            return random.randint(0, 100)

    def _get_fortune_info(self, jrrp: int) -> tuple:
        """根据人品值获取运势信息"""
        # 按照配置的分段从左到右匹配
        for (min_val, max_val), (fortune, emoji) in self.fortune_levels.items():
            if min_val <= jrrp <= max_val:
                return fortune, emoji
        return "未知", "❓"

    async def _get_user_info(self, event: AstrMessageEvent, target_user_id: str = None) -> Dict[str, str]:
        """获取用户信息（从rawmessage_viewer1插件）"""
        user_id = target_user_id or event.get_sender_id()
        nickname = event.get_sender_name() if not target_user_id else f"用户{target_user_id}"
        card = nickname  # 默认值
        title = "无"  # 默认值

        # 尝试从rawmessage_viewer1插件获取增强信息
        try:
            if event.get_platform_name() == "aiocqhttp":
                # 如果是查询自己，直接从事件的raw_message获取信息
                if not target_user_id:
                    raw_message = event.message_obj.raw_message
                    if isinstance(raw_message, dict):
                        sender = raw_message.get("sender", {})
                        if sender:
                            # 优先使用原始消息中的信息
                            nickname = sender.get("nickname", nickname)
                            card = sender.get("card", "") or nickname
                            title = sender.get("title", "") or "无"

                            # 调试日志
                            logger.debug(f"[daily_fortune] 从raw_message获取用户信息: user_id={user_id}, nickname={nickname}, card={card}, title={title}")

                # 如果raw_message中没有，或者是查询他人，再尝试从插件获取
                if (card == nickname and title == "无") or target_user_id:
                    message_id = event.message_obj.message_id
                    plugins = self.context.get_all_stars()
                    for plugin_meta in plugins:
                        if plugin_meta.metadata.name == "astrbot_plugin_rawmessage_viewer1":
                            plugin_instance = plugin_meta.instance
                            if hasattr(plugin_instance, 'enhanced_messages'):
                                enhanced_msg = plugin_instance.enhanced_messages.get(message_id, {})
                                if enhanced_msg:
                                    # 如果是查询自己，确保获取的是当前消息的发送者信息
                                    if not target_user_id:
                                        msg_sender = enhanced_msg.get("sender", {})
                                        if msg_sender.get("user_id") == int(user_id):
                                            nickname = msg_sender.get("nickname", nickname)
                                            card = msg_sender.get("card", nickname)
                                            title = msg_sender.get("title", "无")
                                            logger.debug(f"[daily_fortune] 从rawmessage_viewer1获取用户信息: user_id={user_id}, nickname={nickname}, card={card}, title={title}")
                                    else:
                                        # 查询他人时，尝试从@信息中获取
                                        for i in range(1, 10):  # 检查ater1到ater9
                                            ater_key = f"ater{i}"
                                            if ater_key in enhanced_msg:
                                                ater_info = enhanced_msg[ater_key]
                                                if str(ater_info.get("user_id")) == str(target_user_id):
                                                    nickname = ater_info.get("nickname", nickname)
                                                    card = ater_info.get("card", nickname)
                                                    title = ater_info.get("title", "无")
                                                    logger.debug(f"[daily_fortune] 从ater信息获取用户信息: user_id={user_id}, nickname={nickname}, card={card}, title={title}")
                                                    break
                            break
        except Exception as e:
            logger.debug(f"获取增强用户信息失败: {e}")

        # 确保card有值
        if not card or card == "":
            card = nickname

        return {
            "user_id": user_id,
            "nickname": nickname,
            "card": card,
            "title": title
        }

    async def _generate_with_llm(self, prompt: str, system_prompt: str = "", user_nickname: str = "") -> str:
        """使用LLM生成内容"""
        # 检查是否启用LLM（通过配置）
        if not self.config.get("enable_llm_calls", True):
            logger.debug("[daily_fortune] LLM调用被配置禁用")
            if "过程" in prompt:
                return "水晶球中浮现出神秘的光芒..."
            elif "建议" in prompt:
                return "保持乐观的心态，好运自然来。"
            return "LLM服务已被禁用"
            
        try:
            # 优先使用默认provider，如果配置的provider不可用
            provider = self.context.get_using_provider()
            if not provider and self.provider:
                provider = self.provider

            if not provider:
                logger.warning("[daily_fortune] 没有可用的LLM提供商")
                # 返回备用响应
                if "过程" in prompt:
                    return "水晶球中浮现出神秘的光芒..."
                elif "建议" in prompt:
                    return "保持乐观的心态，好运自然来。"
                return "LLM服务暂时不可用"

            # 获取当前会话的人格信息
            contexts = []

            # 在prompt中明确指定用户昵称，避免混乱
            if user_nickname:
                prompt = f"用户昵称是'{user_nickname}'。{prompt}"

            # 处理system_prompt - 某些模型可能不支持
            try:
                # 首先尝试使用system_prompt
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
            except Exception as e:
                # 如果system_prompt导致错误，尝试将其合并到prompt中
                logger.debug(f"使用system_prompt失败，尝试合并到prompt: {e}")
                combined_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                try:
                    response = await provider.text_chat(
                        prompt=combined_prompt,
                        contexts=contexts
                    )
                except Exception as e2:
                    logger.error(f"LLM调用完全失败: {e2}")
                    # 返回备用响应
                    if "过程" in prompt:
                        return "水晶球中浮现出神秘的光芒..."
                    elif "建议" in prompt:
                        return "保持乐观的心态，好运自然来。"
                    return "生成失败"

            return response.completion_text if response else "生成失败"
        except Exception as e:
            logger.error(f"LLM生成失败: {e}")
            # 返回备用响应
            if "过程" in prompt:
                return "水晶球中浮现出神秘的光芒..."
            elif "建议" in prompt:
                return "保持乐观的心态，好运自然来。"
            return "生成失败"

    def _get_target_user_from_event(self, event: AstrMessageEvent) -> Tuple[Optional[str], Optional[str]]:
        """从消息中提取目标用户ID和昵称"""
        for comp in event.message_obj.message:
            if isinstance(comp, Comp.At):
                return str(comp.qq), f"用户{comp.qq}"
        return None, None

    def _has_confirm_param(self, event: AstrMessageEvent) -> bool:
        """检查消息中是否包含 --confirm 参数"""
        return "--confirm" in event.message_str.lower()

    @filter.command("jrrp")
    async def jrrp(self, event: AstrMessageEvent, subcommand: str = ""):
        """今日人品查询"""
        # 处理help子命令
        if subcommand.lower() == "help":
            # help不需要LLM
            event.should_call_llm(False)
            help_text = """📖 每日人品插件指令帮助

🎲 基础指令：
• 查询自己的今日人品值
    - jrrp
• 查询他人的今日人品值
    - jrrp @某人
• 显示帮助信息
    - jrrp help

📊 排行榜：
• 查看群内今日人品排行榜
    - jrrp rank
    - jrrprank

📚 历史记录：
• 查看历史记录
    - jrrp history
    - jrrp hi
    - jrrphistory
    - jrrphi
• 查看他人历史记录
    - jrrp history @某人
    - jrrphistory @某人

🗑️ 数据管理：
• 删除除今日外的历史记录
    - jrrp delete --confirm
    - jrrp del --confirm
    - jrrpdelete --confirm
    - jrrpdel --confirm

⚙️ 管理员指令：
• 初始化今日记录
    - jrrp init --confirm
    - jrrp initialize --confirm
    - jrrpinit --confirm
    - jrrpinitialize --confirm
• 初始化他人今日记录
    - jrrp init @某人 --confirm
    - jrrpinit @某人 --confirm
• 重置所有数据
    - jrrp reset --confirm
    - jrrp re --confirm
    - jrrpreset --confirm
    - jrrpre --confirm

💡 提示：带 --confirm 的指令需要确认参数才能执行"""
            yield event.plain_result(help_text)
            return

        # 处理其他子命令
        if subcommand.lower() == "rank":
            # 直接调用生成器函数
            async for result in self.jrrprank(event):
                yield result
            return
        
        elif subcommand.lower() in ["history", "hi"]:
            # 直接调用生成器函数
            async for result in self.jrrphistory(event):
                yield result
            return
        
        elif subcommand.lower() in ["init", "initialize"]:
            # 初始化指令需要管理员权限
            if not event.is_admin():
                yield event.plain_result("❌ 此操作需要管理员权限")
                return
            # 检查是否有 --confirm 参数
            confirm_param = "--confirm" if self._has_confirm_param(event) else ""
            # 直接调用生成器函数
            async for result in self.jrrpinitialize(event, confirm_param):
                yield result
            return
        
        elif subcommand.lower() in ["delete", "del"]:
            # 检查是否有 --confirm 参数
            confirm_param = "--confirm" if self._has_confirm_param(event) else ""
            async for result in self.jrrpdelete(event, confirm_param):
                yield result
            return

        elif subcommand.lower() in ["reset", "re"]:
            # 重置指令需要管理员权限
            if not event.is_admin():
                yield event.plain_result("❌ 此操作需要管理员权限")
                return
            # 检查是否有 --confirm 参数
            confirm_param = "--confirm" if self._has_confirm_param(event) else ""
            async for result in self.jrrpreset(event, confirm_param):
                yield result
            return

        # 检查是否有@某人
        target_user_id, target_nickname = self._get_target_user_from_event(event)

        # 如果是查询他人 - 不需要LLM
        if target_user_id:
            event.should_call_llm(False)
            
            today = self._get_today_key()
            sender_info = await self._get_user_info(event)
            sender_nickname = sender_info["nickname"]

            # 获取被查询者的用户信息
            target_user_info = await self._get_user_info(event, target_user_id)
            target_nickname = target_user_info["nickname"]

            # 检查对方是否已经查询过
            if today not in self.daily_data or target_user_id not in self.daily_data[today]:
                # 使用配置的未查询提示信息，支持所有变量
                not_queried_template = self.config.get("others_not_queried_message",
                    "{target_nickname} 今天还没有查询过人品值呢~")

                # 准备变量字典，包含所有可能的变量
                vars_dict = {
                    "target_nickname": target_nickname,
                    "target_user_id": target_user_id,
                    "sender_nickname": sender_nickname,
                    "nickname": target_nickname,  # 兼容原有变量
                    "card": target_user_info["card"],
                    "title": target_user_info["title"],
                    "date": today,
                    # 由于对方未查询，这些值为空或默认值
                    "jrrp": "未知",
                    "fortune": "未知",
                    "femoji": "❓",
                    "process": "",
                    "advice": "",
                    "avgjrrp": 0,
                    "maxjrrp": 0,
                    "minjrrp": 0,
                    "ranks": "",
                    "medal": "",
                    "medals": self.medals_str,
                    "jrrp_ranges": self.jrrp_ranges_str,
                    "fortune_names": self.fortune_names_str,
                    "fortune_emojis": self.fortune_emojis_str
                }

                result = not_queried_template.format(**vars_dict)
                yield event.plain_result(result)
                return

            # 获取对方的查询结果
            cached = self.daily_data[today][target_user_id]
            jrrp = cached["jrrp"]
            fortune, femoji = self._get_fortune_info(jrrp)
            target_nickname = cached.get("nickname", target_nickname)

            # 构建查询模板，支持所有变量
            query_template = self.config.get("templates", {}).get("query",
                "📌 今日人品\n{nickname}，今天已经查询过了哦~\n今日人品值: {jrrp}\n运势: {fortune} {femoji}")

            # 准备变量字典
            vars_dict = {
                "nickname": target_nickname,
                "card": target_user_info["card"],
                "title": target_user_info["title"],
                "jrrp": jrrp,
                "fortune": fortune,
                "femoji": femoji,
                "date": today,
                "process": cached.get("process", ""),
                "advice": cached.get("advice", ""),
                "target_nickname": target_nickname,
                "target_user_id": target_user_id,
                "sender_nickname": sender_nickname,
                # 统计信息（如果需要的话）
                "avgjrrp": jrrp,  # 单个用户的平均值就是当前值
                "maxjrrp": jrrp,
                "minjrrp": jrrp,
                "ranks": "",
                "medal": "",
                "medals": self.medals_str,
                "jrrp_ranges": self.jrrp_ranges_str,
                "fortune_names": self.fortune_names_str,
                "fortune_emojis": self.fortune_emojis_str
            }

            result = query_template.format(**vars_dict)

            # 检查是否显示对方的缓存完整结果
            if self.config.get("show_others_cached_result", False) and "result" in cached:
                result += f"\n\n-----以下为{target_nickname}的今日运势测算场景还原-----\n{cached['result']}"

            yield event.plain_result(result)
            return

        # 查询自己的人品
        user_info = await self._get_user_info(event)
        user_id = user_info["user_id"]
        nickname = user_info["nickname"]
        today = self._get_today_key()

        # 初始化今日数据（修复KeyError）
        if today not in self.daily_data:
            self.daily_data[today] = {}

        # 检查用户是否正在处理中
        if user_id in self.processing_users:
            # 用户正在处理中，彻底阻止事件传播和LLM调用
            event.should_call_llm(False)
            event.stop_event()
            processing_msg = self.config.get("processing_message",
                "已经在努力获取 {nickname} 的命运了哦~")
            yield event.plain_result(processing_msg.format(nickname=nickname))
            return

        # 检查是否已经查询过
        if user_id in self.daily_data[today]:
            # 已查询，返回缓存结果 - 不需要LLM
            event.should_call_llm(False)
            
            cached = self.daily_data[today][user_id]
            jrrp = cached["jrrp"]
            fortune, femoji = self._get_fortune_info(jrrp)

            # 构建查询模板
            query_template = self.config.get("templates", {}).get("query",
                "📌 今日人品\n{nickname}，今天已经查询过了哦~\n今日人品值: {jrrp}\n运势: {fortune} {femoji}")

            # 准备变量字典
            vars_dict = {
                "nickname": nickname,
                "card": user_info["card"],
                "title": user_info["title"],
                "jrrp": jrrp,
                "fortune": fortune,
                "femoji": femoji,
                "date": today,
                "process": cached.get("process", ""),
                "advice": cached.get("advice", ""),
                # 统计信息
                "avgjrrp": jrrp,
                "maxjrrp": jrrp,
                "minjrrp": jrrp,
                "ranks": "",
                "medal": "",
                "medals": self.medals_str,
                "jrrp_ranges": self.jrrp_ranges_str,
                "fortune_names": self.fortune_names_str,
                "fortune_emojis": self.fortune_emojis_str
            }

            result = query_template.format(**vars_dict)

            # 如果配置启用了显示缓存结果
            if self.config.get("show_cached_result", True) and "result" in cached:
                result += f"\n\n-----以下为今日运势测算场景还原-----\n{cached['result']}"

            yield event.plain_result(result)
            return

        # 首次查询，阻止默认的LLM调用（我们自己控制LLM调用）
        event.should_call_llm(False)
        
        # 将用户添加到正在处理的集合中
        self.processing_users.add(user_id)
        
        try:
            # 显示检测中消息
            detecting_msg = self.config.get("detecting_message",
                "神秘的能量汇聚，{nickname}，你的命运即将显现，正在祈祷中...")
            yield event.plain_result(detecting_msg.format(nickname=nickname))

            # 计算人品值
            jrrp = self._calculate_jrrp(user_id)
            fortune, femoji = self._get_fortune_info(jrrp)

            # 准备LLM生成的变量
            vars_dict = {
                "user_id": user_id,
                "nickname": nickname,
                "card": user_info["card"],
                "title": user_info["title"],
                "jrrp": jrrp,
                "fortune": fortune,
                "femoji": femoji,
                "date": today,
                "medals": self.medals_str,
                "jrrp_ranges": self.jrrp_ranges_str,
                "fortune_names": self.fortune_names_str,
                "fortune_emojis": self.fortune_emojis_str
            }

            # 生成过程模拟（传入用户昵称）
            process_prompt = self.config.get("prompts", {}).get("process",
                "使用与{nickname}称呼，模拟你使用水晶球缓慢复现今日结果的过程，50字以内")
            process_prompt = process_prompt.format(**vars_dict)
            process = await self._generate_with_llm(process_prompt, user_nickname=nickname)

            # 生成建议（传入用户昵称）
            advice_prompt = self.config.get("prompts", {}).get("advice",
                "人品值分段为{jrrp_ranges}，对应运势是{fortune_names}\n上述作为人品值好坏的参考，接下来，\n对{user_id}的今日人品值{jrrp}给出你的评语和建议，50字以内")
            advice_prompt = advice_prompt.format(**vars_dict)
            advice = await self._generate_with_llm(advice_prompt, user_nickname=nickname)

            # 构建结果
            result_template = self.config.get("templates", {}).get("random",
                "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}")

            result = result_template.format(
                process=process,
                jrrp=jrrp,
                fortune=fortune,
                advice=advice
            )

            # 缓存结果（确保today已存在）
            if today not in self.daily_data:
                self.daily_data[today] = {}

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
            
        finally:
            # 确保在处理完成后从集合中移除用户
            self.processing_users.discard(user_id)

    @filter.command("jrrprank")
    async def jrrprank(self, event: AstrMessageEvent):
        """群内今日人品排行榜"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
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

        for i, user in enumerate(group_data[:10]):  # 只显示前10名
            medal = self.medals[i] if i < len(self.medals) else self.medals[-1] if self.medals else "🏅"
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
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        # 检查是否有@某人
        target_user_id, target_nickname = self._get_target_user_from_event(event)
        
        if not target_user_id:
            target_user_id = event.get_sender_id()
            target_nickname = event.get_sender_name()
        else:
            # 获取被@用户的信息
            target_user_info = await self._get_user_info(event, target_user_id)
            target_nickname = target_user_info["nickname"]

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
        """删除个人人品历史记录（保留今日）"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        # 只能删除自己的数据
        target_user_id = event.get_sender_id()
        target_nickname = event.get_sender_name()

        # 检查确认参数
        if confirm != "--confirm" and not self._has_confirm_param(event):
            yield event.plain_result(f"⚠️ 警告：此操作将删除您的除今日以外的所有人品历史记录！\n如确认删除，请使用：/jrrpdelete --confirm")
            return

        today = self._get_today_key()
        deleted_count = 0

        # 删除历史记录（保留今日）
        if target_user_id in self.history_data:
            user_history = self.history_data[target_user_id]
            dates_to_delete = [date for date in user_history.keys() if date != today]
            for date in dates_to_delete:
                del user_history[date]
                deleted_count += 1

            # 如果历史记录为空，删除整个用户记录
            if not user_history:
                del self.history_data[target_user_id]

            self._save_data(self.history_data, self.history_file)

        # 删除每日记录（保留今日）
        dates_to_delete = [date for date in self.daily_data.keys() if date != today]
        for date in dates_to_delete:
            if target_user_id in self.daily_data[date]:
                del self.daily_data[date][target_user_id]
                deleted_count += 1
            # 如果该日期没有任何用户数据，删除整个日期记录
            if not self.daily_data[date]:
                del self.daily_data[date]

        self._save_data(self.daily_data, self.fortune_file)

        yield event.plain_result(f"✅ 已删除您的除今日以外的人品历史记录（共 {deleted_count} 条）")

    @filter.command("jrrpinitialize", alias={"jrrpinit"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def jrrpinitialize(self, event: AstrMessageEvent, confirm: str = ""):
        """初始化今日人品记录（仅管理员）"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        # 检查是否有@某人
        target_user_id, target_nickname = self._get_target_user_from_event(event)
        is_target_others = target_user_id is not None

        if not target_user_id:
            target_user_id = event.get_sender_id()
            target_nickname = event.get_sender_name()
        else:
            # 获取被@用户的信息
            target_user_info = await self._get_user_info(event, target_user_id)
            target_nickname = target_user_info["nickname"]

        # 检查确认参数
        if confirm != "--confirm" and not self._has_confirm_param(event):
            action_desc = f"{target_nickname} 的" if is_target_others else "您的"
            cmd_example = f"/jrrpinit @{target_nickname} --confirm" if is_target_others else "/jrrpinit --confirm"
            yield event.plain_result(f"⚠️ 警告：此操作将删除 {action_desc}今日人品记录，使其可以重新随机！\n如确认初始化，请使用：{cmd_example}")
            return

        today = self._get_today_key()
        deleted = False

        # 删除今日记录
        if today in self.daily_data and target_user_id in self.daily_data[today]:
            del self.daily_data[today][target_user_id]
            deleted = True
            # 如果该日期没有任何用户数据，删除整个日期记录
            if not self.daily_data[today]:
                del self.daily_data[today]
            self._save_data(self.daily_data, self.fortune_file)

        # 删除今日历史记录
        if target_user_id in self.history_data and today in self.history_data[target_user_id]:
            del self.history_data[target_user_id][today]
            deleted = True
            # 如果历史记录为空，删除整个用户记录
            if not self.history_data[target_user_id]:
                del self.history_data[target_user_id]
            self._save_data(self.history_data, self.history_file)

        # 从正在处理的集合中移除（如果存在）
        self.processing_users.discard(target_user_id)

        action_desc = f"{target_nickname} 的" if is_target_others else "您的"
        if deleted:
            yield event.plain_result(f"✅ 已初始化 {action_desc}今日人品记录，现在可以重新使用 /jrrp 随机人品值了")
        else:
            yield event.plain_result(f"ℹ️ {action_desc}今日还没有人品记录，无需初始化")

    @filter.command("jrrpreset", alias={"jrrpre"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def jrrpreset(self, event: AstrMessageEvent, confirm: str = ""):
        """重置所有人品数据（仅管理员）"""
        # 防止触发LLM调用
        event.should_call_llm(False)
        
        # 检查确认参数
        if confirm != "--confirm" and not self._has_confirm_param(event):
            yield event.plain_result("⚠️ 警告：此操作将删除所有用户的人品数据！\n如确认重置，请使用：/jrrpreset --confirm")
            return

        # 清空所有数据
        self.daily_data = {}
        self.history_data = {}
        self._save_data(self.daily_data, self.fortune_file)
        self._save_data(self.history_data, self.history_file)

        # 清空正在处理的用户集合
        self.processing_users.clear()

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
