import { defineStore } from "pinia";

import { fetchMe, login } from "@/api/auth";
import type { UserProfile } from "@/types/models";
import { storage } from "@/utils/storage";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: storage.getToken(),
    user: storage.getUser() as UserProfile | null,
    hydrated: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
    isAdmin: (state) => state.user?.role === "admin",
  },
  actions: {
    async signIn(username: string, password: string) {
      const response = await login(username, password);
      this.token = response.data.access_token;
      this.user = response.data.user;
      this.hydrated = true;
      storage.setToken(this.token);
      storage.setUser(this.user);
    },
    async hydrate() {
      if (!this.token) {
        this.hydrated = true;
        return;
      }
      try {
        const response = await fetchMe();
        this.user = response.data;
        storage.setUser(response.data);
      } catch {
        this.signOut();
        return;
      }
      this.hydrated = true;
    },
    signOut() {
      this.token = "";
      this.user = null;
      this.hydrated = true;
      storage.clearToken();
      storage.clearUser();
    },
  },
});
