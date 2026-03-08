# -*- coding: utf-8 -*-
"""
拼多多 WebSocket 消息解析
支持：文字、图片、撤回、商品卡片、订单卡片
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MSG_TYPE_MAP = {
    0: 'text', 1: 'text', 2: 'image', 3: 'audio',
    4: 'video', 5: 'goods', 6: 'order', 7: 'withdraw',
    8: 'system', 9: 'custom', 10: 'withdraw',
}


def parse_message(data: dict) -> Optional[dict]:
    if 'message' in data:
        return _parse_new_format(data['message'])
    if 'msgType' in data or 'type' in data or 'fromUser' in data or 'senderId' in data:
        return _parse_old_format(data)
    return None


def _parse_new_format(msg: dict) -> Optional[dict]:
    from_info = msg.get('from') or {}
    role = from_info.get('role', '')
    if role not in ('user', 'buyer', ''):
        if role == 'mall_cs':
            return None

    buyer_id = str(from_info.get('uid') or msg.get('buyerId') or '')
    buyer_name = msg.get('nickname') or msg.get('buyerNick') or ''
    msg_id = str(msg.get('msg_id') or msg.get('msgId') or '')
    timestamp = msg.get('timestamp') or msg.get('createTime') or 0

    # 判断消息类型
    raw_type = msg.get('type') or msg.get('msgType') or 0
    msg_type = MSG_TYPE_MAP.get(int(raw_type) if str(raw_type).isdigit() else 0, 'text')

    # 从 push_biz_context 里获取更多信息
    biz = msg.get('push_biz_context') or msg.get('bizContext') or {}
    msg_category = biz.get('msg_category') or biz.get('msgCategory') or 0

    content = ''
    image_url = ''
    order_id = ''
    order_info = {}

    # 解析内容
    raw_content = msg.get('content') or msg.get('msgContent') or ''

    # 尝试解析JSON内容（商品卡片、订单卡片等）
    if isinstance(raw_content, str) and raw_content.startswith('{'):
        try:
            content_obj = json.loads(raw_content)
            parsed = _parse_content_obj(content_obj, msg_type)
            content = parsed.get('content', '')
            image_url = parsed.get('image_url', '')
            order_id = parsed.get('order_id', '')
            order_info = parsed.get('order_info', {})
            if parsed.get('msg_type'):
                msg_type = parsed['msg_type']
        except Exception:
            content = raw_content
    elif isinstance(raw_content, dict):
        parsed = _parse_content_obj(raw_content, msg_type)
        content = parsed.get('content', '')
        image_url = parsed.get('image_url', '')
        order_id = parsed.get('order_id', '')
        order_info = parsed.get('order_info', {})
        if parsed.get('msg_type'):
            msg_type = parsed['msg_type']
    elif isinstance(raw_content, str):
        content = raw_content

    # 特殊处理
    if msg_type == 'image' and not image_url:
        image_url = msg.get('imageUrl') or msg.get('url') or ''
        content = '[图片]'
    elif msg_type == 'withdraw':
        content = '[消息已撤回]'

    # 从biz上下文补充订单信息
    if not order_id:
        order_id = str(biz.get('order_sn') or biz.get('orderSn') or biz.get('order_id') or '')

    if not buyer_id and not content:
        return None

    return {
        'msg_id': msg_id,
        'buyer_id': buyer_id,
        'buyer_name': buyer_name,
        'content': content,
        'msg_type': msg_type,
        'image_url': image_url,
        'order_id': order_id,
        'order_info': order_info,
        'timestamp': int(timestamp) if timestamp else 0,
    }


def _parse_content_obj(obj: dict, current_type: str) -> dict:
    """解析JSON格式的消息内容（商品卡片、订单卡片等）"""
    result = {'content': '', 'image_url': '', 'order_id': '', 'order_info': {}, 'msg_type': ''}

    # 商品卡片
    if 'goodsId' in obj or 'goods_id' in obj or 'goodsName' in obj:
        goods_id = str(obj.get('goodsId') or obj.get('goods_id') or '')
        goods_name = str(obj.get('goodsName') or obj.get('goods_name') or obj.get('name') or '')
        price = obj.get('minGroupPrice') or obj.get('price') or obj.get('minPrice') or 0
        price_yuan = f'{int(price)/100:.2f}' if price else ''
        thumb = obj.get('thumbUrl') or obj.get('imageUrl') or obj.get('goodsImageUrl') or ''
        result['msg_type'] = 'goods'
        result['content'] = f'[商品] {goods_name}' + (f' ¥{price_yuan}' if price_yuan else '')
        result['image_url'] = thumb
        result['order_info'] = {'goods_id': goods_id, 'goods_name': goods_name, 'price': price}
        return result

    # 订单卡片
    if 'orderSn' in obj or 'order_sn' in obj or 'sn' in obj:
        order_sn = str(obj.get('orderSn') or obj.get('order_sn') or obj.get('sn') or '')
        goods_name = str(obj.get('goodsName') or obj.get('goods_name') or obj.get('skuName') or '')
        status = str(obj.get('orderStatusStr') or obj.get('statusStr') or obj.get('status') or '')
        amount = obj.get('payAmount') or obj.get('pay_amount') or 0
        amount_yuan = f'{int(amount)/100:.2f}' if amount else ''
        thumb = obj.get('goodsThumbUrl') or obj.get('thumbUrl') or obj.get('imageUrl') or ''
        result['msg_type'] = 'order'
        result['order_id'] = order_sn
        result['content'] = f'[订单] {order_sn}' + (f' {goods_name}' if goods_name else '') + (f' ¥{amount_yuan}' if amount_yuan else '') + (f' {status}' if status else '')
        result['image_url'] = thumb
        result['order_info'] = obj
        return result

    # 图片消息
    if 'url' in obj or 'imageUrl' in obj or 'picUrl' in obj:
        url = obj.get('url') or obj.get('imageUrl') or obj.get('picUrl') or ''
        result['msg_type'] = 'image'
        result['image_url'] = str(url)
        result['content'] = '[图片]'
        return result

    # 普通文本（JSON包装）
    text = obj.get('text') or obj.get('content') or obj.get('message') or ''
    if text:
        result['content'] = str(text)

    return result


def _parse_old_format(body: dict) -> Optional[dict]:
    msg_type_code = body.get('msgType') or body.get('type') or 1
    msg_type = MSG_TYPE_MAP.get(int(msg_type_code), 'text')
    from_user = body.get('fromUser') or body.get('senderId') or ''
    buyer_id = str(from_user) if from_user else ''
    buyer_name = body.get('fromNickname') or body.get('senderName') or body.get('nickName') or ''
    msg_id = str(body.get('msgId') or body.get('id') or '')
    timestamp = body.get('createTime') or body.get('timestamp') or 0
    content = ''
    image_url = ''
    order_id = ''
    order_info = {}

    if msg_type == 'text':
        for field in ('content', 'text', 'msgContent', 'message'):
            val = body.get(field)
            if val and isinstance(val, str):
                content = val
                break
    elif msg_type == 'image':
        for field in ('imageUrl', 'url', 'picUrl', 'imgUrl'):
            val = body.get(field)
            if val:
                image_url = str(val)
                break
        content = '[图片]'
    elif msg_type == 'withdraw':
        content = '[消息已撤回]'

    if not buyer_id and not content:
        return None

    return {
        'msg_id': msg_id,
        'buyer_id': buyer_id,
        'buyer_name': buyer_name,
        'content': content,
        'msg_type': msg_type,
        'image_url': image_url,
        'order_id': order_id,
        'order_info': order_info,
        'timestamp': int(timestamp) if timestamp else 0,
    }
