// Theta Edge Node pane for Hermes Desktop.
// The content is deliberately Theta-skinned (dark navy + cyan/green gradient);
// the pane tab strip and sash remain native Hermes chrome.

import { useQuery, useMutation, useQueryClient } from '@hermes/plugin-sdk'
import React, { useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

let ctxRef = null
const api = (path, options) => {
  if (!ctxRef) return Promise.reject(new Error('plugin not ready'))
  return ctxRef.rest(path, options)
}

const T = {
  bg: '#131722',
  panel: '#1B2436',
  panel2: '#222C42',
  stroke: '#2C3852',
  text: '#F4F7FF',
  dim: '#A7B3C9',
  faint: '#7C8AA3',
  cyan: '#2CB5F5',
  green: '#2AF598',
  danger: '#FF5C7A',
  warning: '#F5B84B',
  onGradient: '#071018'
}

const S = {
  root: {
    position: 'relative',
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    minHeight: 0,
    background: T.bg,
    color: T.text,
    fontSize: '12px',
    overflow: 'hidden'
  },
  header: { padding: '12px 12px 0' },
  wordmarkRow: { display: 'flex', alignItems: 'baseline', gap: '8px' },
  wordmark: { fontSize: '15px', fontWeight: 800, letterSpacing: '0.16em', color: T.text },
  wordmarkDim: { fontSize: '9px', letterSpacing: '0.14em', color: T.faint, textTransform: 'uppercase' },
  gradient: {
    height: '2px',
    marginTop: '9px',
    borderRadius: '1px',
    background: 'linear-gradient(90deg, ' + T.cyan + ', ' + T.green + ')'
  },
  tabs: { display: 'flex', gap: '4px', padding: '10px 12px 0' },
  tab: active => ({
    flex: 1,
    padding: '6px 8px',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '11px',
    fontWeight: active ? 700 : 500,
    background: active ? T.panel2 : 'transparent',
    color: active ? T.text : T.dim
  }),
  body: { flex: 1, minHeight: 0, overflowY: 'auto', padding: '10px 12px 18px' },
  card: {
    background: T.panel,
    border: '1px solid ' + T.stroke,
    borderRadius: '10px',
    padding: '10px',
    marginBottom: '8px'
  },
  label: {
    fontSize: '9px',
    textTransform: 'uppercase',
    letterSpacing: '0.09em',
    color: T.faint,
    marginBottom: '4px'
  },
  value: { fontSize: '21px', fontWeight: 700, fontVariantNumeric: 'tabular-nums' },
  small: { fontSize: '11px', color: T.dim, lineHeight: 1.5 },
  row: { display: 'flex', justifyContent: 'space-between', gap: '8px', padding: '3px 0', alignItems: 'baseline' },
  mono: {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    fontSize: '10px',
    wordBreak: 'break-all',
    color: T.text
  },
  btn: {
    padding: '7px 10px',
    borderRadius: '7px',
    border: '1px solid ' + T.stroke,
    background: T.panel2,
    color: T.text,
    cursor: 'pointer',
    fontSize: '11px'
  },
  primary: {
    padding: '8px 12px',
    borderRadius: '7px',
    border: 'none',
    background: 'linear-gradient(90deg, ' + T.cyan + ', ' + T.green + ')',
    color: T.onGradient,
    cursor: 'pointer',
    fontSize: '11px',
    fontWeight: 800
  },
  danger: {
    padding: '7px 10px',
    borderRadius: '7px',
    border: '1px solid ' + T.danger,
    background: 'transparent',
    color: T.danger,
    cursor: 'pointer',
    fontSize: '11px'
  },
  input: {
    width: '100%',
    padding: '7px 9px',
    borderRadius: '7px',
    border: '1px solid ' + T.stroke,
    background: T.panel2,
    color: T.text,
    fontSize: '11px',
    boxSizing: 'border-box',
    marginBottom: '6px'
  },
  error: { color: T.danger, fontSize: '11px', lineHeight: 1.45, marginTop: '6px' },
  ok: { color: T.green, fontSize: '11px', marginTop: '6px' },
  warning: { color: T.warning, fontSize: '11px', lineHeight: 1.45, marginTop: '6px' },
  bar: { height: '6px', borderRadius: '3px', background: T.stroke, overflow: 'hidden', margin: '7px 0' },
  barFill: pct => ({
    height: '100%',
    width: Math.max(0, Math.min(100, pct)) + '%',
    background: 'linear-gradient(90deg, ' + T.cyan + ', ' + T.green + ')',
    transition: 'width 0.2s'
  }),
  pill: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '5px',
    padding: '3px 7px',
    borderRadius: '999px',
    background: T.panel2,
    color: T.dim,
    fontSize: '10px'
  },
  pre: {
    margin: 0,
    padding: '8px',
    borderRadius: '8px',
    background: T.panel2,
    color: T.dim,
    maxHeight: '220px',
    overflow: 'auto',
    fontSize: '10px',
    lineHeight: 1.45,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word'
  },
  actions: { display: 'flex', flexWrap: 'wrap', gap: '6px' }
}

