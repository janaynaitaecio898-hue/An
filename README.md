# 全球信息日报（Daily Global Info）

这是一个每天自动抓取全球信息的网站示例，基于 Python 标准库 + SQLite（无第三方依赖）。

## 功能

- 每天自动从多个全球 RSS 源抓取新闻。
- 按地区聚合展示（全球、欧洲、亚洲、非洲、美洲）。
- 提供手动“立即刷新”按钮。
- 提供 JSON API：`/api/articles`。
- 自动清理 14 天前数据。

## 快速开始

```bash
python3 app.py
```

打开 `http://localhost:8000` 即可查看。

## 结构

- `app.py`: 抓取逻辑、数据库逻辑、Web 路由、后台调度
- `static/style.css`: 样式
- `test_app.py`: RSS 解析测试

## 说明

默认 RSS 数据源来自 NYTimes 与 BBC，若网络环境受限可替换 `FEEDS` 中 URL。
