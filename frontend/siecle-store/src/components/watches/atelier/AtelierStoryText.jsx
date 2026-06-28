import { motion, AnimatePresence } from 'framer-motion'

export default function AtelierStoryText({ story }) {
  return (
    <AnimatePresence mode="wait">
      <motion.p
        key={story}
        className="atelier-story"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        {story}
      </motion.p>
    </AnimatePresence>
  )
}
