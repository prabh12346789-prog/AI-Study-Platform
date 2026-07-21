import { describe, expect, it } from 'vitest'
import { navigation } from './navigation'
describe('navigation', () => { it('contains the approved pages exactly once and excludes Community', () => { const labels = navigation.map(([label]) => label); expect(new Set(labels).size).toBe(labels.length); expect(labels).not.toContain('Community'); expect(labels).toEqual(['Dashboard','AI Study Coach','My Library','Current Affairs','Quizzes','Visual Learning','Revision Center','Progress','Videos','Profile','Settings']); expect(navigation[0][1]).toBe('/dashboard') }) })
