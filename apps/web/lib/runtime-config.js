const DEV_API_BASE = "http://127.0.0.1:8000";
const DEV_WS_URL = "ws://127.0.0.1:8000/ws/live";

export function getRuntimeConfig() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE || (process.env.NODE_ENV === "development" ? DEV_API_BASE : "");
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || (process.env.NODE_ENV === "development" ? DEV_WS_URL : "");

  return {
    apiBase,
    wsUrl,
    backendConfigured: Boolean(apiBase && wsUrl),
    usingLocalDefaults: process.env.NODE_ENV === "development" && apiBase === DEV_API_BASE && wsUrl === DEV_WS_URL
  };
}
