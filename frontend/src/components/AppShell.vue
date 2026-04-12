<template>
  <div class="page-shell shell-layout">
    <aside class="panel-card sidebar">
      <div class="sidebar-top">
        <div class="brand-card">
          <div class="brand-mark">AI</div>
          <div class="brand-copy">
            <p class="eyebrow">智能面试工作台</p>
            <h1>AI 面试平台</h1>
          </div>
        </div>

        <el-menu :default-active="activePath" class="menu" @select="handleSelect">
          <el-menu-item index="/dashboard">
            <div class="menu-label">
              <strong>仪表盘</strong>
            </div>
          </el-menu-item>
          <el-menu-item index="/growth">
            <div class="menu-label">
              <strong>个人成长</strong>
            </div>
          </el-menu-item>
          <el-menu-item index="/resumes">
            <div class="menu-label">
              <strong>简历中心</strong>
            </div>
          </el-menu-item>
          <el-menu-item index="/interviews/new">
            <div class="menu-label">
              <strong>新建面试</strong>
            </div>
          </el-menu-item>
          <el-menu-item index="/history">
            <div class="menu-label">
              <strong>历史记录</strong>
            </div>
          </el-menu-item>
        </el-menu>
      </div>

      <div class="sidebar-footer">
        <div class="profile-card">
          <div class="profile-avatar">{{ auth.user?.full_name?.slice(0, 1) || "U" }}</div>
          <div>
            <strong>{{ auth.user?.full_name }}</strong>
            <p class="muted small">{{ auth.user?.role }}</p>
          </div>
        </div>
        <el-button type="primary" plain @click="logout">退出登录</el-button>
      </div>
    </aside>

    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const activePath = computed(() => {
  if (route.path.startsWith("/interviews")) return "/interviews/new";
  if (route.path.startsWith("/history")) return "/history";
  if (route.path.startsWith("/resumes")) return "/resumes";
  return route.path;
});

function handleSelect(index: string) {
  router.push(index);
}

function logout() {
  auth.signOut();
  router.push("/login");
}
</script>

<style scoped>
.shell-layout {
  display: flex;
  min-height: 100vh;
  gap: 22px;
}

.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  width: 292px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 24px;
  z-index: 100;
  overflow-y: auto;
  border-radius: 0 28px 28px 0;
  border-right: 1px solid var(--border);
  background:
    linear-gradient(180deg, rgba(255, 251, 246, 0.95), rgba(249, 242, 232, 0.82)),
    rgba(255, 255, 255, 0.62);
}

.sidebar-top {
  display: grid;
  gap: 18px;
}

.brand-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  padding: 16px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.52);
  border: 1px solid rgba(64, 46, 30, 0.08);
}

.brand-mark {
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--primary), #38a89c);
  color: #fff;
  font-weight: 800;
  letter-spacing: 0.06em;
  box-shadow: 0 14px 24px rgba(15, 118, 110, 0.18);
}

.brand-copy h1 {
  margin-bottom: 8px;
  font-size: 24px;
}

.menu {
  border-right: none;
  background: transparent;
}

.menu-label {
  display: flex;
  align-items: center;
  width: 100%;
}

.menu-label strong {
  font-size: 15px;
  color: var(--ink-soft);
}

.menu :deep(.el-menu-item) {
  height: auto;
  min-height: 52px;
  margin-bottom: 8px;
  border-radius: 18px;
  padding: 12px 14px 12px 16px;
  line-height: 1.3;
  border: 1px solid transparent;
  background: transparent;
  transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.72);
  border-color: rgba(64, 46, 30, 0.08);
  transform: translateX(2px);
}

.menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.12), rgba(255, 255, 255, 0.8));
  border-color: rgba(15, 118, 110, 0.14);
}

.menu :deep(.el-menu-item.is-active .menu-label strong) {
  color: var(--primary);
}

.sidebar-footer {
  display: grid;
  gap: 14px;
}

.profile-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.56);
  border: 1px solid rgba(64, 46, 30, 0.08);
}

.profile-avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(201, 111, 61, 0.14);
  color: var(--accent);
  font-weight: 800;
}

.small {
  margin: 4px 0 0;
  font-size: 12px;
}

.content {
  flex: 1;
  margin-left: 292px;
  min-height: 100vh;
  padding: 8px 0 0;
}

@media (max-width: 1100px) {
  .sidebar {
    width: 268px;
  }

  .content {
    margin-left: 268px;
  }
}

@media (max-width: 980px) {
  .shell-layout {
    flex-direction: column;
    gap: 16px;
  }

  .sidebar {
    position: relative;
    width: 100%;
    height: auto;
    border-radius: 24px;
    border-right: none;
    padding: 18px;
  }

  .content {
    margin-left: 0;
    padding-top: 0;
  }
}
</style>
