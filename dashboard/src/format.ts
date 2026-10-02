export const MiB = 1024 * 1024
const GiB = 1024 * MiB

export function formatBytes(bytes: number): string {
  if (bytes >= GiB) return `${(bytes / GiB).toFixed(1)} GiB`
  return `${Math.round(bytes / MiB).toLocaleString('en-US')} MiB`
}

export function formatPercent(value: number): string {
  return `${Number(value.toFixed(1))}%`
}

// CPU readings are a percent of one core, so a total reads best in cores.
export function formatCores(percent: number): string {
  return `${(percent / 100).toFixed(2)} cores`
}

export function formatClock(time: number, withSeconds = true): string {
  return new Date(time).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    ...(withSeconds ? { second: '2-digit' } : {}),
  })
}

export function timeAgo(iso: string, now = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - Date.parse(iso)) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}