const usd = value =>
  Number(value || 0).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2
  })

const num = (value, digits = 4) =>
  Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: digits })

const bytes = value => {
  const n = Number(value || 0)
  if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + ' MB'
  if (n >= 1024) return (n / 1024).toFixed(0) + ' KB'
  return n + ' B'
}

function Dot({ ok, warn }) {
  return jsx('span', {
    style: {
      display: 'inline-block',
      width: '8px',
      height: '8px',
      borderRadius: '50%',
      background: ok ? T.green : warn ? T.warning : T.danger,
      flex: '0 0 auto'
    }
  })
}

function Row({ label, value, mono }) {
  return jsxs('div', {
    style: S.row,
    children: [
      jsx('span', { style: S.small, children: label }),
      jsx('span', { style: mono ? S.mono : { fontSize: '11px', fontVariantNumeric: 'tabular-nums' }, children: value })
    ]
  })
}

function Sparkline({ data }) {
  const points = Array.isArray(data) ? data : []
  const values = points.map(point => Number(point.tfuel || 0))
  const max = Math.max(...values, 0.000001)
  if (!values.length || values.every(value => value === 0)) {
    return jsx('div', { style: { ...S.small, padding: '10px 0' }, children: 'No jobs recorded yet.' })
  }
  const width = 300
  const height = 64
  const step = values.length > 1 ? width / (values.length - 1) : width
  const coords = values.map((value, index) => [
    index * step,
    height - 5 - (value / max) * (height - 14)
  ])
  const line = coords.map(([x, y]) => x.toFixed(1) + ',' + y.toFixed(1)).join(' ')
  const area = '0,' + height + ' ' + line + ' ' + width + ',' + height
  return jsxs('svg', {
    viewBox: '0 0 ' + width + ' ' + height,
    style: { width: '100%', height: '64px', display: 'block' },
    children: [
      jsx('defs', {
        children: jsxs('linearGradient', {
          id: 'theta-spark',
          x1: '0',
          y1: '0',
          x2: '0',
          y2: '1',
          children: [
            jsx('stop', { offset: '0%', stopColor: T.cyan, stopOpacity: '0.34' }),
            jsx('stop', { offset: '100%', stopColor: T.cyan, stopOpacity: '0' })
          ]
        })
      }),
      jsx('polygon', { points: area, fill: 'url(#theta-spark)' }),
      jsx('polyline', {
        points: line,
        fill: 'none',
        stroke: T.green,
        strokeWidth: '2',
        strokeLinejoin: 'round',
        strokeLinecap: 'round'
      })
    ]
  })
}

function StatusChip() {
  const status = useQuery({
    queryKey: ['theta', 'status'],
    queryFn: () => api('/node/status'),
    refetchInterval: 30000
  })
  const running = Boolean(status.data && status.data.running)
  return jsxs('button', {
    type: 'button',
    title: running ? 'Theta Edge Node running' : 'Theta Edge Node offline',
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '5px',
      padding: '0 6px',
      border: 'none',
      background: 'transparent',
      color: 'var(--ui-text-secondary)',
      cursor: 'default',
      fontSize: '11px'
    },
    children: [jsx(Dot, { ok: running }), jsx('span', { children: 'Theta' })]
  })
}

