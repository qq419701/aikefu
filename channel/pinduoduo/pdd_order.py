# -*- coding: utf-8 -*-
import asyncio, logging, time
import aiohttp

logger = logging.getLogger(__name__)

ORDER_API_URL = 'https://mms.pinduoduo.com/mangkhut/mms/recentOrderList'
ORDER_SYNC_INTERVAL = 300

ORDER_STATUS_MAP = {
    0: '待付款', 1: '待发货', 2: '已发货', 3: '已完成',
    4: '已取消', 5: '退款中', 6: '已退款', 7: '纠纷中',
}

class PddOrderCollector:
    def __init__(self, shop_id, db_client=None):
        self.shop_id = shop_id
        self.db_client = db_client
        self._running = False

    def _build_headers(self, cookies):
        cookie_str = '; '.join(f'{k}={v}' for k, v in cookies.items())
        return {
            'Cookie': cookie_str,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://mms.pinduoduo.com/',
            'Content-Type': 'application/json',
            'Origin': 'https://mms.pinduoduo.com',
        }

    async def fetch_orders(self, cookies, page=1, page_size=20):
        """
        POST https://mms.pinduoduo.com/mangkhut/mms/recentOrderList
        """
        now = int(time.time())
        # 近90天
        payload = {
            'orderType': 0,
            'afterSaleType': 0,
            'remarkStatus': -1,
            'urgeShippingStatus': -1,
            'groupStartTime': now - 90 * 86400,
            'groupEndTime': now,
            'pageNumber': page,
            'pageSize': page_size,
            'hideRegionBlackDelayShipping': False,
            'mobileMarkSearch': False,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ORDER_API_URL,
                    json=payload,
                    headers=self._build_headers(cookies),
                    timeout=aiohttp.ClientTimeout(total=15),
                    ssl=False,
                ) as resp:
                    if resp.status != 200:
                        logger.warning('订单接口返回 %d', resp.status)
                        return []
                    data = await resp.json(content_type=None)

            if not data.get('success'):
                logger.warning('获取订单失败: %s', data.get('error_msg') or data.get('errorMsg'))
                return []

            result = data.get('result') or data.get('data') or {}
            if isinstance(result, dict):
                orders = result.get('orderList') or result.get('list') or result.get('orders') or []
            elif isinstance(result, list):
                orders = result
            else:
                orders = []

            logger.info('店铺 %s 获取订单 %d 条 (第%d页)', self.shop_id, len(orders), page)
            return self._normalize_orders(orders)

        except Exception as e:
            logger.error('获取订单列表异常: %s', e)
            return []

    def _normalize_orders(self, raw_orders):
        normalized = []
        for order in raw_orders:
            try:
                # 买家信息
                buyer_id = str(
                    order.get('buyerId') or order.get('buyer_id') or
                    order.get('buyerUid') or ''
                )
                buyer_name = str(
                    order.get('buyerNick') or order.get('buyer_name') or
                    order.get('buyerName') or ''
                )
                # 订单号
                order_sn = str(
                    order.get('orderSn') or order.get('order_sn') or
                    order.get('sn') or ''
                )
                # 商品信息（可能是列表）
                goods_list = order.get('goodsList') or order.get('goods_list') or []
                if goods_list and isinstance(goods_list, list):
                    goods_name = goods_list[0].get('goodsName') or goods_list[0].get('name') or ''
                    goods_count = sum(g.get('goodsCount', 1) or g.get('count', 1) for g in goods_list)
                else:
                    goods_name = str(order.get('goodsName') or order.get('goods_name') or '')
                    goods_count = int(order.get('goodsCount') or order.get('goods_count') or 1)

                normalized.append({
                    'order_sn': order_sn,
                    'order_status': int(order.get('orderStatus') or order.get('order_status') or 0),
                    'goods_name': goods_name,
                    'goods_count': goods_count,
                    'goods_price': int(order.get('goodsPrice') or order.get('goods_price') or 0),
                    'pay_amount': int(order.get('payAmount') or order.get('pay_amount') or 0),
                    'buyer_id': buyer_id,
                    'buyer_name': buyer_name,
                    'receiver_name': str(order.get('receiverName') or order.get('receiver_name') or ''),
                    'receiver_phone': str(order.get('receiverPhone') or order.get('receiver_phone') or ''),
                    'receiver_address': str(order.get('receiverAddress') or order.get('receiver_address') or ''),
                    'created_time': order.get('createdTime') or order.get('created_time'),
                    'pay_time': order.get('payTime') or order.get('pay_time'),
                    'remark': str(order.get('remark') or ''),
                })
            except Exception as e:
                logger.debug('订单标准化失败: %s | %s', e, str(order)[:100])
        return normalized

    async def sync_orders(self, cookies):
        """全量同步近90天订单"""
        logger.info('开始同步店铺 %s 的订单...', self.shop_id)
        page = 1
        total = 0
        while True:
            orders = await self.fetch_orders(cookies, page=page, page_size=20)
            if not orders:
                break
            for o in orders:
                if self.db_client:
                    self.db_client.insert_order(self.shop_id, o)
                    total += 1
            if len(orders) < 20:
                break
            page += 1
            await asyncio.sleep(1)
        logger.info('店铺 %s 订单同步完成，共 %d 条', self.shop_id, total)
        return total

    async def watch_new_orders(self, cookies):
        """定时每5分钟拉取最新订单"""
        self._running = True
        logger.info('店铺 %s 开始监控新订单', self.shop_id)
        while self._running:
            try:
                orders = await self.fetch_orders(cookies, page=1, page_size=20)
                for o in orders:
                    if self.db_client:
                        self.db_client.insert_order(self.shop_id, o)
            except Exception as e:
                logger.error('监控新订单异常: %s', e)
            await asyncio.sleep(ORDER_SYNC_INTERVAL)

    def stop(self):
        self._running = False
