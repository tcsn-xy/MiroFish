<template>
  <div class="consensus-view">
    <header class="topbar">
      <div class="brand" @click="router.push('/')">MIROFISH</div>
      <div class="topbar-actions">
        <button class="ghost-btn" @click="router.push('/')">返回首页</button>
      </div>
    </header>

    <main class="content">
      <section class="hero">
        <div class="hero-copy">
          <div class="eyebrow">CONSENSUS QA</div>
          <h1>Consensus QA / 共识问答</h1>
          <p>
            直接使用默认 10 人 persona catalog 发起 yes/no 共识题。保留当前任务、人格判断与轮次历史，不要求手动选择 simulation。
          </p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>创建题目</h2>
          <span class="meta">默认 persona catalog 同时只允许一道运行中题目</span>
        </div>

        <div class="catalog-summary" v-if="defaultCatalog">
          <div class="catalog-card">
            <span class="status-label">默认入口</span>
            <strong>{{ defaultCatalog.catalog_name }}</strong>
          </div>
          <div class="catalog-card">
            <span class="status-label">兼容 simulation_id</span>
            <strong>{{ activeSimulationId }}</strong>
          </div>
          <div class="catalog-card">
            <span class="status-label">人格数量</span>
            <strong>{{ defaultCatalog.personas?.length || 0 }}</strong>
          </div>
        </div>

        <div class="form-grid">
          <label>阈值 %</label>
          <input v-model.number="thresholdPercent" type="number" min="1" max="100" />

          <label>搜集间隔</label>
          <div class="interval-inputs">
            <input
              v-model.number="pollIntervalValue"
              type="number"
              min="1"
              step="1"
              placeholder="30"
            />
            <select v-model="pollIntervalUnit">
              <option value="seconds">秒</option>
              <option value="minutes">分钟</option>
              <option value="hours">小时</option>
              <option value="days">天</option>
            </select>
          </div>

          <label>问题</label>
          <textarea
            v-model="questionText"
            rows="4"
            placeholder="例如：下一任美国总统会是万斯吗？"
          />
        </div>

        <div class="actions">
          <button
            class="primary-btn"
            :disabled="starting || !catalogReady || !questionText.trim() || Boolean(pollIntervalError)"
            @click="handleStartTask"
          >
            {{ starting ? '启动中...' : '启动题目' }}
          </button>
          <button class="ghost-btn" :disabled="refreshing || !catalogReady" @click="refreshConsensusView">
            刷新
          </button>
        </div>

        <div v-if="pollIntervalError" class="error-box">{{ pollIntervalError }}</div>
        <div v-if="errorMessage" class="error-box">{{ errorMessage }}</div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>默认 Persona Catalog</h2>
          <span class="meta">技术、学术、媒体、政策、创业、教育、法律、医疗、消费与产业视角</span>
        </div>

        <div v-if="defaultCatalog?.personas?.length" class="persona-grid">
          <article
            v-for="persona in defaultCatalog.personas"
            :key="persona.user_id"
            class="persona-card"
          >
            <div class="persona-role">{{ persona.profession || 'Persona' }}</div>
            <p class="persona-bio">{{ persona.bio }}</p>
            <p class="persona-detail">{{ persona.persona }}</p>
          </article>
        </div>

        <div v-else class="empty-box">暂无默认 persona 数据。</div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>当前任务</h2>
          <span class="meta">任务区与人格卡片每 5 秒轮询，历史区每 10 秒轮询</span>
        </div>

        <div v-if="currentTask" class="status-grid">
          <div class="status-card">
            <span class="status-label">任务 UID</span>
            <strong>{{ currentTask.task_uid }}</strong>
          </div>
          <div class="status-card">
            <span class="status-label">状态</span>
            <strong :class="['status-pill', currentTask.status]">{{ getStatusLabel(currentTask.status) }}</strong>
          </div>
          <div class="status-card">
            <span class="status-label">轮次</span>
            <strong>{{ currentTask.current_round_index }}</strong>
          </div>
          <div class="status-card">
            <span class="status-label">阈值</span>
            <strong>{{ currentTask.threshold_percent }}%</strong>
          </div>
          <div class="status-card">
            <span class="status-label">可回答人数</span>
            <strong>{{ currentTask.last_answerable_agents }} / {{ currentTask.total_agents }}</strong>
          </div>
          <div class="status-card">
            <span class="status-label">是 / 否</span>
            <strong>{{ currentTask.last_yes_agents }} / {{ currentTask.last_no_agents }}</strong>
          </div>
          <div class="status-card">
            <span class="status-label">搜集间隔</span>
            <strong>{{ formatPollInterval(currentTask.poll_interval_seconds) }}</strong>
          </div>
          <div class="status-card wide">
            <span class="status-label">问题</span>
            <strong>{{ currentTask.question_text }}</strong>
          </div>
          <div v-if="currentTask.final_reason_short" class="status-card wide">
            <span class="status-label">完成说明</span>
            <strong>{{ currentTask.final_reason_short }}</strong>
          </div>
        </div>

        <div v-else class="empty-box">当前默认 persona catalog 暂无任务。</div>

        <div class="actions">
          <button
            class="danger-btn"
            :disabled="!currentTask || currentTask.status !== 'running' || stopping"
            @click="handleStopTask"
          >
            {{ stopping ? '停止中...' : '停止当前题目' }}
          </button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>人格卡片</h2>
          <span class="meta">已完成任务取完成轮答案。已停止或已中断任务取最后一轮答案。</span>
        </div>

        <div v-if="agentCards.length" class="agent-grid">
          <article v-for="agent in agentCards" :key="agent.agent_source_id" class="agent-card">
            <button class="agent-header" @click="toggleAgent(agent.agent_source_id)">
              <div>
                <div class="agent-name">{{ agent.profession || 'Persona' }}</div>
              </div>
              <div class="agent-answer" :class="answerClass(agent.card_answer)">
                {{ getAnswerLabel(agent.card_answer) }}
              </div>
            </button>

            <div v-if="expandedAgents[agent.agent_source_id]" class="agent-history">
              <div
                v-for="entry in agent.history"
                :key="`${agent.agent_source_id}-${entry.round_index}-${entry.polled_at}`"
                class="history-row"
              >
                <div class="history-top">
                  <span>第 {{ entry.round_index }} 轮</span>
                  <span>{{ getAnswerLabel(entry.candidate_answer) }}</span>
                  <span>{{ entry.polled_at }}</span>
                </div>
                <div class="history-body">{{ entry.content_short }}</div>
                <div class="history-meta">
                  <span>可回答：{{ entry.is_answerable ? '是' : '否' }}</span>
                  <span v-if="entry.evidence_title">标题：{{ entry.evidence_title }}</span>
                  <a
                    v-if="entry.evidence_url"
                    :href="entry.evidence_url"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {{ entry.evidence_url }}
                  </a>
                  <span v-if="entry.evidence_time">时间：{{ entry.evidence_time }}</span>
                  <span v-if="entry.error_text">错误：{{ entry.error_text }}</span>
                </div>
              </div>
            </div>
          </article>
        </div>

        <div v-else class="empty-box">暂无人格卡片数据。</div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>默认 Catalog 历史</h2>
        </div>

        <div v-if="historyTasks.length" class="history-groups">
          <article class="history-group">
            <div class="group-head">
              <h3>{{ activeSimulationId }}</h3>
              <span>{{ historyTasks.length }} 条任务</span>
            </div>

            <div class="task-list">
              <button
                v-for="task in historyTasks"
                :key="task.task_uid"
                class="task-row"
                @click="selectTaskFromHistory(task)"
              >
                <span>{{ task.task_uid }}</span>
                <span>{{ getStatusLabel(task.status) }}</span>
                <span>{{ task.question_text }}</span>
                <span>R{{ task.current_round_index }}</span>
              </button>
            </div>
          </article>
        </div>

        <div v-else class="empty-box">暂无历史记录。</div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getConsensusTaskAgents,
  getCurrentConsensusTask,
  getDefaultConsensusCatalog,
  listConsensusTasks,
  startConsensusTask,
  stopConsensusTask
} from '../api/consensus'

