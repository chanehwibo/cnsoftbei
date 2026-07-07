# 大模型接入说明

## 1. 架构

```text
用户自然语言
   |
意图风险筛查（护栏第一层，LLM 之前）
   |
LLM 意图理解（DeepSeekProvider，OpenAI 兼容接口）
   |  失败/超时/未启用 → 自动回退规则关键词匹配（RuleBasedProvider）
   |
输出侧护栏（clarification/reasoning 截断 + 高危内容屏蔽）
   |
风险裁决（护栏第二层：等级 + 参数校验 + 确认令牌）
   |
工具执行 + 思维链审计
```

关键设计：**LLM 只负责"理解"，不负责"放行"**。模型输出的工具与参数仍要经过
完整的策略裁决；模型宕机、超时、返回垃圾时系统自动降级为规则匹配，功能不中断。

## 2. API Key 配置

1. 复制 `config/llm.local.yaml.example` 为 `config/llm.local.yaml`；
2. 填入 API Key（该文件已被 .gitignore 排除，不会进入仓库）；
3. 也可用环境变量 `LLM_API_KEY` 传入（优先级高于配置文件）。

`config/llm.yaml` 公共配置项：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `llm_enabled` | true | 总开关；false 时始终使用规则匹配 |
| `llm_provider` | deepseek | 目前支持 deepseek（OpenAI 兼容格式，可扩展） |
| `llm_model` | deepseek-v4-pro | 模型名 |
| `llm_base_url` | https://api.deepseek.com/v1 | API 地址 |
| `llm_timeout` | 8 | 请求超时（秒）；超时即回退规则，不阻塞交互 |
| `llm_rule_fast_path` | false | true 时高置信关键词先走本地规则（0 延迟），未命中再请求 LLM |

## 3. 离线模式

以下任一条件成立即进入离线规则模式：

- 环境变量 `SAFEOPS_LLM_DISABLED=1`（测试、CI、无网络演示的推荐方式）；
- `llm_enabled: false`；
- 未配置 API Key。

单元测试与 CI 均在离线模式下运行，保证确定性且不产生 API 费用；
需要测 LLM 相关逻辑时使用 mock（见 `tests/test_llm.py`）。

## 4. 安全边界

- **输入侧**：高危请求在进入 LLM 之前就被意图筛查拦截；
- **输出侧**：模型返回的 `clarification`/`reasoning` 会展示给运维人员并写入审计，
  因此与用户输入过同一套高危筛查，命中即屏蔽（防提示注入借模型之口诱导操作）；
- **参数**：模型提取的参数经命令注入字符、敏感路径、标识符白名单校验；
- **裁决**：工具风险等级与确认要求由本地策略决定，模型无权改变；
- **审计**：意图来源（llm/rule）、模型推理文本、回退原因全部落审计日志。

## 5. 失败降级行为

| 场景 | 行为 | 思维链中的可见性 |
| --- | --- | --- |
| API 超时/网络错误 | 回退规则匹配 | tool_selection 步骤记录"LLM 调用失败，已自动回退规则匹配" |
| 响应非法 JSON | 回退规则匹配 | 记录"LLM 响应解析失败" |
| 返回未注册工具 | 回退规则匹配 | 记录"LLM 返回未知工具: xxx" |
| 缺少必填参数 | 向用户追问（clarification） | tool_selection 记录追问内容 |

Web 服务启动时会打印当前 Provider 自检信息（模型、超时、回退策略），
避免配置错误导致的静默降级难以察觉。