function InstallCard({ install, installStart }) {
  const [consent, setConsent] = useState(false)
  const progress = install.data || {}
  const phase = progress.phase || 'idle'
  const busy = phase === 'downloading' || phase === 'verifying' || phase === 'installing'
  const pct = progress.total ? (progress.downloaded / progress.total) * 100 : 0

  if (!consent && phase === 'idle') {
    return jsxs('div', {
      style: S.card,
      children: [
        jsx('div', { style: S.label, children: 'First run' }),
        jsx('div', { style: { ...S.value, fontSize: '16px', marginBottom: '4px' }, children: 'Theta Edge Node is not installed' }),
        jsx('div', { style: S.small, children: 'Hermes can download the official Theta installer, verify its signature, and install it. The node then runs on this machine and earns TFUEL to its own node wallet.' }),
        jsx('button', { type: 'button', style: { ...S.primary, marginTop: '10px' }, onClick: () => setConsent(true), children: 'Set up Edge Node' })
      ]
    })
  }

  if (!consent && (phase === 'failed' || phase === 'manual')) {
    return jsxs('div', {
      style: S.card,
      children: [
        jsx('div', { style: S.label, children: 'Install' }),
        jsx('div', { style: S.warning, children: progress.error || 'The installer needs attention.' }),
        jsxs('div', { style: { ...S.actions, marginTop: '8px' }, children: [
          jsx('button', { type: 'button', style: S.primary, onClick: () => { setConsent(true); installStart.mutate() }, children: 'Retry install' })
        ] })
      ]
    })
  }

  if (busy || phase === 'done' || phase === 'verifying' || phase === 'manual' || phase === 'failed') {
    return jsxs('div', {
      style: S.card,
      children: [
        jsx('div', { style: S.label, children: 'Installing' }),
        jsx(Row, { label: 'Phase', value: phase }),
        progress.total ? jsx('div', { style: S.bar, children: jsx('div', { style: S.barFill(pct) }) }) : null,
        progress.total
          ? jsx('div', { style: S.small, children: bytes(progress.downloaded) + ' of ' + bytes(progress.total) })
          : null,
        progress.signature && progress.signature.status
          ? jsx(Row, { label: 'Signature', value: progress.signature.status + (progress.signature.subject ? ' · ' + progress.signature.subject : '') })
          : null,
        progress.sha256 ? jsx(Row, { label: 'SHA-256', value: progress.sha256, mono: true }) : null,
        progress.error ? jsx('div', { style: S.error, children: progress.error }) : null,
        phase === 'done' ? jsx('div', { style: S.ok, children: 'Installed: ' + (progress.installed_path || '') }) : null,
        phase === 'failed' || phase === 'manual'
          ? jsx('button', {
              type: 'button',
              style: { ...S.primary, marginTop: '8px' },
              onClick: () => installStart.mutate(),
              children: 'Retry download'
            })
          : null
      ]
    })
  }

  return jsxs('div', {
    style: S.card,
    children: [
      jsx('div', { style: S.label, children: 'Confirm install' }),
      jsx('div', { style: S.small, children: 'Hermes will download the official Theta Edge Node installer (about 230 MB) from theta-mkt-api.thetatoken.org, verify the Authenticode signature, and run it. Nothing is installed until you confirm.' }),
      jsxs('div', { style: { ...S.actions, marginTop: '10px' }, children: [
        jsx('button', { type: 'button', style: S.primary, onClick: () => installStart.mutate(), children: 'Download and install' }),
        jsx('button', { type: 'button', style: S.btn, onClick: () => setConsent(false), children: 'Cancel' })
      ] }),
      installStart.error ? jsx('div', { style: S.error, children: installStart.error.message }) : null
    ]
  })
}

