# AstrBot 每日人品插件 (Daily Fortune)

[![version](https://img.shields.io/badge/version-0.0.7-blue.svg)](https://github.com/xSapientia/astrbot_plugin_daily_fortune1)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/xSapientia/astrbot_plugin_daily_fortune1/blob/main/LICENSE)
[![platform](https://img.shields.io/badge/AstrBot-%3E%3D3.4.0-orange.svg)](https://github.com/AstrBotDevs/AstrBot)

一款功能强大、高度可配置的每日人品值和运势查询插件，为你的 AstrBot 添加趣味性互动！

## ✨ 功能特性

- 🎲 **每日人品值**：每个用户每天只能随机一次人品值（0-100）。
- 🔮 **智能运势解读**：通过 LLM 生成个性化的运势解读和建议。
- 📊 **排行榜系统**：查看群内成员的今日人品排名。
- 📚 **历史记录**：查看个人人品值历史统计（最高、最低、平均）。
- 👥 **查询他人**：支持通过 `@某人` 查询其当日人品值结果，此过程不消耗 LLM。
- ⚙️ **高度可配置**：
  - **多种算法**：内置多种人品值计算算法（哈希、纯随机、正态分布等）。
  - **自定义模板**：所有返回的文本消息都支持模板自定义。
  - **自定义运势**：人品值分段、运势名称、对应的Emoji表情均可自由配置。
- 🎯 **精准识别**：可与 `astrbot_plugin_rawmessage_viewer1` 插件集成，获取用户详细信息（如群名片、头衔）并在模板和 Prompt 中使用。
- 🔧 **数据管理**：提供指令用于删除个人或重置所有数据。

## 📦 安装方法

1.  确保你的 AstrBot 版本 `>= 3.4.0`。
2.  在 AstrBot 管理面板的插件市场搜索 `daily_fortune`。
3.  点击安装即可。插件依赖的 `numpy` 和 `aiohttp` 库将会自动安装。

## 🚀 使用指令

### 基础指令

-   `/jrrp`
    -   查询自己的今日人品值。
    -   首次查询会调用 LLM 生成个性化运势解读。
    -   再次查询会显示缓存结果。
-   `/jrrp @某人`
    -   查询他人的今日人品值。
    -   如果对方未查询，会显示提示信息。
    -   如果对方已查询，会显示其查询结果（此过程**不调用LLM**）。

### 排行榜

-   `/jrrprank`
    -   查看当前群聊内今日人品排行榜（仅群聊可用）。

### 历史记录

-   `/jrrphistory` 或 `/jrrphi`
    -   查看个人历史记录（默认最近30天）。
    -   支持通过 `@某人` 查看他人的历史记录。

### 数据管理

-   `/jrrpdelete` 或 `/jrrpdel`
    -   删除**个人**的所有历史人品值数据。
    -   需要加 `--confirm` 参数确认，例如：`/jrrpdelete --confirm`。
-   `/jrrpreset` 或 `/jrrpre`
    -   **[仅管理员]** 删除**所有用户**的人品数据，重置插件。
    -   需要加 `--confirm` 参数确认，例如：`/jrrpreset --confirm`。

## 🛠️ 配置说明

插件提供了丰富的配置项，您可以在 `管理面板` -> `插件市场` -> `已安装` -> `astrbot_plugin_daily_fortune1` -> `管理` -> `配置` 中进行修改。

### 核心配置

-   `jrrp_algorithm`：人品值计算算法。
    -   `hash` (默认): 基于用户ID和日期的哈希算法，结果固定。
    -   `random`: 纯随机。
    -   `normal`: 正态分布算法（中间值概率高）。
    -   `lucky`: 幸运算法（高分值概率高）。
    -   `challenge`: 挑战算法（极端值概率高）。
-   `history_days`：历史记录保存和计算的天数。

### 运势等级配置

您可以完全自定义运势等级，三个配置项需一一对应。

-   `jrrp_ranges`：人品值分段，格式为 `[ 0-1, 2-10, ...]`。
-   `fortune_names`：运势名称列表，如 `["极凶", "大凶", ...]`。
-   `fortune_emojis`：运势表情列表，如 `["💀", "😨", ...]`。

### 显示与模板配置

-   `detecting_message`：首次查询时的“检测中”提示文本。
-   `show_cached_result`：再次查询自己时，是否显示首次生成的完整结果。
-   `show_others_cached_result`：@查询他人时，是否显示对方首次生成的完整结果。
-   `others_not_queried_message`：@查询他人但对方未查询时的提示信息，支持所有模板变量。
-   `templates`：包含 `random`、`query`、`rank`、`board`、`history` 等多个模板，您可以自定义所有场景下的返回消息格式。

### LLM与人格配置

-   `llm_provider_id`：指定一个LLM服务商ID，留空则使用AstrBot默认。
-   `llm_api`：如果不想使用AstrBot内置服务，可在此配置兼容OpenAI的第三方API。
-   `persona_name`：指定使用的人格，留空则使用AstrBot默认人格。
-   `prompts`：自定义调用LLM时的 `process` (过程模拟) 和 `advice` (评语) 的Prompt。

## 🔄 更新日志

-   **v0.0.7** (2025-07-24)
    -   **【新增】** 新增运势等级映射的插件配置，用户可完全自定义人品值分段、运势名称和Emoji。
-   **v0.0.6** (2025-07-24)
    -   **【新增】** 新增了@查询功能的开关和模板配置。
    -   **【优化】** `others_not_queried_message` 模板现在支持所有变量。
-   **v0.0.5** (2025-07-24)
    -   **【新增】** 新增 `/jrrp @用户` 功能，用于查询他人的人品值结果。
    -   **【优化】** 确保了@查询功能全过程不调用LLM。
    -   **【修复】** 修复了特定情况下LLM Provider无法使用的问题，增强了Provider调用的稳定性。
-   **v0.0.4** (2025-07-23)
    -   **【修复】** 修复了多用户同时使用时，LLM生成内容的用户昵称混乱的严重BUG。
    -   **【优化】** 改进了用户信息获取逻辑，并显式将用户昵称传递给LLM以避免混淆。
-   **v0.0.3** (2025-07-23)
    -   **【新增】** 新增 `normal` (正态分布), `lucky` (幸运) 和 `challenge` (挑战) 三种人品值算法。
    -   **【新增】** 插件加载时会输出LLM服务和人格的连接与加载信息。
    -   **【修复】** 修复了部分LLM模型因不支持`system_prompt`而报错的问题。
    -   **【修复】** 修复了首次使用时可能发生的 `KeyError`。
-   **v0.0.2** (2025-07-23)
    -   **【修复】** 修复了因 `BaseProvider` 导入错误导致的插件加载失败问题。
-   **v0.0.1** (2025-07-23)
    -   **【新增】** 插件首次发布，实现核心功能。

## 💡 反馈与建议

如果您在使用过程中遇到任何问题或有好的建议，欢迎提交 Issue：
https://github.com/xSapientia/astrbot_plugin_daily_fortune1/issues
