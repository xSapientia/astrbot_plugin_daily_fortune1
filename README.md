# AstrBot Daily Fortune Plugin

每日人品值和运势查询插件，为你的 AstrBot 添加趣味性功能！

## 功能特性

- 🎲 **每日人品值**：每个用户每天只能随机一次人品值（0-100）
- 🔮 **智能运势解读**：通过 LLM 生成个性化的运势解读和建议
- 📊 **排行榜系统**：查看群内成员的今日人品排名
- 📚 **历史记录**：查看个人人品值历史统计
- 🎯 **精准识别**：集成 rawmessage_viewer1 插件，获取用户详细信息
- ⚙️ **高度可配置**：支持自定义模板、提示词、算法等

## 安装方法

1. 确保你的 AstrBot 版本 >= 3.4.0
2. 在 AstrBot 管理面板的插件市场搜索 `daily_fortune`
3. 点击安装即可

## 使用指令

### 基础指令

- `/jrrp` - 查询今日人品值
  - 首次查询会通过 LLM 生成运势解读
  - 再次查询显示缓存结果

### 排行榜

- `/jrrprank` - 查看群内今日人品排行榜（仅群聊可用）

### 历史记录

- `/jrrphistory` 或 `/jrrphi` - 查看个人历史记录
  - 支持 @某人 查看他人记录

### 数据管理

- `/jrrpdelete` 或 `/jrrpdel` - 删除个人数据
  - 需要加 `--confirm` 参数确认

- `/jrrpreset` 或 `/jrrpre` - 重置所有数据（仅管理员）
  - 需要加 `--confirm` 参数确认

## 配置说明

### 算法配置

- `jrrp_algorithm`: 人品值计算算法
  - `hash`: 基于用户ID和日期的哈希算法（推荐）
  - `random`: 纯随机算法
  - `normal`: 正态分布算法（中间值概率高）
  - `lucky`: 幸运算法（高分值概率高）
  - `challenge`: 挑战算法（极端值概率高）

### LLM 配置

- `llm_provider_id`: 使用特定的 LLM 提供商
- `llm_api`: 配置第三方 API
- `persona_name`: 使用特定的人格

### 模板配置

支持自定义各种显示模板，可用变量：
- `{nickname}` - 用户昵称
- `{jrrp}` - 人品值
- `{fortune}` - 运势等级
- `{femoji}` - 运势表情
- 更多变量见配置面板

## 与其他插件的集成

本插件可以与 `astrbot_plugin_rawmessage_viewer1` 插件集成，获取更详细的用户信息：
- 群名片
- 群头衔
- 性别等

## 注意事项

1. 人品值每天只能随机一次，结果会缓存
2. LLM 生成内容有一定延迟，请耐心等待
3. 历史记录默认保留 30 天，可在配置中修改
4. 部分模型可能不支持 system_prompt，插件会自动适配

## 反馈与建议

如有问题或建议，欢迎提交 Issue：
https://github.com/xSapientia/astrbot_plugin_daily_fortune1/issues
