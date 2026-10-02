import { useQuery } from '@tanstack/react-query'
import { describeEvent } from './activity.ts'
import { listAudit } from './api.ts'
import type { Resource } from './api.ts'
import { timeAgo } from './format.ts'

export function ActivityFeed({ resources }: { resources: Resource[] }) {
  const audit = useQuery({
    queryKey: ['audit'],
    queryFn: () => listAudit(15),
    refetchInterval: 10_000,
  })
  const names = new Map(resources.map((resource) => [resource.id, resource.name]))
  const events = audit.data ?? []

  return (
    <section className="card" aria-labelledby="activity-title">
      <h2 id="activity-title">Recent activity</h2>
      {events.length === 0 ? (
        <p className="muted">{audit.isPending ? 'Loading…' : 'Nothing yet.'}</p>
      ) : (
        <ol className="activity">
          {events.map((event) => (
            <li key={event.id}>
              <span>
                <strong>{event.actor}</strong> {describeEvent(event, names)}
              </span>
              <time
                className="muted"
                dateTime={event.created_at}
                title={new Date(event.created_at).toLocaleString()}
              >
                {timeAgo(event.created_at)}
              </time>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
