/**
 * The app owns only the /deployops URLs (see deployops/hooks.py `website_route_rules`):
 * other apps on the site keep their own. Router paths are relative to this base.
 */
export const APP_BASE = "/deployops";
