<template>
  <div class="world-info-view">
    <header class="topbar">
      <div class="brand" @click="router.push('/')">MIROFISH</div>
      <div class="topbar-actions">
        <button class="ghost-btn" @click="router.push('/')">Home</button>
      </div>
    </header>

    <main class="content">
      <section class="hero">
        <div>
          <div class="eyebrow">WORLD INFO TEST</div>
          <h1>世界信息写入与回灌测试页</h1>
          <p>用于验证 `POST /api/world-info/ingest`、列表、检索和统计，不改现有主流程。</p>
        </div>
        <div class="project-box">
          <label>Project ID</label>
          <input v-model="projectId" placeholder="proj_xxxxxxxxxxxx" />
          <button class="primary-btn" @click="refreshAll" :disabled="!projectId || loadingAny">刷新当前项目</button>
        </div>
      </section>

      <section class="grid">
        <div class="panel">
          <h2>写入</h2>
          <div class="form-grid">
            <label>标题</label>
            <input v-model="ingestForm.title" placeholder="可选标题" />
            <label>来源</label>
            <input v-model="ingestForm.source" placeholder="来源 URL / 名称" />
            <label>来源类型</label>
            <input v-model="ingestForm.source_type" placeholder="news / report / note" />
            <label>发布时间</label>
            <input v-model="ingestForm.published_at" placeholder="2026-04-15T10:30:00" />
            <label>Metadata(JSON)</label>
            <textarea v-model="metadataText" rows="4" placeholder='{"tag":"demo"}'></textarea>
            <label>正文</label>
            <textarea v-model="ingestForm.content" rows="10" placeholder="输入世界信息正文"></textarea>
          </div>
          <div class="actions">
            <button class="primary-btn" @click="submitIngest" :disabled="loadingIngest || !projectId || !ingestForm.content.trim()">
              {{ loadingIngest ? '写入中...' : '写入世界信息' }}
            </button>
          </div>
          <pre v-if="ingestResult" class="result">{{ ingestResult }}</pre>
        </div>

        <div class="panel">
          <h2>语义检索</h2>
          <div class="form-grid">
            <label>Query</label>
            <input v-model="searchForm.query" placeholder="输入检索问题" />
            <label>Top K</label>
            <input v-model.number="searchForm.top_k" type="number" min="1" max="20" />
          </div>
          <div class="actions">
            <button class="primary-btn" @click="runSearch" :disabled="loadingSearch || !projectId || !searchForm.query.trim()">
              {{ loadingSearch ? '检索中...' : '检索世界信息' }}
            </button>
          </div>
          <div class="hits">
            <article v-for="hit in searchHits" :key="`${hit.chunk_id}-${hit.chunk_index}`" class="hit-card">
              <div class="hit-meta">
                <strong>{{ hit.title || `Item #${hit.item_id}` }}</strong>
                <span>{{ hit.source || '未知来源' }}</span>
                <span>score {{ formatScore(hit.score) }}</span>
              </div>
              <p>{{ hit.chunk_text }}</p>
            </article>
            <div v-if="!loadingSearch && searchHits.length === 0" class="empty">暂无检索结果</div>
          </div>
        </div>

        <div class="panel">
          <h2>项目列表</h2>
          <div class="toolbar">
            <button class="ghost-btn" @click="prevPage" :disabled="page <= 1 || loadingList">上一页</button>
            <span>Page {{ page }}</span>
            <button class="ghost-btn" @click="nextPage" :disabled="loadingList || !hasMore">下一页</button>
          </div>
          <div class="items">
            <article v-for="item in items" :key="item.item_id" class="item-card">
              <div class="item-head">
                <strong>{{ item.title || `Item #${item.item_id}` }}</strong>
                <span>{{ item.updated_at || item.created_at }}</span>
              </div>
              <div class="item-sub">{{ item.source || '未知来源' }}</div>
              <p>{{ item.summary }}</p>
            </article>
            <div v-if="!loadingList && items.length === 0" class="empty">暂无数据</div>
          </div>
        </div>

        <div class="panel">
          <h2>统计</h2>
          <div class="stats">
            <div class="stat">
              <span class="label">Items</span>
              <strong>{{ stats.items_count ?? '-' }}</strong>
            </div>
            <div class="stat">
              <span class="label">Chunks</span>
              <strong>{{ stats.chunks_count ?? '-' }}</strong>
            </div>
            <div class="stat wide">
              <span class="label">Last Updated</span>
              <strong>{{ stats.last_updated_at || '-' }}</strong>
            </div>
          </div>
          <div v-if="error" class="error-box">{{ error }}</div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getWorldInfoStats,
  ingestWorldInfo,
  listWorldInfoItems,
  searchWorldInfo
} from '../api/worldInfo'

const router = useRouter()

const projectId = ref('')
const page = ref(1)
const pageSize = 20

const ingestForm = ref({
  title: '',
  source: '',
  source_type: '',
  published_at: '',
  content: ''
})
const metadataText = ref('{}')
const searchForm = ref({
  query: '',
  top_k: 8
})

const stats = ref({})
const items = ref([])
const total = ref(0)
const searchHits = ref([])
const error = ref('')
const ingestResult = ref('')

