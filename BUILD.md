# 打包为可执行文件

## 方法1: 使用PyInstaller（推荐）

### 安装PyInstaller
```bash
pip install pyinstaller
```

### 打包为Windows可执行文件
```bash
pyinstaller image_crawler.spec
```

打包完成后，可执行文件位于：
- `dist\图片爬虫.exe`

### 生成单个exe（包含所有依赖）
```bash
pyinstaller --onefile --windowed --name "图片爬虫" image_crawler.py
```

## 方法2: 手动命令行打包

```bash
# 安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 打包
pyinstaller --onefile --windowed --name "图片爬虫" --add-data "requirements.txt;." image_crawler.py
```

## 参数说明

- `--onefile`: 打包成单个exe文件
- `--windowed`: 隐藏控制台窗口
- `--name`: 指定可执行文件名
- `--icon`: 添加图标文件（可选）

## JS渲染模式打包

如果需要在打包后支持JS动态页面爬取，需要额外操作：

### 1. 安装Playwright

```bash
pip install playwright
```

### 2. 安装Chromium浏览器

```bash
playwright install chromium
```

**注意：** Chromium浏览器二进制文件（约150MB）不会被打包进exe。在目标机器上，用户需要手动运行 `playwright install chromium` 安装浏览器。

### 3. 使用spec文件打包

```bash
pyinstaller image_crawler.spec
```

程序启动时会自动检查Playwright和Chromium是否可用，并在日志中显示状态。如果不可用，JS渲染模式复选框将被禁用。

## 使用spec文件打包（推荐）

spec文件已经配置好，直接使用：
```bash
pyinstaller image_crawler.spec
```

## 验证打包

1. 进入`dist`目录
2. 运行`图片爬虫.exe`
3. 确认功能正常

## 清理临时文件

```bash
# 删除dist和build目录
rmdir /s /q build dist
```
