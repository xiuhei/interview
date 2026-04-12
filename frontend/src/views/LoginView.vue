<template>
  <div class="page-shell login-page">
    <section class="hero">
      <p class="eyebrow">智能面试训练</p>
      <h1>让追问更像真实面试，让反馈真正能练起来。</h1>
      <p class="hero-copy">
        这一版聚焦动态追问链和多模态评分，岗位画像、简历背景、语音特征与结构化评分依据会一起参与判断。
      </p>

      <div class="hero-points">
        <span class="hero-point">动态追问</span>
        <span class="hero-point">简历联动</span>
        <span class="hero-point">语音评分</span>
      </div>
    </section>

    <section class="panel-card login-card">
      <div class="card-head">
        <h2>登录演示平台</h2>
        <p class="muted">进入后即可体验简历中心、文本面试、语音面试与成长复盘。</p>
      </div>

      <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="demo" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="Demo123!" show-password />
        </el-form-item>
        <el-button type="primary" class="full" :loading="loading" @click="handleLogin">登录</el-button>
      </el-form>

      <div class="account-strip">
        <span class="account-pill">演示账号：demo / Demo123!</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const loading = ref(false);
const form = reactive({ username: "demo", password: "Demo123!" });
const redirectTarget = computed(() => {
  const redirect = route.query.redirect;
  return typeof redirect === "string" && redirect.startsWith("/") ? redirect : "/dashboard";
});

async function handleLogin() {
  loading.value = true;
  try {
    await auth.signIn(form.username, form.password);
    ElMessage.success("登录成功");
    router.push(redirectTarget.value);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: 1.18fr 0.82fr;
  align-items: center;
  gap: 28px;
}

.hero {
  padding: 18px 6px 18px 8px;
}

.hero h1 {
  font-size: clamp(34px, 5vw, 62px);
  line-height: 1.06;
  margin: 0 0 16px;
}

.hero-copy {
  max-width: 680px;
  margin: 0;
  color: var(--muted);
  font-size: 17px;
}

.hero-points {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 22px;
}

.hero-point,
.account-pill {
  display: inline-flex;
  align-items: center;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(30, 60, 110, 0.08);
  box-shadow: var(--shadow-soft);
  font-size: 13px;
  font-weight: 600;
}

.login-card {
  padding: 30px;
}

.card-head {
  margin-bottom: 10px;
}

.card-head .muted {
  margin: 8px 0 0;
}

.full {
  width: 100%;
}

.account-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .hero {
    padding: 0;
  }
}
</style>
