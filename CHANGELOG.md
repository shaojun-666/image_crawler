# 更新日志

## v1.2.0 (2026-06-08)

### 新增
- **翻页检测与批量爬取** — 自动检测页面中的翻页机制（下一页/页码导航/`<link rel="next">`），弹窗询问用户选择单页、全部页面或自定义页码范围
- **"显示更多"自动点击** — JS 渲染模式下自动检测并点击"加载更多"/"显示更多"按钮，支持 19 种点击策略，最多爬取 100 张图片
- **多页爬取结果去重** — 跨页面自动去重，避免重复图片
- **翻页检测进度提示** — 状态栏显示"正在检测翻页机制..."、爬取进度"正在爬取第 3/10 页..."

### 优化
- **Playwright 加载策略** — 将 `networkidle` 替换为 `domcontentloaded` + 手动空闲定时器，避免 SPA 页面 WebSocket 长连导致超时
- **URL 协议白名单** — 爬取结果仅保留 `http://` 和 `https://` 协议，防止异常 URL 注入

### 修复
- **Tkinter 线程安全** — 翻页弹窗通过 `root.after(0, ...)` + `threading.Event` 在主线程创建，避免后台线程操作 GUI 导致崩溃

---

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
