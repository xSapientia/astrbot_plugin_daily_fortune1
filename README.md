# astrbot_plugin_daily_fortune1

每日人品值查询插件，为 AstrBot 提供趣味的运势测算功能。

## 功能介绍

### 主要功能
- **每日人品查询** - 每个用户每天可以查询一次人品值，获得0-100的数值
- **运势等级** - 根据人品值自动判定运势等级（大凶到大吉）
- **LLM个性化内容** - 使用大语言模型生成占卜过程和个性化建议
- **群内排行榜** - 查看群内成员的人品值排名
- **历史记录** - 查看个人的人品值历史统计
- **数据管理** - 支持删除个人数据或重置全部数据

### 特色功能
- 支持从 `astrbot_plugin_rawmessage_viewer1` 插件获取用户的群名片、头衔等信息
- 高度可配置的模板系统，支持自定义各种提示文本
- 支持多种人品值算法（哈希、随机、种子）
- 结果缓存机制，避免重复调用LLM

## 使用方法

### 基础指令
- `/jrrp` - 查询今日人品值
- `/jrrprank` - 查看群内人品排行榜（仅群聊可用）
- `/jrrphistory` 或 `/jrrphi` - 查看个人历史记录
  - 支持@其他人查看他人记录
- `/jrrpdelete` 或 `/jrrpdel` - 删除个人所有记录
  - 需要加 `--confirm` 参数确认
- `/jrrpreset` 或 `/jrrpre` - 重置所有数据（仅管理员）
  - 需要加 `--confirm` 参数确认

### 配置说明

插件提供了丰富的配置选项，可以在 AstrBot 管理面板中进行配置：

#### 基础配置
- **enable_plugin** - 是否启用插件
- **jrrp_algorithm** - 人品值算法选择
  - `hash` - 基于用户ID和日期的哈希值（默认）
  - `random` - 真随机
  - `seed` - 基于种子的伪随机

#### 数据配置
- **cache_days** - 结果缓存天数
- **history_days** - 历史记录显示天数
- **show_cached_result** - 查询时是否显示缓存的完整结果

#### 模板配置
所有模板都支持以下变量：
- `{nickname}` - 用户昵称
- `{card}` - 群名片
- `{title}` - 群头衔
- `{jrrp}` - 人品值
- `{fortune}` - 运势等级
- `{femoji}` - 运势表情
- `{process}` - 占卜过程
- `{advice}` - 评语建议

#### LLM配置
- **provider_id** - 指定使用的LLM提供商ID
- **persona_name** - 指定使用的人格名称

## 数据存储

插件数据存储在以下位置：
- 缓存数据：`./AstrBot/data/plugin_data/astrbot_plugin_daily_fortune1/`
- 配置文件：`./AstrBot/data/config/astrbot_plugin_daily_fortune1_config.json`

## 注意事项

1. 排行榜功能仅在群聊中可用
2. 管理员指令需要相应权限
3. 首次查询会调用LLM生成内容，可能需要等待几秒
4. 建议配合 `astrbot_plugin_rawmessage_viewer1` 插件使用以获得更好的体验

## 更新日志

### v0.0.1
- 初始版本发布
- 实现基础的人品值查询功能
- 支持LLM生成个性化内容
- 实现排行榜和历史记录功能
