import { motion } from 'framer-motion'

const variants = {
  initial:   { opacity: 0, y: 18 },
  animate:   { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } },
  exit:      { opacity: 0, y: -10, transition: { duration: 0.25 } },
}

export default function MotionPage({ children, style }) {
  return (
    <motion.div
      variants={variants}
      initial="initial"
      animate="animate"
      exit="exit"
      style={style}
    >
      {children}
    </motion.div>
  )
}

export const fadeUp = {
  hidden:  { opacity: 0, y: 30 },
  visible: (i = 0) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  }),
}
