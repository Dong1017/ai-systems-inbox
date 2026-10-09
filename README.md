# AI Systems Inbox

[打开只读站点](https://dong1017.github.io/ai-systems-inbox/) · [查看更新任务](https://github.com/Dong1017/ai-systems-inbox/actions/workflows/pages.yml)

面向 AI 系统工程的论文简报。手机和电脑直接浏览，不需要安装程序。保留论文卡片、搜索、方向筛选、来源和日期归档；不增加数据库、登录或推荐系统。

## 自动更新流程

一个工作流 **Update and publish Inbox** 负责：

`官方 cs.DC 批次 → 完整性检查 → 中文整理（需授权）→ 保存结果 → Pages 发布 → 校验线上数据哈希`

计划在上海时间每天 **10:17 和 14:17** 检查，第二次用于上游延迟和失败补查。实际启动可能延迟。没有新批次时不调用模型；不回填更早批次凑数量。也支持 Actions 中手动运行。

**模型默认关闭。** 采集和状态发布无需模型密钥；没有模型授权时，页面显示已检查的官方日期与条目数、`waiting_model`，不把原文摘要或旧聊天摘要当作完整中文简报。

现有 ChatGPT 论文排程没有因这次代码更新而被关闭或修改。站点更新不依赖复制 ChatGPT 会话。

## 一次性启用中文整理（可选）

已准备原生 Gemini API 适配，固定使用 `gemini-2.5-flash`，没有付费备用服务，也不使用 ChatGPT/Codex 登录凭据。

Google 的 [价格页](https://ai.google.dev/gemini-api/docs/pricing)列出该模型的免费层，但仍需要本人创建 API Key。**请在 Google AI Studio 确认项目是免费层、没有启用付费调用；脚本不能检查或改变你的计费状态。** 免费额度、地区资格和模型可用性以提供商账户为准。

选择使用这一通道后，在仓库 **Settings → Secrets and variables → Actions** 设置：

| 类型 | 名称 | 值 |
|---|---|---|
| Repository secret | `INBOX_GEMINI_API_KEY` | 你在 [Google AI Studio](https://aistudio.google.com/apikey) 创建的密钥。不要发进聊天或写入代码。 |
| Repository variable | `INBOX_GENERATION_ENABLED` | `true`，表示授权定时任务把公开论文材料发送给该模型。 |

两项同时存在才会调用。删除密钥或把变量改为 `false` 可停用生成，已完成的历史简报保留。模型接口只收到公开论文文本及公开分析，不发送私人笔记、会话、登录信息。Google 免费层的输入输出可能用于改进产品，详见官方价格与数据条款。

设置后等待下次检查，或手动运行一次 **Update and publish Inbox**。首次真实模型生成、批次校验、部署哈希校验都通过后，才能算完整链路通过验收；代码和模拟测试通过不等于模型已实测。

## 失败与进度

- 官方 `new` 和 `recent` 日期不一致、总数/分区不完整、页面超过 7 天或日期倒退：拒绝生成，保留旧简报并公布错误状态。
- 按 arXiv 编号去重；只在来源明确时记录版本，未知版本留空，不猜测 v1。
- 只有本批全部条目完成筛选和整理、整体信号生成成功、数据验证通过，才追加一个完整简报。
- 经验证的分组结果保存在 `data/generation-cache.json`，后续运行可接着生成。这里仅含公开论文的 AI 分析，不含密钥。
- 每组最多 6 篇；每轮最多 12 次模型请求，每个 UTC 日记录上限 20 次，串行请求。额度不足不发布半份简报，不自动切换收费服务。上游实际配额可能更低。
- 请求计数是应用侧保护措施，不是提供商账单的硬预算；强制取消运行、提交失败或人工重置缓存可能使未提交计数丢失。免费使用必须同时由提供商的免费项目约束。
- 生成后直接由同一个 workflow 发布，不依赖机器人提交再次触发工作流。并发运行串行化；不强制推送覆盖其他人的修改。
- 公网检查比较本次 `digests.json` 的 SHA-256，不能用旧页面的 HTTP 200 冒充新内容发布成功。
- 采集/生成错误仍会部署诊断状态和上一期内容，然后将工作流标为失败；缺少授权/达到额度则显示明确警告。不可恢复的测试、配置或发布错误由 Actions 保留失败日志。

`pipeline.latest_generated_date` 是最新完整内容日期。旧字段 `published_at` 保存内容生成时间；实际部署是否成功以 Actions 和公网哈希检查为准，页面不会据生成时间声称已部署。

## 证据边界

每篇论文保留官方编号、标题、状态、来源和中文分析。模型不能修改编号或标题。程序要求主要机制的短引文能在提供的原文中找到；机构需原文支持，否则 `Unknown`；代码地址只能来自论文正文中实际出现的候选链接。

**这些检查不是科学结论的形式化证明。** 代码链接出现在正文不自动证明开源许可证或作者所有权，仍可能需要核验。内容标为 AI 整理、未独立复现；工程映射与作者结论分开。优先阅读按研究方向规则排序，不冒充质量评分。

有明确版本且 HTML 可用时读取正文节选，移除参考文献和图表。其他论文仅用官方摘要并标注材料范围；不声称检查了 PDF 图表、完整实验、真实代码集成或独立复现。历史聊天材料不自动进入公开库。

## 项目结构

```text
site/index.html                 只读页面
site/digests.json               完整简报及最近检查状态
scripts/collect_arxiv.py        串行采集、批次完整性与日期检查
scripts/update_digest.py        增量生成、来源约束、缓存与调用上限
scripts/validate_site.py        公开数据及文件白名单校验
requirements-pipeline.txt       固定解析器依赖
tests/                          离线测试，不使用真实密钥
.github/workflows/pages.yml     定时、生成、保存、部署和公网验证
data/generation-cache.json      运行时创建，仅公开分析检查点
```

本次新增流程的本地 **42 项自动化测试通过**，网页 JavaScript 语法检查通过；真实采集和真实模型调用需要分别查看 Actions 运行结果。测试中的合成论文仅存在于临时目录，绝不作为正式内容发布。

```sh
python3 -m pip install -r requirements-pipeline.txt
python3 -m unittest discover -s tests -v
python3 scripts/validate_site.py
# 不配置生成授权时，只采集并记录状态，不调用模型。
python3 scripts/update_digest.py
```

## 隐私和访问权限

公开仓库只放网站代码、公开论文资料及 AI 分析。网页部署白名单仅 `site/index.html`、`site/digests.json`。不上传历史会话 ZIP、数据库、笔记、反馈、`.env`、访问令牌、`auth.json` 或任何订阅登录凭据。

访客只读；网站无写入接口。收藏、登录、个人笔记暂不属于本阶段。自由文本仍需注意隐私，文件白名单不能自动识别所有敏感内容。

参考：[GitHub 定时事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) · [Pages 工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) · [GitHub Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) · [Gemini API Key](https://ai.google.dev/gemini-api/docs/api-key)
