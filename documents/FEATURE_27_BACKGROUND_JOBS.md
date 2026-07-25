q# Feature 27 installation

1. Replace the existing DRC folder with this package while preserving your local `.env` and service-account key outside Git.
2. Activate the virtual environment and install requirements.
3. Apply migrations:

   ```powershell
   alembic upgrade head
   ```

4. Start DRC with the environment file:

   ```powershell
   uvicorn app.main:app --reload --env-file .env
   ```

5. Upload a CSV. The interface will show the persistent job state and open the audit when processing completes.

Existing synchronous audit endpoints remain available for compatibility.
