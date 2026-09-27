"""Authentication and Role-Based Access Control (RBAC) engine for PIXEL Control Plane."""

import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime
from typing import Any

from packages.contracts.control_plane import TokenPayload, UserIdentity, UserRole


class ControlPlaneAuthManager:
    """Manages user authentication, password hashing, JWT-like cryptographic tokens, and RBAC."""

    def __init__(
        self,
        secret_key: str = "pixel-production-control-plane-secret-key-2026",
        token_lifetime_seconds: int = 3600,
    ) -> None:
        self.secret_key = secret_key.encode("utf-8")
        self.token_lifetime_seconds = token_lifetime_seconds
        self._users: dict[str, dict[str, Any]] = {}
        self._revoked_tokens: set[str] = set()
        self._init_default_users()

    def _hash_password(self, password: str, salt: str | None = None) -> tuple[str, str]:
        """Hash password using PBKDF2-HMAC-SHA256 with cryptographic salt."""
        s = salt or secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), s.encode("utf-8"), 100_000
        ).hex()
        return pwd_hash, s

    def _verify_password(self, password: str, pwd_hash: str, salt: str) -> bool:
        """Verify password against stored hash."""
        computed, _ = self._hash_password(password, salt)
        return hmac.compare_digest(computed, pwd_hash)

    def _init_default_users(self) -> None:
        """Initialize authoritative default users for testing and bootstrap."""
        # admin user (role: ADMIN)
        h1, s1 = self._hash_password("pixel-admin-secure-2026")
        self._users["admin"] = {
            "user_id": "usr_admin_001",
            "username": "admin",
            "role": UserRole.ADMIN,
            "pwd_hash": h1,
            "salt": s1,
            "created_at": datetime.now(UTC),
            "is_active": True,
        }

        # operator user (role: OPERATOR)
        h2, s2 = self._hash_password("pixel-operator-2026")
        self._users["operator"] = {
            "user_id": "usr_operator_001",
            "username": "operator",
            "role": UserRole.OPERATOR,
            "pwd_hash": h2,
            "salt": s2,
            "created_at": datetime.now(UTC),
            "is_active": True,
        }

        # viewer user (role: READ_ONLY)
        h3, s3 = self._hash_password("pixel-viewer-2026")
        self._users["viewer"] = {
            "user_id": "usr_viewer_001",
            "username": "viewer",
            "role": UserRole.READ_ONLY,
            "pwd_hash": h3,
            "salt": s3,
            "created_at": datetime.now(UTC),
            "is_active": True,
        }

    def register_user(self, username: str, password: str, role: UserRole) -> UserIdentity:
        """Register a new user in the auth system."""
        if username in self._users:
            raise ValueError(f"User '{username}' already exists.")

        pwd_hash, salt = self._hash_password(password)
        user_id = f"usr_{secrets.token_hex(6)}"
        now = datetime.now(UTC)
        self._users[username] = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "pwd_hash": pwd_hash,
            "salt": salt,
            "created_at": now,
            "is_active": True,
        }
        return UserIdentity(
            user_id=user_id,
            username=username,
            role=role,
            created_at=now,
            is_active=True,
        )

    def authenticate(self, username: str, password: str) -> UserIdentity | None:
        """Authenticate user credentials and return user profile if valid."""
        user_data = self._users.get(username)
        if not user_data or not user_data.get("is_active", False):
            return None

        if self._verify_password(password, user_data["pwd_hash"], user_data["salt"]):
            user_data["last_login"] = datetime.now(UTC)
            return UserIdentity(
                user_id=user_data["user_id"],
                username=user_data["username"],
                role=user_data["role"],
                created_at=user_data["created_at"],
                last_login=user_data["last_login"],
                is_active=user_data["is_active"],
            )
        return None

    def create_access_token(self, user: UserIdentity) -> str:
        """Create signed HMAC-SHA256 access token for authenticated user."""
        now = int(time.time())
        payload = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role.value,
            "iat": now,
            "exp": now + self.token_lifetime_seconds,
            "jti": secrets.token_hex(12),
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(self.secret_key, payload_bytes, hashlib.sha256).hexdigest()
        raw_token = f"{payload_bytes.hex()}.{signature}"
        return raw_token

    def verify_token(self, token: str) -> TokenPayload | None:
        """Verify signature, expiration, and revocation of an access token."""
        if not token or "." not in token:
            return None

        if token in self._revoked_tokens:
            return None

        try:
            raw_hex, signature = token.split(".", 1)
            payload_bytes = bytes.fromhex(raw_hex)
            expected_sig = hmac.new(self.secret_key, payload_bytes, hashlib.sha256).hexdigest()

            if not hmac.compare_digest(signature, expected_sig):
                return None

            data = json.loads(payload_bytes.decode("utf-8"))
            now = int(time.time())
            if now > data["exp"]:
                return None

            return TokenPayload(
                sub=data["sub"],
                username=data["username"],
                role=UserRole(data["role"]),
                exp=data["exp"],
                iat=data["iat"],
                jti=data["jti"],
            )
        except Exception:
            return None

    def revoke_token(self, token: str) -> None:
        """Revoke a token upon logout."""
        self._revoked_tokens.add(token)

    def check_permission(self, user_role: UserRole, required_role: UserRole) -> bool:
        """Check if user role satisfies required RBAC hierarchy tier."""
        hierarchy = {
            UserRole.READ_ONLY: 1,
            UserRole.OPERATOR: 2,
            UserRole.ADMIN: 3,
            UserRole.SYSTEM: 4,
        }
        return hierarchy.get(user_role, 0) >= hierarchy.get(required_role, 0)

    def get_user_by_id(self, user_id: str) -> UserIdentity | None:
        """Retrieve user identity by ID."""
        for user_data in self._users.values():
            if user_data["user_id"] == user_id:
                return UserIdentity(
                    user_id=user_data["user_id"],
                    username=user_data["username"],
                    role=user_data["role"],
                    created_at=user_data["created_at"],
                    last_login=user_data.get("last_login"),
                    is_active=user_data["is_active"],
                )
        return None