const router = useRouter()

const defaultCatalog = ref(null)
const questionText = ref('')
const thresholdPercent = ref(60)
const pollIntervalValue = ref(30)
const pollIntervalUnit = ref('seconds')

const currentTask = ref(null)
const agentCards = ref([])
const historyTasks = ref([])
const expandedAgents = reactive({})

const starting = ref(false)
const stopping = ref(false)
const refreshing = ref(false)
const loadingCatalog = ref(false)
const errorMessage = ref('')

let taskPollTimer = null
let agentPollTimer = null
let historyPollTimer = null

const activeSimulationId = computed(() => defaultCatalog.value?.simulation_id || '')
const catalogReady = computed(() => Boolean(activeSimulationId.value))
const pollIntervalSeconds = computed(() => {
  const value = Number(pollIntervalValue.value)
  const unitMultipliers = {
    seconds: 1,
    minutes: 60,
    hours: 3600,
    days: 86400
  }
  return Number.isFinite(value) ? Math.floor(value * (unitMultipliers[pollIntervalUnit.value] || 1)) : 0
})
const pollIntervalError = computed(() => {
  const rawValue = pollIntervalValue.value
  if (!Number.isInteger(rawValue) || rawValue < 1) {
    return '搜集间隔必须是正整数'
  }
  const seconds = pollIntervalSeconds.value
  if (seconds < 30) {
    return '搜集间隔不能少于 30 秒'
  }
  if (seconds > 30 * 24 * 60 * 60) {
    return '搜集间隔不能超过 30 天'
  }
  return ''
})

