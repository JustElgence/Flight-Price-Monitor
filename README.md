# Flight-Price-Monitor (FlyMon)

自用机票价格监控站：输入出发地/目的地 + 日期，自动追踪**每日最低价**并绘制历史价格曲线；跌破阈值时通过 **QQ / 企业微信 / 钉钉** 推送提醒。

**线上地址**：http://fly.teardrop.cn:8090 （口令访问）

## 功能

- 🛫 航线监控：城市名/三字码 + 日期，可选**指定航班号**（如 MU6345）只盯某一班
- 📈 历史最低价曲线（ECharts，自动标注最低点与阈值线），价格历史自行落库累积
- 🕵️ 每次抓取解析**全部在售航班明细**：航司 / 航班号 / 机型 / 起降时间与机场 / 价格 / 舱位折扣
- 🔔 IM 告警：Qmsg酱（QQ 公共机器人）、NapCat/OneBot（QQ 自建）、企业微信、钉钉、通用 Webhook；6 小时冷却去重
- 🔐 访问口令登录（`FLYMON_PASSWORD`）
- 🌏 城市中文显示，未收录城市自动回退三字码

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Python 3.12 · FastAPI · APScheduler（进程内定时） |
| 数据库 | SQLite（WAL），5 张表，零运维 |
| 抓取 | Playwright 无头 Chromium，解析同程（ly.com）列表页 SSR 数据 |
| 前端 | 原生 JS 单页 + ECharts（本地 vendor，无 CDN 依赖） |
| 部署 | Docker Compose 单容器 · 8090 端口 |

## 快速开始

```bash
# 本地运行（需先安装 Playwright Chromium）
pip install -r backend/requirements.txt
playwright install chromium
FLYMON_PASSWORD=yourpass uvicorn app.main:app --app-dir backend --port 8000

# Docker 部署
docker compose up -d --build
```

环境变量：

| 变量 | 说明 | 默认 |
|------|------|------|
| `FLYMON_PASSWORD` | 访问口令，留空则不启用认证 | 空（不启用） |
| `FLYMON_DATA` | SQLite 数据目录 | `./data` |

## 数据源说明

数据来自同程旅行 PC 机票列表页（免费、匿名可访问），页面 SSR 渲染约 75~108 天的每日最低价日历与航班列表。抓取频率默认每天 3 次（可按任务配置 1~24 次/天）。若页面改版，`fetcher.py` 适配器可快速更换数据源。

## API 概览

```
GET/POST/PATCH/DELETE  /api/tasks[/{id}]     任务管理
POST                   /api/tasks/{id}/refresh   手动抓取
GET                    /api/tasks/{id}/history   历史价格
GET                    /api/tasks/{id}/latest    最新快照（日历+航班明细）
GET/POST               /api/settings/notify      通知设置
POST                   /api/settings/notify/test 发送测试消息
```

## 风险与声明

- 仅供个人学习与自用，不含出票/交易功能
- 抓取行为保持低频（默认每天 2~3 次/航线），请遵守目标站点访问礼仪
