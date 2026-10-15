# 亚洲大学中文公告 · Ajou Notices

[打开公告网站](https://zhupoxixixi.github.io/ajou-notices/) · [自动更新记录](https://github.com/zhupoxixixi/ajou-notices/actions)

面向中国留学生及一般大学院研究生，持续收录亚洲大学官方公告的中文要点。界面沿用 [Ajou Menu 食堂项目](https://zhupoxixixi.github.io/ajou-menu/) 的黑白配色、绿色标识、圆角卡片和底部导航。

## 自动更新

GitHub Actions 每日韩国时间 **08:17、12:17、18:17** 检查，执行时间可能延迟，也可在 Actions 手动运行。工作流程为：扫描官方列表 → 读取新增及已收录公告正文、海报 → 比较内容指纹 → 用 **GPT-6 Luna（gpt-6-luna）** 整理新增或变化内容 → 保留结果、构建 → 发布 GitHub Pages。

未变化的内容不重复调用翻译 API。模型和提示词版本进入缓存指纹；海报内容也计算摘要。网站访问只读取静态文件，不调用翻译 API。

定时更新逐条重新检查来源；提交代码或手动运行时，对最近30分钟刚检查过的条目复用检查结果，仍扫描列表以发现新公告，避免接连部署时重复访问官网。原文检查时间保留实际检查时刻。单个公告板暂不可达时保留存档，不连续重试它的其余列表页。

翻译密钥来自你提供的接口，保存在仓库 **Actions Secret `TRANSLATE_API_KEY`**。源码与网页只保留变量名称；API 端点通过仓库 Variable `TRANSLATE_API_ENDPOINT` 配置，模型通过 `TRANSLATE_MODEL` 配置，默认 gpt-6-luna。

## 来源与收录边界

- [一般大学院](https://grad.ajou.ac.kr/gs/community/notice.do)
- [大学院英文公告](https://grad.ajou.ac.kr/gs_eng/community/notice.do)
- [外国留学生](https://www.ajou.ac.kr/iadmissions/life/lifenotice.do)
- [国际交流处](https://www.ajou.ac.kr/oia/notice/notice.do)
- [学校综合公告](https://www.ajou.ac.kr/kr/ajou/notice.do)

另接入大学院创新／BK21、奖学金专板、中央图书馆、大学院学事日历和软件融合学院，共 10 个公开来源。用户所属为 사이버보안학과（网络安全学科）；学科官网“大学院公告”指向已经接入的大学院主板，不重复采集，也不套用计算机工程系的专属要求。

按近期日期、已知记录、末页和请求上限决定翻页，不再固定只扫 3 页。新项目一般取最近 150 天，保留长期置顶指南和已收录历史项目；触及请求上限会在来源状态中标明，不能视为完整覆盖历史。学校综合公告、国际交流处及图书馆做可解释的候选筛选，再由模型读取内容判断适用范围。明确仅限本科生、韩国籍的项目排除；资格不明确标记“资格需确认”。同一官方 articleNo 跨板只展示一次，保留共同来源；已核实的中英文通知继续合并展示。

来源列的发布日期、公告展示结束日、申请截止日、活动日期分别处理。图书馆只使用公开公告 API，不访问个人消息。大学院日历只规范化明确的日期，含糊的“月中／月初”不猜具体日期。

## 日常使用

- 首页默认隐藏已经结束的事项，可选择“全部（含已结束）”或“已截止／结束”查看；收藏与详情链接继续有效。报名已截止但活动尚未举行时，仍保留活动状态并注明报名截止。
- 页面底部“日历／安装”提供全站 ICS 订阅、单次下载、中文 Markdown 与 JSON 导出。单条详情可下载对应日历；资格不明、待复核或无日期依据的条目不生成日历事项。UID 稳定，改期有 SEQUENCE，撤回导出保留取消标记；订阅刷新和提醒由日历 App 决定。
- 用 Safari 打开网站 → 分享 → 添加到主屏幕。安装图标与作用范围限定本站项目路径。首次联网打开后缓存页面与公告；离线显示缓存检查时间，恢复联网后刷新获取最新数据。
- 保持食堂项目的配色和组件，只增加短促的弹窗／收藏反馈，并尊重系统“减少动态效果”。不需要额外注册或登录。

## 运行监控与可选提醒

每个来源展示实际检查时间、最近完整检查时间、扫描页数和异常／覆盖受限状态；整理失败的条目进入待处理清单，失败时保留之前的摘要。部署后 `delivery.py` 会比较线上 JSON 与构建产物，避免把构建成功当成线上发布成功。

用户当前选择**不开手机推送**，外部失效监控仅准备接口，不创建外部账号。仓库变量 `ENABLE_NOTIFICATIONS`、`ENABLE_HEALTHCHECKS` 默认 `false`；以后需要明确启用对应变量为 `true`，并配置以下 Actions Secrets：

- `HEALTHCHECK_PING_URL`：独立监控的 Ping URL。数据检查与线上验证通过后报告成功；部分来源失败或部署失败发送 `/fail`。监控应按三个时段或至少覆盖 14 小时夜间间隔并留宽限时间；主任务根本未运行的提醒依赖外部服务，未配置前本站不会主动通知。
- `NTFY_TOPIC`：可选手机提醒主题；当前未配置。首次运行仅建立基线，后续只推语义或日期变化，并在发布成功后记录发送状态。普通检查时间变化不通知；发送失败不推进记录。主题及密钥不进入前端或公开数据。

公开站只收公开资料，不保存个人课表、学号、邮箱或课程平台内容。GitHub Actions 标准 runner 对公开仓库免费，翻译服务仍受所用 API 的额度约束。

中文是要点摘要，不是附件逐字全文翻译。首版人工核验内容保留核验日期；后续自动内容标记“AI 自动”，不能视为已完成逐条人工核验。来源缺少日期、存在起止顺序冲突时不猜测截止日。网页按韩国时间显示状态；日期未给具体时刻时按该日结束后切换状态，并明确注明未给时刻。

正文或翻译失败时保留原结果；未成功读取的新公告不发布。页面显示最近检查时间、更新异常与来源链接。超过24小时未成功检查会提示资料陈旧。只识别海报前四张，超过范围会说明；PDF 无可提取文本时不猜测内容。登录后课程平台内容不在抓取范围。

## 本地运行

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# 只在被忽略的 .env 填写密钥
python -X utf8 update.py
python -X utf8 build.py
python -m http.server 8789 --bind 127.0.0.1 --directory dist
```

只构建已有存档可直接运行 build.py，不需要密钥。

```powershell
python -m unittest discover -s tests -p 'test_*.py'
node tests.cjs
node --check src/app.js
```

## 文件

- update.py：发现、增量检查、筛选与更新，抓取错误时保留旧记录。
- ai_translate.py：Luna 请求、海报输入、输出校验、日期证据和重试。
- crawl.py：官方公告页面结构解析。
- data/seed.json：首版人工整理的中文摘要与来源。
- data/archive.json：持续累积的中文摘要。
- data/state.json：内容指纹、模型、检查时间和排除原因，不保存密钥或原始全文。
- data/update.json：上次更新统计与错误。
- src/：网页源文件；dist/：GitHub Pages 发布文件。
- .github/workflows/update-notices.yml：定时抓取、翻译、检查与 Pages 发布。

## 网页功能

中韩文关键词搜索、外国人与一般大学院筛选、课程/科研/资助/生活签证等主题筛选、截止状态、官方来源筛选、收藏、单条链接、深浅色与中文 Markdown / JSON 导出。收藏只保存在当前浏览器。

## 样式许可

保留食堂项目所用 MIT 样式归属，见 [THIRD_PARTY_NOTICES](src/THIRD_PARTY_NOTICES.md)。公告版权属于相应发布方，网站只提供中文摘要与官方链接。
