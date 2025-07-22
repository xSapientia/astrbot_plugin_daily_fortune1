# astrbot_plugin_daily_fortune1

全新重构的今日人品测试插件，支持高度自定义和模板系统。

## ✨ 核心特性

- 🎯 **变量系统** - 支持 {nickname}、{card}、{title}、{jrrp} 等丰富变量
- 📝 **模板系统** - 所有输出都可通过模板自定义
- 🤖 **灵活的LLM配置** - 支持使用AstrBot配置或自定义API
- 👤 **人格系统** - 占卜师可以有不同的人格
- 💾 **智能缓存** - 支持配置缓存天数
- 📊 **全局数据** - 私聊群聊共享人品值

## 🎮 使用指令

| 指令 | 别名 | 说明 |
|------|------|------|
| `/jrrp` | `-jrrp` | 测试/查询今日人品 |
| `/jrrprank` | - | 查看群内人品排行榜 |
| `/jrrphistory` | `/jrrphi` | 查看人品历史（支持@查询他人） |
| `/jrrpdelete` | `/jrrpdel` | 删除个人数据（需--confirm） |
| `/jrrpreset` | `/jrrpre` | 删除所有数据（管理员，需--confirm） |

## 🔧 配置说明

### 基础配置
- `enable_plugin` - 插件开关
- `detecting_message` - 检测中的提示消息
- `result_cache_days` - 结果缓存天数
- `show_cached_result` - 查询时是否显示缓存

### 模板配置
- `random_template` - 首次测试的结果模板
- `query_template` - 查询时的结果模板
- `rank_template` - 排行榜模板
- `history_template` - 历史记录模板

### LLM配置
- `llm_provider_id` - 使用AstrBot中的provider
- `llm_api_key/url/model` - 自定义LLM配置
- `persona_name` - 占卜师人格

### 提示词配置
- `process_prompt/template` - 过程描述生成
- `advice_prompt/template` - 评语建议生成

## 📊 运势等级

| 人品值 | 运势 | 表情 |
|--------|------|------|
| 0-10 | 大凶 | 😱 |
| 11-30 | 凶 | 😰 |
| 31-50 | 末吉 | 😐 |
| 51-70 | 吉 | 😊 |
| 71-90 | 中吉 | 😄 |
| 91-99 | 大吉 | 🎉 |
| 100 | 神吉 | 🌟 |

## 🎨 变量列表

- `{nickname}` - 用户昵称
- `{card}` - 群昵称
- `{title}` - 群头衔
- `{jrrp}` - 人品值
- `{fortune}` - 运势文字
- `{femoji}` - 运势表情
- `{process}` - 过程描述
- `{advice}` - 评语建议
- `{avgjrrp}` - 平均人品值
- `{maxjrrp}` - 最高人品值
- `{minjrrp}` - 最低人品值

## 📝 更新日志

### v0.0.1 (2024-12-27)
- 全新重构，从零开始
- 实现变量系统和模板系统
- 支持灵活的LLM配置
- 优化代码结构，提高效率

---

作者：xSapientia
