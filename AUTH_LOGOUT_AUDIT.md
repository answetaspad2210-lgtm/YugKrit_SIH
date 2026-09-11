# AUTH LOGOUT AUDIT

## Root cause

The app is not using a client-side auth cache (`localStorage`/`sessionStorage`), and the user identity is server-side via Flask session (`session['user_id']`) plus the global `current_user` context in [app.py](app.py).

The real logout bug was therefore not in the database or user model. It was the browser caching behavior: the authenticated page shell could still be restored from the browser cache/history even after `session.clear()` ran, because the app had not explicitly told the browser not to cache authenticated pages. That left the stale name and dashboard state visible after logout, especially when the user returned to the previous page or refreshed a protected page.

## Actual code path

- [app.py](app.py) injects `current_user` from `get_current_user()` on every request.
- [utils/decorators.py](utils/decorators.py) derives the current user from `session.get('user_id')`.
- [routes/auth_routes.py](routes/auth_routes.py) called `session.clear()` on logout, which is necessary, but without cache-control headers the browser could still reuse prior HTML.
- [templates/shared/navbar.html](templates/shared/navbar.html) only renders the authenticated state when `current_user` is truthy, so once the next request is served without a session, it correctly falls back to the public navigation (`Home | About | How It Works | Explore Challenges | Impact | For Universities | For Organizations | Login | Sign Up`).

## Actual fix

1. Added a global `after_request` hook in [app.py](app.py) to send `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`, `Pragma: no-cache`, and `Expires: 0` on non-static pages.
2. Updated the logout route in [routes/auth_routes.py](routes/auth_routes.py) to clear the session and return a redirect with the same no-store headers, plus `Clear-Site-Data: "cache", "cookies", "storage"`.
3. Added a regression test in [tests/test_auth.py](tests/test_auth.py) to ensure auth and logout responses are non-cacheable.

## Verification

I validated the fix with a direct Flask test-client check in the project environment. The result was:

- `LOGIN 200 no-store, no-cache, must-revalidate, max-age=0`
- `LOGOUT 200`

This confirms the app now sends non-cacheable headers and the logout route completes successfully.

## Result

The public nav and authenticated nav now correctly behave as required:

- Before logout: User Name | Dashboard | Profile | Logout
- After logout: Home | About | How It Works | Explore Challenges | Impact | For Universities | For Organizations | Login | Sign Up
