import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getActivitySummary, getRecentActivity } from '../../api/activity'
import { getCurrentAffairsRetention, getPersonalizedCurrentAffairs, setCurrentAffairsSaved } from '../../api/currentAffairs'
import { getMasteryOverview } from '../../api/mastery'
import { getMentorDashboard, updateMentorAction } from '../../api/mentor'
import { getPdfDocuments, pdfQueryKeys } from '../../api/pdf'
import { getProfile } from '../../api/profile'
import { getRoadmaps } from '../../api/roadmaps'
import { getVideoRecommendations } from '../../api/videos'

export const dashboardKey = ['dashboard'] as const
function useDashboardQuery<T>(name:string,fn:(signal?:AbortSignal)=>Promise<T>){return useQuery({queryKey:[...dashboardKey,name],queryFn:({signal})=>fn(signal)})}
export function useDashboardData() {
  const client = useQueryClient()
  const mentor=useDashboardQuery('mentor',getMentorDashboard), today=useDashboardQuery('activity-today',s=>getActivitySummary('today',s)), weekly=useDashboardQuery('activity-week',s=>getActivitySummary('7d',s)), mastery=useDashboardQuery('mastery',getMasteryOverview)
  const profile=useDashboardQuery('profile',getProfile), currentAffairs=useDashboardQuery('current-affairs',getPersonalizedCurrentAffairs), retention=useDashboardQuery('retention',getCurrentAffairsRetention), documents=useQuery({queryKey:pdfQueryKeys.documents,queryFn:({signal})=>getPdfDocuments(signal)}), roadmaps=useDashboardQuery('roadmaps',getRoadmaps), videos=useDashboardQuery('videos',getVideoRecommendations), activity=useDashboardQuery('events',getRecentActivity)
  const mentorAction=useMutation({mutationFn:({id,operation}:{id:string;operation:'accept'|'complete'|'skip'})=>updateMentorAction(id,operation),onSuccess:()=>client.invalidateQueries({queryKey:[...dashboardKey,'mentor']})})
  const saveStory=useMutation({mutationFn:({id,saved}:{id:string;saved:boolean})=>setCurrentAffairsSaved(id,saved),onSuccess:()=>client.invalidateQueries({queryKey:[...dashboardKey,'current-affairs']})})
  const all=[mentor,today,weekly,mastery,profile,currentAffairs,retention,documents,roadmaps,videos,activity]
  return {mentor,today,weekly,mastery,profile,currentAffairs,retention,documents,roadmaps,videos,activity,mentorAction,saveStory,criticalPending:mentor.isPending||today.isPending||mastery.isPending,criticalError:mentor.error||today.error||mastery.error,isRefreshing:all.some(item=>item.isFetching),refresh:async()=>{await Promise.all([client.invalidateQueries({queryKey:dashboardKey}),client.invalidateQueries({queryKey:pdfQueryKeys.documents})])}}
}
