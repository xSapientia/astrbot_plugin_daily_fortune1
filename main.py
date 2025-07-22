from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import random
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
import aiofiles
import asyncio
import re
import math

# 全局锁
_fortune_lock = asyncio.Lock()

@register(
    "astrbot_plugin_daily_fortune1",
    "xSapientia",
    "今日人品测试插件 - 完全重构版",
    "0.0.3",
    "https://github.com/xSapientia/astrbot_plugin_daily_fortune1",
)
class DailyFortunePlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        # 在 __init__ 方法中添加
        hasattr(self, 'metadata') and hasattr(self.metadata, 'config'):
        self.config = self.metadata.config
        # 监听配置变化
        if hasattr(self.metadata, 'save_config'):
            self._config_save_callback = self.metadata.save_config


        self.context = context
        self.config = config if config else {}

        # 更新配置
        if hasattr(self, 'metadata') and hasattr(self.metadata, 'config'):
            self.config = self.metadata.config

        # 数据文件路径
        self.data_dir = os.path.join("data", "plugin_data", "astrbot_plugin_daily_fortune1")
        self.fortune_file = os.path.join(self.data_dir, "fortunes.json")
        self.history_file = os.path.join(self.data_dir, "history.json")
        os.makedirs(self.data_dir, exist_ok=True)

        # 运势等级定义 - 这是固定的，不是配置
        self.fortune_levels = [
            (0, 10, "大凶", "😱"),
            (11, 30, "凶", "😰"),
            (31, 50, "末吉", "😐"),
            (51, 70, "吉", "😊"),
            (71, 90, "中吉", "😄"),
            (91, 99, "大吉", "🎉"),
            (100, 100, "神吉", "🌟")
        ]

        logger.info("今日人品插件 v0.0.3 加载成功！")

    def _get_config(self, key: str) -> Any:
        """获取配置值，不再传入默认值"""
        if self.config and key in self.config:
            return self.config[key]
        # 如果配置不存在，返回None，让调用方处理
        return None

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

    def _get_fortune_info(self, jrrp: int) -> Tuple[str, str]:
        """获取运势信息"""
        for min_val, max_val, fortune, emoji in self.fortune_levels:
            if min_val <= jrrp <= max_val:
                return fortune, emoji
        return "吉", "😊"

    def _get_fortune_value(self) -> int:
        """根据配置的算法获取人品值"""
        algorithm = self._get_config("fortune_algorithm")
        if not algorithm:
            algorithm = "uniform"  # 仅在配置完全缺失时使用

        if algorithm == "uniform":
            # 均匀分布
            return random.randint(0, 100)

        elif algorithm == "normal":
            # 正态分布
            mean = self._get_config("fortune_normal_mean")
            std = self._get_config("fortune_normal_std")
            if mean is None:
                mean = 60
            if std is None:
                std = 20
            value = random.gauss(mean, std)
            return max(0, min(100, int(value)))

        elif algorithm == "lucky":
            # 幸运算法 - 偏向高分
            base = random.randint(40, 100)
            if random.random() < 0.3:  # 30%概率加成
                base = min(100, base + random.randint(10, 30))
            return base

        elif algorithm == "unlucky":
            # 厄运算法 - 偏向低分
            base = random.randint(0, 60)
            if random.random() < 0.3:  # 30%概率减成
                base = max(0, base - random.randint(10, 30))
            return base

        elif algorithm == "polarized":
            # 极化算法 - 两极分化
            if random.random() < 0.5:
                return random.randint(0, 30)
            else:
                return random.randint(70, 100)

        elif algorithm == "ladder":
            # 阶梯算法 - 固定几个值
            values = [0, 25, 50, 75, 100]
            return random.choice(values)

        elif algorithm == "golden":
            # 黄金分割算法
            if random.random() < 0.618:
                return random.randint(38, 62)  # 黄金分割点附近
            else:
                return random.randint(0, 100)

        elif algorithm == "sin_wave":
            # 正弦波算法 - 根据日期
            day_of_year = date.today().timetuple().tm_yday
            base = int(50 + 30 * math.sin(day_of_year * math.pi / 180))
            noise = random.randint(-10, 10)
            return max(0, min(100, base + noise))

        elif algorithm == "weighted":
            # 加权算法 - 从配置读取权重
            weights = {}
            weight_0_20 = self._get_config("fortune_weight_0_20")
            weight_21_40 = self._get_config("fortune_weight_21_40")
            weight_41_60 = self._get_config("fortune_weight_41_60")
            weight_61_80 = self._get_config("fortune_weight_61_80")
            weight_81_100 = self._get_config("fortune_weight_81_100")

            # 使用配置值或使用默认分布
            weights[(0, 20)] = weight_0_20 if weight_0_20 is not None else 10
            weights[(21, 40)] = weight_21_40 if weight_21_40 is not None else 20
            weights[(41, 60)] = weight_41_60 if weight_41_60 is not None else 40
            weights[(61, 80)] = weight_61_80 if weight_61_80 is not None else 20
            weights[(81, 100)] = weight_81_100 if weight_81_100 is not None else 10

            # 构建权重列表
            choices = []
            for (start, end), weight in weights.items():
                choices.extend([random.randint(start, end) for _ in range(weight)])

            return random.choice(choices) if choices else random.randint(0, 100)

        elif algorithm == "custom":
            # 自定义算法 - 使用配置的表达式
            expression = self._get_config("fortune_custom_expression")
            if not expression:
                expression = "random.randint(0, 100)"
            try:
                # 安全地评估表达式
                allowed_names = {
                    'random': random,
                    'math': math,
                    'date': date,
                    'datetime': datetime
                }
                return max(0, min(100, int(eval(expression, {"__builtins__": {}}, allowed_names))))
            except:
                return random.randint(0, 100)

        else:
            # 默认使用均匀分布
            return random.randint(0, 100)

    async def _get_user_info(self, event: AstrMessageEvent) -> Dict[str, str]:
        """获取用户信息"""
        user_id = event.get_sender_id()
        basic_name = event.get_sender_name() or f"用户{user_id[-4:]}"

        info = {
            'user_id': user_id,
            'nickname': basic_name,
            'card': basic_name,
            'title': ''
        }

        # 尝试获取增强信息
        if event.get_platform_name() == "aiocqhttp":
            try:
                if hasattr(event.message_obj, 'raw_message'):
                    raw = event.message_obj.raw_message
                    if isinstance(raw, dict) and 'sender' in raw:
                        sender = raw['sender']
                        info['nickname'] = sender.get('nickname', basic_name)
                        info['card'] = sender.get('card', '') or info['nickname']
                        info['title'] = sender.get('title', '')
            except:
                pass

        return info

    def _replace_variables(self, template: str, variables: Dict[str, Any]) -> str:
        """替换模板中的变量"""
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    async def _get_llm_provider(self):
        """获取LLM提供商"""
        provider_id = self._get_config("llm_provider_id")

        if provider_id:
            # 使用指定的provider
            provider = self.context.get_provider_by_id(provider_id)
            if provider:
                return provider

        # 使用自定义配置
        api_key = self._get_config("llm_api_key")
        api_url = self._get_config("llm_api_url")
        model = self._get_config("llm_model")

        if api_key and api_url and model:
            # 创建临时provider
            from astrbot.core.provider.openai_official import ProviderOpenAIOfficial
            return ProviderOpenAIOfficial({
                "key": api_key,
                "endpoint": api_url,
                "model": [model]
            })

        # 使用默认provider
        return self.context.get_using_provider()

    async def _get_persona_name(self) -> str:
        """获取人格名称"""
        persona_name = self._get_config("persona_name")

        if not persona_name:
            # 使用默认人格
            if hasattr(self.context, 'provider_manager'):
                if hasattr(self.context.provider_manager, 'selected_default_persona'):
                    default_persona = self.context.provider_manager.selected_default_persona
                    if default_persona:
                        persona_name = default_persona.get("name", "")

        return persona_name if persona_name else ""

    async def _generate_fortune_text(self, user_info: Dict[str, str], jrrp: int, fortune: str) -> Tuple[str, str]:
        """使用LLM生成占卜文本"""
        # 如果未启用LLM，使用固定文本
        use_llm = self._get_config("use_llm")
        if use_llm is False:  # 明确设置为False时
            return "水晶球闪烁着神秘的光芒...", "今天记得多喝水哦~"

        provider = await self._get_llm_provider()
        if not provider:
            return "水晶球闪烁着神秘的光芒...", "今天记得多喝水哦~"

        persona_name = await self._get_persona_name()

        # 准备变量
        variables = {
            'nickname': user_info['nickname'],
            'card': user_info['card'],
            'title': user_info['title'],
            'jrrp': jrrp,
            'fortune': fortune
        }

        # 获取配置的提示词
        process_prompt = self._get_config("process_prompt")
        if process_prompt:
            process_prompt = self._replace_variables(process_prompt, variables)
        else:
            process_prompt = f"为用户{user_info['nickname']}占卜今日人品值{jrrp}，描述占卜过程，50字以内"

        process_template = self._get_config("process_template")
        if process_template:
            process_prompt = self._replace_variables(process_template, variables)

        try:
            params = {
                "prompt": process_prompt,
                "session_id": None,
                "contexts": []
            }

            if persona_name:
                params["personality"] = persona_name

            resp = await provider.text_chat(**params)
            process_text = resp.completion_text if resp and resp.completion_text else "水晶球闪烁着神秘的光芒..."
        except:
            process_text = "水晶球闪烁着神秘的光芒..."

        # 生成评语
        advice_prompt = self._get_config("advice_prompt")
        if advice_prompt:
            advice_prompt = self._replace_variables(advice_prompt, variables)
        else:
            advice_prompt = f"对用户{user_info['nickname']}的今日人品值{jrrp}（{fortune}）给出建议，50字以内"

        advice_template = self._get_config("advice_template")
        if advice_template:
            advice_prompt = self._replace_variables(advice_template, variables)

        try:
            params = {
                "prompt": advice_prompt,
                "session_id": None,
                "contexts": []
            }

            if persona_name:
                params["personality"] = persona_name

            resp = await provider.text_chat(**params)
            advice_text = resp.completion_text if resp and resp.completion_text else "今天记得多喝水哦~"
        except:
            advice_text = "今天记得多喝水哦~"

        return process_text, advice_text

    @filter.command("jrrp", alias={"-jrrp"})
    async def daily_fortune(self, event: AstrMessageEvent):
        """查看今日人品"""
        async with _fortune_lock:
            try:
                # 检查插件是否启用
                enable_plugin = self._get_config("enable_plugin")
                if enable_plugin is False:  # 明确设置为False时
                    yield event.plain_result("今日人品插件已关闭")
                    return

                user_id = event.get_sender_id()
                user_info = await self._get_user_info(event)
                today = date.today().strftime("%Y-%m-%d")

                # 加载数据
                fortunes = await self._load_json(self.fortune_file)
                if today not in fortunes:
                    fortunes[today] = {}

                # 检查是否已测试
                if user_id in fortunes[today]:
                    # 已测试，查询模式
                    data = fortunes[today][user_id]
                    jrrp = data["jrrp"]
                    fortune, femoji = self._get_fortune_info(jrrp)

                    # 准备变量
                    variables = {
                        'nickname': user_info['nickname'],
                        'card': user_info['card'],
                        'title': user_info['title'],
                        'jrrp': jrrp,
                        'fortune': fortune,
                        'femoji': femoji
                    }

                    # 使用查询模板
                    query_template = self._get_config("query_template")
                    if not query_template:
                        query_template = "📌 今日人品\n[{title}]{card}({nickname})，今天已经查询过了哦~\n今日人品值: {jrrp}\n运势: {fortune} {femoji}"
                    result = self._replace_variables(query_template, variables)

                    # 是否显示缓存结果
                    show_cached = self._get_config("show_cached_result")
                    if show_cached is not False and "process" in data:  # 默认显示
                        result += "\n\n-----以下为今日运势测算场景还原-----\n"
                        cached_vars = {
                            'process': data.get('process', ''),
                            'jrrp': jrrp,
                            'fortune': fortune,
                            'advice': data.get('advice', '')
                        }
                        random_template = self._get_config("random_template")
                        if not random_template:
                            random_template = "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}"
                        result += self._replace_variables(random_template, cached_vars)

                    yield event.plain_result(result)
                    return

                # 首次测试，显示检测中消息
                detecting_msg = self._get_config("detecting_message")
                if not detecting_msg:
                    detecting_msg = "神秘的能量汇聚，[{title}]{card}({nickname})，你的命运即将显现，正在祈祷中..."
                detecting_msg = self._replace_variables(detecting_msg, {
                    'nickname': user_info['nickname'],
                    'card': user_info['card'],
                    'title': user_info['title']
                })
                yield event.plain_result(detecting_msg)

                # 使用配置的算法生成人品值
                jrrp = self._get_fortune_value()
                fortune, femoji = self._get_fortune_info(jrrp)

                # 使用LLM生成文本
                process_text, advice_text = await self._generate_fortune_text(user_info, jrrp, fortune)

                # 缓存天数
                cache_days = self._get_config("result_cache_days")
                if cache_days is None:
                    cache_days = 7

                # 保存数据
                fortunes[today][user_id] = {
                    "jrrp": jrrp,
                    "fortune": fortune,
                    "femoji": femoji,
                    "process": process_text,
                    "advice": advice_text,
                    "user_info": user_info,
                    "expire_date": (date.today() + timedelta(days=cache_days)).strftime("%Y-%m-%d")
                }
                await self._save_json(self.fortune_file, fortunes)

                # 保存历史
                history = await self._load_json(self.history_file)
                if user_id not in history:
                    history[user_id] = {}
                history[user_id][today] = {
                    "jrrp": jrrp,
                    "fortune": fortune,
                    "user_info": user_info
                }
                await self._save_json(self.history_file, history)

                # 使用随机模板
                variables = {
                    'process': process_text,
                    'jrrp': jrrp,
                    'fortune': fortune,
                    'advice': advice_text
                }
                random_template = self._get_config("random_template")
                if not random_template:
                    random_template = "🔮 {process}\n💎 人品值：{jrrp}\n✨ 运势：{fortune}\n💬 建议：{advice}"
                result = self._replace_variables(random_template, variables)

                yield event.plain_result(result)

            except Exception as e:
                logger.error(f"处理今日人品指令时出错: {e}", exc_info=True)
                yield event.plain_result("抱歉，占卜过程中出现了神秘的干扰...")

    @filter.command("jrrprank")
    async def fortune_rank(self, event: AstrMessageEvent):
        """查看群内人品排行"""
        async with _fortune_lock:
            try:
                # 检查插件是否启用
                enable_plugin = self._get_config("enable_plugin")
                if enable_plugin is False:
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

                # 获取群成员列表
                group_id = event.get_group_id()
                group_members = set()

                # 尝试获取群成员列表
                if event.get_platform_name() == "aiocqhttp":
                    try:
                        # 尝试从平台获取
                        if hasattr(event, 'bot'):
                            client = event.bot
                            members = await client.api.get_group_member_list(group_id=group_id)
                            group_members = {str(m['user_id']) for m in members}
                    except:
                        pass

                # 筛选群成员的人品数据
                group_fortunes = []
                for user_id, data in fortunes[today].items():
                    if not group_members or user_id in group_members:
                        group_fortunes.append((user_id, data))

                if not group_fortunes:
                    yield event.plain_result("📊 本群今天还没有人查询人品哦~")
                    return

                # 排序
                sorted_fortunes = sorted(group_fortunes, key=lambda x: x[1]["jrrp"], reverse=True)

                # 获取排行模板和项目模板
                rank_template = self._get_config("rank_template")
                if not rank_template:
                    rank_template = "📊【今日人品排行榜】{date}\n━━━━━━━━━━━━━━━\n{ranks}"

                rank_item_template = self._get_config("rank_item_template")
                if not rank_item_template:
                    rank_item_template = "{medal} [{title}]{card}: {jrrp} ({fortune})"

                ranks = []
                medals = ["🥇", "🥈", "🥉"]

                display_count = self._get_config("rank_display_count")
                if display_count is None:
                    display_count = 10
                display_list = sorted_fortunes if display_count == -1 else sorted_fortunes[:display_count]

                for idx, (_, data) in enumerate(display_list):
                    medal = medals[idx] if idx < 3 else f"{idx+1}."
                    user_info = data.get("user_info", {})

                    # 使用模板生成每一行
                    rank_vars = {
                        'medal': medal,
                        'title': user_info.get('title', ''),
                        'card': user_info.get('card', '未知'),
                        'nickname': user_info.get('nickname', '未知'),
                        'jrrp': data['jrrp'],
                        'fortune': data['fortune'],
                        'femoji': data.get('femoji', ''),
                        'rank': idx + 1
                    }

                    rank_item = self._replace_variables(rank_item_template, rank_vars)
                    ranks.append(rank_item)

                result = rank_template.replace("{date}", today).replace("{ranks}", "\n".join(ranks))

                if display_count != -1 and len(sorted_fortunes) > display_count:
                    result += f"\n\n...共 {len(sorted_fortunes)} 人已测试"

                yield event.plain_result(result)

            except Exception as e:
                logger.error(f"处理人品排行时出错: {e}")
                yield event.plain_result("抱歉，获取排行榜时出现了错误。")

    @filter.command("jrrphistory", alias={"jrrphi"})
    async def fortune_history(self, event: AstrMessageEvent, target: str = ""):
        """查看人品历史"""
        async with _fortune_lock:
            try:
                # 检查插件是否启用
                enable_plugin = self._get_config("enable_plugin")
                if enable_plugin is False:
                    yield event.plain_result("今日人品插件已关闭")
                    return

                # 处理@查询
                target_id = event.get_sender_id()
                target_name = ""

                if target:
                    # 尝试从消息中提取@的用户ID
                    from astrbot.api.message_components import At
                    for msg_comp in event.message_obj.message:
                        if isinstance(msg_comp, At):
                            target_id = str(msg_comp.qq)
                            break

                # 获取目标用户信息
                if target_id == event.get_sender_id():
                    user_info = await self._get_user_info(event)
                    target_name = user_info['card']
                else:
                    target_name = f"用户{target_id[-4:]}"

                history = await self._load_json(self.history_file)

                if target_id not in history:
                    yield event.plain_result(f"【{target_name}】还没有人品测试记录")
                    return

                # 获取历史记录天数
                history_days = self._get_config("history_days")
                if history_days is None:
                    history_days = 30
                cutoff_date = (date.today() - timedelta(days=history_days)).strftime("%Y-%m-%d")

                # 筛选有效记录
                user_history = {k: v for k, v in history[target_id].items() if k >= cutoff_date}

                if not user_history:
                    yield event.plain_result(f"【{target_name}】最近{history_days}天没有人品测试记录")
                    return

                # 计算统计
                all_values = [record["jrrp"] for record in user_history.values()]
                avg_jrrp = sum(all_values) / len(all_values) if all_values else 0
                max_jrrp = max(all_values) if all_values else 0
                min_jrrp = min(all_values) if all_values else 0

                # 准备历史记录
                sorted_history = sorted(user_history.items(), reverse=True)[:10]
                history_items = []

                for date_key, data in sorted_history:
                    history_items.append(f"{date_key}: {data['jrrp']} ({data['fortune']})")

                # 使用历史模板
                history_template = self._get_config("history_template")
                if not history_template:
                    history_template = "📚 {name} 的人品历史记录\n{items}\n\n📊 统计信息:\n平均人品值: {avgjrrp}\n最高人品值: {maxjrrp}\n最低人品值: {minjrrp}"

                # 修复这里：使用正确的变量名
                result = self._replace_variables(history_template, {
                    'name': target_name,
                    'nickname': target_name,  # 添加nickname支持
                    'items': "\n".join(history_items),
                    'avgjrrp': f"{avg_jrrp:.1f}",
                    'maxjrrp': max_jrrp,
                    'minjrrp': min_jrrp
                })

                yield event.plain_result(result)

            except Exception as e:
                logger.error(f"处理人品历史时出错: {e}")
                yield event.plain_result("抱歉，获取历史记录时出现了错误。")

    @filter.command("jrrpdelete", alias={"jrrpdel"})
    async def delete_fortune(self, event: AstrMessageEvent, confirm: str = ""):
        """删除个人数据"""
        async with _fortune_lock:
            try:
                if confirm != "--confirm":
                    yield event.plain_result("⚠️ 此操作将清除你的所有人品数据！\n如果确定要继续，请使用：/jrrpdelete --confirm")
                    return

                user_id = event.get_sender_id()
                user_info = await self._get_user_info(event)
                deleted = False

                # 清除今日人品数据
                fortunes = await self._load_json(self.fortune_file)
                for date_key in list(fortunes.keys()):
                    if user_id in fortunes[date_key]:
                        del fortunes[date_key][user_id]
                        deleted = True
                        if not fortunes[date_key]:
                            del fortunes[date_key]

                if deleted:
                    await self._save_json(self.fortune_file, fortunes)

                # 清除历史记录
                history = await self._load_json(self.history_file)
                if user_id in history:
                    del history[user_id]
                    await self._save_json(self.history_file, history)
                    deleted = True

                if deleted:
                    yield event.plain_result(f"✅ 已清除 {user_info['card']} 的所有人品数据")
                else:
                    yield event.plain_result(f"ℹ️ {user_info['card']} 没有人品数据记录")

            except Exception as e:
                logger.error(f"清除用户数据时出错: {e}")
                yield event.plain_result("抱歉，清除数据时出现了错误。")

    @filter.command("jrrpreset", alias={"jrrpre"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def reset_all_fortune(self, event: AstrMessageEvent, confirm: str = ""):
        """清除所有数据（仅管理员）"""
        async with _fortune_lock:
            try:
                if confirm != "--confirm":
                    yield event.plain_result("⚠️ 警告：此操作将清除所有人品数据！\n如果确定要继续，请使用：/jrrpreset --confirm")
                    return

                for file_path in [self.fortune_file, self.history_file]:
                    if os.path.exists(file_path):
                        os.remove(file_path)

                yield event.plain_result("✅ 所有人品数据已清除")
                logger.info(f"Admin {event.get_sender_id()} reset all fortune data")

            except Exception as e:
                yield event.plain_result(f"❌ 清除数据时出错: {str(e)}")

    async def terminate(self):
        """插件卸载时调用"""
        try:
            # 删除配置文件
            config_file = os.path.join("data", "config", "astrbot_plugin_daily_fortune1_config.json")
            if os.path.exists(config_file):
                os.remove(config_file)
                logger.info(f"Removed config file: {config_file}")

            # 删除数据目录
            if os.path.exists(self.data_dir):
                import shutil
                shutil.rmtree(self.data_dir)
                logger.info(f"Removed data directory: {self.data_dir}")

        except Exception as e:
            logger.error(f"Error during plugin termination: {e}")

        logger.info("今日人品插件已卸载")
