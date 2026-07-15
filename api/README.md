# InterviewCopilot 后端服务

支持 Python 3.12 或 3.13。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn interview_copilot.main:app --reload --port 8000
```

启动后可访问：

- 接口文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

第三方服务和产品决策中的未知事项请查看 `../docs/待确认问题.md`，不得靠猜测实现。
