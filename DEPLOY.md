# IntelNexus Docker 部署指南

把 IntelNexus 简报中心以容器方式部署到一台常开的云主机，实现：

- **外网访问**：非开发者通过浏览器打开 `https://你的域名` 使用。
- **稳定定时推送**：容器 24/7 常驻（不休眠），APScheduler 后台调度持续运行，简报按订阅者设定时间自动生成并推送（邮件 / 企业微信 / 钉钉）。
- **数据安全**：用户数据挂 Docker 卷持久化，密钥经 `.env` 注入、绝不入镜像。

> 前置：一台有公网 IP 的 Linux 云主机（Ubuntu 22.04+ 推荐），已解析一个域名到该主机，开放 80/443 端口。本机已装 Docker 与 docker-compose v2。

---

## 1. 安装 Docker

```bash
# Ubuntu 示例
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # 退出重登后免 sudo
docker --version && docker compose version
```

## 2. 上传项目并准备配置

将整个仓库上传到云主机（如 `/opt/intelnexus`）。进入目录后：

```bash
cd /opt/intelnexus

# 1) 准备密钥文件（复制模板并填入真实值）
cp .env.example .env
nano .env            # 填 OPENROUTER_API_KEY / GOOGLE_API_KEY / SMTP_* 等

# 2) 准备 basic auth 账号（nginx 用）
sudo apt-get install -y apache2-utils
htpasswd -c ./nginx/htpasswd admin     # 按提示输入密码，可再加其他账号去掉 -c

# 3) 创建证书与 webroot 目录
mkdir -p ./certs/webroot
```

`.env` 关键项：

| 变量 | 说明 |
|---|---|
| `OPENROUTER_API_KEY` / `GOOGLE_API_KEY` | **定时简报必需**：容器内无 Ollama，不填则定时简报走降级模板文案（UI 横幅会提示 `sched_llm_degraded`）。也可稍后在界面「模型设置」添加自定义模型。 |
| `OLLAMA_BASE_URL` | 留空（容器无本地 Ollama）。 |
| `INTELNEXUS_DATA_DIR` | 固定 `/app/data`，由卷挂载持久化，无需改。 |
| `SMTP_*` | 可选；UI 模式优先用界面配置的 `data/email_settings.json`，`.env` 密码可覆盖。 |
| `HTTP_PROXY` / `HTTPS_PROXY` | **切勿**填本地代理（如 `http://127.0.0.1:7890`）。容器内无此代理，填了会导致全部外网请求（抓取情报、调用模型 API）失败。云主机直连外网时**留空**。 |
| `OLLAMA_BASE_URL` | 仅当云主机确已安装并运行 Ollama 才填；否则留空（定时链路改用 API Key 模型）。 |
| `ENABLE_*` | 搜索源开关，按需开启。 |

## 3. 申请 TLS 证书（certbot）

```bash
sudo apt-get install -y certbot
# 用 webroot 模式，挑战文件写到 ./certs/webroot（nginx 已挂载该目录）
sudo certbot certonly --webroot -w /opt/intelnexus/certs/webroot \
  -d 你的域名 \
  --agree-tos -m 你的邮箱
```

证书生成于 `/etc/letsencrypt/live/你的域名/`。把它软链 / 复制到项目 `./certs/live/你的域名/`：

```bash
mkdir -p ./certs/live
sudo cp -rL /etc/letsencrypt/live/你的域名 ./certs/live/你的域名
```

> 也可直接把 `.env` 同级的 `./certs` 指向 `/etc/letsencrypt`。关键是 nginx.conf 中的路径与 `./certs/live/<域名>/` 一致。

## 4. 替换 nginx 配置中的域名占位符

```bash
sed -i 's/__DOMAIN__/你的域名/g' ./nginx/nginx.conf
```

确认 `./nginx/nginx.conf` 中 `server_name` 与两条 `ssl_certificate*` 路径已变为真实域名。

## 5. 构建并启动

```bash
docker compose up -d --build
docker compose ps          # 应看到 app(healthy) 与 nginx(up)
docker compose logs -f app # 观察启动，首次会初始化 data/ 并加载依赖
```

启动后访问 `https://你的域名`，输入 basic auth 账号即可使用。

## 6. 迁移已有本地数据（可选）

若你本地已用过 IntelNexus，想保留订阅者 / 简报历史 / 邮件配置：

```bash
# 本地机器：打包 data/
cd d:/Improve/Project/Python/IntelNexus
tar czf data.tar.gz data

# 云主机：解压到卷挂载点（先停容器，再写入命名卷对应的宿主机路径）
docker compose down
# 命名卷实际路径：
sudo tar xzf data.tar.gz -C /var/lib/docker/volumes/intelnexus_intelnexus_data/_data
docker compose up -d
```

> 更简单：先 `docker compose up -d` 让卷创建，再用 `docker cp`：
> `docker cp ./data/. intelnexus-app:/app/data/`

## 7. 在界面完成最后配置

浏览器登录后：

1. **模型设置**（侧边栏）：添加 API Key 模型（OpenRouter / Google），保存。定时链路会自动解析使用，横幅显示 `sched_llm_ok`。
2. **简报中心 → 订阅管理**：添加订阅者、配置邮件 / 企业微信 / 钉钉、设推送时间。
3. 顶部状态横幅确认「定时推送运行中（N 个任务）」。

## 8. 运维

```bash
# 查看日志
docker compose logs -f app
docker compose logs -f nginx

# 健康检查端点（需带 basic auth）
curl -u admin:密码 https://你的域名/_stcore/health

# 重启 / 停止
docker compose restart
docker compose down

# 升级（拉最新代码后）
git pull
docker compose up -d --build
```

### 定时推送稳定性说明

容器由 `restart: unless-stopped` 保证常驻与崩溃自愈，且容器不像 Cloud Studio 沙箱会休眠，因此 APScheduler 后台线程持续运行，到时即推。错过触发点有 1 小时补推窗口（`misfire_grace_time=3600`）。

### 防火墙

仅开放 80/443；**不要**将 8501 暴露到公网（应用仅 listen 内部网络，由 nginx 反代）。

```bash
sudo ufw allow 80,443/tcp
sudo ufw enable
```

### 证书自动续期（建议）

```bash
# 加入 crontab：每月续期并 reload nginx
0 3 1 * * certbot renew --quiet && docker compose exec nginx nginx -s reload
```

---

## 排错

| 现象 | 排查 |
|---|---|
| 访问提示 502 | `docker compose logs nginx`；确认 app 健康（`docker compose ps`）；nginx.conf 域名/证书路径是否正确。 |
| 定时简报是降级模板 | 模型未就绪：界面「模型设置」添加 API Key 模型，或 `.env` 填 `OPENROUTER_API_KEY`/`GOOGLE_API_KEY`，重启容器。 |
| 推送失败 | 检查 `data/email_settings.json` 或订阅者渠道 webhook；UI 横幅 `sched_smtp_missing` 提示 SMTP 未配。 |
| 数据丢失 | 确认卷已挂载：`docker volume inspect intelnexus_intelnexus_data`；未挂载则 data 写入容器层，重建即丢。 |
