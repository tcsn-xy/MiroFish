<template>
  <div class="consensus-view">
    <header class="topbar">
      <div class="brand" @click="router.push('/')">MIROFISH</div>
      <div class="topbar-actions">
        <LanguageSwitcher />
        <button class="ghost-btn" @click="router.push('/')">{{ $t('common.back') }}</button>
      </div>
    </header>

    <main class="content">
      <section class="hero">
        <div>
          <div class="eyebrow">CONSENSUS QA</div>
          <h1>{{ $t('consensus.title') }}</h1>
          <p>{{ $t('consensus.subtitle') }}</p>
        </div>
      </section>

      <section class="panel input-panel">
        <div class="panel-header">
          <h2>{{ $t('consensus.inputTitle') }}</h2>
          <div class="header-actions">
            <button class="ghost-btn" @click="refreshAll" :disabled="loading">{{ $t('consensus.refresh') }}</button>
          </div>
        </div>
        <div class="form-grid">
          <label>{{ $t('consensus.question') }}</label>
          <textarea
            v-model="form.question"
            :placeholder="$t('consensus.questionPlaceholder')"
            rows="4"
            :disabled="hasRunningTask || starting"
          />
          <label>{{ $t('consensus.threshold') }}</label>
          <input
            v-model.number="form.thresholdPercent"
            type="number"
            min="0"
            max="100"
            :disabled="hasRunningTask || starting"
          />
        </div>
        <div class="button-row">
          <button class="primary-btn" @click="handleStart" :disabled="startDisabled">
            {{ starting ? $t('consensus.starting') : $t('consensus.start') }}
          </button>
          <button class="danger-btn" @click="handleStop" :disabled="!hasRunningTask || stopping">
            {{ stopping ? $t('consensus.stopping') : $t('consensus.stop') }}
          </button>
        </div>
        <div v-if="message" class="info-box">{{ message }}</div>
        <div v-if="error" class="error-box">{{ error }}</div>
      </section>

      <section class="grid">
        <div class="panel">
          <h2>{{ $t('consensus.statusTitle') }}</h2>
          <div v-if="task" class="status-grid">
            <div class="status-item"><span>{{ $t('consensus.status') }}</span><strong>{{ statusLabel(task.status) }}</strong></div>
            <div class="status-item"><span>{{ $t('consensus.round') }}</span><strong>{{ task.current_round }}</strong></div>
            <div class="status-item"><span>{{ $t('consensus.readyCount') }}</span><strong>{{ task.ready_count }}/{{ task.total_agents }}</strong></div>
            <div class="status-item"><span>{{ $t('consensus.acceptedRatio') }}</span><strong>{{ formatRatio(task.accepted_ratio) }}</strong></div>
            <div class="status-item wide"><span>{{ $t('consensus.question') }}</span><strong>{{ task.question }}</strong></div>
            <div class="status-item wide"><span>{{ $t('consensus.thresholdMet') }}</span><strong>{{ task.is_threshold_met ? $t('common.confirm') : $t('common.pending') }}</strong></div>
          </div>
          <div v-else class="empty">{{ $t('consensus.noTask') }}</div>
        </div>

        <div class="panel">
          <h2>{{ $t('consensus.finalTitle') }}</h2>
          <div v-if="task?.final_answer" class="final-box">
            <p class="final-answer">{{ task.final_answer }}</p>
            <p class="final-evidence">{{ task.final_evidence_text }}</p>
          </div>
          <div v-else class="waiting">{{ $t('consensus.waiting') }}</div>
        </div>
      </section>

      <section class="agents-section">
        <div class="section-head">
          <h2>{{ $t('consensus.agentsTitle') }}</h2>
          <span>{{ agents.length }}/10</span>
        </div>
        <div class="agents-grid">
          <article v-for="agent in agents" :key="agent.agent_id" class="agent-card">
            <div class="agent-head">
              <div>
                <strong>{{ agent.agent_name }}</strong>
                <div class="agent-meta">
                  <span :class="['ready-pill', agent.latest?.is_ready_to_answer ? 'yes' : 'no']">
                    {{ agent.latest?.is_ready_to_answer ? $t('common.ready') : $t('common.pending') }}
                  </span>
                  <span>{{ formatTime(agent.latest?.created_at) }}</span>
                </div>
              </div>
              <button
                class="ghost-btn small-btn"
                @click="toggleExpand(agent.agent_id)"
                :disabled="!agent.history?.length"
              >
                {{ expandedAgents.has(agent.agent_id) ? $t('consensus.collapseHistory') : $t('consensus.expandHistory') }}
              </button>
            </div>
            <p class="content-short">{{ agent.latest?.content_short }}</p>
            <div class="card-actions">
              <a
                v-if="agent.latest?.evidence_url"
                :href="agent.latest.evidence_url"
                target="_blank"
                rel="noopener noreferrer"
                class="source-link"
              >
                {{ $t('consensus.source') }}
              </a>
            </div>
            <div v-if="expandedAgents.has(agent.agent_id)" class="history-list">
              <div v-for="item in agent.history" :key="`${agent.agent_id}-${item.round_no}-${item.created_at || 'pending'}`" class="history-item">
                <div class="history-head">
                  <span>{{ $t('consensus.round') }} {{ item.round_no }}</span>
                  <span>{{ formatTime(item.created_at) }}</span>
                </div>
                <p>{{ item.content_short }}</p>
              </div>
            </div>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import {
  getCurrentConsensusAgents,
  getCurrentConsensusTask,
  startConsensusTask,
  stopConsensusTask
} from '../api/consensus'

