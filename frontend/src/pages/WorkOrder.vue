<template>
  <div class="min-h-screen bg-slate-100 flex justify-center py-0 sm:py-6 font-sans">
    <div class="w-full max-w-md bg-white min-h-screen sm:min-h-[840px] flex flex-col shadow-xl sm:rounded-2xl overflow-hidden relative border border-slate-200">
      <div class="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-white">
        <div class="flex items-center space-x-3">
          <button @click="router.push('/manufacturing')" class="text-slate-600 hover:text-slate-900">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
          </button>
          <h1 class="text-xl font-bold font-serif text-slate-800 tracking-tight">Work Order</h1>
        </div>
        <div class="flex items-center space-x-2">
          <div class="w-8 h-8 rounded-full bg-slate-100 border border-slate-300 text-slate-700 font-semibold text-xs flex items-center justify-center">
            {{ userInitial }}
          </div>
        </div>
      </div>

      <div class="p-4 bg-white border-b border-slate-100 space-y-3">
        <input 
          v-model="searchQuery" 
          type="text" 
          placeholder="Search order or item" 
          class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
        />
        
        <div>
          <label class="text-[11px] font-semibold text-slate-500 block mb-1">Batch No.</label>
          <input 
            v-model="batchQuery" 
            type="text" 
            placeholder="Search and select batch" 
            class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
          />
        </div>

        <div class="flex space-x-2 pt-1 overflow-x-auto pb-1">
          <button 
            v-for="tab in ['All', 'Not Started', 'In Process', 'Completed']" 
            :key="tab"
            @click="activeTab = tab"
            :class="['px-3.5 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition', 
              activeTab === tab ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200']"
          >
            {{ tab }}
          </button>
        </div>
      </div>

      <div class="p-4 flex-1 bg-slate-50 overflow-y-auto space-y-3">
        <div v-if="loading" class="text-center py-10 text-xs text-slate-400">Loading work orders...</div>
        <div v-else-if="filteredOrders.length === 0" class="text-center py-10 text-xs text-slate-400">
          No work orders found.
        </div>

        <div 
          v-for="order in filteredOrders" 
          :key="order.name"
          class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm hover:border-slate-300 transition text-left"
        >
          <div class="flex justify-between items-start">
            <span class="text-xs font-bold text-slate-800 tracking-tight">{{ order.name }}</span>
            <span class="text-[11px] font-semibold text-slate-500">{{ order.status }}</span>
          </div>

          <div class="mt-2 text-xs space-y-0.5 text-slate-600">
            <p><span class="text-slate-400">Production Item:</span> <span class="font-medium text-slate-700">{{ order.production_item }}</span></p>
            <p><span class="text-slate-400">Item Name:</span> <span class="font-medium text-slate-700">{{ order.item_name || order.production_item }}</span></p>
            <p><span class="text-slate-400">Batch No.:</span> <span class="font-medium text-slate-700">{{ order.batch_no || 'N/A' }}</span></p>
            <p><span class="text-slate-400">Quantity:</span> <span class="font-semibold text-slate-800">{{ order.produced_qty || 0 }} / {{ order.qty }}</span></p>
          </div>
        </div>
      </div>

      <div v-if="showInstall" class="p-3 bg-white border-t border-slate-200 flex items-center justify-between shadow-lg">
        <div>
          <p class="text-xs font-bold text-slate-800">Install SR Connect</p>
          <p class="text-[10px] text-slate-500">Get the app on your device for easy access.</p>
        </div>
        <div class="flex items-center space-x-1.5">
          <button @click="installApp" class="px-3.5 py-1.5 bg-slate-900 text-white text-xs font-semibold rounded-lg hover:bg-slate-800">Install</button>
          <button @click="showInstall = false" class="px-2 py-1 text-slate-400 hover:text-slate-600 text-xs">✕</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const showInstall = ref(true)

let deferredInstallPrompt = null

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault()
  deferredInstallPrompt = event
  window.__srDeferredInstallPrompt = event
  showInstall.value = true
})

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null
  window.__srDeferredInstallPrompt = null
  showInstall.value = false
})

const installApp = async () => {
  const promptEvent =
    deferredInstallPrompt ||
    window.__srDeferredInstallPrompt

  if (!promptEvent) {
    alert("Install prompt এখনো available হয়নি। Page refresh করে আবার Install চাপুন।")
    return
  }

  try {
    promptEvent.prompt()

    const choice = await promptEvent.userChoice

    deferredInstallPrompt = null
    window.__srDeferredInstallPrompt = null

    console.log(
      "SR Connect install:",
      choice && choice.outcome
    )

    if (choice && choice.outcome === "accepted") {
      showInstall.value = false
    }
  } catch (error) {
    console.error("SR Connect install failed:", error)
  }
}

const activeTab = ref('All')
const searchQuery = ref('')
const batchQuery = ref('')
const loading = ref(true)
const workOrders = ref<any[]>([])

const userInitial = computed(() => {
  const name = (window as any).frappe?.boot?.user?.full_name || 'S'
  return name.charAt(0).toUpperCase()
})

const fetchWorkOrders = async () => {
  loading.value = true
  try {
    const res = await fetch('/api/method/frappe.desk.reportview.get', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': (window as any).frappe?.csrf_token || ''
      },
      body: JSON.stringify({
        doctype: 'Work Order',
        fields: ['name', 'production_item', 'item_name', 'qty', 'produced_qty', 'status', 'batch_no'],
        limit_page_length: 50,
        order_by: 'creation desc'
      })
    })
    const data = await res.json()
    if (data.message && data.message.values) {
      workOrders.value = data.message.values.map((row: any[]) => ({
        name: row[0],
        production_item: row[1],
        item_name: row[2],
        qty: row[3],
        produced_qty: row[4],
        status: row[5],
        batch_no: row[6]
      }))
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const filteredOrders = computed(() => {
  return workOrders.value.filter(o => {
    const matchTab = activeTab.value === 'All' || o.status === activeTab.value
    const matchSearch = !searchQuery.value || 
      o.name.toLowerCase().includes(searchQuery.value.toLowerCase()) || 
      (o.production_item && o.production_item.toLowerCase().includes(searchQuery.value.toLowerCase()))
    const matchBatch = !batchQuery.value || 
      (o.batch_no && o.batch_no.toLowerCase().includes(batchQuery.value.toLowerCase()))
    return matchTab && matchSearch && matchBatch
  })
})

onMounted(() => {
  fetchWorkOrders()
})
</script>
