import { apiRequest } from './client'
export interface RoadmapQuiz {id:string;roadmap_id:string;difficulty:string;questions:Array<{id:string;question_type:string;question:string;options:string[];correct_answer:string;explanation:string;source_node_ids:string[];difficulty:string}>}
export const getRoadmapQuiz=(id:string,signal?:AbortSignal)=>apiRequest<RoadmapQuiz>(`/visual-roadmaps/${id}/quiz`,{signal})