const answerClass = (answer) => {
  if (answer === 'yes') return 'yes'
  if (answer === 'no') return 'no'
  return 'pending'
}

const getAnswerLabel = (answer) => {
  if (answer === 'yes') return '是'
  if (answer === 'no') return '否'
  return '待定'
}

const getStatusLabel = (status) => {
  if (status === 'running') return '运行中'
  if (status === 'completed') return '已完成'
  if (status === 'stopped') return '已停止'
  if (status === 'interrupted') return '已中断'
  return status || '-'
}

const formatPollInterval = (seconds) => {
  const value = Number(seconds)
  if (!Number.isFinite(value) || value <= 0) return '-'
  if (value % 86400 === 0) return `${value / 86400} 天`
  if (value % 3600 === 0) return `${value / 3600} 小时`
  if (value % 60 === 0) return `${value / 60} 分钟`
  return `${value} 秒`
}

const toggleAgent = (agentId) => {
  expandedAgents[agentId] = !expandedAgents[agentId]
}

const clearPolling = () => {
  if (taskPollTimer) clearInterval(taskPollTimer)
  if (agentPollTimer) clearInterval(agentPollTimer)
  if (historyPollTimer) clearInterval(historyPollTimer)
}

const resetPolling = () => {
  clearPolling()

  taskPollTimer = setInterval(() => {
    refreshCurrentTask()
  }, 5000)

  agentPollTimer = setInterval(() => {
    refreshAgentCards()
  }, 5000)

  historyPollTimer = setInterval(() => {
    refreshHistory()
  }, 10000)
}

const loadDefaultCatalog = async () => {
  loadingCatalog.value = true
  try {
    const res = await getDefaultConsensusCatalog()
    defaultCatalog.value = res.data || null
  } finally {
    loadingCatalog.value = false
  }
}

const refreshCurrentTask = async () => {
  if (!activeSimulationId.value) {
    currentTask.value = null
    return
  }
  const res = await getCurrentConsensusTask(activeSimulationId.value)
  currentTask.value = res.data || null
}