function NodeTab({ settings, toggleAutoLaunch }) {
  const queryClient = useQueryClient()
  const status = useQuery({
    queryKey: ['theta', 'status'],
    queryFn: () => api('/node/status'),
    refetchInterval: 15000
  })
  const install = useQuery({
    queryKey: ['theta', 'install'],
    queryFn: () => api('/node/install/status'),
    refetchInterval: 2000
  })
  const [openLogs, setOpenLogs] = useState(false)
  const [confirmReinstall, setConfirmReinstall] = useState(false)
  const [diagMessage, setDiagMessage] = useState('')
  const logs = useQuery({
    queryKey: ['theta', 'logs'],
    queryFn: () => api('/node/logs?lines=200'),
    enabled: openLogs,
    refetchInterval: openLogs ? 5000 : false
  })
  const launch = useMutation({
    mutationFn: () => api('/node/launch', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['theta', 'status'] })
  })
  const stop = useMutation({
    mutationFn: () => api('/node/stop', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['theta', 'status'] })
  })
  const installStart = useMutation({
    mutationFn: () => api('/node/install', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['theta', 'install'] })
  })
  const updateStart = useMutation({
    mutationFn: () => api('/node/update', { method: 'POST' }),
    onSuccess: () => {
      setConfirmReinstall(false)
      queryClient.invalidateQueries({ queryKey: ['theta', 'install'] })
    }
  })
  const previousRunning = useRef(false)

  useEffect(() => {
    const running = Boolean(status.data && status.data.running)
    if (previousRunning.current && !running) {
      ctxRef.os.notify({
        title: 'Theta Edge Node offline',
        body: 'The local node stopped responding. Open the Theta pane to check it.'
      })
    }
    previousRunning.current = running
  }, [status.data])

  const data = status.data || {}
  const rewards = data.rewards || {}
  const busy = launch.isLoading || launch.isPending || stop.isLoading || stop.isPending

  return jsxs('div', {
    children: [
      !data.installed ? jsx(InstallCard, { install, installStart }) : null,
      data.installed
        ? jsxs('div', {
            style: S.card,
            children: [
              jsxs('div', {
                style: { display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '7px' },
                children: [
                  jsx(Dot, { ok: Boolean(data.running), warn: Boolean(data.process_running) && !data.running }),
                  jsx('span', { style: { fontWeight: 700 }, children: data.running ? 'Node running' : data.process_running ? 'Process up, RPC offline' : 'Node offline' }),
                  data.version ? jsx('span', { style: S.pill, children: 'v' + data.version }) : null
                ]
              }),
              jsx(Row, { label: 'Holder', value: data.holder_address || '—', mono: true }),
              jsx(Row, { label: 'Synced', value: data.synced === null || data.synced === undefined ? '—' : data.synced ? 'yes' : 'no' }),
              jsx(Row, { label: 'Peers', value: data.peers === null || data.peers === undefined ? '—' : data.peers }),
              jsx(Row, { label: 'Keystore', value: data.keystore_path || 'not found', mono: true }),
              data.error ? jsx('div', { style: S.error, children: data.error }) : null
            ]
          })
        : null,
      data.installed
        ? jsxs('div', {
            style: S.card,
            children: [
              jsx('div', { style: S.label, children: 'Rewards' }),
              jsxs('div', { style: { display: 'flex', gap: '16px', marginTop: '2px' }, children: [
                jsxs('div', { children: [
                  jsx('div', { style: S.label, children: 'Pending' }),
                  jsx('div', { style: S.value, children: num(rewards.pending_tfuel, 2) }),
                  jsx('div', { style: S.small, children: 'TFUEL' })
                ] }),
                jsxs('div', { children: [
                  jsx('div', { style: S.label, children: 'Paid' }),
                  jsx('div', { style: S.value, children: num(rewards.paid_tfuel, 2) }),
                  jsx('div', { style: S.small, children: 'TFUEL' })
                ] })
              ] }),
              jsx('div', { style: { marginTop: '6px' }, children: jsx(Sparkline, { data: rewards.daily }) }),
              jsx(Row, { label: 'Jobs seen', value: rewards.jobs === undefined ? '—' : rewards.jobs }),
              jsx('div', { style: S.small, children: 'Rewards are distributed during the first week of each month.' })
            ]
          })
        : null,
      data.installed
        ? jsxs('div', {
            style: { ...S.card, background: 'transparent' },
            children: [
              jsxs('div', { style: S.actions, children: [
                jsx('button', { type: 'button', style: S.primary, disabled: busy, onClick: () => launch.mutate(), children: 'Launch node' }),
                jsx('button', { type: 'button', style: S.danger, disabled: busy, onClick: () => stop.mutate(), children: 'Stop node' }),
                jsx('button', { type: 'button', style: S.btn, onClick: () => setConfirmReinstall(true), children: 'Reinstall / update' }),
                jsx('button', { type: 'button', style: S.btn, onClick: () => setOpenLogs(value => !value), children: openLogs ? 'Hide logs' : 'Logs' }),
                jsx('button', {
                  type: 'button',
                  style: S.btn,
                  onClick: async () => {
                    setDiagMessage('')
                    try {
                      const report = await api('/diagnostics')
                      await ctxRef.os.writeClipboard(JSON.stringify(report, null, 2))
                      setDiagMessage('Diagnostics copied.')
                    } catch (error) {
                      setDiagMessage('Could not copy diagnostics: ' + error.message)
                    }
                  },
                  children: 'Copy diagnostics'
                })
              ] }),
              confirmReinstall
                ? jsxs('div', { style: { marginTop: '8px' }, children: [
                    jsx('div', { style: S.warning, children: 'Reinstall downloads the latest official installer and runs it over the current install. The node wallet is preserved.' }),
                    jsxs('div', { style: { ...S.actions, marginTop: '6px' }, children: [
                      jsx('button', { type: 'button', style: S.primary, onClick: () => updateStart.mutate(), children: 'Confirm reinstall' }),
                      jsx('button', { type: 'button', style: S.btn, onClick: () => setConfirmReinstall(false), children: 'Cancel' })
                    ] })
                  ] })
                : null,
              diagMessage ? jsx('div', { style: S.small, children: diagMessage }) : null,
              launch.error ? jsx('div', { style: S.error, children: launch.error.message }) : null,
              stop.error ? jsx('div', { style: S.error, children: stop.error.message }) : null,
              updateStart.error ? jsx('div', { style: S.error, children: updateStart.error.message }) : null
            ]
          })
        : null,
      data.installed && openLogs
        ? jsxs('div', {
            style: S.card,
            children: [
              jsx('div', { style: S.label, children: 'Node logs' }),
              jsx('div', { style: { ...S.mono, marginBottom: '6px' }, children: logs.data && logs.data.path ? logs.data.path : 'No log file found.' }),
              jsx('pre', { style: S.pre, children: (logs.data && logs.data.lines && logs.data.lines.length ? logs.data.lines.join('\n') : 'No lines yet.') })
            ]
          })
        : null,
      jsxs('div', {
        style: { ...S.card, background: 'transparent' },
        children: [
          jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }, children: [
            jsxs('div', { children: [
              jsx('div', { style: { fontSize: '11px', fontWeight: 600 }, children: 'Resume on Hermes launch' }),
              jsx('div', { style: S.small, children: 'Only starts the node if it was running when Hermes last exited.' })
            ] }),
            jsx('button', {
              type: 'button',
              style: settings && settings.auto_launch ? S.primary : S.btn,
              onClick: () => toggleAutoLaunch(!(settings && settings.auto_launch)),
              children: settings && settings.auto_launch ? 'On' : 'Off'
            })
          ] })
        ]
      })
    ]
  })
}

