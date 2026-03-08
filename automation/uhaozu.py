# -*- coding: utf-8 -*-
"""
U号租商户端自动化操作
使用 Playwright (异步) 实现账号登录、换号、选号等功能
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class UHaozuAutomation:
    """U号租商户端自动化操作"""

    BASE_URL = "https://b.uhaozu.com"

    def __init__(self, username: str, password: str, cookies: Optional[dict] = None):
        self.username = username
        self.password = password
        self.cookies = cookies or {}
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_browser(self):
        """启动浏览器（如果尚未启动）"""
        from playwright.async_api import async_playwright

        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)

        if self._context is None:
            self._context = await self._browser.new_context()
            # 恢复保存的 cookies
            if self.cookies:
                cookie_list = [
                    {
                        "name": k,
                        "value": v,
                        "domain": "b.uhaozu.com",
                        "path": "/",
                    }
                    for k, v in self.cookies.items()
                ]
                await self._context.add_cookies(cookie_list)

        if self._page is None:
            self._page = await self._context.new_page()

    async def close(self):
        """关闭浏览器"""
        try:
            if self._page:
                await self._page.close()
                self._page = None
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if hasattr(self, "_playwright"):
                await self._playwright.stop()
        except Exception as e:
            logger.warning("关闭浏览器时出错: %s", e)

    async def login(self) -> bool:
        """
        登录U号租，保存cookies
        访问 https://b.uhaozu.com，填写账号密码登录，保存cookies
        """
        try:
            await self._ensure_browser()
            page = self._page

            await page.goto(self.BASE_URL, wait_until="networkidle", timeout=30000)

            # 检查是否已在登录状态
            if await self.check_login_status():
                logger.info("账号 %s 已处于登录状态", self.username)
                return True

            # 定位账号输入框并填写
            username_input = page.locator(
                'input[name="username"], input[placeholder*="账号"]'
            ).first
            await username_input.fill(self.username)
            password_input = page.locator(
                'input[name="password"], input[placeholder*="密码"], input[type="password"]'
            ).first
            await password_input.fill(self.password)

            # 点击登录按钮
            await page.locator('button[type="submit"], button:has-text("登录")').first.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

            # 验证是否登录成功
            if "login" in page.url.lower() or "signin" in page.url.lower():
                logger.warning("账号 %s 登录失败，仍在登录页", self.username)
                return False

            # 保存 cookies
            all_cookies = await self._context.cookies()
            self.cookies = {c["name"]: c["value"] for c in all_cookies}
            logger.info("账号 %s 登录成功", self.username)
            return True

        except Exception as e:
            logger.error("账号 %s 登录异常: %s", self.username, e)
            return False

    async def check_login_status(self) -> bool:
        """
        检测是否在线（访问首页检查是否跳转登录页）
        """
        try:
            await self._ensure_browser()
            page = self._page

            await page.goto(self.BASE_URL, wait_until="networkidle", timeout=20000)
            current_url = page.url.lower()

            is_logged_in = "login" not in current_url and "signin" not in current_url
            logger.debug("账号 %s 登录状态: %s (url: %s)", self.username, is_logged_in, page.url)
            return is_logged_in

        except Exception as e:
            logger.error("检测登录状态异常: %s", e)
            return False

    async def get_balance(self) -> float:
        """
        获取账户余额
        从页面右上角余额区域获取数字
        """
        try:
            await self._ensure_browser()
            page = self._page

            if not await self.check_login_status():
                return 0.0

            # 尝试多种选择器获取余额
            selectors = [
                ".balance",
                "[class*='balance']",
                "[class*='余额']",
                ".user-balance",
                ".account-balance",
            ]
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    text = await el.text_content(timeout=3000)
                    if text:
                        # 提取数字
                        import re
                        nums = re.findall(r"\d+\.?\d*", text)
                        if nums:
                            return float(nums[0])
                except Exception:
                    continue

            return 0.0

        except Exception as e:
            logger.error("获取余额异常: %s", e)
            return 0.0

    async def exchange_number(self, pdd_order_id: str) -> dict:
        """
        自动换号
        访问 https://b.uhaozu.com/key-exchange
        输入拼多多订单号，点击一键换货
        返回 {"success": bool, "message": str, "new_account": str}
        """
        try:
            await self._ensure_browser()
            page = self._page

            if not await self.check_login_status():
                success = await self.login()
                if not success:
                    return {"success": False, "message": "登录失败", "new_account": ""}

            await page.goto(f"{self.BASE_URL}/key-exchange", wait_until="networkidle", timeout=30000)

            # 输入拼多多订单号
            order_input = page.locator(
                'input[placeholder*="订单"], input[placeholder*="order"], input[name*="order"]'
            ).first
            await order_input.fill(pdd_order_id)

            # 点击换货按钮
            await page.locator(
                'button:has-text("换货"), button:has-text("一键换货"), button:has-text("换号")'
            ).first.click()
            await page.wait_for_load_state("networkidle", timeout=15000)

            # 获取结果提示
            result_sel = ".result, .success, .error, [class*='result'], [class*='message']"
            try:
                result_el = page.locator(result_sel).first
                result_text = await result_el.text_content(timeout=5000)
            except Exception:
                result_text = ""

            # 尝试获取新账号信息
            new_account = ""
            account_sel = "[class*='account'], [class*='号码'], .new-account"
            try:
                acc_el = page.locator(account_sel).first
                new_account = await acc_el.text_content(timeout=3000) or ""
                new_account = new_account.strip()
            except Exception:
                pass

            success = bool(result_text) and "成功" in result_text
            return {
                "success": success,
                "message": result_text.strip() if result_text else "换号操作已执行",
                "new_account": new_account,
            }

        except Exception as e:
            logger.error("换号异常 (订单 %s): %s", pdd_order_id, e)
            return {"success": False, "message": str(e), "new_account": ""}

    async def search_numbers(self, game: str, filters: dict) -> list:
        """
        自动选号 - 在开单助手搜索符合条件的号
        访问 https://b.uhaozu.com/opening-order
        选择游戏、筛选条件
        返回号码列表 [{"id": str, "title": str, "price": float, "role": str}]
        """
        try:
            await self._ensure_browser()
            page = self._page

            if not await self.check_login_status():
                success = await self.login()
                if not success:
                    return []

            await page.goto(f"{self.BASE_URL}/opening-order", wait_until="networkidle", timeout=30000)

            # 选择游戏
            game_sel = f'[class*="game"]:has-text("{game}"), li:has-text("{game}"), .game-item:has-text("{game}")'
            try:
                await page.click(game_sel, timeout=5000)
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                logger.warning("未找到游戏选项: %s", game)

            # 应用筛选条件
            filter_map = {
                "no_deposit": "无押金",
                "time_rental_bonus": "时租满送",
                "login_tool": "登号器",
                "anti_addiction": "防沉迷",
                "non_cloud": "非云",
                "high_login_rate": "上号率高",
                "no_friend_add": "禁言",
                "allow_ranked": "排位赛允许",
            }
            for key, label in filter_map.items():
                if filters.get(key):
                    try:
                        checkbox_sel = f'[class*="filter"]:has-text("{label}"), label:has-text("{label}")'
                        checkbox = page.locator(checkbox_sel).first
                        if not await checkbox.is_checked():
                            await checkbox.click()
                    except Exception:
                        pass

            # 等待结果加载
            await page.wait_for_timeout(2000)

            # 抓取结果列表
            results = []
            import re
            item_sel = ".product-item, .card-item, [class*='item'], li[class*='product']"
            items = await page.locator(item_sel).all()
            for item in items[:20]:  # 最多取20条
                try:
                    title = await item.locator("[class*='title'], h3, .name").first.text_content(timeout=2000)
                    price_text = await item.locator("[class*='price'], .price").first.text_content(timeout=2000)
                    price_nums = re.findall(r"\d+\.?\d*", price_text or "")
                    price = float(price_nums[0]) if price_nums else 0.0
                    role_text = ""
                    try:
                        role_text = await item.locator("[class*='role'], .role").first.text_content(timeout=1000) or ""
                    except Exception:
                        pass
                    item_id = await item.get_attribute("data-id") or ""
                    results.append({
                        "id": item_id,
                        "title": (title or "").strip(),
                        "price": price,
                        "role": role_text.strip(),
                    })
                except Exception:
                    continue

            return results

        except Exception as e:
            logger.error("搜索号码异常: %s", e)
            return []

    async def place_order(self, product_id: str) -> dict:
        """
        按商品编号下单
        返回 {"success": bool, "account": str, "password": str}
        """
        try:
            await self._ensure_browser()
            page = self._page

            if not await self.check_login_status():
                success = await self.login()
                if not success:
                    return {"success": False, "account": "", "password": ""}

            # 定位商品并下单
            await page.goto(f"{self.BASE_URL}/opening-order", wait_until="networkidle", timeout=30000)

            # 找到对应商品并点击下单
            item_sel = f'[data-id="{product_id}"]'
            try:
                order_btn = page.locator(item_sel).locator('button:has-text("下单"), button:has-text("购买")').first
                await order_btn.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                return {"success": False, "account": "", "password": ""}

            # 获取账号密码
            account_text = ""
            password_text = ""
            try:
                account_text = await page.locator("[class*='account-info'] .account, [class*='account-num']").first.text_content(timeout=5000) or ""
                password_text = await page.locator("[class*='account-info'] .password, [class*='account-pwd']").first.text_content(timeout=5000) or ""
            except Exception:
                pass

            return {
                "success": True,
                "account": account_text.strip(),
                "password": password_text.strip(),
            }

        except Exception as e:
            logger.error("下单异常 (商品 %s): %s", product_id, e)
            return {"success": False, "account": "", "password": ""}
