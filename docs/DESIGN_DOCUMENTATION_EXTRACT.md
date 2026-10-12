TIMEWISE
Product Design Documentation
Version 1.0 · October 2026
Design handoff for the TIMEWISE responsive college portal prototype
Document guide
1. Product overview
2. Goals and scope
3. Information architecture
4. Roles and permissions
5. Key screens and behavior
6. Visual design system
7. Responsive behavior
8. Alerts, empty states, and feedback
9. Accessibility and usability
10. Core user flows
11. Data model and integration notes
12. Acceptance criteria
13. Recommended next steps
Reference basis: user-supplied college portal screenshots. This document describes the proposed product design and prototype behavior; it does not represent an official university specification.
1. Product overview
Purpose
TIMEWISE is a responsive college portal concept for bringing academic schedules, student services, appointments, examination notices, and role-specific workspaces into one coherent experience.
Design direction
The interface follows the supplied Kristu Jayanti University portal screenshots: a white canvas, blue academic accents, understated gray text, clear breadcrumb navigation, restrained borders, rounded cards, and familiar portal navigation.
Design principle
Keep the recognizable structure of a traditional university portal while improving readability, mobile usability, information hierarchy, and visibility of time-sensitive actions.
2. Goals and scope
Primary goals
Make the next class and upcoming academic actions easy to find; centralize alerts; support timetable planning; provide distinct dashboards for different college roles; and work well on phones, tablets, and desktops.
Prototype scope
Front-end demonstration with sample data and client-side interactions. It is not connected to the university’s live systems.
Out of scope for this prototype
Production authentication, server-side authorization, real student records, institutional single sign-on, live timetable synchronization, push notifications, and official examination or payment transactions.
3. Information architecture
Global shell
Header with TIMEWISE mark, page title or breadcrumbs, alert access, and profile menu; responsive primary navigation; main content area; optional mobile bottom navigation.
Primary navigation
Dashboard; Academics; Timetable; Hall Tickets; Appointments; Mentor Meeting; Programmes; Fees; Alerts; Profile/Settings.
Navigation behavior
On desktop, use a persistent sidebar. On small screens, use a slide-out menu or compact bottom navigation. Keep the current section visibly selected and retain breadcrumb context on deeper pages.
4. Roles and permissions
Student
Can view their own timetable, attendance, hall-ticket status, alerts, programmes, fees, and appointments; can create personal study blocks and request/reschedule eligible appointments.
Faculty
Can view assigned teaching schedule and relevant class information; manage permitted class-level notices and appointment availability; access only students and records authorized by institutional policy.
Mentor
Can view assigned mentees, meeting schedules, mentor-book information, and permitted academic progress summaries; record meeting notes only where policy allows.
Administrator
Can manage configuration, role assignments, timetable publication, programme/event information, institution-wide alerts, and administrative reports according to delegated permissions.
Security rule
Role-based visibility in the interface is not a security boundary. Every protected action and data request must also be authorized on the server. Apply least privilege and audit sensitive administrative actions.
5. Key screens and behavior
Dashboard
Greeting and date; role-specific summary cards; next scheduled activity; recent alerts; upcoming appointments; quick actions. Use compact metrics and avoid overwhelming users with too many cards.
Timetable planner
Week/day navigation, date selector, schedule rows with subject/activity, time, room or location, and status. Allow users to add personal study blocks in the demo. Production conflicts must be validated before saving.
Alerts
Show severity, source, date/time, and a concise action. Use blue for general information, amber for attention, and red for urgent or blocking states. Allow read/unread state and filtering.
Hall tickets
Search by examination or batch; show examination name, course/semester, issue date, and status such as Available, Pending, or On Hold. A real system must obtain statuses from the authoritative academic source.
Appointments
Separate available events from the user’s appointments. Show date, time, host, location or meeting link, and booking state. Confirm reschedule/cancel actions before committing.
Mentor meeting
Tabs for personal details and academic records, with clear empty states and an explicit action to add permitted information.
Profile
Show account identity and settings entry points. Sign-out and password-change flows should require appropriate confirmation and secure identity-provider handling.
6. Visual design system
Color palette
Primary blue #1261A0; deep navy #17324D; pale blue #EAF3FB; page background #F7F9FC; card surface #FFFFFF; main text #1F2937; secondary text #697586; border #E2E7EE; success #16805D; warning #A96500; danger #B42332.
Typography
Use a legible system sans-serif stack. Suggested hierarchy: page title 24–28 px desktop / 21–24 px mobile; section title 18–20 px; card title 15–17 px; body 14–16 px; helper text 12–14 px. Maintain comfortable line height.
Spacing
Use a 4 px base scale: 4, 8, 12, 16, 24, 32, 40, 48 px. Prefer consistent 16–24 px card padding and 16 px gaps between stacked mobile cards.
Shape and elevation
Cards use 12–18 px corner radius, subtle 1 px borders, and very light shadows only when needed. Buttons and fields use 10–14 px radii. Avoid heavy gradients and excessive shadows.
Controls
Primary action: solid blue with white text. Secondary action: pale blue/white with blue or navy text. Destructive action: red and visually distinct. Focus states must be visible and not rely on color alone.
7. Responsive behavior
Mobile: under 640 px
Single-column content; compact header; navigation drawer or bottom nav; full-width buttons where useful; timetable rows become stacked cards; filters wrap or move into a panel.
Tablet: 640–1023 px
Use a collapsible sidebar or drawer; allow two-column summary cards; keep timetable readable without horizontal overflow.
Desktop: 1024 px and above
Persistent sidebar, broad main content, two-to-four-column metric cards depending on available width, and a wider timetable view.
Interaction targets
Aim for at least 44 × 44 px touch targets. Avoid hover-only functionality; provide keyboard and touch equivalents.
8. Alerts, empty states, and feedback
Alert hierarchy
Urgent: requires immediate action; Warning: status may block a task; Informational: a useful update; Success: a completed action. Pair color with text and an icon or label.
Empty states
Explain what is missing in plain language, then offer a relevant next step where possible. Example: “No timetable found for this date” with a date-change action.
Feedback
Use inline validation for forms, visible loading states for remote requests, confirmation before destructive actions, and success/error messages after operations. Do not imply a save succeeded until the server confirms it.
9. Accessibility and usability
Accessibility baseline
Target WCAG 2.2 AA. Ensure text contrast, semantic headings, form labels, keyboard navigation, visible focus, screen-reader names, reduced-motion support, and error messages that identify the field and correction.
Content design
Use short labels, sentence case, consistent terms (“Timetable” rather than mixing “Time Table” and “Schedule”), localized date/time formatting, and clear status words.
Privacy
Avoid exposing sensitive student data in notifications or on shared screens. Minimize displayed personal details and use role-appropriate access.
10. Core user flows
View today’s timetable
Sign in → Dashboard → Today’s classes → Select class for details.
Create a study block
Timetable → Add study block → Enter title/date/time → Validate overlap → Save → Show confirmation.
Review an exam alert
Alerts → Open examination notice → Review hall-ticket status → Follow available next action.
Book an appointment
Appointments → Available events → Select slot → Confirm details → Book → Display booking status.
Role switch for prototype
Use the demo role selector to preview different dashboards. In production, role membership must come from trusted identity and authorization services.
11. Data model and integration notes
Suggested entities
User; Role; Course/Programme; ClassSession; TimetableEntry; PersonalStudyBlock; Alert; Examination; HallTicketStatus; AppointmentSlot; AppointmentBooking; MentorAssignment; AuditEvent.
Integration points
Identity provider/SSO; student information system; learning management system if applicable; timetable service; notification service; appointment service; finance/fees system. Define the system of record for each data type before integration.
Reliability
Store timestamps with time-zone context; handle stale data and network failures; prevent duplicate bookings; validate overlapping events; log administrative changes; and expose clear retry paths.
12. Acceptance criteria
Responsive layout
No essential content requires horizontal scrolling at 360 px viewport width; all navigation remains usable on touch devices.
Role access
Each role sees only its intended navigation and actions; server APIs enforce the same permissions independently of the UI.
Timetable
Users can navigate dates, inspect schedule items, and create/edit/delete personal blocks in the demo; production saves are validated server-side.
Alerts
Users can identify severity and date, open alert details, and update read state where supported.
Accessibility
All core flows can be completed by keyboard; controls have accessible names; status is not conveyed by color alone.
Prototype disclosure
Sample data and demo-only interactions are clearly distinguished from live institutional records.
13. Recommended next steps
Before development
Confirm the official logo and brand rules; validate role definitions with college stakeholders; approve data fields and status vocabulary; define integrations and privacy retention rules.
For engineering handoff
Convert key screens into Figma frames and component variants; document API contracts; implement server-side authorization; add automated responsive/accessibility tests; and test with students, faculty, mentors, and administrators.
Appendix A — Design token quick reference
Token
Value
Usage
Primary blue
#1261A0
Primary actions, active navigation, links
Deep navy
#17324D
Headings, emphasis
Pale blue
#EAF3FB
Selected surfaces, icon backgrounds
Page background
#F7F9FC
Main canvas
Card surface
#FFFFFF
Cards and panels
Main text
#1F2937
Primary body text
Secondary text
#697586
Metadata and helper text
Border
#E2E7EE
Card and input outlines
Success
#16805D
Positive status
Warning
#A96500
Attention status
Danger
#B42332
Blocking/destructive status
Appendix B — Prototype disclaimer
The HTML prototype is intended for design review and usability discussion. Any role switcher, sample records, booking state, alert state, or timetable edit performed only in the browser is a demonstration and must not be treated as a secure or authoritative academic record.