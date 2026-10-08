"""用于将 webhook 授权地址与诊断身份分离。"""
import hashlib


def webhook_identity(webhook_url: str) -> str:
    """返回稳定、不可直接还原 URL 的诊断标识。"""
    digest = hashlib.sha256(webhook_url.encode("utf-8")).hexdigest()[:16]
    return "wh-" + digest
