# AI Systems Inbox

面向 AI 系统工程的只读论文简报站。手机与电脑使用浏览器访问，不需要安装本地后端。

## 当前状态

- 已提交静态阅读页面、公开数据格式、校验脚本和 Pages 发布工作流。
- 支持最新简报、历史日期、搜索、方向筛选、论文详情和来源链接。
- 初始公开数据为空，不将旧聊天摘要或演示论文冒充官方新批次。
- 2026-10-09 首次 Actions 运行：数据校验和网页打包通过；部署在 `Configure Pages` 阶段返回 `Not Found`，需要先启用仓库 Pages。
- **尚未完成：定时采集、完整中文分析的无人值守生成，以及首次公网部署验收。** 当前 workflow 只在内容提交或手动触发时发布，不运行每日生成任务。

[首次运行记录](https://github.com/Dong1017/ai-systems-inbox/actions/runs/37910862246)

仓库创建和网页发布不需要模型 API。本阶段没有接入付费模型、上传订阅登录凭据或修改现有 ChatGPT 排程。

## 首次开启 Pages

1. 打开 [Settings → Pages](https://github.com/Dong1017/ai-systems-inbox/settings/pages)。
2. 在 **Build and deployment → Source** 选择 **GitHub Actions**。
3. 在首次运行页面选择 **Re-run jobs → Re-run failed jobs**，或在 Actions 中手动运行 **Publish Inbox site**。

部署成功后的预期地址：

https://Dong1017.github.io/ai-systems-inbox/

**首次部署成功并检查页面前，不将该地址视为已上线。**

工作流只上传 `site/`，不会上传整个仓库。它使用运行时 `GITHUB_TOKEN` 发布，不需要额外填写部署密钥。默认 `GITHUB_TOKEN` 不负责首次开启 Pages；不要为绕过这一步上传账号凭据。

## 项目内容

```text
site/index.html                  只读响应式界面，无构建依赖
site/digests.json                公开简报数据，当前为空
scripts/validate_site.py         数据格式与发布文件白名单校验
tests/test_public_export.py      12 项回归测试
.github/workflows/pages.yml      校验 → 打包 → Pages 发布
```

内容全部以文本节点渲染，不把论文标题或摘要当作 HTML 执行。数据抓取失败、空初始化、已处理但无入选论文分别显示。

## 公开数据约定

`digests.json` 的根字段为 `schema_version`、`generation_status` 和 `digests`。生成通道未配置时，`generation_status` 为 `not_configured`。

每期简报包括官方 `listing_date`、带时区的 `published_at`、`source_count`、`signal_title`、`signal`、`mind_model` 和 `papers`。

每篇论文包括 `arxiv_id`、`version`、`status`、`title`、`summary`、`tags`、`read_now`、`institution`、`code_url`、`systems_problem`、`mapping`、`evidence` 和 `sources`。`sources` 中每个来源为 `label` 与 HTTPS `url`。机构无法确认时写 `Unknown`；代码地址无法确认时写 `null`；版本未知时留空，不猜测 v1。

校验拒绝重复批次、同批重复论文、缺少对应 arXiv 来源、异常 URL、额外私人字段及不在发布白名单的文件。**这些检查不能替代论文事实核验，也不能识别所有藏在自由文本内的私人内容。公开前仍须审查内容来源。**

## 验证

```sh
python3 scripts/validate_site.py
python3 -m unittest discover -s tests -v
```

本轮本地 12 项回归测试通过，GitHub Actions 的校验和打包步骤也通过。另有 12 项离线浏览器交互检查通过，覆盖空状态、移动端溢出、标题转义、筛选、归档跳转和读取失败提示。浏览器检查使用内存中的模拟公开数据，**不代表公网导航或完整自动生成链路已验收**。测试样例不会写入 `site/`。

## 内容与隐私

公开仓库只允许网站代码和经过确认可公开的论文简报。

- 不上传历史会话 ZIP、个人数据库、笔记、反馈或聊天摘录。
- 不上传 `.env`、API Key、访问令牌、`auth.json` 或浏览器登录数据。
- 访客只有阅读权限；站内收藏、笔记和登录不属于这一阶段的范围。
- 历史论文必须先核对标题、编号、版本及来源，不默认将旧聊天中的分析视为已验证事实。

## 后续验收边界

完整目标仍是：官方批次 → 完整性检查 → 去重与分析 → 保存公开简报 → 自动发布。

自动生成通道需要独立配置和验证，不能用本次网页发布成功替代。采集进度、生成结果、部署结果必须分开记录；任何失败都不能被当作“没有新论文”。本次不创建新的 ChatGPT 排程、不调用付费模型，也不把任务降级为只有原文摘要。

参考：[GitHub Pages 自定义工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。
