# RM Auth Testing Playbook

## Backend Seed Credentials
The backend seeds RM users from environment variables on startup.

Default fallback credentials from `backend/.env.example`:
- User ID: `rm_demo`
- Password: `ChangeMe123!`

Override them in `backend/.env` with:
- `RM_DEFAULT_USER_ID`
- `RM_DEFAULT_PASSWORD`
- `RM_DEFAULT_NAME`
- `RM_DEFAULT_EMAIL`
- or `RM_SEED_USERS_JSON`

## Step 1: Test Backend Login
```bash
curl -X POST "$EXPO_PUBLIC_API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"rm_demo","password":"ChangeMe123!"}'
```

## Step 2: Test Backend Authenticated API
```bash
curl -X GET "$EXPO_PUBLIC_API_URL/api/auth/me" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

## Step 3: Frontend Test
- Open the app and enter a seeded RM user ID and password on the login screen.
- On success, the app should route to `/dashboard`.
- Reload the app and verify the stored session restores automatically.
- Tap `Logout` and verify the app returns to `/login`.

## Checklist
- `RM_DEFAULT_USER_ID` and `RM_DEFAULT_PASSWORD` or `RM_SEED_USERS_JSON` are set in `backend/.env`.
- `EXPO_PUBLIC_API_URL` is set in `Frontend/.env`.
- The authenticated user returned by `/api/auth/me` includes `role: "rm"`.
- Unauthorized requests to `/api/auth/me` return `401`.
- Inactive or non-RM users cannot obtain a session token from `/api/auth/login`.
