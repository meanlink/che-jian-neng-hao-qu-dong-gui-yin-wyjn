# 绿电凭证月度核验

用同月绿电凭证匹配各线实测日耗的台账核验小型项目。模拟客户、痛点、上下游、核发规则与一天工作剧本见 [BUSINESS.md](BUSINESS.md)。

## 模块与业务流程
用电接入（CSV/JSON、逐日校验、批次指纹）→ 凭证登记与核发声明（同月匹配、双重上限、队列核发）→ 撤销与换证补发（失效份额留痕、幂等重试）→ 月度核验与简报投递（本地收件箱、CSV/JSON、SHA256）；另有业务总览和审计轨迹。
四个贯穿全栈的实体：用电日记录、绿电凭证、核发声明、月度核验简报；辅助 Customer、Line、User、Audit、Delivery。

## 快速启动
```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```
访问 http://localhost:18215；后端文档 http://localhost:19215/docs；数据库宿主端口 17715。
`SEED_DEMO=true` 自动幂等 seed；不覆盖用户修改。手动 seed 命令可重复执行。

## 演示账号与权限
|账号|密码|真实权限|
|---|---|---|
|admin@demo.local|Demo123!|接入、登记、核发、撤销、补发、简报计划、读取与下载|
|analyst@demo.local|Demo123!|接入、登记、核发、补发、读取与下载；不能撤销凭证或维护简报计划|
|viewer@demo.local|Demo123!|只读与下载|

## 核心规则（服务端强制）
- 同月匹配：声明归属月强制取凭证归属月，只能匹配该线体同月实测电量。
- 双重上限：凭证 `reserved+issued≤总量`，线体当月 `reserved+issued≤实测`；提交即占用，原子条件更新兜底并发，核发与重试不重复占量。
- 撤销生效后停止核发：在途声明取消并释放占用，已核发份额失效；旧声明全部留档。
- 简报只扣失效份额：绿电=有效已核发；未匹配部分计普通用电；失效份额单列扣减。
- 换证补发：金额恒等于失效份额，同一失效份额最多一个在途补发（唯一索引保证），失效份额沿补发链下移。

## 技术与本地开发
Python 3.12 / FastAPI / SQLAlchemy 2 / MySQL 8.0 / Redis 7 / Nginx；原生 HTML CSS JavaScript ES modules（用户指定）。后端所有校验、持久化和台账规则在服务端。无前端打包步骤。
后端：安装 backend/requirements.txt，设置 DATABASE_URL、REDIS_URL、JWT_SECRET、ARTIFACT_DIR 后在 backend/ 执行 `python -m migrations.initial`、`python -m scripts.seed_demo`、`uvicorn src.main:app`，另开 `python -m src.worker`。前端使用带 /api 反向代理的 Nginx，直接打开 index.html 不支持 API。

## 目录与工程约定
backend/src/{models,schemas,services,routes,controllers,middlewares,constants,config,utils}；backend/scripts/seed_demo.py；backend/migrations/initial.py。
frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}。
Role 枚举：admin/analyst/viewer；ClaimStatus：pending/issued/invalidated/cancelled；CertStatus：active/revoked。后端 backend/src/constants/enums.py，前端 frontend/src/constants/enums.js；路由权限在 middlewares/auth.py；页面按相同角色控制操作入口。

## 环境变量与 Docker
COMPOSE_PROJECT_NAME=green-ledger；FRONTEND_PORT=18215；BACKEND_PORT=19215；DB_PORT=17715；DB_PASSWORD、JWT_SECRET 见 .env.example；SEED_DEMO 默认 true。共享命名产物卷供后端下载与 worker 写入，数据库/Redis 各持久卷。
恰好五服务均有健康检查。Redis 队列加 SQL 在途状态兜底；worker 按队列核发声明、到点执行凭证撤销、按 next_run 生成简报文件。周期 60 秒至 30 天。简报为生成时点台账快照；口径变化后由下次执行生成新文件。当前不连接邮件或企业聊天。
错误响应、请求编号、Redis 每 IP 每分钟 240 次限流、JWT 和数据库操作审计。演示密钥与密码仅供本机模拟；生产部署前配置独立密钥与账号。

## 数据与验收
所有数据为固定随机种子生成的模拟业务数据，不能作为实际生产决策证据。项目核发规则、输入边界及业务局限详见 BUSINESS.md。测试与截图统一存放源码仓库外的 test-artifacts/green-ledger/，源码不含日志/截图/测试报告。
清理本项目演示数据：`docker compose down -v --remove-orphans`（会删除本项目命名卷）。

## License
MIT，见 LICENSE。
