#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片爬虫引擎模块
支持静态页面解析和JS动态渲染页面爬取
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


def _ensure_playwright_browsers_path():
    """确保PLAYWRIGHT_BROWSERS_PATH已设置，默认指向D:\Apps"""
    if not os.environ.get('PLAYWRIGHT_BROWSERS_PATH'):
        test_path = r'D:\Apps'
        if os.path.isdir(test_path):
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = test_path


def check_playwright_available():
    """检查Playwright和Chromium浏览器是否可用"""
    try:
        _ensure_playwright_browsers_path()
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            chromium_path = p.chromium.executable_path
            if chromium_path and os.path.exists(chromium_path):
                return True, "Playwright可用"
            return False, "未找到Chromium浏览器，请运行: playwright install chromium"
    except ImportError:
        return False, "未安装Playwright，请运行: pip install playwright"
    except Exception as e:
        return False, f"Playwright初始化失败: {e}"


class StaticCrawler:
    """静态页面图片提取器（基于 requests + BeautifulSoup）"""

    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg: None)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })

    def extract_images(self, url):
        """提取静态页面中的所有图片URL"""
        images = []
        try:
            self.log(f"正在访问: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            self.log(f"访问成功，状态码: {response.status_code}")

            soup = BeautifulSoup(response.text, 'html.parser')
            img_tags = soup.find_all('img')
            self.log(f"找到 {len(img_tags)} 个图片标签")

            for img_tag in img_tags:
                img_url = img_tag.get('src') or img_tag.get('data-src')
                if not img_url:
                    continue
                img_url = urljoin(url, img_url)
                if self._is_valid_image_url(img_url):
                    images.append(img_url)

            self.log(f"提取到 {len(images)} 个有效图片")
            return images, response.text

        except Exception as e:
            self.log(f"静态提取失败: {str(e)}")
            return [], ""

    @staticmethod
    def _is_valid_image_url(url):
        """检查URL是否是有效的图片地址"""
        path = urlparse(url).path.lower()
        return bool(re.search(r'\.(jpg|jpeg|png|gif|webp|bmp)', path))

    @staticmethod
    def check_js_required(html_text, img_count):
        """检测页面是否依赖JS渲染（启发式）"""
        if img_count > 0 and len(html_text) > 500:
            return False

        # 检测SPA容器
        spa_roots = ['id="root"', 'id="app"', 'id="__next"', 'id="__nuxt"']
        if any(root in html_text for root in spa_roots):
            # 检查这些容器内是否有内容
            for root in spa_roots:
                pattern = re.compile(
                    rf'{re.escape(root)}[^>]*>\s*</',
                    re.IGNORECASE
                )
                if pattern.search(html_text):
                    return True

        # 检测大量JS框架脚本
        js_indicators = ['/static/js/main.', 'react', 'vue', 'angular', 'react-dom']
        script_count = sum(html_text.count(s) for s in js_indicators)
        if script_count > 3:
            return True

        # 检测Cloudflare验证页面
        if 'Just a moment' in html_text or 'cf-browser-verification' in html_text:
            return True

        return False


class JSCrawler:
    """JS动态渲染页面图片提取器（基于 Playwright）"""

    IMG_ATTRS = [
        'src', 'data-src', 'data-lazy-src', 'data-original',
        'data-srcset', 'data-sources', 'data-lazy',
    ]

    def __init__(self, log_callback=None, headless=True, scroll_delay=0.8,
                 max_scrolls=10, timeout=30000):
        self.log = log_callback or (lambda msg: None)
        self.headless = headless
        self.scroll_delay = scroll_delay
        self.max_scrolls = max_scrolls
        self.timeout = timeout
        self._playwright = None
        self._browser = None

    def extract_images(self, url):
        """使用浏览器渲染页面并提取图片URL"""
        try:
            _ensure_playwright_browsers_path()
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )

            context = self._create_stealth_context()
            page = context.new_page()
            page.set_default_timeout(self.timeout)

            self.log(f"浏览器正在加载: {url}")
            page.goto(url, wait_until='networkidle', timeout=self.timeout)
            self.log(f"页面加载完成，标题: {page.title()}")

            images = self._scroll_and_collect(page)
            self.log(f"JS渲染提取到 {len(images)} 个图片")

            page.close()
            context.close()
            return images

        except Exception as e:
            self.log(f"JS渲染提取失败: {str(e)}")
            return []

        finally:
            self._close_resources()

    def _create_stealth_context(self):
        """创建反检测浏览器上下文"""
        context = self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
            permissions=['notifications'],
            device_scale_factor=1,
            extra_http_headers={
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        )

        # 注入反检测脚本
        context.add_init_script("""
            // 隐藏 webdriver 属性
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            // 模拟插件
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            // 模拟语言
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
            // 模拟 Chrome 运行时
            window.chrome = { runtime: {} };
            // 覆盖权限查询
            const originalQuery = navigator.permissions.query;
            navigator.permissions.query = (params) => (
                params.name === 'notifications'
                    ? Promise.resolve({ state: 'prompt' })
                    : originalQuery(params)
            );
        """)

        return context

    def _scroll_and_collect(self, page):
        """滚动页面并收集所有图片URL"""
        all_urls = set()

        # 获取页面总高度
        total_height = page.evaluate('document.body.scrollHeight')
        viewport_height = page.evaluate('window.innerHeight')
        scroll_step = max(1, total_height // self.max_scrolls)

        for scroll_num in range(self.max_scrolls):
            scroll_to = (scroll_num + 1) * scroll_step
            page.evaluate(f'window.scrollTo(0, {scroll_to})')

            import time
            time.sleep(self.scroll_delay)

            # 等待网络空闲
            try:
                page.wait_for_load_state('networkidle', timeout=5000)
            except Exception:
                pass

            # 提取当前可见的图片URL
            urls = page.evaluate(f"""
                () => {{
                    const attrs = {self.IMG_ATTRS};
                    const urls = new Set();
                    document.querySelectorAll('img').forEach(img => {{
                        for (const attr of attrs) {{
                            const val = img.getAttribute(attr);
                            if (val && val.startsWith('http')) {{
                                urls.add(val);
                                break;
                            }}
                        }}
                    }});
                    return Array.from(urls);
                }}
            """)

            for u in urls:
                if StaticCrawler._is_valid_image_url(u):
                    all_urls.add(u)

            # 检查是否已到页面底部
            new_height = page.evaluate('document.body.scrollHeight')
            current_scroll = page.evaluate('window.scrollY + window.innerHeight')
            if current_scroll >= new_height:
                self.log(f"已到达页面底部，提前结束滚动 (第 {scroll_num + 1} 次)")
                break

        return list(all_urls)

    def _close_resources(self):
        """清理浏览器资源"""
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._browser = None
        self._playwright = None


class AutoCrawler:
    """智能图片提取器 - 自动判断是否需要JS渲染"""

    def __init__(self, log_callback=None, force_js=False):
        self.log = log_callback or (lambda msg: None)
        self.force_js = force_js

    def extract_images(self, url):
        """提取图片URL，自动选择提取方式"""
        if self.force_js:
            self.log("已启用JS渲染模式，直接使用浏览器提取")
            return self._js_extract(url)

        # 先尝试静态提取
        self.log("尝试静态页面提取...")
        static_crawler = StaticCrawler(log_callback=self.log)
        images, html = static_crawler.extract_images(url)

        if images:
            self.log(f"静态提取成功，找到 {len(images)} 张图片")
            return images

        # 静态提取失败，检测是否需要JS
        self.log("静态提取未找到图片，检测页面是否依赖JS渲染...")
        needs_js = StaticCrawler.check_js_required(html, len(images))

        if needs_js:
            self.log("检测到页面依赖JS渲染，切换到浏览器模式...")
            return self._js_extract(url)
        else:
            self.log("页面不依赖JS渲染，但未找到图片")
            return []

    def _js_extract(self, url):
        """使用JS渲染提取图片"""
        js_crawler = JSCrawler(log_callback=self.log)
        return js_crawler.extract_images(url)
