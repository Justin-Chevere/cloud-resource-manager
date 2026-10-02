import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { createResource } from './api.ts'

export function CreateResourceForm({ onCreated }: { onCreated: (id: string) => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [image, setImage] = useState('nginx:latest')
  const create = useMutation({
    mutationFn: () => createResource(name.trim(), image.trim()),
    onSuccess: (resource) => {
      setName('')
      onCreated(resource.id)
      void queryClient.invalidateQueries({ queryKey: ['resources'] })
      void queryClient.invalidateQueries({ queryKey: ['audit'] })
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    create.mutate()
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>New resource</h2>
      <div className="create-fields">
        <label>
          Name
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="web-1"
            required
            pattern="[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]"
            title="3 to 63 lowercase letters, digits or hyphens, starting and ending with a letter or digit"
          />
        </label>
        <label>
          Image
          <input value={image} onChange={(event) => setImage(event.target.value)} required />
        </label>
        <button type="submit" className="button button-primary" disabled={create.isPending}>
          {create.isPending ? 'Creating…' : 'Create'}
        </button>
      </div>
      {create.isError && (
        <p className="form-error" role="alert">
          {create.error.message}
        </p>
      )}
    </form>
  )
}
