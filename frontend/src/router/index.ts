import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/LoginView.vue"),
      meta: { public: true },
    },
    {
      path: "/interviews/:id/room",
      name: "interview-room",
      component: () => import("@/views/InterviewRoomView.vue"),
    },
    {
      path: "/",
      component: () => import("@/components/AppShell.vue"),
      children: [
        { path: "", redirect: "/dashboard" },
        { path: "/dashboard", name: "dashboard", component: () => import("@/views/DashboardView.vue") },
        { path: "/growth", name: "growth", component: () => import("@/views/GrowthView.vue") },
        { path: "/resumes", name: "resume-center", component: () => import("@/views/ResumeCenterView.vue") },
        { path: "/interviews/new", name: "interview-create", component: () => import("@/views/InterviewCreateView.vue") },
        { path: "/interviews/:id/run", name: "interview-run", component: () => import("@/views/InterviewRunView.vue") },
        { path: "/interviews/:id/report", name: "interview-report", component: () => import("@/views/ReportView.vue") },
        { path: "/history", name: "history", component: () => import("@/views/HistoryView.vue") },
        { path: "/history/:id", name: "history-detail", component: () => import("@/views/HistoryDetailView.vue") },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/views/NotFoundView.vue"),
      meta: { public: true },
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (auth.token && !auth.hydrated) {
    await auth.hydrate();
  }
  if (to.meta.public) {
    return true;
  }
  if (!auth.isAuthenticated) {
    return { name: "login" };
  }
  return true;
});

export default router;
