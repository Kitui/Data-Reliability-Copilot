# Test Failure Classification

## Corrected failures

### Bootstrap login failures

**Cause:** Secure example credentials replaced historical test defaults.

**Resolution:** Tests now explicitly set their own isolated bootstrap credentials and environment.

### Historical asset-version assertions

**Cause:** Several tests required obsolete JavaScript version strings.

**Resolution:** Assertions now verify that a versioned application bundle is present without coupling tests to a historical release number.

### External AI test delay

**Cause:** Test execution could inherit an external `OPENAI_API_KEY`.

**Resolution:** The isolated test fixture explicitly disables external OpenAI calls.

## Test isolation improvements

- Internal scheduling is disabled in tests.
- Every test uses a temporary SQLite database.
- Settings, engine, session factory, and audit-store caches are cleared between tests.
