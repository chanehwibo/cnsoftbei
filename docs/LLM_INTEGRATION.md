# 大模型接入

## 1. 职责

LLM 只执行意图理解：

- 从已注册工具中选择一个候选；
- 提取对象参数；
- 返回一句话工具选择说明；
- 参数不足时返回 clarification。

PolicyEngine 独立完成工具存在性、Schema、注入、敏感路径、服务边界、风险等级和确认裁决。模型没有授权能力。

## 2. 配置

复制私密配置模板：

~~~powershell
Copy-Item config\llm.local.yaml.example config\llm.local.yaml
~~~

在新文件中设置 `llm_api_key`。也可以设置 `LLM_API_KEY`，环境变量优先。`config/llm.local.yaml` 已从 Git 和发布包排除。

公共配置：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `llm_enabled` | true | Provider 总开关 |
| `llm_provider` | deepseek | 支持 `deepseek`、`openai-compatible`（也接受 `openai`） |
| `llm_model` | deepseek-chat | 请求模型名 |
| `llm_base_url` | https://api.deepseek.com/v1 | OpenAI 兼容基址 |
| `llm_timeout` | 8 | 秒级超时 |
| `llm_rule_fast_path` | false | true 时先用高置信本地规则 |

配置使用标准 YAML，并由 `python -m safeops_agent.config_check` 校验。

## 3. 离线模式

以下任一条件使用 RuleBasedProvider：

- `SAFEOPS_LLM_DISABLED=1`；
- `llm_enabled: false`；
- API Key 为空；
- Provider 名称不受支持。

调用超时、网络错误、响应不是合法 JSON、模型返回未知工具时，当前请求自动回退本地路由。回退原因进入工具选择步骤。

## 4. 输出契约

模型响应内容是 JSON 对象：

~~~json
{
  "tool": "system.resources",
  "args": {},
  "reasoning": "用户询问当前主机负载",
  "clarification": null
}
~~~

`reasoning` 是面向用户的一句话选择说明，不是隐藏思维过程。系统会截断并过滤该文本。`reasoning_chain` 是历史兼容字段名，内容是本地代码生成的结构化决策事实。

## 5. 安全顺序

~~~text
输入高危筛查
  -> 模型选择候选工具
  -> 模型文本输出护栏
  -> 注册表与参数校验
  -> 风险/服务策略
  -> 令牌确认或执行
  -> 脱敏签名审计
~~~

模型调用使用低温度、JSON response_format、512 token 上限和八秒超时。

## 6. 验证

离线确定性验证：

~~~powershell
$env:SAFEOPS_LLM_DISABLED='1'
python -m unittest tests.test_llm tests.test_reasoning_chain -v
~~~

在线人工验证：

~~~powershell
Remove-Item Env:SAFEOPS_LLM_DISABLED -ErrorAction SilentlyContinue
python -m safeops_agent.cli "帮我看看这台机器现在忙不忙" --json
~~~

工具选择步骤的 `source=llm` 表示模型响应被采用；后续仍必须通过本地策略。
