# -*- coding: utf-8 -*-
"""
AES加密工具，用于本地加密存储MySQL密码
使用AES-CBC模式，随机IV与密文一起存储（Base64编码：IV + ciphertext）
"""
import os
import base64
import hashlib

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

IV_SIZE = 16  # AES block size


def _get_key() -> bytes:
    """从机器特征派生32字节AES密钥"""
    machine_id = _get_machine_id()
    return hashlib.sha256(machine_id.encode("utf-8")).digest()


def _get_machine_id() -> str:
    """获取机器唯一标识"""
    candidates = []

    # Windows: 从注册表读取MachineGuid
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        )
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        candidates.append(guid)
    except Exception:
        pass

    # Linux: 读取 /etc/machine-id
    try:
        with open("/etc/machine-id", "r") as f:
            candidates.append(f.read().strip())
    except Exception:
        pass

    # macOS: 使用 ioreg
    try:
        import subprocess
        result = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "IOPlatformUUID" in line:
                candidates.append(line.split('"')[-2])
                break
    except Exception:
        pass

    if candidates:
        return candidates[0]

    # 后备方案：使用用户主目录路径哈希
    return hashlib.md5(os.path.expanduser("~").encode()).hexdigest()


def encrypt_password(plain_password: str) -> str:
    """
    加密密码，返回 base64(random_iv + ciphertext)。
    每次加密使用随机IV，防止相同明文产生相同密文。
    """
    key = _get_key()
    iv = os.urandom(IV_SIZE)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(plain_password.encode("utf-8"), AES.block_size))
    # 将 IV 拼接在密文前面一起存储
    return base64.b64encode(iv + encrypted).decode("utf-8")


def decrypt_password(encrypted_b64: str) -> str:
    """
    解密 base64(random_iv + ciphertext) 格式的加密密码。
    同时兼容旧的固定IV格式（如果解密失败则尝试旧格式）。
    """
    key = _get_key()
    raw = base64.b64decode(encrypted_b64.encode("utf-8"))

    # 新格式：前16字节为IV，其余为密文
    if len(raw) > IV_SIZE:
        iv = raw[:IV_SIZE]
        ciphertext = raw[IV_SIZE:]
        try:
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
            return decrypted.decode("utf-8")
        except Exception:
            pass

    raise ValueError("无法解密密码，请重新输入并保存")
