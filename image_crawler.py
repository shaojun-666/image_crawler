#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片爬虫程序 - GUI版本
支持自定义网址、图片预览、选择保存、日志记录
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import re
import requests
from urllib.parse import urlparse
import os
import shutil
import logging
from datetime import datetime
from PIL import Image, ImageTk
import threading
from crawler_engine import AutoCrawler, check_playwright_available


class PaginationDialog(tk.Toplevel):
    """翻页选择对话框 — 必须从主线程创建"""

    def __init__(self, parent, pagination_info):
        super().__init__(parent)
        self.result = 'current'
        self.page_start = 1
        self.page_end = 1
        page_count = len(pagination_info['pages'])
        page_type = pagination_info['type']

        self.title("翻页检测")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{x}+{y}")

        # Info label
        ttk.Label(self, text=f"检测到翻页机制 ({page_type}, {page_count} 个链接)，是否同时爬取其他页面？",
                  wraplength=350).pack(pady=(12, 5))

        # Radio buttons
        self.choice = tk.StringVar(value='current')
        ttk.Radiobutton(self, text="仅当前页", variable=self.choice,
                        value='current').pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(self, text="全部页面", variable=self.choice,
                        value='all').pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(self, text="自定义页码范围", variable=self.choice,
                        value='range').pack(anchor=tk.W, padx=20)

        # Range input
        range_frame = ttk.Frame(self)
        range_frame.pack(pady=5)
        ttk.Label(range_frame, text="从").pack(side=tk.LEFT, padx=2)
        self.start_entry = ttk.Entry(range_frame, width=6, justify=tk.CENTER)
        self.start_entry.pack(side=tk.LEFT, padx=2)
        self.start_entry.insert(0, '1')
        ttk.Label(range_frame, text="到").pack(side=tk.LEFT, padx=2)
        self.end_entry = ttk.Entry(range_frame, width=6, justify=tk.CENTER)
        self.end_entry.pack(side=tk.LEFT, padx=2)
        self.end_entry.insert(0, str(page_count))

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=(5, 12))
        ttk.Button(btn_frame, text="确定", command=self._confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self._cancel).pack(side=tk.LEFT, padx=5)

        # Validation: only enable range entry when 'range' is selected
        def toggle_range(*_):
            state = 'normal' if self.choice.get() == 'range' else 'disabled'
            self.start_entry.configure(state=state)
            self.end_entry.configure(state=state)
        self.choice.trace_add('write', toggle_range)
        toggle_range()

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.wait_window()

    def _confirm(self):
        choice = self.choice.get()
        if choice == 'range':
            s = self.start_entry.get().strip()
            e = self.end_entry.get().strip()
            if not s.isdigit() or not e.isdigit():
                messagebox.showerror("输入错误", "页码请输入数字", parent=self)
                return
            self.page_start = int(s)
            self.page_end = int(e)
            if self.page_start < 1 or self.page_end < 1:
                messagebox.showerror("输入错误", "页码必须≥1", parent=self)
                return
            if self.page_start > self.page_end:
                messagebox.showerror("输入错误", "起始页码不能大于结束页码", parent=self)
                return
        self.result = choice
        self.destroy()

    def _cancel(self):
        self.result = 'current'
        self.destroy()


class ImageCrawlerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("图片爬虫程序")
        self.root.geometry("1000x700")

        self.crawled_images = []
        self.selected_images = set()
        self.check_vars = []
        self.temp_dir = os.path.join(os.getcwd(), "temp_crawl")
        self.log_file = os.path.join(os.getcwd(), "crawl_log.txt")
        self.use_js_var = tk.BooleanVar(value=False)
        self.playwright_ok = False

        # 创建临时目录
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

        # 配置日志
        self.setup_logging()

        # 创建GUI界面（必须在检查Playwright之前，因为 log_message 会访问GUI组件）
        self.create_widgets()

        # 检查Playwright可用性
        self._check_playwright()

    def _check_playwright(self):
        """检查JS渲染模式是否可用"""
        ok, msg = check_playwright_available()
        self.playwright_ok = ok
        if ok:
            self.log_message("JS渲染模式可用 (Playwright + Chromium)")
            self.js_check.configure(state='normal')
            self.js_hint.configure(text="说明: 如果网页是JS动态生成的，勾选此项可正确提取图片")
        else:
            self.log_message(f"JS渲染模式不可用: {msg}")
            self.js_check.configure(state='disabled')
            self.js_hint.configure(text="需安装Playwright: pip install playwright && playwright install chromium")

    def setup_logging(self):
        """配置日志记录"""
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)

    def create_widgets(self):
        """创建所有GUI组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 上半部分：控制区域
        control_frame = ttk.LabelFrame(main_frame, text="设置", padding="10")
        control_frame.pack(fill=tk.X, pady=5)

        # 网址输入
        ttk.Label(control_frame, text="网址:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.url_entry = ttk.Entry(control_frame, width=50)
        self.url_entry.grid(row=0, column=1, sticky="we", padx=5, pady=5)
        self.url_entry.insert(0, "https://example.com")

        # 保存位置
        ttk.Label(control_frame, text="保存位置:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.save_path_entry = ttk.Entry(control_frame, width=50)
        self.save_path_entry.grid(row=1, column=1, sticky="we", padx=5, pady=5)
        self.save_path_entry.insert(0, os.getcwd())

        ttk.Button(control_frame, text="浏览...", command=self.browse_save_path).grid(
            row=1, column=2, padx=5, pady=5
        )

        # 操作按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=5)
        ttk.Button(button_frame, text="开始爬取", command=self.start_crawling).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="保存选中图片", command=self.save_selected_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空选择", command=self.clear_selection).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清除所有", command=self.clear_all).pack(side=tk.LEFT, padx=5)

        # JS渲染模式选项
        js_frame = ttk.Frame(control_frame)
        js_frame.grid(row=3, column=0, columnspan=3, pady=2)
        self.js_check = ttk.Checkbutton(
            js_frame, text="开启JS渲染模式 (处理动态网页，速度较慢)",
            variable=self.use_js_var
        )
        self.js_check.pack(side=tk.LEFT, padx=5)
        self.js_hint = ttk.Label(
            js_frame,
            text="说明: 如果网页是JS动态生成的，勾选此项可正确提取图片",
            foreground="gray"
        )
        self.js_hint.pack(side=tk.LEFT, padx=5)

        # 下半部分：图片预览区域
        preview_frame = ttk.LabelFrame(main_frame, text="图片预览", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 图片标签页（显示多张图片）
        self.notebook = ttk.Notebook(preview_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 日志显示区域
        log_frame = ttk.LabelFrame(main_frame, text="爬取日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def browse_save_path(self):
        """浏览保存位置"""
        path = filedialog.askdirectory(title="选择保存位置")
        if path:
            self.save_path_entry.delete(0, tk.END)
            self.save_path_entry.insert(0, path)

    def log_message(self, message):
        """记录消息到日志文件和控制台"""
        self.logger.info(message)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.update_status(f"{message}...")

    def update_status(self, message):
        """更新状态栏"""
        self.status_var.set(message)
        self.root.update_idletasks()

    def download_images(self, image_urls, base_url="", session=None):
        """下载图片"""
        downloaded = []
        failed = []
        if session is None:
            session = requests

        for idx, url in enumerate(image_urls, 1):
            self.update_status(f"正在下载图片 {idx}/{len(image_urls)}...")
            try:
                response = session.get(url, timeout=10, stream=True, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': base_url,
                    'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                })
                response.raise_for_status()

                # 提取文件名
                parsed_url = urlparse(url)
                filename = os.path.basename(parsed_url.path)
                if not filename or filename in ('', '.'):
                    filename = f"image_{idx:04d}.jpg"
                else:
                    name_part, ext = os.path.splitext(filename)
                    # 清除扩展名后的污染后缀（如 .jpg-pcthumbs → .jpg）
                    ext_clean = re.search(
                        r'(\.(?:jpg|jpeg|png|gif|webp|bmp))', ext, re.IGNORECASE
                    )
                    if ext_clean:
                        ext = ext_clean.group(1)
                    filename = f"{idx:04d}_{name_part}{ext}"

                # 保存到临时目录
                temp_path = os.path.join(self.temp_dir, filename)
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)

                downloaded.append((url, temp_path))
                self.log_message(f"成功下载: {filename}")

            except Exception as e:
                failed.append((url, str(e)))
                self.log_message(f"下载失败 {url}: {str(e)}")

        return downloaded, failed

    def start_crawling(self):
        """开始爬取"""
        url = self.url_entry.get().strip()
        save_path = self.save_path_entry.get().strip()

        if not url:
            messagebox.showerror("错误", "请输入网址")
            return

        if not url.startswith(('http://', 'https://')):
            messagebox.showerror("错误", "请输入有效的网址（以 http:// 或 https:// 开头）")
            return

        if not save_path:
            messagebox.showerror("错误", "请选择保存位置")
            return

        # 清空之前的数据
        self.clear_all()

        # 在后台线程中执行爬取
        self.log_message("=" * 50)
        self.log_message(f"开始爬取: {url}")
        self.log_message(f"保存位置: {save_path}")

        threading.Thread(
            target=self.crawl_thread,
            args=(url, save_path),
            daemon=True
        ).start()

    def crawl_thread(self, url, save_path):
        """爬取线程函数 — 支持翻页检测和多页爬取"""
        try:
            crawler = AutoCrawler(
                log_callback=self.log_message,
                force_js=self.use_js_var.get()
            )

            # Step 1: Detect pagination on the first page
            self.log_message("正在检测翻页机制...")
            pagination = crawler.detect_pagination(url)

            # Step 2: Determine which pages to crawl
            page_urls = [url]  # always include the current page
            if pagination['pages']:
                event = threading.Event()
                result = {}

                def show_dialog():
                    dlg = PaginationDialog(self.root, pagination)
                    result['choice'] = dlg.result
                    result['start'] = dlg.page_start
                    result['end'] = dlg.page_end
                    event.set()

                self.root.after(0, show_dialog)
                event.wait()

                choice = result.get('choice', 'current')
                if choice == 'all':
                    extras = [p['url'] for p in pagination['pages'] if p['url'] != url]
                    page_urls = [url] + extras
                    self.log_message(f"将爬取全部 {len(page_urls)} 页")
                elif choice == 'range':
                    s = result.get('start', 1)
                    e = result.get('end', 1)
                    selected = [p['url'] for idx, p in enumerate(pagination['pages'])
                                if s - 1 <= idx <= e - 1 and p['url'] != url]
                    page_urls = [url] + selected
                    self.log_message(f"将爬取 {len(page_urls)} 页 (范围 {s}-{e})")
                else:
                    self.log_message("仅爬取当前页")
            else:
                self.log_message("未检测到翻页机制")

            # Step 3: Crawl all pages
            all_image_urls = []
            total_pages = len(page_urls)

            for i, page_url in enumerate(page_urls):
                if total_pages > 1:
                    self.update_status(f"正在爬取第 {i + 1}/{total_pages} 页...")
                    self.log_message(f"正在爬取第 {i + 1}/{total_pages} 页: {page_url}")
                else:
                    self.update_status("正在提取图片...")

                page_images = crawler.extract_images(page_url)
                all_image_urls.extend(page_images)

            # Step 4: Deduplicate across pages
            seen = set()
            unique = []
            for img in all_image_urls:
                if img not in seen:
                    seen.add(img)
                    unique.append(img)

            dedup_count = len(all_image_urls) - len(unique)
            if dedup_count > 0:
                self.log_message(f"跨页去重移除 {dedup_count} 个重复图片")
            self.log_message(f"共提取到 {len(unique)} 张图片 ({total_pages} 页汇总)")

            if not unique:
                self.root.after(0, lambda: messagebox.showinfo("提示", "未找到图片"))
                return

            # Step 5: Download images
            session = requests.Session()
            downloaded, failed = self.download_images(unique, base_url=url, session=session)

            if not downloaded:
                self.root.after(0, lambda: messagebox.showwarning("警告", "没有图片被下载"))
                return

            # Step 6: Display images
            self.root.after(0, lambda: self.display_images(downloaded, failed, save_path))

            stats = (
                f"爬取完成!\n\n"
                f"成功: {len(downloaded)} 张\n"
                f"失败: {len(failed)} 张\n"
                f"总页数: {total_pages}\n\n"
                f"请勾选需要保存的图片并点击「保存选中图片」按钮"
            )
            self.root.after(0, lambda: messagebox.showinfo("完成", stats))

        except Exception as e:
            self.log_message(f"爬取过程出错: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"爬取失败: {str(e)}"))

    def display_images(self, images, failed, save_path):
        """显示图片预览"""
        self.crawled_images = images
        self.selected_images = set(range(len(images)))
        self.check_vars = []

        # 清空之前的标签页
        for tab in self.notebook.winfo_children():
            tab.destroy()

        # 分批显示图片（每页显示20张）
        batch_size = 20
        total_batches = (len(images) + batch_size - 1) // batch_size

        for batch in range(total_batches):
            batch_images = images[batch * batch_size:(batch + 1) * batch_size]
            page_frame = ttk.Frame(self.notebook)
            self.notebook.add(page_frame, text=f"第 {batch + 1}/{total_batches} 页")

            # 创建网格布局
            grid_frame = ttk.Frame(page_frame)
            grid_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            for idx, (url, temp_path) in enumerate(batch_images):
                # 创建图片容器
                container = ttk.Frame(grid_frame, relief=tk.RIDGE, borderwidth=1)
                container.grid(row=idx // 5, column=idx % 5, padx=5, pady=5, sticky="nsew")

                container.grid_columnconfigure(0, weight=1)
                container.grid_rowconfigure(0, weight=1)

                # 检查图片是否能打开
                try:
                    img = Image.open(temp_path)
                    # 调整图片大小
                    max_size = 150, 150
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    img_photo = ImageTk.PhotoImage(img)

                    # 标签页标签
                    label_frame = ttk.Frame(container)
                    label_frame.pack(fill=tk.X)

                    # 复选框
                    check_var = tk.BooleanVar(value=True)
                    self.check_vars.append(check_var)
                    check = ttk.Checkbutton(
                        label_frame,
                        variable=check_var,
                        command=lambda v=check_var, i=batch * batch_size + idx: self.toggle_selection(i, v)
                    )
                    check.pack(side=tk.LEFT)

                    # 图片标签
                    img_label = ttk.Label(label_frame, text=f"#{batch * batch_size + idx + 1}")
                    img_label.pack(side=tk.LEFT, padx=5)

                    # 图片显示
                    img_display = ttk.Label(container)
                    img_display.pack(fill=tk.BOTH, expand=True)

                    # 保存引用以防止被垃圾回收
                    img_display.img_photo = img_photo
                    img_display.img_path = temp_path
                    img_display.img_url = url
                    img_display.config(image=img_photo)

                except Exception as e:
                    error_label = ttk.Label(container, text=f"无法加载图片\n{str(e)}", foreground="red")
                    error_label.pack(fill=tk.BOTH, expand=True)

        self.notebook.select(0)
        self.log_message(f"显示了 {len(images)} 张图片")

    def toggle_selection(self, index, var):
        """切换图片选择状态"""
        if var.get():
            self.selected_images.add(index)
        else:
            self.selected_images.discard(index)

    def save_selected_images(self):
        """保存选中的图片"""
        if not self.crawled_images:
            messagebox.showwarning("警告", "没有可保存的图片")
            return

        if not self.selected_images:
            messagebox.showwarning("警告", "请先勾选要保存的图片")
            return

        save_path = self.save_path_entry.get().strip()
        if not save_path:
            messagebox.showerror("错误", "请选择保存位置")
            return

        # 确保保存目录存在
        os.makedirs(save_path, exist_ok=True)

        saved_count = 0
        for idx in sorted(self.selected_images):
            url, temp_path = self.crawled_images[idx]

            # 从URL提取文件名并清理污染后缀
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename or filename in ('', '.'):
                filename = f"image_{idx:04d}.jpg"
            else:
                name_part, ext = os.path.splitext(filename)
                ext_clean = re.search(
                    r'(\.(?:jpg|jpeg|png|gif|webp|bmp))', ext, re.IGNORECASE
                )
                if ext_clean:
                    ext = ext_clean.group(1)
                filename = f"{name_part}{ext}"

            # 添加时间戳避免重名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"

            # 复制到目标位置
            dest_path = os.path.join(save_path, filename)

            try:
                shutil.copy2(temp_path, dest_path)
                saved_count += 1
                self.log_message(f"已保存: {dest_path}")

            except Exception as e:
                self.log_message(f"保存失败 {temp_path}: {str(e)}")

        messagebox.showinfo("完成", f"成功保存了 {saved_count} 张图片到:\n{save_path}")
        self.log_message(f"保存了 {saved_count} 张图片")

    def clear_selection(self):
        """清空选择"""
        for var in self.check_vars:
            var.set(False)
        self.selected_images.clear()
        self.log_message("已清空选择")

    def clear_all(self):
        """清空所有数据"""
        self.crawled_images = []
        self.selected_images.clear()
        self.check_vars = []
        # 清理并重建临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)
        for tab in self.notebook.winfo_children():
            tab.destroy()
        self.log_text.delete(1.0, tk.END)


def main():
    root = tk.Tk()
    app = ImageCrawlerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
