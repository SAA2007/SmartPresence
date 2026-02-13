# SmartPresence – Design Specification

## Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| Primary BG | `#0f1117` | Page background |
| Card BG | `rgba(26, 29, 39, 0.8)` + `backdrop-filter: blur(12px)` | Glass cards |
| Accent | `#6C63FF` | Buttons, active states, links |
| Success | `#2ecc71` | Present, On Time badges |
| Danger | `#e74c3c` | Absent, errors |
| Warning | `#f39c12` | Late badges |
| Info | `#3498db` | Informational badges |
| Text Primary | `#ffffff` | Headings |
| Text Secondary | `rgba(255,255,255,0.7)` | Body text |
| Border | `rgba(255,255,255,0.08)` | Card/input borders |

## Typography

- **Font**: Inter (Google Fonts)
- Headings: 600 weight
- Body: 400 weight
- Small: 300 weight

## Spacing

- Card border-radius: `12px`
- Button border-radius: `8px`
- Input border-radius: `8px`
- Sidebar width: `240px`
- Card padding: `20px`

## Screens Included

1. `01_login.png` — Login page with glassmorphism card
2. `02_dashboard.png` — Stats, Chart.js trend, attendance table
3. `03_settings.png` — System controls, schedule, admin config
4. `04_student_detail.png` — Student profile with attendance history

## Missing Screens (to be designed)

- Live View (embedded video + detected faces panel)
- Students Management (table + add/edit modals)
- Enrollment (camera capture + photo upload)
- User Management (admin CRUD for teacher accounts)
- Report Issue (form with severity selector)
