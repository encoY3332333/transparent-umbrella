commit 642c26c8d7a7c0b23df6fc58157911e1f19b0e48
Author: realpcy <3239214173@qq.com>
Date:   Tue Nov 10 20:39:04 2026 +0800

    style(tests): wrap the long fixture lines that broke the CI lint step
    
    加长测试密钥以满足 PyJWT 的 32 字节建议后，三行 fixture 超过 line-length=100。
    本地只跑了 pytest 没重跑 ruff，CI 才把它拦下来——这正是要 CI 的原因。

diff --git a/backend/tests/test_security.py b/backend/tests/test_security.py
index 85f4f6b..cf27341 100644
--- a/backend/tests/test_security.py
+++ b/backend/tests/test_security.py
@@ -21,7 +21,10 @@ FIXED_NOW = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)
 
 @pytest.fixture
 def settings() -> Settings:
-    return Settings(jwt_secret="unit-test-jwt-secret-0123456789abcdef", share_sign_salt="unit-test-share-salt-0123456789abcdef")
+    return Settings(
+        jwt_secret="unit-test-jwt-secret-0123456789abcdef",
+        share_sign_salt="unit-test-share-salt-0123456789abcdef",
+    )
 
 
 def test_access_token_roundtrip(settings: Settings) -> None:
@@ -33,7 +36,10 @@ def test_access_token_roundtrip(settings: Settings) -> None:
 
 def test_access_token_rejects_other_secret(settings: Settings) -> None:
     token, _ = create_access_token(1001, settings, now=FIXED_NOW)
-    other = Settings(jwt_secret="another-secret-0123456789abcdefghij", share_sign_salt="unit-test-share-salt-0123456789abcdef")
+    other = Settings(
+        jwt_secret="another-secret-0123456789abcdefghij",
+        share_sign_salt="unit-test-share-salt-0123456789abcdef",
+    )
 
     with pytest.raises(TokenError):
         decode_access_token(token, other)
@@ -78,7 +84,10 @@ def test_share_token_rejects_bad_signature(settings: Settings) -> None:
 
 def test_share_token_rejects_other_salt(settings: Settings) -> None:
     token, _ = sign_share_token(3001, settings, now=FIXED_NOW)
-    other = Settings(jwt_secret="unit-test-jwt-secret-0123456789abcdef", share_sign_salt="different-salt-0123456789abcdefghij")
+    other = Settings(
+        jwt_secret="unit-test-jwt-secret-0123456789abcdef",
+        share_sign_salt="different-salt-0123456789abcdefghij",
+    )
 
     with pytest.raises(TokenError):
         verify_share_token(token, other, now=FIXED_NOW)
