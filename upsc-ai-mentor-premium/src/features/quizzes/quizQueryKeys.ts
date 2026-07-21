export const quizKeys={all:['quizzes'] as const,list:['quizzes','list'] as const,attempts:(id:string)=>['quizzes','attempts',id] as const,roadmap:(id:string)=>['quizzes','roadmap',id] as const}
