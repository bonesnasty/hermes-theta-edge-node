import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = fileURLToPath(new URL('.', import.meta.url))
const sourcePath = join(here, '..', 'desktop', 'plugin.js')
const sdkStub = join(here, 'sdk-stub.mjs')
const jsxStub = join(here, 'jsx-stub.mjs')

writeFileSync(sdkStub, `
export const host = { request: async () => ({}), notify: () => {}, navigate: () => {} }
export const useQuery = () => ({ data: undefined, isLoading: false, error: null })
export const useMutation = () => ({ mutate: () => {}, isLoading: false, isPending: false, error: null, data: null })
export const useQueryClient = () => ({ invalidateQueries: () => {} })
`)

writeFileSync(jsxStub, `
export const jsx = (type, props) => ({ type, props })
export const jsxs = jsx
export const useState = value => [value, () => {}]
export const useEffect = () => {}
export const useRef = value => ({ current: value })
export default { useState, useEffect, useRef }
`)

let source = readFileSync(sourcePath, 'utf8')
source = source.replace("'@hermes/plugin-sdk'", JSON.stringify(pathToFileURL(sdkStub).href))
source = source.replace("'react/jsx-runtime'", JSON.stringify(pathToFileURL(jsxStub).href))
source = source.replace("'react'", JSON.stringify(pathToFileURL(jsxStub).href))

const temp = join(mkdtempSync(join(tmpdir(), 'theta-plugin-')), 'plugin.mjs')
writeFileSync(temp, source)

const module = await import(pathToFileURL(temp).href)
const plugin = module.default
if (!plugin || plugin.id !== 'theta-edge-node') throw new Error('wrong plugin id')
const contributions = []
plugin.register({
  register: contribution => contributions.push(contribution),
  os: {},
  rest: async () => ({})
})
if (contributions.length !== 2) throw new Error('expected pane + chip')
if (contributions[0].data.placement !== 'left') throw new Error('pane is not on the left')
if (contributions[0].data.width !== '360px') throw new Error('pane width mismatch')
if (contributions[0].title !== 'Theta') throw new Error('pane title mismatch')
console.log('desktop plugin loads: pane=' + contributions[0].id + ' chip=' + contributions[1].id)