function WalletTab() {
  const queryClient = useQueryClient()
  const wallet = useQuery({ queryKey: ['theta', 'wallet'], queryFn: () => api('/wallet') })
  const balances = useQuery({
    queryKey: ['theta', 'balances'],
    queryFn: () => api('/wallet/balances'),
    enabled: Boolean(wallet.data && wallet.data.exists),
    refetchInterval: 30000
  })
  const verify = useMutation({ mutationFn: () => api('/wallet/verify-export', { method: 'POST' }) })
  const exportKey = useMutation({
    mutationFn: () => api('/wallet/export', { method: 'POST', body: { password: exportPassword } }),
    onSuccess: () => setKeyVisible(true)
  })
  const [advanced, setAdvanced] = useState(false)
  const [exportPassword, setExportPassword] = useState('')
  const [exportWord, setExportWord] = useState('')
  const [keyVisible, setKeyVisible] = useState(false)
  const [message, setMessage] = useState('')

  const data = wallet.data || {}
  const balance = balances.data || {}

  if (!wallet.isLoading && !data.exists) {
    return jsxs('div', {
      children: [
        jsxs('div', { style: S.card, children: [
          jsx('div', { style: S.label, children: 'Node wallet' }),
          jsx('div', { style: { ...S.value, fontSize: '16px' }, children: 'No node wallet found yet' }),
          jsx('div', { style: S.small, children: 'The Edge Node creates its internal wallet on first launch. Install and launch the node, then reopen this tab.' }),
          data.keystore_dir ? jsx('div', { style: { ...S.mono, marginTop: '8px' }, children: data.keystore_dir }) : null
        ] })
      ]
    })
  }

  return jsxs('div', {
    children: [
      jsxs('div', { style: S.card, children: [
        jsx('div', { style: S.label, children: 'Node wallet' }),
        jsx('div', { style: S.mono, children: data.address || '—' }),
        jsxs('div', { style: { ...S.actions, marginTop: '8px' }, children: [
          jsx('button', { type: 'button', style: S.btn, onClick: () => ctxRef.os.writeClipboard(data.address), children: 'Copy address' }),
          jsx('button', { type: 'button', style: S.btn, onClick: () => ctxRef.os.openExternal('https://explorer.thetatoken.org/account/' + data.address), children: 'Explorer' })
        ] })
      ] }),
      jsxs('div', { style: S.card, children: [
        jsx('div', { style: S.label, children: 'Value' }),
        jsx('div', { style: S.value, children: usd(balance.total_usd) }),
        jsx(Row, { label: 'TFUEL', value: num(balance.tfuel, 4) + (balance.tfuel_usd ? ' @ ' + usd(balance.tfuel_usd) : '') }),
        jsx(Row, { label: 'Price source', value: balance.price_source || '—' }),
        balance.price_error ? jsx('div', { style: S.warning, children: 'USD price unavailable: ' + balance.price_error }) : null,
        jsx('div', { style: { ...S.small, marginTop: '4px' }, children: 'Liquid TFUEL only; staked TFUEL is shown in the Edge Node app and the explorer.' })
      ] }),
      jsxs('div', { style: S.card, children: [
        jsx('div', { style: S.label, children: 'Export wallet' }),
        jsx('div', { style: S.small, children: 'Recommended: use the Edge Node app. Open the node, choose Info → Export Wallet as Keystore, and save the file. It works even if you later forget the node password.' }),
        jsxs('div', { style: { ...S.actions, marginTop: '8px' }, children: [
          jsx('button', { type: 'button', style: S.btn, onClick: () => data.downloads_dir && ctxRef.os.revealPath(data.downloads_dir), children: 'Open Downloads' }),
          jsx('button', { type: 'button', style: S.primary, disabled: verify.isLoading || verify.isPending, onClick: () => { setMessage(''); verify.mutate() }, children: 'Verify exported keystore' })
        ] }),
        verify.data
          ? jsxs('div', { style: { marginTop: '8px' }, children: [
              verify.data.found
                ? jsxs('div', { children: [
                    jsx(Row, { label: 'Exported address', value: verify.data.address, mono: true }),
                    jsx('div', { style: verify.data.matches_node_wallet ? S.ok : S.warning, children: verify.data.matches_node_wallet ? 'Matches the node wallet.' : 'Does not match the node wallet.' })
                  ] })
                : jsx('div', { style: S.warning, children: 'No keystore-looking file found in Downloads in the last 7 days.' })
            ] })
          : null,
        verify.error ? jsx('div', { style: S.error, children: verify.error.message }) : null,
        jsxs('div', { style: { marginTop: '12px', borderTop: '1px solid ' + T.stroke, paddingTop: '10px' }, children: [
          jsxs('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }, children: [
            jsxs('div', { children: [
              jsx('div', { style: { fontSize: '11px', fontWeight: 600 }, children: 'Advanced: decrypt in Hermes' }),
              jsx('div', { style: S.small, children: 'Requires the password you set when you installed the node. No recovery if it is forgotten.' })
            ] }),
            jsx('button', { type: 'button', style: S.btn, onClick: () => setAdvanced(value => !value), children: advanced ? 'Hide' : 'Show' })
          ] }),
          advanced
            ? jsxs('div', { style: { marginTop: '8px' }, children: [
                jsx('input', { style: S.input, type: 'password', placeholder: 'Node password', value: exportPassword, onChange: event => setExportPassword(event.target.value) }),
                jsx('input', { style: S.input, type: 'text', placeholder: 'Type EXPORT to confirm', value: exportWord, onChange: event => setExportWord(event.target.value) }),
                jsx('button', {
                  type: 'button',
                  style: S.danger,
                  disabled: exportWord !== 'EXPORT' || !exportPassword || exportKey.isLoading || exportKey.isPending,
                  onClick: () => { setMessage(''); setKeyVisible(false); exportKey.reset(); exportKey.mutate() },
                  children: 'Reveal private key'
                }),
                keyVisible && exportKey.data && exportKey.data.private_key
                  ? jsxs('div', { style: { marginTop: '8px' }, children: [
                      jsx('div', { style: S.mono, children: exportKey.data.private_key }),
                      jsxs('div', { style: { ...S.actions, marginTop: '8px' }, children: [
                        jsx('button', { type: 'button', style: S.btn, onClick: () => ctxRef.os.writeClipboard(exportKey.data.private_key), children: 'Copy key' }),
                        jsx('button', { type: 'button', style: S.btn, onClick: () => { setKeyVisible(false); exportKey.reset() }, children: 'Hide' })
                      ] })
                    ] })
                  : null,
                exportKey.error ? jsx('div', { style: S.error, children: exportKey.error.message }) : null,
                jsx('div', { style: S.warning, children: 'Anyone with this key controls the node wallet. Copy it once, store it offline, then close this panel. The plugin never logs it.' })
              ] })
            : null
        ] }),
        message ? jsx('div', { style: S.small, children: message }) : null
      ] })
    ]
  })
}

