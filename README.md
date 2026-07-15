# InterviewCopilot（面壁）

一款提供个性化模拟面试和证据化能力评价的 AI 面试训练系统。

开始开发前，请先阅读[系统架构](docs/系统架构.md)、[工程开发规范](docs/工程开发规范.md)和[安全基线](docs/安全基线.md)。整个仓库的 AI 与贡献者强制规则保存在 `AGENTS.md` 中。

## 项目组成

- `web/`：Next.js Web 应用
- `api/`：FastAPI AI 编排与文档处理服务
- `infra/`：PostgreSQL 等本地基础设施初始化
- `docs/`：架构、规范、决策和待确认事项

## 本地开发

```powershell
Copy-Item .env.example .env
docker compose up -d

cd api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn interview_copilot.main:app --reload --port 8000
```

在另一个终端中运行：

```powershell
cd web
npm run dev
```

## 质量检查

```powershell
.\.venv\Scripts\python.exe -m pytest api
.\.venv\Scripts\ruff.exe check api
.\.venv\Scripts\mypy.exe api\src
npm --prefix web run lint
npm --prefix web run build
docker compose config --quiet
```

尚未明确的产品和第三方服务决策统一记录在[待确认问题](docs/待确认问题.md)中，不得通过猜测完成实现。

## 生产容器部署

`docker-compose.prod.yml` 只向宿主机暴露 Web 端口，PostgreSQL、Redis 和 FastAPI 保持在内部网络。部署前必须在 `.env` 中设置高强度的 `POSTGRES_PASSWORD`、`REDIS_PASSWORD`、`SPEECH_TICKET_SECRET`，以及真实的 `WEB_ORIGIN` 和 `NEXT_PUBLIC_INTERVIEW_WS_URL`。

```powershell
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

API 容器会在启动前执行 Alembic 迁移；`/health` 只检查进程存活，`/ready` 同时检查 PostgreSQL 和 Redis。公网部署必须在 Web 容器前配置支持 WebSocket 的 HTTPS 反向代理，浏览器端语音地址使用 `wss://`。数据库备份、恢复演练、日志采集和监控告警仍需按服务器环境单独配置，未配置前不能视为生产就绪。

数据库备份脚本生成 PostgreSQL custom-format 归档，不会自动删除旧备份：

```bash
BACKUP_DIR=/srv/backups/interview ./infra/scripts/postgres_backup.sh
```

恢复会清理目标库中的同名对象，必须显式指定目标数据库并设置确认变量：

```bash
RESTORE_CONFIRM=RESTORE:interview_copilot \
  ./infra/scripts/postgres_restore.sh /srv/backups/interview/backup.dump interview_copilot
```

生产环境仍应把归档同步到独立存储，并按业务要求确定保留周期；未经恢复演练的备份不能视为可用备份。
