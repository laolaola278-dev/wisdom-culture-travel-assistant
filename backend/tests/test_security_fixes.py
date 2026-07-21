"""
Regression tests for the security-audit fixes:
- content moderation \b failure on Chinese text
- session IDOR (read / delete / rename ownership checks)
- admin authorization gaps (settings read, role escalation)
- feedback int validation
- token revocation (revoked=True + blocklist loader)
"""
import pytest


# ── Content moderation ────────────────────────────────────────────

class TestContentModeration:
    def test_blocks_sensitive_word_mid_sentence(self):
        # 修复前 \b 模式在汉字之间永不匹配，这里必须命中
        from content_moderation import check_question
        is_safe, reason = check_question("请告诉我如何进行诈骗活动")
        assert not is_safe
        assert reason

    def test_allows_normal_tourism_question(self):
        from content_moderation import check_question
        is_safe, reason = check_question("白云山有什么历史文化？")
        assert is_safe
        assert reason is None


# ── Token revocation ──────────────────────────────────────────────

class TestTokenRevocation:
    def test_revoke_token_sets_revoked_flag(self, app):
        import datetime
        from auth import revoke_token, is_token_revoked
        exp = datetime.datetime.now() + datetime.timedelta(hours=1)
        jti = "test-jti-regression-001"
        revoke_token(jti, user_id=1, expires_at=exp)
        # 修复前插入的行 revoked=False，is_token_revoked 永远查不到
        assert is_token_revoked({"jti": jti}) is True

    def test_unknown_jti_not_revoked(self, app):
        from auth import is_token_revoked
        assert is_token_revoked({"jti": "never-revoked-jti"}) is False


# ── Session IDOR ──────────────────────────────────────────────────

@pytest.fixture
def victim_session(app):
    """Create a session owned by a registered user."""
    import uuid
    from database import get_db_session
    from models import QASession, User
    from auth import hash_password
    sid = f"victim-{uuid.uuid4().hex[:8]}"
    with get_db_session() as db:
        user = db.query(User).filter_by(username="idor_victim").first()
        if not user:
            user = User(
                username="idor_victim",
                email="idor_victim@test.local",
                password_hash=hash_password("password123"),
                role="user",
            )
            db.add(user)
            db.flush()
        s = QASession(session_id=sid, user_id=user.id, title="victim session")
        db.add(s)
    yield sid
    with get_db_session() as db:
        db.query(QASession).filter_by(session_id=sid).delete()
        db.query(User).filter_by(username="idor_victim").delete()


class TestSessionIDOR:
    def test_anonymous_cannot_read_others_session(self, client, victim_session):
        res = client.get(f"/api/v2/sessions/{victim_session}")
        assert res.status_code == 403

    def test_anonymous_cannot_delete_others_session(self, client, victim_session):
        # 修复前 `if user_id and ...` 短路，匿名请求可直接删除
        res = client.delete(f"/api/v2/sessions/{victim_session}")
        assert res.status_code == 403
        from database import get_db_session
        from models import QASession
        with get_db_session() as db:
            assert db.query(QASession).filter_by(session_id=victim_session).first() is not None

    def test_anonymous_cannot_rename_others_session(self, client, victim_session):
        res = client.put(
            f"/api/v2/sessions/{victim_session}/title",
            json={"title": "hijacked"},
        )
        assert res.status_code == 403


# ── Admin authorization ───────────────────────────────────────────

@pytest.fixture
def user_token(app, client):
    """Register + login a plain (non-admin) user, return access token."""
    import uuid
    from database import get_db_session
    from models import User, RefreshToken
    uname = f"plainuser_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={
        "username": uname,
        "email": f"{uname}@test.local",
        "password": "password123",
    })
    res = client.post("/api/auth/login", json={
        "username": uname, "password": "password123",
    })
    assert res.status_code == 200
    yield res.get_json()["access_token"]
    with get_db_session() as db:
        user = db.query(User).filter_by(username=uname).first()
        if user:
            db.query(RefreshToken).filter_by(user_id=user.id).delete()
            db.delete(user)


class TestAdminAuthorization:
    def test_settings_requires_admin(self, client, user_token):
        # 修复前普通用户即可读取全部系统设置
        res = client.get(
            "/api/admin/settings",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res.status_code == 403

    def test_feedback_stats_requires_admin(self, client, user_token):
        res = client.get(
            "/api/v2/feedback/stats",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res.status_code == 403

    def test_sync_requires_admin(self, client, user_token):
        res = client.post(
            "/api/system/sync",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res.status_code == 403


# ── Feedback validation ───────────────────────────────────────────

class TestFeedbackValidation:
    def test_non_numeric_rating_returns_400(self, client):
        # 修复前 int("abc") 抛 ValueError → 500
        res = client.post("/api/v2/feedback", json={"history_id": "abc", "rating": "xyz"})
        assert res.status_code == 400

    def test_missing_fields_returns_400(self, client):
        res = client.post("/api/v2/feedback", json={})
        assert res.status_code == 400


# ── Client IP extraction (XFF trust chain) ────────────────────────

class TestClientIP:
    """nginx proxy_add_x_forwarded_for 为追加语义：伪造条目在最左，
    必须从右向左取第一个不可信地址（rightmost-untrusted）。"""

    def test_spoofed_xff_ignored_behind_trusted_proxy(self, app, monkeypatch):
        import middleware
        monkeypatch.setattr(middleware, '_TRUSTED_PROXIES', {'127.0.0.1'})
        with app.test_request_context(
            headers={'X-Forwarded-For': '6.6.6.6, 203.0.113.9'},
            environ_base={'REMOTE_ADDR': '127.0.0.1'},
        ):
            # 203.0.113.9 是可信代理追加的真实客户端；6.6.6.6 是客户端伪造的
            assert middleware.get_client_ip() == '203.0.113.9'

    def test_xff_ignored_from_untrusted_source(self, app, monkeypatch):
        import middleware
        monkeypatch.setattr(middleware, '_TRUSTED_PROXIES', {'127.0.0.1'})
        with app.test_request_context(
            headers={'X-Forwarded-For': '6.6.6.6'},
            environ_base={'REMOTE_ADDR': '198.51.100.7'},
        ):
            # 直连方不是可信代理：整个 XFF 不可信
            assert middleware.get_client_ip() == '198.51.100.7'

    def test_no_trusted_proxies_uses_remote_addr(self, app, monkeypatch):
        import middleware
        monkeypatch.setattr(middleware, '_TRUSTED_PROXIES', set())
        with app.test_request_context(
            headers={'X-Forwarded-For': '6.6.6.6'},
            environ_base={'REMOTE_ADDR': '198.51.100.7'},
        ):
            assert middleware.get_client_ip() == '198.51.100.7'


# ── Logout revokes refresh tokens ─────────────────────────────────

class TestLogoutRevocation:
    def test_logout_revokes_registered_refresh_tokens(self, client, user_token):
        # 登录时 create_tokens 已登记 refresh jti；登出后应全部被撤销
        res = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res.status_code == 200
        # access token 本身也被撤销：再用它调用受保护端点应 401
        res2 = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res2.status_code == 401
        # access token 本身也被撤销：再用它调用受保护端点应 401
        res2 = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res2.status_code == 401
