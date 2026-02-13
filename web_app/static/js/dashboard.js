/* ═══════════════════════════════════════════════════
   SmartPresence – Dashboard JavaScript
   ═══════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
    // Only auto-refresh on dashboard page
    const isDashboard = !!document.getElementById('attendanceTable');

    if (isDashboard) {
        loadStats();
        loadAttendance();

        setInterval(() => {
            loadStats();
            loadAttendance();
        }, 5000);
    }

    // Date filter
    const dateInput = document.getElementById('dateFilter');
    if (dateInput) {
        dateInput.value = new Date().toISOString().split('T')[0];

        dateInput.addEventListener('change', () => {
            loadAttendance(dateInput.value);
            updateExportLinks(dateInput.value);
        });
    }
});


// ── Load Stats ──────────────────────────────

function loadStats() {
    safeFetch('/api/stats').then(r => {
        if (!r) return;
        return r.json();
    }).then(data => {
        if (!data) return;
        setTextSafe('totalStudents', data.total_students);
        setTextSafe('presentToday', data.present_today);
        setTextSafe('absentToday', data.absent_today);
        setTextSafe('totalLogs', data.total_logs);
    }).catch(() => { });
}


// ── Load Attendance Table ────────────────────

function loadAttendance(date) {
    let url = '/api/attendance';
    if (date) url += '?date=' + date;

    safeFetch(url).then(r => {
        if (!r) return;
        return r.json();
    }).then(data => {
        if (!data) return;
        const tbody = document.getElementById('attendanceTable');
        if (!tbody) return;

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No records found</td></tr>';
            return;
        }

        const statusColors = {
            'Present': 'bg-present',
            'On Time': 'bg-ontime',
            'Late': 'bg-late',
            'Absent': 'bg-absent',
            'Disappeared': 'bg-disappeared',
            'Early Leave': 'bg-earlyleave',
            'Permitted': 'bg-permitted',
            'Excused': 'bg-excused'
        };

        tbody.innerHTML = data.map((row, i) => {
            const colorClass = statusColors[row.status] || 'bg-secondary';
            const time = new Date(row.timestamp).toLocaleString();
            const sourceIcon = row.source === 'ai' ? '<i class="bi bi-robot text-info"></i>' :
                row.source === 'manual' ? '<i class="bi bi-pencil text-warning"></i>' :
                    '<i class="bi bi-arrow-repeat text-danger"></i>';
            return `
                <tr>
                    <td>${i + 1}</td>
                    <td><strong>${row.name}</strong></td>
                    <td class="text-muted small">${time}</td>
                    <td><span class="badge ${colorClass}">${row.status}</span></td>
                    <td>${sourceIcon}</td>
                    <td>
                        <button class="btn btn-outline-light btn-xs" onclick="openOverride(${row.id}, '${row.status}', '${(row.notes || '').replace(/'/g, "\\'")}')"
>
                            <i class="bi bi-pencil-square"></i>
                        </button>
                        <button class="btn btn-outline-danger btn-xs" onclick="deleteLog(${row.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }).catch(() => { });
}


// ── Export Links ──────────────────────────────

function updateExportLinks(date) {
    const xlsx = document.getElementById('exportXlsx');
    const csv = document.getElementById('exportCsv');
    if (xlsx) xlsx.href = date ? `/api/export?format=xlsx&date=${date}` : '/api/export?format=xlsx';
    if (csv) csv.href = date ? `/api/export?format=csv&date=${date}` : '/api/export?format=csv';
}


// ── Helper ───────────────────────────────────
// showToast and setTextSafe are defined globally in base.html
// No duplicates needed here.
function setTextSafe(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}
