<template>
  <div class="min-h-screen bg-slate-100 flex justify-center py-0 sm:py-6 font-sans">
    <div class="w-full max-w-md bg-white min-h-screen sm:min-h-[840px] flex flex-col shadow-xl sm:rounded-2xl overflow-hidden relative border border-slate-200">
      <div class="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-white">
        <div class="flex items-center space-x-3">
          <button @click="router.push('/')" class="text-slate-600 hover:text-slate-900">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
          </button>
          <h1 class="text-xl font-bold font-serif text-slate-800 tracking-tight">Manufacturing</h1>
        </div>
        <div class="flex items-center space-x-2">
          <div class="w-8 h-8 rounded-full bg-slate-100 border border-slate-300 text-slate-700 font-semibold text-xs flex items-center justify-center">
            {{ userInitial }}
          </div>
        </div>
      </div>

      <div class="p-4 flex-1 bg-slate-50 space-y-3">
        <div 
          v-for="item in menuItems" 
          :key="item.label"
          @click="router.push(item.route)"
          class="flex items-center justify-between p-4 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-slate-300 cursor-pointer active:bg-slate-50 transition"
        >
          <div class="flex items-center space-x-3.5">
            <div class="w-9 h-9 rounded-lg bg-teal-50 border border-teal-200 flex items-center justify-center font-bold text-teal-800 text-xs">
              {{ item.code }}
            </div>
            <span class="text-sm font-semibold text-slate-800">{{ item.label }}</span>
          </div>
          <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
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
import { ref, computed } from 'vue'
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


const userInitial = computed(() => {
  const name = (window as any).frappe?.boot?.user?.full_name || 'S'
  return name.charAt(0).toUpperCase()
})

const menuItems = [
  { label: 'Work Order', code: 'WO', route: '/manufacturing/work-order' },
  { label: 'Job Card', code: 'JC', route: '/manufacturing/work-order' },
  { label: 'Stock Entry', code: 'SE', route: '/manufacturing/work-order' },
  { label: 'Stock Balance', code: 'SB', route: '/manufacturing/work-order' }
]
</script>
