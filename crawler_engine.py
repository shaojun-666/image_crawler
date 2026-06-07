#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片爬虫引擎模块
支持静态页面解析和JS动态渲染页面爬取
支持多种图片提取方式：
  - <img> 标签 (src, data-src, data-lazy-src, data-echo, data-url ...)
  - CSS background-image (内联样式 + 计算样式)
  - <picture>/<source> 响应式图片
  - <img srcset>/data-srcset 响应式属性
  - <video poster> 封面图
  - <svg image> 矢量图内嵌图片
  - og:image / twitter:image / msapplication-TileImage 元标签
  - <style> 样式块中的 background-image
  - <link rel="preload" as="image"> 预加载图片
  - <link rel="icon/apple-touch-icon"> 网站图标
  - <noscript> 降级图片
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


def _ensure_playwright_browsers_path():
    """确保PLAYWRIGHT_BROWSERS_PATH已设置，默认指向D:\\Apps"""
    if not os.environ.get('PLAYWRIGHT_BROWSERS_PATH'):
        test_path = r'D:\\Apps'
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


# ---------- CSS background-image URL 提取 ----------

_CSS_URL_RE = re.compile(
    r'url\(\s*(?:"([^"]*)"|\'([^\']*)\'|([^)]+?))\s*\)',
    re.IGNORECASE
)


def _extract_urls_from_css(css_text):
    """从CSS文本中提取所有 url() 中的URL"""
    urls = []
    for m in _CSS_URL_RE.finditer(css_text):
        url = m.group(1) or m.group(2) or m.group(3)
        if url and url.strip():
            urls.append(url.strip())
    return urls


# ---------- 图片URL校验 ----------

_IMAGE_EXT_RE = re.compile(r'\.(avif|bmp|gif|heic|heif|ico|jpe?g|png|svg|tiff?|webp)', re.IGNORECASE)


def _has_image_ext(url):
    """检查URL路径是否包含图片扩展名"""
    return bool(_IMAGE_EXT_RE.search(urlparse(url).path.lower()))


# ---------- srcset 解析 ----------

def _parse_srcset(srcset_str, base_url):
    """解析 srcset 属性，返回绝对URL列表"""
    urls = []
    for part in srcset_str.split(','):
        part = part.strip()
        if not part:
            continue
        url = part.split()[0] if ' ' in part else part
        if url:
            full_url = urljoin(base_url, url)
            if full_url:
                urls.append(full_url)
    return urls


# ---------- 常见的图片懒加载属性 ----------

_IMG_LAZY_ATTRS = (
    'src', 'data-src', 'data-lazy-src', 'data-original',
    'data-lazy', 'data-echo', 'data-url', 'data-sources',
)


