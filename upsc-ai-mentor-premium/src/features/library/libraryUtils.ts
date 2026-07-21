import type { PdfDocument } from '../../api/types'
export type LibraryStatus='indexed'|'processing'|'failed'|'legacy'|'unknown'
export const safeDocumentName=(value:string)=>{const raw=value.replaceAll('\\','/').split('/').pop()??'';const name=[...raw].filter(character=>character.charCodeAt(0)>=32&&!['<','>'].includes(character)).join('').trim();return name||'Document.pdf'}
export const documentStatus=(document:PdfDocument):LibraryStatus=>document.indexed?'indexed':['processing','failed','legacy'].includes(document.status.toLowerCase())?document.status.toLowerCase() as LibraryStatus:'unknown'
export const statusLabel=(status:LibraryStatus)=>({indexed:'Indexed',processing:'Processing',failed:'Failed',legacy:'Legacy / Re-index required',unknown:'Status unavailable'}[status])
export const isPdf=(file:File)=>file.type==='application/pdf'||file.name.toLowerCase().endsWith('.pdf')
export const chatNavigation=(document:PdfDocument)=>{const name=safeDocumentName(document.name);return{path:'/coach',state:{documentName:name,documentId:document.document_id,prompt:`Using the uploaded document ‘${name}’, explain its most important UPSC themes and ask me which topic I want to study.`}}}
export const visualNavigation=(document:PdfDocument)=>{const name=safeDocumentName(document.name);return{path:'/visual-learning',state:{documentName:name,documentId:document.document_id,prompt:`Create a visual learning roadmap from ${name}`}}}
