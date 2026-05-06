# Daily CloudCode/Codex Intelligence Digest

一个轻量的每日自动情报脚本：
- 从网络抓取关键词相关的最新信息（新闻 RSS + Hacker News + GitHub 仓库动态）
- 自动去重并按日期排序
- 通过邮件推送每日摘要

> 适合你这种“每天自动看进展和技巧”的场景。

## 1) 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 SMTP 邮箱参数
python3 digest.py
```

## 2) 定时执行（每天 8:30）

```bash
crontab -e
```

加入：

```cron
30 8 * * * cd /workspace/An && /usr/bin/env bash -lc 'source .venv/bin/activate && python digest.py >> digest.log 2>&1'
```

## 3) 可配置项

在 `.env` 中配置：

- `KEYWORDS`: 逗号分隔关键词（默认：`cloud code,codex,claude code`）
- `SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS`: 邮箱 SMTP 参数
- `EMAIL_FROM/EMAIL_TO`: 发件和收件地址
- `MAX_ITEMS_PER_SOURCE`: 每个来源保留的条目数

## 4) 当前支持的数据源

- Google News RSS（按关键词）
- Hacker News Search API（按关键词）
- GitHub Repositories API（按关键词）

后续你可以继续加：Reddit、X、官方博客 RSS、YouTube。
