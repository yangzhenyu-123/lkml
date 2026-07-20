# ============ 构建阶段 ============
# 基于 Node 20 alpine 镜像，编译前端静态资源
FROM node:20-alpine AS builder

# 设置工作目录
WORKDIR /app

# 先复制 package.json 与 package-lock.json，最大化利用 Docker 层缓存
COPY package*.json ./

# 安装依赖（CI 环境使用 npm ci 保证锁文件一致性）
RUN npm ci

# 复制源代码
COPY . .

# 接收构建时变量 VITE_API_BASE，用于注入 Vite 环境变量
ARG VITE_API_BASE
# 将构建参数转为运行时环境变量，供 vite build 读取
ENV VITE_API_BASE=$VITE_API_BASE

# 执行生产构建，产物输出到 dist 目录
RUN npm run build

# 构建失败快速失败：确保 index.html 存在
RUN test -f /app/dist/index.html || (echo "BUILD FAILED: dist/index.html not found" && exit 1)


# ============ 运行阶段 ============
# 基于 nginx alpine 镜像，托管静态资源
FROM nginx:alpine

# 从构建阶段复制编译产物到 nginx 默认静态目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制自定义 nginx 配置，覆盖默认配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 确保 nginx worker 可读静态文件（防止 403）
# nginx:alpine 默认 worker 以 nginx 用户运行，但 COPY 产物 owner 是 root
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# 暴露 80 端口供外部访问
EXPOSE 80

# 前台运行 nginx
CMD ["nginx", "-g", "daemon off;"]
