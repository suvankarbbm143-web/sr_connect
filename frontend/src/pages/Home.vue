<template>
  <div class="min-h-screen bg-slate-100 flex justify-center py-0 sm:py-6 font-sans">
    <div class="w-full max-w-md bg-white min-h-screen sm:min-h-[840px] flex flex-col shadow-xl sm:rounded-2xl overflow-hidden relative border border-slate-200">
      <div class="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-white">
        <h1 class="text-xl font-bold font-serif text-slate-800 tracking-tight">
          {{ userFullName }}
        </h1>
        <div class="flex items-center space-x-2">
          <button @click="logout" title="Logout" class="p-1.5 rounded-lg text-rose-500 hover:bg-rose-50 transition text-xs font-semibold flex items-center space-x-1">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
            <span>Exit</span>
          </button>
          <div class="w-8 h-8 rounded-full bg-slate-100 border border-slate-300 text-slate-700 font-semibold text-xs flex items-center justify-center">
            {{ userInitial }}
          </div>
        </div>
      </div>

      <div class="p-4 flex-1 bg-slate-50 overflow-y-auto pb-24">
        <h2 class="text-sm font-bold text-slate-800 mb-3 px-1">Quick Links</h2>
        <div class="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden shadow-sm">
          <div 
            v-for="item in quickLinks" 
            :key="item.label"
            @click="navigate(item)"
            class="flex items-center justify-between p-3.5 hover:bg-slate-50 active:bg-slate-100 cursor-pointer transition"
          >
            <div class="flex items-center space-x-3">
              <div :class="['w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold', item.colorClass]">
                {{ item.iconText || '' }}
                <span v-if="!item.iconText" v-html="item.svg"></span>
              </div>
              <span class="text-sm font-medium text-slate-700">{{ item.label }}</span>
            </div>
            <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const userFullName = computed(() => {
  return (window as any).frappe?.boot?.user?.full_name || 'Suvankar Roy'
})

const userInitial = computed(() => {
  return userFullName.value.charAt(0).toUpperCase()
})

const logout = () => {
  window.location.href = '/api/method/logout'
}

const navigate = (item: any) => {
  if (item.internal) {
    router.push(item.route)
  } else {
    window.location.href = `/app/${item.route}`
  }
}

const quickLinks = [
  {
    label: 'ToDo',
    route: 'todo',
    colorClass: 'bg-slate-100 text-slate-700',
    svg: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>'
  },
  {
    label: 'Manufacturing',
    route: '/manufacturing',
    internal: true,
    colorClass: 'bg-teal-100 text-teal-800 font-bold',
    iconText: 'M'
  },
  {
    label: 'Sales Order',
    route: 'sales-order',
    colorClass: 'bg-sky-100 text-sky-800',
    svg: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>'
  },
  {
    label: 'Pick List',
    route: 'pick-list',
    colorClass: 'bg-emerald-100 text-emerald-800',
    svg: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>'
  },
  {
    label: 'Delivery Note',
    route: 'delivery-note',
    colorClass: 'bg-indigo-100 text-indigo-800',
    svg: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0"/></svg>'
  }
]
</script>
