# 图片爬虫程序

一个基于 Python 的 GUI 图片爬虫工具，支持静态页面和 JS 动态渲染页面的图片爬取、预览、选择性保存和日志记录。

## 功能特性

- **智能爬取引擎** — 自动识别页面是否需要 JS 渲染，也可手动强制开启 JS 模式
- **图片预览** — 分页展示爬取到的所有图片（每页 20 张）
- **选择性保存** — 勾选/取消勾选需要保存的图片，按需下载
- **文件名自动清理** — 自动处理图片 URL 中的后缀污染（如 `.jpg-pcthumbs` → `.jpg`）
- **异步爬取** — 后台线程执行爬取，不阻塞界面操作
- **详细日志** — 实时显示爬取进度和结果

## 快速开始

### 环境要求

- Python 3.8+
- Windows / macOS / Linux

### 安装与运行

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/image_crawler.git
cd image_crawler

# 安装依赖
pip install -r requirements.txt

# 运行程序
python image_crawler.py
```

### JS 渲染模式（可选）

如需爬取 JS 动态生成内容的网页：

```bash
pip install playwright
playwright install chromium
```

## 使用方法

1. **输入网址** — 在地址栏输入目标网页 URL
2. **选择保存位置** — 点击"浏览..."选择图片保存目录
3. **（可选）开启 JS 渲染** — 如果网页内容是 JS 动态加载的，勾选"开启JS渲染模式"
4. **开始爬取** — 点击"开始爬取"，等待图片提取完成
5. **勾选图片** — 在预览区域勾选需要保存的图片（默认全选）
6. **保存选中** — 点击"保存选中图片"，图片将保存到指定目录

## 项目结构

```
image_crawler/
├── image_crawler.py      # GUI 主程序（tkinter）
├── crawler_engine.py      # 爬虫引擎（静态 + JS 渲染）
├── requirements.txt       # Python 依赖
├── image_crawler.spec     # PyInstaller 打包配置
├── BUILD.md               # 打包为 EXE 的详细说明
└── CHANGELOG.md           # 项目更新日志
```

## 技术栈

| 模块 | 技术 |
|------|------|
| GUI 框架 | tkinter / ttk |
| 静态爬虫 | requests + BeautifulSoup |
| JS 渲染爬虫 | Playwright (Chromium) |
| 图片处理 | Pillow |
| 打包分发 | PyInstaller |

## 打包为 EXE

查看 [BUILD.md](BUILD.md) 了解详细的打包和分发说明。

```bash
pip install pyinstaller
pyinstaller image_crawler.spec
```

打包后的文件位于 `dist/图片爬虫.exe`。

## 注意事项

- 请遵守目标网站的 `robots.txt` 及相关法律法规
- JS 渲染模式需要安装 Chromium 浏览器（约 150MB），但不会被打包进 EXE
- 打包后的 EXE 在目标机器上仍需 `playwright install chromium` 才能使用 JS 模式