const refreshAgentCards = async () => {
  if (!currentTask.value?.task_uid) {
    agentCards.value = []
    return
  }
  const res = await getConsensusTaskAgents(currentTask.value.task_uid)
  agentCards.value = res.data?.agents || []
}

const refreshHistory = async () => {
  if (!activeSimulationId.value) {
    historyTasks.value = []
    return
  }
  const res = await listConsensusTasks(activeSimulationId.value)
  historyTasks.value = res.data || []
}

const refreshConsensusView = async () => {
  if (!catalogReady.value) return
  refreshing.value = true
  errorMessage.value = ''
  try {
    await Promise.all([refreshCurrentTask(), refreshHistory()])
    await refreshAgentCards()
  } catch (error) {
    errorMessage.value = error.message || '刷新失败'
  } finally {
    refreshing.value = false
  }
}

const handleStartTask = async () => {
  if (pollIntervalError.value) {
    errorMessage.value = pollIntervalError.value
    return
  }
  starting.value = true
  errorMessage.value = ''
  try {
    const res = await startConsensusTask({
      simulation_id: activeSimulationId.value,
      question_text: questionText.value,
      threshold_percent: thresholdPercent.value,
      poll_interval_seconds: pollIntervalSeconds.value
    })
    currentTask.value = res.data
    questionText.value = ''
    await Promise.all([refreshAgentCards(), refreshHistory()])
  } catch (error) {
    errorMessage.value = error.message || '启动失败'
  } finally {
    starting.value = false
  }
}

const handleStopTask = async () => {
  if (!currentTask.value?.task_uid) return
  stopping.value = true
  errorMessage.value = ''
  try {
    const res = await stopConsensusTask({
      task_uid: currentTask.value.task_uid
    })
    currentTask.value = res.data
    await Promise.all([refreshAgentCards(), refreshHistory()])
  } catch (error) {
    errorMessage.value = error.message || '停止失败'
  } finally {
    stopping.value = false
  }
}

const selectTaskFromHistory = async (task) => {
  currentTask.value = task
  await refreshAgentCards()
}

onMounted(async () => {
  try {
    await loadDefaultCatalog()
    await refreshConsensusView()
    resetPolling()
  } catch (error) {
    errorMessage.value = error.message || '页面初始化失败'
  }
})

onUnmounted(() => {
  clearPolling()
})
</script>

<style scoped>
.consensus-view {
  min-height: 100vh;
  background:
    radial-gradient(circle at top right, rgba(255, 115, 0, 0.15), transparent 32%),
    linear-gradient(180deg, #f9f4eb 0%, #f4efe8 100%);
  color: #141414;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.topbar {
  height: 64px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #111111;
  color: #ffffff;
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  cursor: pointer;
}

.topbar-actions {
  display: flex;
  gap: 12px;
}

.content {
  max-width: 1440px;
  margin: 0 auto;
  padding: 32px;
  display: grid;
  gap: 24px;
}

.hero {
  background: linear-gradient(135deg, rgba(20, 20, 20, 0.95), rgba(20, 20, 20, 0.8));
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 32px;
}

.eyebrow {
  display: inline-block;
  margin-bottom: 12px;
  padding: 4px 8px;
  background: #ff6a00;
  color: #111111;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
}

.panel {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(17, 17, 17, 0.08);
  backdrop-filter: blur(8px);
  padding: 24px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: baseline;
  margin-bottom: 16px;
}

.panel-head h2 {
  margin: 0;
}

.meta {
  color: #6f6f6f;
  font-size: 13px;
}

.catalog-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.catalog-card {
  background: #fffaf3;
  border: 1px solid #e5ded0;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-grid {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 14px 16px;
}

.interval-inputs {
  display: flex;
  gap: 10px;
  align-items: center;
}

.interval-inputs input {
  width: 140px;
}

.interval-inputs select {
  min-width: 120px;
  border: 1px solid #d9d4c9;
  background: rgba(255, 250, 243, 0.9);
  padding: 12px;
  font: inherit;
  color: #141414;
}

.form-grid label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  padding-top: 12px;
}