const loadingIngest = ref(false)
const loadingSearch = ref(false)
const loadingList = ref(false)
const loadingStats = ref(false)

const loadingAny = computed(() => {
  return loadingIngest.value || loadingSearch.value || loadingList.value || loadingStats.value
})

const hasMore = computed(() => page.value * pageSize < total.value)

const parseMetadata = () => {
  if (!metadataText.value.trim()) return {}
  return JSON.parse(metadataText.value)
}

const refreshStats = async () => {
  if (!projectId.value) return
  loadingStats.value = true
  try {
    const res = await getWorldInfoStats(projectId.value)
    stats.value = res.data || {}
  } finally {
    loadingStats.value = false
  }
}

const refreshList = async () => {
  if (!projectId.value) return
  loadingList.value = true
  try {
    const res = await listWorldInfoItems(projectId.value, { page: page.value, page_size: pageSize })
    items.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally {
    loadingList.value = false
  }
}

const refreshAll = async () => {
  error.value = ''
  searchHits.value = []
  ingestResult.value = ''
  if (!projectId.value) return
  try {
    await Promise.all([refreshStats(), refreshList()])
  } catch (err) {
    error.value = err.message || '刷新失败'
  }
}

const submitIngest = async () => {
  error.value = ''
  ingestResult.value = ''
  loadingIngest.value = true
  try {
    const res = await ingestWorldInfo({
      project_id: projectId.value,
      ...ingestForm.value,
      metadata: parseMetadata()
    })
    ingestResult.value = JSON.stringify(res.data, null, 2)
    await refreshAll()
  } catch (err) {
    error.value = err.message || '写入失败'
  } finally {
    loadingIngest.value = false
  }
}

const runSearch = async () => {
  error.value = ''
  loadingSearch.value = true
  try {
    const res = await searchWorldInfo({
      project_id: projectId.value,
      query: searchForm.value.query,
      top_k: searchForm.value.top_k
    })
    searchHits.value = res.data?.hits || []
  } catch (err) {
    error.value = err.message || '检索失败'
  } finally {
    loadingSearch.value = false
  }
}

const prevPage = async () => {
  if (page.value <= 1) return
  page.value -= 1
  await refreshList()
}

const nextPage = async () => {
  if (!hasMore.value) return
  page.value += 1
  await refreshList()
}

const formatScore = (score) => {
  if (score === null || score === undefined || Number.isNaN(Number(score))) return '-'
  return Number(score).toFixed(4)
}
</script>

<style scoped>
.world-info-view {
  min-height: 100vh;
  background: linear-gradient(180deg, #fafafa 0%, #f0f0ef 100%);
  color: #111;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.topbar {
  height: 64px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #dedede;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  letter-spacing: 1px;
  cursor: pointer;
}

.content {
  max-width: 1440px;
  margin: 0 auto;
  padding: 36px 32px 48px;
}

.hero {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 24px;
  margin-bottom: 28px;
}

.eyebrow {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  letter-spacing: 2px;
  color: #8a5a00;
  margin-bottom: 12px;
}

.hero h1 {
  font-size: 42px;
  line-height: 1.1;
  margin-bottom: 12px;
}

.hero p {
  color: #555;
  max-width: 820px;
}

.project-box,
.panel {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid #d8d8d8;
  border-radius: 18px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}

.project-box {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.panel {
  padding: 20px;
}

.panel h2 {
  margin-bottom: 16px;
  font-size: 24px;
}

.form-grid {
  display: grid;
  gap: 10px;
}

label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #777;
}

input,
textarea {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #d4d4d4;
  border-radius: 12px;
  background: #fcfcfc;
  font: inherit;
}

textarea {
  resize: vertical;
}

.actions,
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.primary-btn,
.ghost-btn {
  border-radius: 999px;
  padding: 10px 16px;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
}

.primary-btn {
  background: #111;
  color: #fff;
  border: 1px solid #111;
}

.primary-btn:disabled,
.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ghost-btn {
  background: transparent;
  border: 1px solid #cfcfcf;
}

.result,
.error-box {
  margin-top: 16px;
  padding: 14px;
  border-radius: 12px;
  overflow: auto;
}

.result {
  background: #f7f7f7;
  border: 1px solid #e0e0e0;
}

.error-box {
  background: #fff1f1;
  color: #9e2a2a;
  border: 1px solid #f1c9c9;
}

.hits,
.items,
.stats {
  display: grid;
  gap: 12px;
}

.hit-card,
.item-card {
  padding: 14px;
  border: 1px solid #e3e3e3;
  border-radius: 14px;
  background: #fbfbfb;
}

.hit-meta,
.item-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}

.item-sub {
  margin-bottom: 8px;
  color: #888;
  font-size: 13px;
}

.stats {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.stat {
  padding: 16px;
  border-radius: 16px;
  background: linear-gradient(135deg, #fff7e8 0%, #fff 100%);
  border: 1px solid #ead7b5;
}

.stat.wide {
  grid-column: 1 / -1;
}

.label {
  display: block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #8a6a2f;
  margin-bottom: 6px;
}

.empty {
  padding: 20px 0;
  color: #888;
}

@media (max-width: 980px) {
  .hero,
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
