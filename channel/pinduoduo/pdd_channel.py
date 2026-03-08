# -*- coding: utf-8 -*-
import asyncio, json, logging, time
from collections import deque
import websockets
from websockets.exceptions import ConnectionClosed
from channel.base_channel import BaseChannel
from channel.pinduoduo.pdd_message import parse_message

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL = 30

class PddChannel(BaseChannel):
    def __init__(self, shop_id, shop_info, im_token, cookies, db_client=None, server_api=None, sender=None):
        super().__init__(shop_id, shop_info)
        self.im_token = im_token
        self.cookies = cookies
        self.db_client = db_client
        self.server_api = server_api
        self.sender = sender
        self._ws = None
        self._heartbeat_task = None
        # 已处理消息ID（去重用）
        self._processed_ids = deque(maxlen=500)
        self._processed_ids_set = set()
        # 处理锁（防止重复处理）
        self._processing_lock = asyncio.Lock()

    def _build_ws_url(self):
        version = time.strftime('%Y%m%d%H%M', time.localtime())
        return 'wss://m-ws.pinduoduo.com/?access_token={}&role=mall_cs&client=web&version={}'.format(
            self.im_token, version)

    async def connect(self):
        try:
            ws_url = self._build_ws_url()
            cookie_str = '; '.join('{}={}'.format(k, v) for k, v in self.cookies.items())
            headers = {
                'Cookie': cookie_str,
                'Origin': 'https://mms.pinduoduo.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            }
            ver = tuple(int(x) for x in websockets.__version__.split('.')[:2])
            kw = 'additional_headers' if ver >= (14, 0) else 'extra_headers'
            logger.info('店铺 %s 连接WS...', self.shop_id)
            self._ws = await websockets.connect(ws_url, **{kw: headers},
                ping_interval=None, open_timeout=15, close_timeout=10)
            logger.info('店铺 %s WebSocket连接成功', self.shop_id)
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            return True
        except Exception as e:
            logger.error('店铺 %s 连接失败: %s', self.shop_id, e)
            return False

    async def disconnect(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try: await self._heartbeat_task
            except asyncio.CancelledError: pass
        if self._ws:
            try: await self._ws.close()
            except Exception: pass
            self._ws = None

    async def run(self):
        if not self._ws: raise RuntimeError('未连接')
        try:
            async for raw_msg in self._ws:
                if not self.is_running: break
                await self._handle_raw_message(raw_msg)
        except ConnectionClosed as e:
            logger.warning('店铺 %s 连接断开: %s', self.shop_id, e)
        except Exception as e:
            logger.error('店铺 %s 接收异常: %s', self.shop_id, e)

    async def _heartbeat_loop(self):
        try:
            while self.is_running and self._ws:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if self._ws and self.is_running:
                    try:
                        await self._ws.send(json.dumps({'cmd':'ping','timestamp':int(time.time()*1000)}))
                    except Exception as e:
                        logger.warning('心跳失败: %s', e); break
        except asyncio.CancelledError: pass

    async def _handle_raw_message(self, raw_msg):
        try:
            if isinstance(raw_msg, bytes): raw_msg = raw_msg.decode('utf-8')
            data = json.loads(raw_msg)
        except Exception: return

        cmd = data.get('cmd') or data.get('type') or data.get('response') or ''
        if cmd in ('pong','ack','ping','auth'): return

        parsed = parse_message(data)
        if not parsed: return

        buyer_id = parsed.get('buyer_id','')
        content = parsed.get('content','')

        # 过滤无效消息
        if not buyer_id or buyer_id in ('4','0',''):
            return
        if not content and parsed.get('msg_type','text') == 'text':
            return

        # 消息去重（用content+buyer_id+时间戳前缀）
        msg_id = parsed.get('msg_id','')
        if not msg_id:
            msg_id = '{}_{}_{}_{}'.format(
                buyer_id, content[:20],
                parsed.get('msg_type',''), int(time.time()//5)
            )

        async with self._processing_lock:
            if msg_id in self._processed_ids_set:
                logger.debug('重复消息已跳过: %s', msg_id[:30])
                return
            if len(self._processed_ids) == self._processed_ids.maxlen:
                old = self._processed_ids[0]
                self._processed_ids_set.discard(old)
            self._processed_ids.append(msg_id)
            self._processed_ids_set.add(msg_id)

        await self._process_message(parsed)

    async def _process_message(self, msg):
        buyer_id = msg.get('buyer_id','')
        buyer_name = msg.get('buyer_name','')
        content = msg.get('content','')
        msg_type = msg.get('msg_type','text')
        image_url = msg.get('image_url','')
        order_id = msg.get('order_id','')

        logger.info('店铺%s 买家%s[%s]: %s', self.shop_id, buyer_name or buyer_id, msg_type, content[:60])

        if self._message_callback:
            try: self._message_callback(self.shop_id, msg)
            except Exception: pass

        # 查买家最近订单
        order_info = {}
        if self.db_client and buyer_id:
            try:
                latest = self.db_client.get_buyer_latest_order(self.shop_id, buyer_id)
                if latest:
                    order_info = latest
                    if not order_id:
                        order_id = str(latest.get('order_id',''))
            except Exception as e:
                logger.debug('查询买家订单失败: %s', e)

        # 入库
        message_id = 0
        if self.db_client:
            message_id = self.db_client.insert_message(
                shop_id=self.shop_id, buyer_id=buyer_id, buyer_name=buyer_name,
                order_id=order_id, direction='in', content=content,
                msg_type=msg_type, image_url=image_url, status='pending'
            )

        if msg_type not in ('text','image','goods','order') or not content:
            return
        if not self.server_api: return

        try:
            api_result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.server_api.send_message(
                    shop_id=self.shop_id, buyer_id=buyer_id, buyer_name=buyer_name,
                    content=content, order_id=order_id, msg_type=msg_type, image_url=image_url,
                )
            )
        except Exception as e:
            logger.error('API调用异常: %s', e); return

        if not api_result.get('success'): return

        reply = api_result.get('reply','')
        needs_human = api_result.get('needs_human', False)
        process_by = api_result.get('process_by','ai')
        token_used = api_result.get('token_used', 0)

        if self.db_client and message_id:
            self.db_client.update_message_reply(
                message_id=message_id, reply_content=reply,
                process_by=process_by, needs_human=needs_human, token_used=token_used or 0
            )

        if reply and not needs_human and self.sender:
            try:
                await self.sender.send_text(buyer_id, reply)
                if self.db_client:
                    self.db_client.insert_message(
                        shop_id=self.shop_id, buyer_id=buyer_id, buyer_name=buyer_name,
                        order_id=order_id, direction='out', content=reply,
                        msg_type='text', status='processed'
                    )
            except Exception as e:
                logger.error('发送AI回复失败: %s', e)
