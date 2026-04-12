import axios from "axios";

import { storage } from "@/utils/storage";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 30000,
});

client.interceptors.request.use((config) => {
  const token = storage.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error?.response?.data?.message || error?.message || "请求失败";
    const status = error?.response?.status;
    if (
      status === 401 &&
      typeof window !== "undefined" &&
      ["无效的登录状态", "缺少 Bearer Token", "用户不存在"].includes(message)
    ) {
      storage.clearToken();
      storage.clearUser();
      if (window.location.pathname !== "/login") {
        const redirect = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        window.location.replace(`/login?redirect=${encodeURIComponent(redirect)}`);
      }
    }
    return Promise.reject(new Error(message));
  },
);

export default client;
