import { useState } from 'react'
import { motion } from 'framer-motion'
import '../../styles/community.css'

export default function CommunityPostCard({ post, onLike }) {
  const [liked, setLiked] = useState(false)
  const [count, setCount] = useState(post.likes || 0)

  const handleLike = () => {
    if (liked) return
    setLiked(true)
    setCount(c => c + 1)
    onLike?.(post.id)
  }

  return (
    <motion.div className="community-post" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
      <div className="community-post-image">
        {post.image ? <img src={post.image} alt={post.caption} /> : '📸'}
      </div>
      <div className="community-post-body">
        <div className="community-post-user">
          <div className="community-avatar">{post.username?.[0]?.toUpperCase() || 'S'}</div>
          <div>
            <div className="community-username">@{post.username || 'siecle_fan'}</div>
            {post.universe && <div className="community-tag">#{post.universe}</div>}
          </div>
          {post.verified && (
            <span style={{ marginLeft: 'auto', background: 'rgba(216,199,163,0.1)', border: '1px solid rgba(216,199,163,0.2)', borderRadius: 999, fontSize: 10, padding: '3px 10px', color: 'var(--siecle-beige)', fontWeight: 700 }}>MEMBRE</span>
          )}
        </div>
        {post.caption && <p className="community-caption">{post.caption}</p>}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <motion.button className="community-likes" onClick={handleLike} whileTap={{ scale: 0.85 }}
            style={{ color: liked ? '#F15A5A' : undefined }}>
            {liked ? '❤️' : '🤍'} {count}
          </motion.button>
          {post.products?.length > 0 && (
            <span style={{ fontSize: 11, color: '#555', letterSpacing: '0.08em' }}>{post.products.length} produit{post.products.length > 1 ? 's' : ''} tagué{post.products.length > 1 ? 's' : ''}</span>
          )}
        </div>
      </div>
    </motion.div>
  )
}
