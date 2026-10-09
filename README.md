# AI Systems Inbox

[打开只读站点](https://dong1017.github.io/ai-systems-inbox/) · [发布运行记录](https://github.com/Dong1017/ai-systems-inbox/actions/workflows/pages.yml)

## 当前采用的简单流程

**ChatGPT 生成论文分析 → 直接提交一个公开 JSON 文件 → GitHub Actions 校验并发布网站。**

手机和电脑只需打开网址。不增加数据库、登录、模型提供商账号或 API Key。

- 只有现有 ChatGPT 每日任务负责定时生成。GitHub workflow 不再包含 cron，不再采集论文或调用 Gemini。
- 每期文件写入 `data/digests/YYYY-MM-DD.json`。Actions 用 `scripts/build_site.py` 汇总成网页读取的 `site/digests.json`，校验后发布，并比较线上 JSON 的 SHA-256。
- Actions 没有仓库写权限，不会反过来改动已提交的正文；不再读取模型 Secrets。旧采集/模型脚本暂留作历史实现，不在当前工作流中调用。
- **当前会话直接提交已执行；后台排程能否执行同样的 GitHub 写入，仍须独立验收。** 不用“任务有运行记录”代替 commit，不用 HTTP 200 代替本期内容已上线。
- 原 ChatGPT 每日任务的时间不变，已加入直接提交与发布状态检查的指令。写入不可用或需要审批时必须如实报告，不绕过平台权限，也不静默改用付费 API。

## 首期内容的边界

`data/digests/2026-10-09.json` 转存此前会话中 7 篇公开论文分析。原简报只覆盖 new/cross-list，修订列表未补齐；本次 arXiv 读取存在陈旧缓存和无法访问的论文页，因此这是 **待核验会话转存**，不是新一轮完整官方 batch 核验。

机构、版本及代码断言没有沿用为已验证字段。历史技术解读与数字保留出处限制；每篇详情均说明本次未复核、未独立复现。没有复制私人聊天、笔记、账号信息或私有项目资料。

`complete:false` 的内容可以在站点阅读，但 **不推进完整批次进度**。后续补齐该日完整官方条目和来源核验后，才可更新同一文件为 `complete:true`。这不是允许普通定时任务跳过核验、发布不实数据的规则。

## 每日提交约定

只在最新官方 batch 尚未完整写入时生成；来源日期、分区总数或页面完整性无法确认时应报错，不拿旧论文补数量。网站状态来自仓库文件，不来自聊天里的固定 watermark。

每个文件必须是一个 UTF-8 JSON 对象，且文件名与 `listing_date` 一致。

| 字段 | 含义 |
|---|---|
| `listing_date` | arXiv 官方批次日期；历史转存保留原记录日期并说明范围。 |
| `published_at` | 本次内容生成/转存时间，含时区；不代表部署成功时间。 |
| `source_count` | 本期核验范围的来源条目数；部分转存不得冒充完整总数。 |
| `complete` | 必须显式填布尔值；只有完成全批核验才能为 `true`。 |
| `signal_title`, `signal` | 本期标题、主要系统信号与必要的证据范围说明。 |
| `mind_model` | 一条因果链或系统自检问题。 |
| `papers` | 按相关性排序的论文条目，通常 3–6 篇标为优先阅读。 |

每篇字段：`arxiv_id`、`version`、`status`、`title`、`summary`、`tags`、`read_now`、`institution`、`code_url`、`systems_problem`、`mapping`、`evidence`、`sources`。

`status` 为 `new` / `cross-list` / `revised`。版本未知留空；机构无一手证据填 `Unknown`；代码未确认填 `null`。来源为 `[{"label":"来源/章节说明","url":"https://..."}]`，必须含与编号对应的 arXiv 地址，不使用 ChatGPT 内部引用标记。工程映射标为推断，数据结论须给适用条件和原文证据。

创建前读取目标文件；更新已有文件必须使用最新 blob SHA，不强推覆盖。已完整提交的日期不重复生成。发布失败只重试发布；明确区分“正文已生成”“文件已提交”“网页已发布”。

## 构建和测试

```sh
python3 -m pip install -r requirements-pipeline.txt
python3 -m unittest discover -s tests -v
python3 scripts/build_site.py
python3 scripts/validate_site.py
```

`build_site.py` 只读取已提交的公开 JSON，不联网、不调用模型。网页发布目录仍限 `site/index.html` 和 `site/digests.json`。新增回归测试覆盖直接构建、日期一致性、私人字段拒绝，以及不完整记录不得推进已完成游标。

程序可以检查格式、链接与文件边界，不能证明科学结论真实，也不能自动识别所有自由文本中的私人信息。访问凭据、历史 ZIP、个人数据库、笔记、`.env`、`auth.json` 和完整会话均不得公开。

## 排程与权限验收

用户无需为当前发布路径配置 Gemini 或其他模型 API。交互式提交成功不等于后台自动写入成功；只有无人操作的排程产生可验证 commit，并触发网站部署和内容检查，才能报告无人值守链路通过。

当前站点为公开只读，没有收藏、笔记写入或用户登录接口。
