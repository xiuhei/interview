import client from "./client";
import type { ApiEnvelope, AuthToken, UserProfile } from "@/types/models";

export function login(username: string, password: string) {
  return client.post<never, ApiEnvelope<AuthToken>>("/auth/login", { username, password });
}

export function register(payload: { email: string; username: string; full_name: string; password: string }) {
  return client.post<never, ApiEnvelope<AuthToken>>("/auth/register", payload);
}

export function fetchMe() {
  return client.get<never, ApiEnvelope<UserProfile>>("/auth/me");
}
