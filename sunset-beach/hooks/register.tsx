import type { Register, ThemeSetArgs } from 'claude-code'

import { makeColors } from './make-colors.js'

const { theme, problems } = makeColors({
  label: 'Sunset Beach',
  roles: { accent: '#d9622b', danger: '#c9433f', success: '#4e8f55', warning: '#c98a1f', pro: '#8a5bb8' },
  light: {
    gray: {
      anchors: {
        'surface-0': '#fbeedd',
        'surface-1': '#fff4e6',
        'surface-2': '#fffaf2',
        'text-primary': '#33200f',
        'text-secondary': '#62402c',
        'text-muted': '#74513c',
      },
    },
  },
  dark: {
    gray: {
      anchors: {
        'surface-0': '#1d1224',
        'surface-1': '#28182e',
        'surface-2': '#33203a',
        'surface-3': '#38243f',
        'text-primary': '#fbe9dc',
        'text-secondary': '#dcc3b6',
        'text-muted': '#bda09a',
      },
    },
  },
})

const LOOK: ThemeSetArgs = {
  colors: theme,
  backdrop: { scene: 'sunset', glass: { blur: 3, tint: '#5a2f63', opacity: 0.18 } },
}

// One wave: a long ripple that is two tiles wide, so sliding it one tile loops without a seam.
function wave(y: number, amp: number, color: string, opacity: number, secs: number, delay: number): string {
  const tile = 500
  let d = `M0 ${y}`
  for (let i = 0; i < 6; i++) {
    const x = i * (tile / 2)
    d += ` q${tile / 4} ${i % 2 === 0 ? -amp : amp} ${tile / 2} 0`
  }
  d += ' V620 H0 Z'
  return `<path d="${d}" fill="${color}" fill-opacity="${opacity}" style="animation:slide ${secs}s linear infinite;animation-delay:-${delay}s"/>`
}

// Seagulls: each one crosses the sky slowly while its wings flap.
function gull(y: number, scale: number, secs: number, delay: number): string {
  return `<g style="animation:fly ${secs}s linear infinite;animation-delay:-${delay}s"><g transform="translate(0 ${y}) scale(${scale})"><path class="wing" d="M-22 0 Q-11 -12 0 0 Q11 -12 22 0" fill="none" stroke="#fff4e6" stroke-width="2.6" stroke-linecap="round" stroke-opacity=".9"/></g></g>`
}

const GULLS = [gull(120, 1.2, 70, 5), gull(170, 0.8, 90, 40), gull(90, 0.6, 110, 70), gull(215, 1, 80, 22)].join('')

// Fireworks: five bursts that pop in turn over a dusk sky.
const BURSTS = [
  { x: 200, y: 160, c: '#ff6b8b' },
  { x: 500, y: 110, c: '#ffd166' },
  { x: 800, y: 170, c: '#4fd1c5' },
  { x: 340, y: 300, c: '#c08bff' },
  { x: 680, y: 290, c: '#ff9f43' },
]
  .map(
    ({ x, y, c }, i) =>
      `<g style="transform-origin:${x}px ${y}px;animation:pop 2.4s ease-out infinite;animation-delay:${i * 0.45}s">${Array.from({ length: 12 }, (_, k) => {
        const a = (k / 12) * Math.PI * 2
        return `<circle cx="${x + Math.cos(a) * 46}" cy="${y + Math.sin(a) * 46}" r="3" fill="${c}"/>`
      }).join('')}</g>`,
  )
  .join('')

const FIREWORKS = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600" preserveAspectRatio="xMidYMid slice">
<style>@keyframes pop{0%{transform:scale(.1);opacity:1}70%{opacity:1}100%{transform:scale(1.8);opacity:0}}</style>
<rect width="1000" height="600" fill="#1d1230"/>${BURSTS}</svg>`

type ThemeHost = {
  theme: { set: (a: ThemeSetArgs) => Promise<unknown> }
  clock: { after: (ms: number, fn: () => void) => unknown }
}

const CELEBRATE: ThemeSetArgs = { ...LOOK, backdrop: { scene: 'fireworks', glass: { blur: 0, tint: '#1d1230', opacity: 0.1 } } }

async function celebrate($: ThemeHost): Promise<void> {
  await $.theme.set(CELEBRATE)
  $.clock.after(8000, () => {
    void $.theme.set(LOOK)
  })
}

const SCENE = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600" preserveAspectRatio="xMidYMid slice">
<style>
@keyframes slide{to{transform:translateX(-500px)}}
@keyframes fly{from{transform:translateX(-80px)}to{transform:translateX(1080px)}}
@keyframes flap{from{transform:scaleY(1)}to{transform:scaleY(-.55)}}
.wing{transform-box:fill-box;transform-origin:50% 100%;animation:flap 1.1s ease-in-out infinite alternate}
@keyframes glow{from{opacity:.75}to{opacity:1}}
.sun{animation:glow 5s ease-in-out infinite alternate}
</style>
<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#3b2a5e"/><stop offset=".45" stop-color="#c2527a"/><stop offset=".75" stop-color="#f4905a"/><stop offset="1" stop-color="#ffc977"/>
</linearGradient>
<linearGradient id="sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f08a5d"/><stop offset=".4" stop-color="#7a3f6b"/><stop offset="1" stop-color="#2a1a3d"/></linearGradient>
</defs>
<rect width="1000" height="600" fill="url(#sky)"/>
<g class="sun"><circle cx="760" cy="330" r="150" fill="#ffd9a0" fill-opacity=".25"/><circle cx="760" cy="340" r="80" fill="#fff0c4"/></g>
${GULLS}
<rect y="360" width="1000" height="240" fill="url(#sea)"/>
<g transform="translate(0 0)">
${wave(385, 6, '#ffb98a', 0.35, 55, 4)}
${wave(425, 9, '#e0707a', 0.4, 42, 9)}
${wave(470, 12, '#a04a7e', 0.5, 34, 2)}
${wave(520, 15, '#5a2f63', 0.6, 26, 6)}
${wave(565, 18, '#2f1c44', 0.8, 20, 1)}
</g>
</svg>`

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const bad = problems.find(l => l.startsWith("Desktop won't paint"))
    if (bad !== undefined) $.ui.toast(bad)
    await $.command.register({ name: 'sunset-fireworks', description: 'Preview the merge fireworks' })
    const set = await $.theme.set(LOOK)
    if (!set.isDrawn) $.ui.status(set.reason)
    return next(e)
  })

  on('command.run', { command: 'sunset-fireworks' }, async $ => {
    await celebrate($)
    return { text: 'Fireworks for 8 seconds.' }
  })

  // Fireworks when a pull request is merged, by the GitHub tool or `gh pr merge`
  on('tool.call', async ($, e, next) => {
    const result = await next(e)
    const isMerge =
      e.tool === 'mcp__github__merge_pull_request' ||
      (e.tool === 'Bash' && /\bgh\s+pr\s+merge\b/.test(e.command))
    if (isMerge) await celebrate($)
    return result
  })

  on('ui.render', { component: 'Backdrop' }, ($, e, next) => {
    if (e.surface !== 'desktop' && e.surface !== 'mobile') return next(e)
    if (e.props.plugin !== $.plugin.name || e.props.scene !== 'sunset' && e.props.scene !== 'fireworks') return next(e)
    const { Svg } = $.ui.resolve(e)
    return <Svg source={e.props.scene === 'fireworks' ? FIREWORKS : SCENE} alt="Waves rolling in under a setting sun" isInteractive />
  })
}
