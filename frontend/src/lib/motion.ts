/** Shared motion vocabulary. One easing family, three durations, one spring. */
export const EASE = [0.22, 1, 0.36, 1] as const
export const DUR = { fast: 0.14, base: 0.24, slow: 0.48 } as const
export const SPRING = { type: 'spring', stiffness: 380, damping: 34, mass: 0.9 } as const

export const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: DUR.slow, ease: EASE } },
}
export const stagger = (s = 0.06) => ({ hidden: {}, show: { transition: { staggerChildren: s } } })

/** Props for a scroll-reveal block. Respects reduced motion through <MotionConfig reducedMotion="user">. */
export const reveal = {
  initial: 'hidden',
  whileInView: 'show',
  viewport: { once: true, margin: '0px 0px -12% 0px' },
  variants: fadeUp,
} as const
