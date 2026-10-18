import {DAY_MS,beijingDayStart,calendarDaysRange,eventGeometry,formatBeijingDateTime} from '../calendar.js'

export function imageCalendarWindows(events,asOf){
 const start=beijingDayStart(asOf)-2*DAY_MS
 const range=calendarDaysRange(start,start+14*DAY_MS)
 const visible=events.filter(event=>eventGeometry(event,range).visible)
 return [{range,events:visible,label:formatBeijingDateTime(range.start).slice(0,10)+' 至 '+formatBeijingDateTime(range.end-1).slice(0,10)}]
}
