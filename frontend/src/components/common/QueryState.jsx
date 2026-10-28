/** Uniform loading / error / empty handling for TanStack Query results. */
export default function QueryState({ query, empty, children }) {
  if (query.isError) return <p role="alert" className="error">{query.error.message}</p>
  // A disabled query (e.g. waiting for the season to load) has no data and is not "loading".
  if (query.isLoading || query.data === undefined) return <p role="status" className="muted">Loading…</p>
  if (empty && empty(query.data)) {
    return <p className="muted">No data yet. Ingest a session first.</p>
  }
  return children(query.data)
}