const router = useRouter()
const { t } = useI18n()

const form = ref({
  question: '',
  thresholdPercent: 80
})

const task = ref(null)
const agents = ref([])
const starting = ref(false)
const stopping = ref(false)
const loading = ref(false)
const error = ref('')
const message = ref('')
const expandedAgents = ref(new Set())
let pollTimer = null

const rosterNames = ['程序员', '产品经理', '记者', '研究员', '行业分析师', '普通用户', '投资人', '学者', '社区观察者', '谨慎怀疑者']

const buildEmptyAgents = () => rosterNames.map((name, index) => ({
  agent_id: `placeholder-${index}`,
  agent_name: name,
  latest: {
    round_no: 0,
    content_short: t('consensus.pendingResult'),
    is_ready_to_answer: false,
    evidence_url: null,
    created_at: null
  },
  history: []
}))

const hasRunningTask = computed(() => task.value?.status === 'running')
const startDisabled = computed(() => {
  const threshold = Number(form.value.thresholdPercent)
  return (
    starting.value ||
    hasRunningTask.value ||
    !form.value.question.trim() ||
    !Number.isInteger(threshold) ||
    threshold < 0 ||
    threshold > 100
  )
})

const statusLabel = (status) => {
  const map = {
    running: 'common.running',
    answered: 'common.completed',
    stopped: 'consensus.stoppedStatus',
    failed: 'common.failed'
  }
  return map[status] ? t(map[status]) : status
}

const formatRatio = (value) => `${Number(value || 0).toFixed(2)}%`

const formatTime = (value) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

const toggleExpand = (agentId) => {
  const next = new Set(expandedAgents.value)
  if (next.has(agentId)) next.delete(agentId)
  else next.add(agentId)
  expandedAgents.value = next
}

const applyPayload = (taskData, agentData) => {
  task.value = taskData
  agents.value = agentData?.agents?.length ? agentData.agents : buildEmptyAgents()
}

const refreshAll = async () => {
  loading.value = true
  error.value = ''
  try {
    const [taskRes, agentRes] = await Promise.all([
      getCurrentConsensusTask(),
      getCurrentConsensusAgents()
    ])
    applyPayload(taskRes.data, agentRes.data)
  } catch (err) {
    const status = err?.response?.status
    if ([404, 409, 503].includes(status)) {
      error.value = err?.response?.data?.error || err.message
    } else {
      error.value = err.message || t('consensus.loadFailed')
    }
    applyPayload(null, null)
  } finally {
    loading.value = false
  }
}

const restartPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  const interval = hasRunningTask.value ? 60000 : 30000
  pollTimer = setInterval(refreshAll, interval)
}

const handleStart = async () => {
  starting.value = true
  error.value = ''
  message.value = ''
  try {
    await startConsensusTask({
      question: form.value.question.trim(),
      threshold_percent: Number(form.value.thresholdPercent)
    })
    message.value = t('consensus.startSuccess')
    await refreshAll()
    restartPolling()
  } catch (err) {
    error.value = err?.response?.data?.error || err.message || t('consensus.startFailed')
  } finally {
    starting.value = false
  }
}

