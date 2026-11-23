import { useEffect, useState } from 'react'

// The UI never loads "everything" and filters it. Every change of org, reason
// or sort asks the Django API again, and the API does the filtering.
const ORGS = ['ORG-A', 'ORG-B']
const REASONS = [
  ['MISSING_IN_B', 'Missing in B'],
  ['ORPHAN_IN_B', 'Orphan in B'],
  ['DUPLICATE_IN_B', 'Duplicate in B'],
  ['VALUE_MISMATCH', 'Value mismatch'],
  ['LOCATION_MISMATCH', 'Location mismatch'],
  ['DATE_MISMATCH', 'Date mismatch'],
  ['VOIDED_IN_A', 'Voided in A, still in B'],
]
const REASON_LABEL = Object.fromEntries(REASONS)

// Display only: money arrives as exact text like "83361.40".
// A missing value (null) is shown as an EMPTY cell, never "0" or "null".
function money(text) {
  if (text === null || text === undefined) return ''
  return Number(text).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Sort cycle for the value column: none -> ascending -> descending -> none
const NEXT_SORT = { '': 'value', value: '-value', '-value': '' }
const SORT_ARROW = { '': '', value: ' ▲', '-value': ' ▼' }

export default function App() {
  const [org, setOrg] = useState(ORGS[0])
  const [reason, setReason] = useState('')
  const [sort, setSort] = useState('')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController() // cancels a stale request if the filters change quickly
    const params = new URLSearchParams({ org })
    if (reason) params.set('reason', reason)
    if (sort) params.set('sort', sort)

    setLoading(true)
    setError('')
    fetch(`/api/disagreements/?${params}`, { signal: controller.signal })
      .then(async (response) => {
        const body = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`)
        setRows(body)
        setLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setRows([])
        setError(err.message)
        setLoading(false)
      })
    return () => controller.abort()
  }, [org, reason, sort])

  return (
    <main className="page">
      <h1>DealerOS Reconciliation Dashboard</h1>

      <div className="controls">
        <label>
          Organization
          <select value={org} onChange={(e) => setOrg(e.target.value)}>
            {ORGS.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>
        <label>
          Reason
          <select value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">All reasons</option>
            {REASONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          </select>
        </label>
      </div>

      {loading && <p className="status">Loading…</p>}
      {error && <p className="status error" role="alert">Could not load data: {error}</p>}
      {!loading && !error && rows.length === 0 && (
        <p className="status">No disagreements found for {org}{reason ? ` with reason ${REASON_LABEL[reason]}` : ''}.</p>
      )}

      {!loading && !error && rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Reason</th>
                <th>Record ID</th>
                <th>Location</th>
                <th className="num sortable" onClick={() => setSort(NEXT_SORT[sort])}
                    title="Click to sort by value">
                  System A Value{SORT_ARROW[sort]}
                </th>
                <th className="num">System B Value</th>
                <th className="num">Difference</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={`${row.reason}-${row.record_id}-${i}`}>
                  <td><span className={`tag ${row.reason}`}>{REASON_LABEL[row.reason] || row.reason}</span></td>
                  <td>{row.record_id}</td>
                  <td>
                    {row.location}
                    {row.b_location && row.b_location !== row.location && (
                      <div className="note">B: {row.b_location}</div>
                    )}
                    {row.b_details_hidden && (
                      <div className="note">B-side details hidden: they belong to another organization</div>
                    )}
                  </td>
                  <td className="num">{money(row.a_value)}</td>
                  <td className="num">{money(row.b_value)}</td>
                  <td className="num">{money(row.difference)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}
