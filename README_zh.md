# iPhone Photo Manager

*其他语言版本: [English](README.md), [中文](README_zh.md).*

一个轻量级、本地优先的 iPhone 照片浏览与管理工具。将 iPhone 照片导出到文件夹后，通过 Web 界面按时间线和地理位置浏览，支持 HEIC、Live Photo（实况照片）、MOV 视频等格式。

### ✨ 功能特性

一个轻量级、本地优先的 iPhone 照片 Web 画廊。原生支持 HEIC 和 Live Photo（实况照片）解析，以及按地点/时间线的离线照片聚合。所有处理均在本地设备完成，保护隐私。支持手机端自适应浏览和 4K 满画质无缝渲染。

使用时，只需将你 iPhone 中的照片完整复制到指定的目录下，例如当前项目根目录的 `./photos`（你可以在 `.env` 文件中通过 `PHOTOS_DIR` 进行配置），系统在启动时会自动扫描。

**照片存放目录结构示例：**

```text
iphone-photo-manager/
├── photos/                  # 你的 PHOTOS_DIR 照片存放目录
│   ├── 202601/              # （可选）建议按年月建立子文件夹管理
│   │   ├── IMG_0001.HEIC
│   │   ├── IMG_0001.MOV     # 自动与同名 HEIC 配对为 Live Photo
│   │   └── IMG_0002.JPG
│   └── ...
├── server/                  # Python 后端
│   ├── app.py               # FastAPI 主入口，API 路由，后台任务
│   ├── database.py          # SQLite 数据库 schema 与查询
│   ├── scanner.py           # 文件扫描与 EXIF/MOV 元数据提取
│   ├── thumbnail.py         # WebP 缩略图生成（small / medium）
│   └── geocoder.py          # 离线反向地理编码（reverse_geocoder + pycountry）
├── frontend/                # 纯 HTML/CSS/JS 前端（无框架）
│   ├── index.html           # 页面结构
│   ├── index.css            # 样式（深色/浅色主题、移动端媒体查询）
│   └── index.js             # 交互逻辑、Gallery 渲染、Modal、侧边栏
├── photos/                  # 照片存放目录（按 YYYYMM 子文件夹组织）
├── data/                    # 运行时数据（自动生成，已 gitignore）
│   ├── photos.db            # SQLite 数据库
│   └── thumbnails/          # 缩略图及高清渲染缓存
├── .env                     # 环境变量配置（不提交）
├── .env.template            # 环境变量模板
├── requirements.txt         # Python 依赖
├── stop.sh                  # 停止服务脚本
└── ARCHITECTURE_zh.md       # 项目架构与原理说明
```

### 🚀 快速开始

#### 1. 环境准备
需要 Python 3.10+。

```bash
# 克隆项目
git clone <repo-url>
cd iphone-photo-manager

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置

```bash
# 复制环境变量模板并按需修改
cp .env.template .env
```

主要配置项：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_LANGUAGE` | `zh` | 界面语言：`zh`（中文）或 `en`（英文） |
| `APP_THEME` | `light` | 主题：`light` 或 `dark` |
| `PHOTOS_DIR` | `photos` | 照片目录路径（相对于项目根目录，或绝对路径） |
| `SERVER_HOST` | `127.0.0.1` | 服务绑定地址（设为 `0.0.0.0` 可允许局域网访问） |
| `SERVER_PORT` | `8000` | 服务端口 |
| `SCAN_ON_STARTUP` | `True` | 启动时是否自动执行增量扫描 |
| `LOAD_ORIGINAL_ON_CLICK`| `False` | 打开单张图片时是否直接加载高清原图 |
| `DB_PATH` | `data/photos.db` | SQLite 数据库文件路径 |
| `THUMBNAIL_DIR` | `data/thumbnails` | 缩略图缓存目录 |

#### 3. 导入照片
将 iPhone 照片按年月分子文件夹放入 `photos/` 目录。（支持用 AirDrop 或 USB 直接导出，系统会自动配对 Live Photo）。

#### 4. 启动服务
```bash
PYTHONPATH=. python3 server/app.py
```
启动完成后在浏览器打开：**http://127.0.0.1:8000**

#### 5. 停止服务
```bash
./stop.sh
```

### 📖 使用指南
- **时间筛选**：左侧时间线点击月份快速跳转，点击箭头展开可精确到天。
- **查看原图**：如果 `LOAD_ORIGINAL_ON_CLICK` 为 false，可以在大图预览界面底部点击“查看原图”，系统会自动渲染并缓存一张满画质（4K）的高清大图供你查阅。