const handleStop = async () => {
  stopping.value = true
  error.value = ''
  message.value = ''
  try {
    await stopConsensusTask()
    message.value = t('consensus.stopSuccess')
    await refreshAll()
    restartPolling()
  } catch (err) {
    error.value = err?.response?.data?.error || err.message || t('consensus.stopFailed')
  } finally {
    stopping.value = false
  }
}

onMounted(async () => {
  agents.value = buildEmptyAgents()
  await refreshAll()
  restartPolling()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

watch(
  () => task.value?.status,
  () => {
    restartPolling()
  }
)
</script>

<style scoped>
.consensus-view {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(255, 125, 64, 0.18), transparent 28%),
    linear-gradient(180deg, #f8f4ee 0%, #f2ede4 100%);
  color: #111;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 28px;
  border-bottom: 1px solid rgba(17, 17, 17, 0.08);
}

.brand {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: 0.08em;
  cursor: pointer;
}

.topbar-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.content {
  max-width: 1280px;
  margin: 0 auto;
  padding: 28px;
}

.hero {
  margin-bottom: 24px;
}

.eyebrow {
  font-size: 12px;
  letter-spacing: 0.22em;
  color: #d2632b;
  margin-bottom: 8px;
}

.hero h1 {
  font-size: clamp(34px, 4vw, 56px);
  margin-bottom: 10px;
}

.hero p {
  max-width: 760px;
  font-size: 16px;
  color: #4b4b4b;
}

.panel {
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(17, 17, 17, 0.08);
  border-radius: 20px;
  padding: 22px;
  backdrop-filter: blur(10px);
  box-shadow: 0 18px 50px rgba(17, 17, 17, 0.07);
}

.input-panel {
  margin-bottom: 22px;
}

.panel-header,
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.form-grid {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 12px 16px;
  align-items: start;
}

textarea,
input {
  width: 100%;
  border: 1px solid rgba(17, 17, 17, 0.12);
  border-radius: 14px;
  padding: 12px 14px;
  background: #fffdf9;
  font: inherit;
}

.button-row {
  display: flex;
  gap: 12px;
  margin-top: 18px;
}

.primary-btn,
.danger-btn,
.ghost-btn,
.source-link {
  border-radius: 999px;
  padding: 10px 16px;
  border: 1px solid transparent;
  cursor: pointer;
  font: inherit;
  transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}

.primary-btn {
  background: #111;
  color: #fff;
}

.danger-btn {
  background: #c75028;
  color: #fff;
}

.ghost-btn {
  background: transparent;
  border-color: rgba(17, 17, 17, 0.16);
  color: #111;
}

.small-btn {
  padding: 6px 12px;
  font-size: 13px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  margin-bottom: 22px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.status-item {
  padding: 14px;
  background: rgba(17, 17, 17, 0.03);
  border-radius: 14px;
}

.status-item span {
  display: block;
  color: #666;
  font-size: 13px;
  margin-bottom: 6px;
}

.status-item.wide {
  grid-column: 1 / -1;
}

.final-box {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.final-answer {
  font-size: 18px;
  line-height: 1.6;
  font-weight: 600;
}

.final-evidence {
  line-height: 1.7;
  color: #454545;
}

.waiting,
.empty {
  color: #666;
  min-height: 48px;
  display: flex;
  align-items: center;
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.agent-card {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(17, 17, 17, 0.08);
  border-radius: 20px;
  padding: 18px;
  min-height: 168px;
}

.agent-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.agent-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: #666;
  margin-top: 6px;
}

.ready-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
}

.ready-pill.yes {
  background: rgba(41, 156, 94, 0.14);
  color: #1f7447;
}

.ready-pill.no {
  background: rgba(199, 80, 40, 0.14);
  color: #a74b27;
}

.content-short {
  margin: 16px 0;
  line-height: 1.7;
}

.card-actions {
  display: flex;
  gap: 10px;
}

.source-link {
  display: inline-flex;
  align-items: center;
  background: #fff3eb;
  color: #9a431f;
  text-decoration: none;
}

.history-list {
  border-top: 1px solid rgba(17, 17, 17, 0.08);
  margin-top: 14px;
  padding-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  background: rgba(17, 17, 17, 0.03);
  border-radius: 14px;
  padding: 12px;
}

.history-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.info-box,
.error-box {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 14px;
}

.info-box {
  background: rgba(17, 17, 17, 0.05);
}

.error-box {
  background: rgba(199, 80, 40, 0.14);
  color: #9c3f1f;
}

@media (max-width: 980px) {
  .grid,
  .agents-grid {
    grid-template-columns: 1fr;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
