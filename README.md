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

每个公告板检查前三页，新项目一般取最近 150 天，并保留长期置顶指南和已收录历史项目。学校综合公告与国际交流处先做相关关键词筛选，再由模型判断适用范围。排除仅限本科生、仅限韩国籍等不适用项目。已确认是同一通知的中英文版本合并为一张卡，保留其他版本链接。

中文是要点摘要，不是附件逐字全文翻译。首版人工核验内容保留核验日期；后续自动内容标记“AI 自动”，不能视为已完成逐条人工核验。来源缺少日期、存在起止顺序冲突时不猜测截止日。网页按韩国时间显示状态；日期未给具体时刻时按该日结束后切换状态，并明确注明未给时刻。

正文或翻译失败时保留原结果；未成功读取的新公告不发布。页面显示最近检查时间、更新异常与来源链接。超过三天未成功检查会提示资料陈旧。只识别海报前四张，超过范围会说明；PDF 无可提取文本时不猜测内容。登录后课程平台内容不在抓取范围。

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