# ====================================================================


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
        """提取静态页面中的所有图片URL — 自动调用多种提取器"""
        images = []
        try:
            self.log(f"正在访问: {url}")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            self.log(f"访问成功，状态码: {response.status_code}")

            soup = BeautifulSoup(response.text, 'html.parser')

            extractors = [
                ('img标签', self._extract_img_tags),
                ('CSS background-image(内联样式)', self._extract_inline_backgrounds),
                ('picture/source标签', self._extract_picture_sources),
                ('video poster', self._extract_video_posters),
                ('og:image等元标签', self._extract_meta_images),
                ('CSS样式块', self._extract_style_backgrounds),
                ('link预加载/图标', self._extract_link_images),
                ('noscript降级', self._extract_noscript_images),
            ]

            for name, extractor in extractors:
                found = extractor(soup, url)
                if found:
                    self.log(f"  [{name}] 找到 {len(found)} 张")
                    images.extend(found)

            # 去重（保持顺序）
            seen = set()
            unique = []
            for img in images:
                if img not in seen:
                    seen.add(img)
                    unique.append(img)

            self.log(f"共提取到 {len(unique)} 个有效图片")
            return unique, response.text

        except Exception as e:
            self.log(f"静态提取失败: {str(e)}")
            return [], ""

    # ---------- 各种提取方法 ----------

    def _extract_img_tags(self, soup, base_url):
        """<img> 标签：src / data-src / srcset 等"""
        images = []
        for img in soup.find_all('img'):
            # 懒加载属性
            for attr in _IMG_LAZY_ATTRS:
                val = img.get(attr)
                if val:
                    full_url = urljoin(base_url, val)
                    if full_url and _has_image_ext(full_url):
                        images.append(full_url)
                        break
            # srcset / data-srcset
            for sattr in ('srcset', 'data-srcset'):
                val = img.get(sattr)
                if val:
                    images.extend(_parse_srcset(val, base_url))
        return images

    def _extract_inline_backgrounds(self, soup, base_url):
        """内联 style 中的 background-image: url(...)"""
        images = []
        for tag in soup.find_all(style=True):
            style = tag.get('style', '')
            if 'background' not in style.lower():
                continue
            for url in _extract_urls_from_css(style):
                full_url = urljoin(base_url, url)
                if full_url and not full_url.startswith('data:'):
                    images.append(full_url)
        return images

    def _extract_picture_sources(self, soup, base_url):
        """<picture> / <source> 响应式图片"""
        images = []
        for picture in soup.find_all('picture'):
            for source in picture.find_all('source'):
                for attr in ('srcset', 'data-srcset'):
                    val = source.get(attr)
                    if val:
                        images.extend(_parse_srcset(val, base_url))
            img = picture.find('img')
            if img:
                for attr in _IMG_LAZY_ATTRS:
                    val = img.get(attr)
                    if val:
                        full_url = urljoin(base_url, val)
                        if full_url and _has_image_ext(full_url):
                            images.append(full_url)
                            break
        return images

    def _extract_video_posters(self, soup, base_url):
        """<video poster> 封面图"""
        images = []
        for video in soup.find_all('video'):
            poster = video.get('poster')
            if poster:
                full_url = urljoin(base_url, poster)
                if full_url and not full_url.startswith('data:'):
                    images.append(full_url)
        return images

    def _extract_meta_images(self, soup, base_url):
        """<meta> 标签图片 (og:image / twitter:image / msapplication-TileImage)"""
        images = []
        patterns = [
            ('property', re.compile(r'og:image', re.I)),
            ('name', re.compile(r'twitter:image', re.I)),
            ('name', re.compile(r'msapplication-TileImage', re.I)),
        ]
        for attr_name, pattern in patterns:
            if attr_name == 'property':
                metas = soup.find_all('meta', property=pattern)
            else:
                metas = soup.find_all('meta', attrs={attr_name: pattern})
            for meta in metas:
                content = meta.get('content')
                if content:
                    full_url = urljoin(base_url, content)
                    if full_url:
                        images.append(full_url)
        return images

    def _extract_style_backgrounds(self, soup, base_url):
        """<style> 样式块中的 background-image"""
        images = []
        for style_tag in soup.find_all('style'):
            if not style_tag.string:
                continue
            text = style_tag.string
            if 'background' not in text.lower():
                continue
            for url in _extract_urls_from_css(text):
                full_url = urljoin(base_url, url)
                if full_url and not full_url.startswith('data:'):
                    images.append(full_url)
        return images

    def _extract_link_images(self, soup, base_url):
        """<link> 预加载图片、favicon、apple-touch-icon"""
        images = []
        for link in soup.find_all('link', attrs={'rel': 'preload', 'as': 'image'}):
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                if full_url and _has_image_ext(full_url):
                    images.append(full_url)
        for link in soup.find_all('link', attrs={'rel': re.compile(r'icon|apple-touch-icon', re.I)}):
            href = link.get('href')
            if href:
                full_url = urljoin(base_url, href)
                if full_url:
                    images.append(full_url)
        return images

    def _extract_noscript_images(self, soup, base_url):
        """<noscript> 中降级提供的 <img>"""
        images = []
        for noscript in soup.find_all('noscript'):
            try:
                content = noscript.decode_contents()
                if not content:
                    continue
                ns_soup = BeautifulSoup(content, 'html.parser')
                for img in ns_soup.find_all('img'):
                    for attr in _IMG_LAZY_ATTRS:
                        val = img.get(attr)
                        if val:
                            full_url = urljoin(base_url, val)
                            if full_url and _has_image_ext(full_url):
                                images.append(full_url)
                                break
            except Exception:
                pass
        return images

    # ---------- 辅助方法 ----------

    @staticmethod
    def _is_valid_image_url(url):
        return _has_image_ext(url)

    @staticmethod
    def check_js_required(html_text, img_count):
        """检测页面是否依赖JS渲染（启发式）"""
        if img_count > 0 and len(html_text) > 500:
            return False

        spa_roots = ['id="root"', 'id="app"', 'id="__next"', 'id="__nuxt"']
        if any(root in html_text for root in spa_roots):
            for root in spa_roots:
                pattern = re.compile(
                    rf'{re.escape(root)}[^>]*>\s*</',
                    re.IGNORECASE
                )
                if pattern.search(html_text):
                    return True

        js_indicators = ['/static/js/main.', 'react', 'vue', 'angular', 'react-dom']
        script_count = sum(html_text.count(s) for s in js_indicators)
        if script_count > 3:
            return True

        if 'Just a moment' in html_text or 'cf-browser-verification' in html_text:
            return True

        return False


# ====================================================================


