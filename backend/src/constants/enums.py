from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
class ClaimStatus(str, Enum):
    pending = 'pending'        # 待核发
    issued = 'issued'          # 已核发
    invalidated = 'invalidated'  # 已失效（凭证撤销）
    cancelled = 'cancelled'    # 已取消（撤销生效前未核发）
class CertStatus(str, Enum):
    active = 'active'
    revoked = 'revoked'
class ClaimKind(str, Enum):
    original = 'original'  # 初次申领
    reissue = 'reissue'    # 换证补发
