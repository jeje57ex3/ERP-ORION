import * as THREE from 'three'

export function createWatchMaterial(option) {
  const color = option?.color || '#ffffff'

  switch (option?.material) {
    case 'metal':
      return new THREE.MeshStandardMaterial({ color, metalness: 0.85, roughness: 0.22 })
    case 'leather':
      return new THREE.MeshStandardMaterial({ color, metalness: 0.05, roughness: 0.72 })
    case 'gloss':
      return new THREE.MeshStandardMaterial({ color, metalness: 0.1,  roughness: 0.12 })
    case 'satin':
      return new THREE.MeshStandardMaterial({ color, metalness: 0.35, roughness: 0.38 })
    case 'matte':
      return new THREE.MeshStandardMaterial({ color, metalness: 0.04, roughness: 0.88 })
    default:
      return new THREE.MeshStandardMaterial({ color, metalness: 0.2, roughness: 0.45 })
  }
}

export function applyMaterialToMesh(mesh, option) {
  if (!mesh?.isMesh) return
  const prev = mesh.material
  mesh.material = createWatchMaterial(option)
  if (prev && prev !== mesh.material) prev.dispose()
}
