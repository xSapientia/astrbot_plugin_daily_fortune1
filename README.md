# AstrBot 每日人品插件 (Daily Fortune)

[![version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/xSapientia/astrbot_plugin_daily_fortune1)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/xSapientia/astrbot_plugin_daily_fortune1/blob/main/LICENSE)
[![platform](https://img.shields.io/badge/AstrBot-%3E%3D3.4.0-orange.svg)](https://github.com/AstrBotDevs/AstrBot)

一款功能强大、高度可配置的每日人品值和运势查询插件，为你的 AstrBot 添加趣味性互动！

## ✨ 功能特性

- 🎲 **每日人品值**：每个用户每天只能随机一次人品值（0-100）。
- 🔮 **智能运势解读**：通过 LLM 生成个性化的运势解读和建议。
- 📊 **排行榜系统**：查看群内成员的今日人品排名。
- 📚 **历史记录**：查看个人人品值历史统计（最高、最低、平均）。
- 👥 **查询他人**：支持通过 `@某人` 查询其当日人品值结果，此过程不消耗 LLM。
- 📖 **内置帮助**：通过 `/jrrp help` 查看所有可用指令。
- ⚙️ **高度可配置**：
  - **多种算法**：内置多种人品值计算算法（哈希、纯随机、正态分布等）。
  - **自定义模板**：所有返回的文本消息都支持模板自定义。
  - **自定义运势**：人品值分段、运势名称、对应的Emoji表情均可自由配置。
  - **自定义奖牌**：排行榜奖牌系统支持自定义配置。
- 🎯 **精准识别**：可与 `astrbot_plugin_rawmessage_viewer1` 插件集成，获取用户详细信息（如群名片、头衔）并在模板和 Prompt 中使用。
- 🔧 **数据管理**：提供多种数据管理指令，支持精细化的权限控制。

## 📦 安装方法

1.  确保你的 AstrBot 版本 `>= 3.4.0`。
2.  在 AstrBot 管理面板的插件市场搜索 `daily_fortune`。
3.  点击安装即可。插件依赖的 `numpy` 和 `aiohttp` 库将会自动安装。

## 🚀 使用指令

### 基础指令

#### 查询人品值
- **查询自己的今日人品值**
  - `jrrp`
- **查询他人的今日人品值**
  - `jrrp @某人`
- **显示帮助信息**
  - `jrrp help`

### 排行榜

#### 查看群内今日人品排行榜
- `jrrp rank`
- `jrrprank`

### 历史记录

#### 查看历史记录
- `jrrp history`
- `jrrp hi`
- `jrrphistory`
- `jrrphi`

#### 查看他人历史记录
- `jrrp history @某人`
- `jrrphistory @某人`

### 数据管理

#### 删除除今日外的历史记录
- `jrrp delete --confirm`
- `jrrp del --confirm`
- `jrrpdelete --confirm`
- `jrrpdel --confirm`

### 管理员指令

#### 初始化今日记录
- `jrrp init --confirm`
- `jrrp initialize --confirm`
- `jrrpinit --confirm`
- `jrrpinitialize --confirm`

#### 重置所有数据
- `jrrp reset --confirm`
- `jrrp re --confirm`
- `jrrpreset --confirm`
- `jrrpre --confirm`

## 🛠️ 配置说明

插件提供了丰富的配置项，您可以在 `管理面板` -> `插件市场` -> `已安装` -> `astrbot_plugin_daily_fortune1` -> `管理` -> `配置` 中进行修改。

### 核心配置

-   `jrrp_algorithm`：人品值计算算法。
    -   `hash`: 基于用户ID和日期的哈希算法，结果固定。
    -   `random`: 纯随机。
    -   `normal`: 正态分布算法（中间值概率高）。
    -   `lucky`: 幸运算法（高分值概率高）。
    -   `challenge`: 挑战算法（极端值概率高）。
-   `history_days`：历史记录保存和计算的天数。

### 运势等级配置

您可以完全自定义运势等级，所有配置项均为字符串格式，使用逗号分隔。

-   `jrrp_ranges`：人品值分段，格式为 `0-1, 2-10, 11-20, ...`。
-   `fortune_names`：运势名称列表，如 `极凶, 大凶, 凶, ...`。
-   `fortune_emojis`：运势表情列表，如 `💀, 😨, 😰, ...`。
-   `medals`：排行榜奖牌列表，如 `🥇, 🥈, 🥉, 🏅, 🏅`。

### 显示与模板配置

-   `detecting_message`：首次查询时的"开始检测"提示文本。
-   `processing_message`：重复调用时的"正在检测中"提示文本。
-   `show_cached_result`：再次查询自己时，是否显示首次生成的完整结果。
-   `show_others_cached_result`：@查询他人时，是否显示对方首次生成的完整结果。
-   `others_not_queried_message`：@查询他人但对方未查询时的提示信息，支持所有模板变量。
-   `templates`：包含 `random`、`query`、`rank`、`board`、`history` 等多个模板，您可以自定义所有场景下的返回消息格式。

### LLM与人格配置

-   `llm_provider_id`：指定一个LLM服务商ID，留空则使用AstrBot默认。
-   `llm_api`：如果不想使用AstrBot内置服务，可在此配置兼容OpenAI的第三方API。
-   `persona_name`：指定使用的人格，留空则使用AstrBot默认人格。
-   `prompts`：自定义调用LLM时的 `process` (过程模拟) 和 `advice` (评语) 的Prompt。

### 支持的模板变量

在模板和提示词中可以使用以下变量：
- **基础变量**：`{nickname}`, `{card}`, `{title}`, `{jrrp}`, `{fortune}`, `{femoji}`, `{date}`
- **配置变量**：`{jrrp_ranges}`, `{fortune_names}`, `{fortune_emojis}`, `{medals}`
- **统计变量**：`{avgjrrp}`, `{maxjrrp}`, `{minjrrp}`
- **特殊变量**：`{target_nickname}`, `{target_user_id}`, `{sender_nickname}` (仅在特定场景)

## 🔄 更新日志

-   **v0.1.0** (2025-07-26)
    -   **【调整】** 移除 `jrrpdelete` 中@他人的功能，现在只能删除自己的数据。
    -   **【新增】** 添加防止重复调用机制，在生成结果期间再次调用会显示"正在检测中"消息。
    -   **【新增】** 新增 `processing_message` 配置项，支持自定义"正在检测中"提示文本。

-   **v0.0.9** (2025-07-25)
    -   **【修复】** 子指令无效传参的问题。
    -   **【修复】** 所有算法的随机种子被写死的问题。

-   **v0.0.8** (2025-07-23)
    -   **【新增】** 运势等级映射配置改为字符串格式，使用更加直观。
    -   **【新增】** 添加排行榜奖牌(`medals`)的字符串配置，支持自定义奖牌样式。
    -   **【新增】** 在模板和提示词中添加 `{jrrp_ranges}`, `{fortune_names}`, `{fortune_emojis}`, `{medals}` 变量支持。
    -   **【新增】** 新增 `/jrrpinitialize` (`/jrrpinit`) 指令，管理员可初始化任意用户的今日记录。
    -   **【新增】** 添加 `/jrrp help` 指令，显示所有可用指令的详细帮助信息。
    -   **【新增】** 支持空格分隔的指令别名：
        - `/jrrp rank` 对应 `/jrrprank`
        - `/jrrp history` 和 `/jrrp hi` 对应 `/jrrphistory` 和 `/jrrphi`
        - `/jrrp delete` 和 `/jrrp del` 对应 `/jrrpdelete` 和 `/jrrpdel`
        - `/jrrp init` 和 `/jrrp initialize` 对应 `/jrrpinit` 和 `/jrrpinitialize`
        - `/jrrp reset` 和 `/jrrp re` 对应 `/jrrpreset` 和 `/jrrpre`
    -   **【优化】** `jrrphistory`/`jrrphi` 现在支持查询自己和@对象的历史数据统计。
    -   **【调整】** `jrrpdelete`/`jrrpdel` 功能重新设计：
        -   现在删除除今日以外的所有历史记录。
        -   所有人都可以删除自己的数据。
        -   删除他人数据需要管理员权限。
    -   **【修复】** 修复了 `jrrpreset`/`jrrpre` 和 `jrrpinit`/`jrrpinitialize` 没有重置随机种子的问题。
    -   **【优化】** 改进了权限控制系统，使功能划分更加合理。

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

## 💡 使用技巧

1. **多种指令格式**：插件支持多种指令格式，您可以选择最习惯的方式使用。
2. **权限管理**：普通用户只能管理自己的数据，管理员可以管理所有用户的数据。
3. **模板自定义**：通过配置文件可以完全自定义所有输出文本的格式。
4. **变量丰富**：模板中支持大量变量，可以创建个性化的显示效果。
5. **算法选择**：根据群聊氛围选择合适的人品值算法，增加趣味性。

## 🔗 与其他插件的集成

本插件可以与以下插件集成以获得更好的体验：

- **`astrbot_plugin_rawmessage_viewer1`**：获取更详细的用户信息（群名片、群头衔等）

## ⚠️ 注意事项

1. **人品值唯一性**：每个用户每天只能随机一次人品值，结果会被缓存。
2. **LLM依赖**：首次查询需要调用LLM生成运势解读，请确保LLM服务正常。
3. **权限控制**：删除他人数据和初始化功能需要管理员权限。
4. **数据持久化**：插件数据存储在 `data/plugin_data/astrbot_plugin_daily_fortune1/` 目录下。
5. **随机种子**：重置和初始化操作会重置随机种子，确保随机性。

## 💡 反馈与建议

如果您在使用过程中遇到任何问题或有好的建议，欢迎提交 Issue：
https://github.com/xSapientia/astrbot_plugin_daily_fortune1/issues

---

**感谢使用 AstrBot 每日人品插件！祝您每天都有好运气！** 🍀
