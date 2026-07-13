# Emergent Auth Testing Playbook

## Step 1: Create Test User & Session
```
mongosh --eval "
use('test_database');
var userId = 'test-user-' + Date.now();
var sessionToken = 'test_session_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'test.user.' + Date.now() + '@example.com',
  name: 'Test User',
  picture: 'https://via.placeholder.com/150',
  created_at: new Date()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print('Session token: ' + sessionToken);
print('User ID: ' + userId);
"
```

## Step 2: Test Backend API
```
curl -X GET "$EXPO_PUBLIC_BACKEND_URL/api/auth/me" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN"
```

## Step 3: Frontend Test
- Expo Go: Google sign-in is not suitable for the native redirect flow. Use the dev login or a development build.
- Development build: run `npx expo start --dev-client`, open the installed dev client, then tap `Sign in with Google`.
- The frontend opens `${EXPO_PUBLIC_API_URL}/api/auth/google?redirect=${FRONTEND_CALLBACK_URL}`.
- Google returns to `${API_URL}/api/auth/google/callback`.
- Backend creates the app session and redirects to `${FRONTEND_URL}/oauth/callback?token=...`.
- The frontend callback route validates the token with `/api/auth/me`, stores the session, and routes to `/`.

## Checklist
- Google Cloud Console authorized redirect URI exactly matches `GOOGLE_CALLBACK_URL`.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_CALLBACK_URL`, and `FRONTEND_APP_URL` are set in `backend/.env`.
- `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_FRONTEND_URL`, and `EXPO_PUBLIC_NATIVE_APP_SCHEME` are set in `Frontend/.env`.
- Native builds use a LAN, tunnel, or production backend URL rather than `localhost`.
- User document has `user_id` field (custom UUID).
- Session user_id matches user's user_id.
- All queries use `{"_id": 0}` projection.
- API returns user data without 401.
