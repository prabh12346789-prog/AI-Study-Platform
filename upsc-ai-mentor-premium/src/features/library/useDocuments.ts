import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { getPdfDocuments, pdfQueryKeys } from '../../api/pdf'
export function useDocuments(){const client=useQueryClient(),polls=useRef(0);const query=useQuery({queryKey:pdfQueryKeys.documents,queryFn:({signal})=>getPdfDocuments(signal)});const processing=query.data?.some(item=>item.status.toLowerCase()==='processing')??false;useEffect(()=>{if(!processing||document.hidden||polls.current>=12){if(!processing)polls.current=0;return}const timer=window.setTimeout(()=>{polls.current+=1;void client.invalidateQueries({queryKey:pdfQueryKeys.documents})},10_000);return()=>clearTimeout(timer)},[client,processing,query.dataUpdatedAt]);return query}
