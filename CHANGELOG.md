# 更新日志

## v1.1.0 (2026-06-07)

### 修复
- **文件名后缀污染** — `save_selected_images()` 方法缺少文件名清理逻辑，导致保存的图片仍带有 `-pcthumbs` 等污染后缀。已添加与 `download_images()` 一致的扩展名正则清洗逻辑。
- **`import re` 缺失** — `image_crawler.py` 中未引入 `re` 模块，导致下载时 `name 're' is not defined` 错误。

### 变更
- `save_selected_images()` 在保存图片前，通过 `os.path.splitext()` + `re.search()` 清理 URL 中附加的污染后缀

---

## v1.0.1 (2026-06-06)

### 修复
- **图片 URL 过滤过于严格** — `crawler_engine.py` 中 `_is_valid_image_url()` 的正则 `\.(jpg|jpeg|png|gif|webp|bmp)(\?|#|$)` 要求扩展名必须在路径末尾，导致图床 `s.panlai.com` 附加的 `-pcthumbs` 后缀被错误过滤。修改为 `\.(jpg|jpeg|png|gif|webp|bmp)`，放宽匹配条件。

### 变更
- 爬虫引擎 URL 过滤正则放宽，支持 `s.panlai.com` 等图床的缩略图后缀格式

---

## v1.0.0 (2026-06-05)

### 新增
- **GUI 主程序** — tkinter 界面的图片爬虫工具，支持网址输入、图片预览、选择保存、日志显示
- **静态爬虫引擎** — 基于 requests + BeautifulSoup 的静态页面图片提取
- **JS 渲染爬虫引擎** — 基于 Playwright + Chromium 的动态页面图片提取，含反检测脚本
- **智能模式** — `AutoCrawler` 自动判断页面是否需要 JS 渲染，也可手动强制开启
- **图片预处理** — Pillow 缩略图生成，分页预览（每页 20 张），勾选保存
- **日志系统** — 文件日志 + GUI 实时显示
- **打包配置** — PyInstaller spec 文件，支持打包为 Windows EXE

### 修复
- **Playwright 检测时序** — 修复 GUI 初始化时 `_check_playwright()` 在组件创建前调用导致勾选框不可用的 Bug
