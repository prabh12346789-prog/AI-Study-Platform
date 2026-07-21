import { apiRequest } from './client'
import type { PdfDocument } from './types'
export const pdfQueryKeys={documents:['pdf','documents'] as const}
export const getPdfDocuments = (signal?:AbortSignal) => apiRequest<PdfDocument[]>('/pdf/documents',{signal})
export const uploadPdf=(file:File,signal?:AbortSignal)=>{const form=new FormData();form.append('file',file);return apiRequest<Record<string,unknown>>('/pdf/upload',{method:'POST',body:form,signal})}
