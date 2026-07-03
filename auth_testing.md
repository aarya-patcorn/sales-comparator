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
- Expo Go: Google sign-in is intentionally blocked. The login screen explains that a development build is required.
- Development build: run `npx expo start --dev-client`, open the installed dev client, then tap `Sign in with Google`.
- Google returns an auth code to `com.kamdhenu.comparisontool:/oauth`.
- Backend exchanges the code at `/api/auth/google/exchange` and returns app session plus Google tokens.
- Frontend stores the auth bundle in `expo-secure-store` and sends `session_token` as `Authorization: Bearer ...` on API calls.

## Checklist
- Google Cloud Console has `com.kamdhenu.comparisontool:/oauth` registered.
- `EXPO_PUBLIC_GOOGLE_CLIENT_ID` is set in `frontend/.env`.
- `GOOGLE_CLIENT_ID` is set in `backend/.env`.
- User document has `user_id` field (custom UUID).
- Session user_id matches user's user_id.
- All queries use `{"_id": 0}` projection.
- API returns user data without 401.
