import type { VisualType } from './api'

export function buildVisualRoadmapRequest(topic: string, visualType: VisualType, language: 'english' | 'hindi' | 'punjabi') {
  return { topic: topic.trim(), visual_type: visualType, language, conversation_id: null }
}