function ThetaPane() {
  const [tab, setTab] = useState('node')
  const queryClient = useQueryClient()
  const settings = useQuery({ queryKey: ['theta', 'settings'], queryFn: () => api('/settings') })
  const status = useQuery({ queryKey: ['theta', 'status'], queryFn: () => api('/node/status'), refetchInterval: 15000 })
  const resumed = useRef(false)

  useEffect(() => {
    if (resumed.current) return
    const current = settings.data
    const node = status.data
    if (!current || !node) return
    if (current.auto_launch && current.last_running && node.installed && !node.process_running && !node.running) {
      resumed.current = true
      api('/node/launch', { method: 'POST' })
        .then(() => queryClient.invalidateQueries({ queryKey: ['theta', 'status'] }))
        .catch(() => {})
    }
  }, [settings.data, status.data, queryClient])

  const toggleAutoLaunch = enabled => {
    api('/settings', { method: 'POST', body: { auto_launch: enabled } })
      .then(() => queryClient.invalidateQueries({ queryKey: ['theta', 'settings'] }))
      .catch(() => {})
  }

  const tabs = [
    ['node', 'Node'],
    ['wallet', 'Wallet']
  ]

  return jsxs('div', {
    style: S.root,
    children: [
      jsxs('div', { style: S.header, children: [
        jsxs('div', { style: S.wordmarkRow, children: [
          jsx('span', { style: S.wordmark, children: 'THETA' }),
          jsx('span', { style: S.wordmarkDim, children: 'Edge Node' })
        ] }),
        jsx('div', { style: S.gradient })
      ] }),
      jsx('div', {
        style: S.tabs,
        children: tabs.map(([id, label]) =>
          jsx('button', {
            key: id,
            type: 'button',
            style: S.tab(tab === id),
            onClick: () => setTab(id),
            children: label
          })
        )
      }),
      jsx('div', {
        style: S.body,
        children:
          tab === 'node'
            ? jsx(NodeTab, { settings: settings.data, toggleAutoLaunch })
            : jsx(WalletTab, {})
      })
    ]
  })
}

export default {
  id: 'theta-edge-node',
  name: 'Theta Edge Node',
  register(ctx) {
    ctxRef = ctx
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'Theta',
      data: { placement: 'left', width: '360px' },
      render: () => jsx(ThetaPane, {})
    })
    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 140,
      render: () => jsx(StatusChip, {})
    })
  }
}