.form-grid input,
.form-grid textarea {
  width: 100%;
  border: 1px solid #d9d4c9;
  background: rgba(255, 250, 243, 0.9);
  padding: 12px;
  font: inherit;
  color: #141414;
}

.actions {
  margin-top: 18px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.primary-btn,
.ghost-btn,
.danger-btn {
  border: none;
  padding: 12px 18px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
}

.primary-btn {
  background: #111111;
  color: #ffffff;
}

.ghost-btn {
  background: transparent;
  border: 1px solid #111111;
  color: #111111;
}

.danger-btn {
  background: #c53d13;
  color: #ffffff;
}

.primary-btn:disabled,
.ghost-btn:disabled,
.danger-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.persona-grid,
.status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.persona-card,
.status-card {
  background: #fffaf3;
  border: 1px solid #e5ded0;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.persona-role,
.status-label {
  font-size: 12px;
  color: #72695c;
  font-family: 'JetBrains Mono', monospace;
}

.persona-bio,
.persona-detail {
  line-height: 1.5;
}

.persona-detail {
  color: #5a5348;
}

.status-card.wide {
  grid-column: span 3;
}

.status-pill.running {
  color: #945f00;
}

.status-pill.completed {
  color: #197447;
}

.status-pill.stopped,
.status-pill.interrupted {
  color: #9a2c2c;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.agent-card {
  border: 1px solid #e2dbce;
  background: #fffdf9;
}

.agent-header {
  width: 100%;
  border: none;
  background: transparent;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  text-align: left;
}

.agent-name {
  font-weight: 700;
}

.agent-answer {
  min-width: 70px;
  text-align: center;
  padding: 8px 10px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
}

.agent-answer.yes {
  background: rgba(25, 116, 71, 0.12);
  color: #197447;
}

.agent-answer.no {
  background: rgba(175, 51, 51, 0.12);
  color: #af3333;
}

.agent-answer.pending {
  background: rgba(148, 95, 0, 0.12);
  color: #945f00;
}

.agent-history {
  border-top: 1px solid #e2dbce;
  padding: 12px 16px 16px;
  display: grid;
  gap: 12px;
}

.history-row {
  border: 1px solid #ece4d7;
  background: #faf6ef;
  padding: 12px;
  display: grid;
  gap: 8px;
}

.history-top,
.history-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #6f675a;
  font-family: 'JetBrains Mono', monospace;
}

.history-body {
  line-height: 1.5;
}

.history-meta a {
  color: #b64c0b;
  word-break: break-all;
}

.history-groups {
  display: grid;
  gap: 16px;
}

.history-group {
  border: 1px solid #e2dbce;
  background: #fffdf9;
}

.group-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #ece4d7;
}

.group-head h3 {
  margin: 0;
  font-size: 18px;
}

.task-list {
  display: grid;
}

.task-row {
  display: grid;
  grid-template-columns: 240px 120px 1fr 70px;
  gap: 12px;
  text-align: left;
  padding: 14px 16px;
  border: none;
  border-top: 1px solid #f2ebde;
  background: transparent;
  cursor: pointer;
}

.task-row:hover {
  background: rgba(255, 106, 0, 0.06);
}

.empty-box,
.error-box {
  padding: 16px;
  background: #fffaf3;
  border: 1px dashed #d9d0c0;
}

.error-box {
  margin-top: 16px;
  color: #af3333;
}

@media (max-width: 960px) {
  .content {
    padding: 20px;
  }

  .interval-inputs {
    flex-direction: column;
    align-items: stretch;
  }

  .interval-inputs input {
    width: 100%;
  }

  .catalog-summary,
  .form-grid,
  .persona-grid,
  .status-grid,
  .task-row {
    grid-template-columns: 1fr;
  }

  .status-card.wide {
    grid-column: span 1;
  }
}
</style>