# 在浏览器页面上下文中执行的 JS 综合提取脚本
# （JSCrawler 通过 page.evaluate() 调用）
EXTRACTION_SCRIPT = r"""
() => {
    const urls = new Set();
    const baseUrl = document.baseURI || location.href;

    const resolve = (url) => {
        try { return new URL(url, baseUrl).href; } catch(e) { return null; }
    };

    const extractSrcset = (srcset) => {
        if (!srcset) return;
        srcset.split(',').forEach(part => {
            part = part.trim();
            if (!part) return;
            const url = part.split(/\s+/)[0];
            if (url) {
                const r = resolve(url);
                if (r) urls.add(r);
            }
        });
    };

    const extractBg = (bgValue) => {
        if (!bgValue || bgValue === 'none') return;
        const re = /url\(["']?([^"')]+)["']?\)/g;
        let m;
        while ((m = re.exec(bgValue)) !== null) {
            const r = resolve(m[1].trim());
            if (r) urls.add(r);
        }
    };

    /* 1. <img> tags */
    const imgAttrs = ['src','data-src','data-lazy-src','data-original','data-lazy','data-echo','data-url'];
    document.querySelectorAll('img').forEach(img => {
        for (const attr of imgAttrs) {
            const val = img.getAttribute(attr);
            if (val) { const r = resolve(val); if (r) { urls.add(r); break; } }
        }
        extractSrcset(img.getAttribute('srcset'));
        extractSrcset(img.getAttribute('data-srcset'));
    });

    /* 2. CSS background-image (inline styles) */
    document.querySelectorAll('[style*="background"]').forEach(el => {
        extractBg(el.style.backgroundImage);
    });

    /* 3. CSS background-image (computed styles on image-related class names) */
    document.querySelectorAll(
        '[class*="bg"],[class*="image"],[class*="thumb"],[class*="photo"],' +
        '[class*="img"],[class*="cover"],[class*="preview"],[class*="gallery"]'
    ).forEach(el => {
        extractBg(getComputedStyle(el).backgroundImage);
    });

    /* 4. picture / source */
    document.querySelectorAll('source[srcset],source[data-srcset]').forEach(source => {
        extractSrcset(source.getAttribute('srcset') || source.getAttribute('data-srcset'));
    });

    /* 5. video poster */
    document.querySelectorAll('video[poster]').forEach(v => {
        const r = resolve(v.getAttribute('poster'));
        if (r) urls.add(r);
    });

    /* 6. svg image */
    document.querySelectorAll('image[href],image[xlink\:href]').forEach(svgImg => {
        const href = svgImg.getAttribute('href') || svgImg.getAttribute('xlink:href');
        if (href) { const r = resolve(href); if (r) urls.add(r); }
    });

    /* 7. meta og:image / twitter:image */
    ['meta[property="og:image"]','meta[name="twitter:image"]','meta[name="msapplication-TileImage"]'
    ].forEach(sel => {
        const el = document.querySelector(sel);
        if (el) {
            const content = el.getAttribute('content');
            if (content) { const r = resolve(content); if (r) urls.add(r); }
        }
    });

    /* 8. link preload / icon */
    document.querySelectorAll('link[rel="preload"][as="image"]').forEach(link => {
        const href = link.getAttribute('href');
        if (href) { const r = resolve(href); if (r) urls.add(r); }
    });
    document.querySelectorAll('link[rel*="icon"],link[rel*="apple-touch-icon"]').forEach(link => {
        const href = link.getAttribute('href');
        if (href) { const r = resolve(href); if (r) urls.add(r); }
    });

    return Array.from(urls);
}
"""


class JSCrawler:
    """JS动态渲染页面图片提取器（基于 Playwright）"""

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

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
            window.chrome = { runtime: {} };
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

        total_height = page.evaluate('document.body.scrollHeight')
        viewport_height = page.evaluate('window.innerHeight')
        scroll_step = max(1, total_height // self.max_scrolls)

        for scroll_num in range(self.max_scrolls):
            scroll_to = (scroll_num + 1) * scroll_step
            page.evaluate(f'window.scrollTo(0, {scroll_to})')

            time.sleep(self.scroll_delay)

            try:
                page.wait_for_load_state('networkidle', timeout=5000)
            except Exception:
                pass

            urls = page.evaluate(EXTRACTION_SCRIPT)

            for u in urls:
                if u and not u.startswith('data:'):
                    all_urls.add(u)

            new_height = page.evaluate('document.body.scrollHeight')
            current_scroll = page.evaluate('window.scrollY + window.innerHeight')
            if current_scroll >= new_height:
                self.log(f"已到达页面底部，提前结束 (第 {scroll_num + 1} 次)")
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


# ====================================================================


class AutoCrawler:
    """智能图片提取器 — 自动判断是否需要JS渲染"""

    def __init__(self, log_callback=None, force_js=False):
        self.log = log_callback or (lambda msg: None)
        self.force_js = force_js

    def extract_images(self, url):
        """提取图片URL，自动选择提取方式"""
        if self.force_js:
            self.log("已启用JS渲染模式，直接使用浏览器提取")
            return self._js_extract(url)

        self.log("尝试静态页面提取...")
        static_crawler = StaticCrawler(log_callback=self.log)
        images, html = static_crawler.extract_images(url)

        if images:
            self.log(f"静态提取成功，找到 {len(images)} 张图片")
            return images

        self.log("静态提取未找到图片，检测页面是否依赖JS渲染...")
        needs_js = StaticCrawler.check_js_required(html, len(images))

        if needs_js:
            self.log("检测到页面依赖JS渲染，切换到浏览器模式...")
            return self._js_extract(url)
        else:
            self.log("页面不依赖JS渲染，但未找到图片")
            return []

    def _js_extract(self, url):
        js_crawler = JSCrawler(log_callback=self.log)
        return js_crawler.extract_images(url)
