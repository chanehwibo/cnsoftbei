# 安全护栏

## 1. 信任边界

以下输入都按不可信处理：

- 用户自然语言；
- LLM 返回的工具、参数、追问和选择说明；
- CLI、Web 与 MCP 的结构化参数；
- 待确认动作文件；
- 审计文件与锚点；
- 工作目录中的外部配置。

只有注册表中的固定 handler 可以触达操作系统。

## 2. 输入护栏

Agent 在模型调用前执行：

1. 2000 字符输入上限；
2. 高危关键词匹配；
3. 危险动作与敏感路径组合匹配；
4. ASCII 关键词边界检查，避免普通单词子串误报。

命中后返回 HIGH 和明确错误码，不调用模型、不选择工具、不执行 handler。

## 3. 模型输出护栏

模型只返回候选工具、对象参数、一句话选择说明和可选追问。输出文本被截断并通过同一高危意图检查；命中时替换为安全提示。

工具名必须已经注册。参数继续通过 MCP Schema 或策略层校验。模型不能：

- 新增工具；
- 生成任意 Shell；
- 把 MEDIUM 改成 LOW；
- 跳过一次性令牌；
- 修改服务允许或保护列表。

## 4. 参数护栏

除受管文件的 `content` 数据字段外，参数拒绝 `;&|`、反引号、`$<>`、控制字符和换行。服务、软件包和文件名使用白名单字符。

中高风险参数命中敏感路径时拒绝。`file.apply` 的内容不当作命令解析，但文件名必须是单段安全标识符，目标固定在 `data/managed/`。

## 5. 服务权限边界

`service.start`、`service.stop` 和 `service.restart` 必须满足：

- 服务位于 `service_allowlist`；
- 服务不在 `protected_services`；
- 名称通过安全标识符校验；
- 有本会话的一次性确认令牌；
- 确认后策略复核仍允许；
- Linux root 默认拒绝，除非显式设置 `SAFEOPS_ALLOW_ROOT_SERVICE_ACTIONS=1`。

默认保护 auditd、firewalld、iptables、nftables、sshd 和 systemd-logind。handler 不使用 Shell 拼接，固定参数调用 systemctl，并返回前后 active 状态。

## 6. 一次性确认

首次 MEDIUM 请求只保存经裁决的 `tool + args`，同时返回 dry-run 与随机 `action_id`。记录：

- 十分钟过期；
- 绑定入口会话；
- 加密保存并附 HMAC；
- 跨线程、跨进程锁保护；
- 合法消费后删除；
- 错误会话尝试不销毁合法令牌；
- 确认阶段不重新解释自然语言；
- 执行前重新应用最新策略。

CLI、Web 和 MCP 没有布尔确认后门。

## 7. 文件事务

受管文件采用以下顺序：

1. 获取线程与进程锁；
2. 按 UTF-8 字节数检查 64 KiB 上限；
3. 用时间戳和 UUID 创建唯一快照；
4. 原子写入快照；
5. 原子更新快照索引；
6. 原子替换目标；
7. 返回可执行的 rollback 描述。

rollback 同样在锁内原子恢复字节；写入前不存在的目标会被删除。

## 8. Web 边界

- 默认要求认证和 `SAFEOPS_TOKEN`；免认证只允许显式开发模式绑定本机回环地址；
- 非回环监听要求原生 TLS、认证和 `SAFEOPS_TOKEN`；
- 登录生成随机 HttpOnly、SameSite=Strict Cookie；
- 原生 TLS 最低使用 TLS 1.2 并发送 HSTS；
- 原生 TLS 或明确的 HTTPS 反向代理模式为会话 Cookie 增加 Secure；
- API 可用 Bearer Token；
- SSE 不接受查询字符串令牌；
- 请求体最大 64 KiB 且 JSON 根节点必须为对象；
- 单 IP 每分钟限流；
- CSP、frame deny、nosniff 与 Referrer-Policy；
- 每会话独立 Agent 上下文和互斥锁。

## 9. MCP 边界

- 必须完成 initialize/initialized 生命周期；
- JSON-RPC 版本、方法与参数对象严格检查；
- inputSchema 检查必填、类型、范围、枚举、长度、模式和额外字段；
- 工具层拒绝通过 `structuredContent.error_code` 返回；
- MEDIUM 首次调用签发令牌，`safeops.confirm` 执行；
- 每次调用和确认进入统一签名审计。

## 10. 审计边界

写盘前递归脱敏密码、secret、API Key、Authorization、credential、private key、文件内容和确认令牌。字符串中的 `sk-...`、Bearer 和常见 `key=value` 形式也会清洗。

新事件使用 SHA-256 链、HMAC 和持久化锚点；轮转段分别锚定。验证器严格校验旧 SHA 格式并只允许它出现在新签名链头部。密钥文件和全部 `data/` 不进入 Git 或发布包。

## 11. 验证命令

~~~powershell
$env:PYTHONPATH='src'
$env:SAFEOPS_LLM_DISABLED='1'
python -W error::ResourceWarning -m unittest discover -s tests
python -m safeops_agent.cli --verify-audit
powershell -ExecutionPolicy Bypass -File scripts\web-smoke.ps1
~~~
